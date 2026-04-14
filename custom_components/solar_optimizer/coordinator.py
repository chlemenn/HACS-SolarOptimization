"""Data update coordinator for Solar Optimizer."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_API_KEY,
    CONF_AZIMUTH,
    CONF_BATTERY_SOC,
    CONF_CAR_CHARGER_SWITCH,
    CONF_CAR_PLUGGED_IN,
    CONF_DECLINATION,
    CONF_HOME_CONSUMPTION,
    CONF_HOT_WATER_POWER,
    CONF_HOT_WATER_SWITCH,
    CONF_HOT_WATER_TEMP,
    CONF_KWP,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SOLAR_PRODUCTION,
    DOMAIN,
    FORECAST_CACHE_MAX_AGE_SECONDS,
    FORECAST_SOLAR_BASE_URL,
    FORECAST_UPDATE_INTERVAL_SECONDS,
    MODE_ERROR,
    SCAN_INTERVAL_SECONDS,
)
from .optimizer import OptimizerSnapshot, compute_actions

_LOGGER = logging.getLogger(__name__)


class SolarOptimizerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls sensors, calls the optimizer, and drives switches."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise coordinator."""
        self._entry = entry

        # Override state managed here; switch entities read/write these
        self._overrides: dict[str, bool] = {
            "force_hot_water": False,
            "force_car_charge": False,
            "dry_run": False,
        }

        # Hot-water energy accumulation
        self._hw_kwh_today: float = 0.0
        self._hw_last_ts: float | None = None
        self._hw_last_date: date | None = None

        # Forecast cache
        self._forecast_kwh: float = 0.0
        self._forecast_last_ts: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )

    # ── Public override API (used by switch entities) ─────────────────────────

    def set_override(self, key: str, value: bool) -> None:
        """Set a manual override flag and schedule an immediate refresh."""
        self._overrides[key] = value
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self.async_request_refresh())
        )

    def get_override(self, key: str) -> bool:
        """Return current override state."""
        return self._overrides.get(key, False)

    # ── DataUpdateCoordinator ─────────────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Main polling cycle — runs every 60 s."""
        cfg = {**self._entry.data, **self._entry.options}

        try:
            snapshot = await self._build_snapshot(cfg)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("Failed to read sensors: %s", err)
            return {**self._last_data_or_defaults(), "mode": MODE_ERROR}

        result = compute_actions(snapshot, cfg)

        if not self._overrides["dry_run"]:
            await self._execute_actions(result, cfg)
        else:
            _LOGGER.debug(
                "[dry-run] hot_water=%s car=%s mode=%s",
                result.hot_water_on,
                result.car_charger_on,
                result.mode,
            )

        return {
            "solar_production_w": snapshot.solar_production_w,
            "home_consumption_w": snapshot.home_consumption_w,
            "surplus_power_w": snapshot.solar_production_w - snapshot.home_consumption_w,
            "battery_soc": snapshot.battery_soc,
            "car_plugged_in": snapshot.car_plugged_in,
            "hot_water_temp": snapshot.hot_water_temp,
            "hot_water_power_w": snapshot.hot_water_power_w,
            "hot_water_kwh_today": snapshot.hot_water_kwh_today,
            "forecast_today_kwh": snapshot.forecast_today_kwh,
            "mode": result.mode,
            "hot_water_on": result.hot_water_on,
            "car_charger_on": result.car_charger_on,
            "hot_water_target_kwh": cfg.get("hot_water_daily_target_kwh", 8.0),
        }

    # ── Sensor reading ────────────────────────────────────────────────────────

    async def _build_snapshot(self, cfg: dict) -> OptimizerSnapshot:
        """Read all HA states and return an OptimizerSnapshot."""
        now = dt_util.now()
        today = now.date()
        now_ts = now.timestamp()

        # ── Midnight reset ────────────────────────────────────────────────────
        if self._hw_last_date != today:
            self._hw_kwh_today = 0.0
            self._hw_last_ts = None
            self._hw_last_date = today

        def _float_state(entity_id: str, default: float = 0.0) -> float:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown", ""):
                return default
            try:
                return float(state.state)
            except ValueError:
                return default

        def _bool_state(entity_id: str) -> bool:
            state = self.hass.states.get(entity_id)
            if state is None:
                return False
            return state.state in ("on", "true", "True", "1", "home", "plugged_in")

        solar_w = _float_state(cfg[CONF_SOLAR_PRODUCTION])
        home_w = _float_state(cfg[CONF_HOME_CONSUMPTION])
        battery_soc = _float_state(cfg[CONF_BATTERY_SOC], default=50.0)
        hot_water_temp = _float_state(cfg[CONF_HOT_WATER_TEMP], default=20.0)
        hot_water_power_w = _float_state(cfg[CONF_HOT_WATER_POWER])
        car_plugged_in = _bool_state(cfg[CONF_CAR_PLUGGED_IN])

        hw_switch_state = self.hass.states.get(cfg[CONF_HOT_WATER_SWITCH])
        hw_switch_on = hw_switch_state is not None and hw_switch_state.state == "on"

        # ── Hot-water energy integration ──────────────────────────────────────
        if hw_switch_on and hot_water_power_w > 0 and self._hw_last_ts is not None:
            elapsed_h = (now_ts - self._hw_last_ts) / 3600.0
            self._hw_kwh_today += hot_water_power_w * elapsed_h / 1000.0

        self._hw_last_ts = now_ts

        # ── Forecast (cached, refreshed every 30 min) ─────────────────────────
        forecast_stale = (
            self._forecast_last_ts is None
            or (now_ts - self._forecast_last_ts) >= FORECAST_UPDATE_INTERVAL_SECONDS
        )
        if forecast_stale:
            try:
                self._forecast_kwh = await self._fetch_forecast(cfg)
                self._forecast_last_ts = now_ts
            except Exception as err:  # pylint: disable=broad-except
                age = now_ts - (self._forecast_last_ts or 0)
                if age > FORECAST_CACHE_MAX_AGE_SECONDS:
                    _LOGGER.warning(
                        "forecast.solar unavailable and cache is >24 h old (%s). "
                        "Using 0 kWh fallback.",
                        err,
                    )
                    self._forecast_kwh = 0.0
                else:
                    _LOGGER.debug("Using cached forecast (API error: %s)", err)

        return OptimizerSnapshot(
            solar_production_w=solar_w,
            home_consumption_w=home_w,
            hot_water_power_w=hot_water_power_w,
            hot_water_switch_on=hw_switch_on,
            hot_water_kwh_today=self._hw_kwh_today,
            hot_water_temp=hot_water_temp,
            battery_soc=battery_soc,
            car_plugged_in=car_plugged_in,
            car_charger_on=_bool_state(cfg[CONF_CAR_CHARGER_SWITCH]),
            force_hot_water=self._overrides["force_hot_water"],
            force_car_charge=self._overrides["force_car_charge"],
            forecast_today_kwh=self._forecast_kwh,
            current_hour=now.hour,
        )

    # ── Forecast API ──────────────────────────────────────────────────────────

    async def _fetch_forecast(self, cfg: dict) -> float:
        """Call forecast.solar and return today's predicted kWh."""
        lat = cfg[CONF_LATITUDE]
        lon = cfg[CONF_LONGITUDE]
        dec = cfg[CONF_DECLINATION]
        az = cfg[CONF_AZIMUTH]
        kwp = cfg[CONF_KWP]
        api_key = cfg.get(CONF_API_KEY, "")

        if api_key:
            url = f"{FORECAST_SOLAR_BASE_URL}/{api_key}/estimate/{lat}/{lon}/{dec}/{az}/{kwp}"
        else:
            url = f"{FORECAST_SOLAR_BASE_URL}/estimate/{lat}/{lon}/{dec}/{az}/{kwp}"

        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(15):
                resp = await session.get(url, raise_for_status=True)
                data = await resp.json()

        today_str = dt_util.now().date().isoformat()
        watt_hours_day: dict = data.get("result", {}).get("watt_hours_day", {})
        wh_today = watt_hours_day.get(today_str, 0)
        return float(wh_today) / 1000.0   # Wh → kWh

    # ── Switch execution ──────────────────────────────────────────────────────

    async def _execute_actions(self, result, cfg: dict) -> None:
        """Call HA services to apply the optimizer's decisions."""
        await self._set_switch(
            cfg[CONF_HOT_WATER_SWITCH], result.hot_water_on, "hot water"
        )
        await self._set_switch(
            cfg[CONF_CAR_CHARGER_SWITCH], result.car_charger_on, "car charger"
        )

    async def _set_switch(self, entity_id: str, desired_on: bool, label: str) -> None:
        """Turn a switch on or off, with one retry on failure."""
        state = self.hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning("Switch entity %s not found", entity_id)
            return

        current_on = state.state == "on"
        if current_on == desired_on:
            return  # already in desired state

        service = "turn_on" if desired_on else "turn_off"
        try:
            await self.hass.services.async_call(
                "switch", service, {"entity_id": entity_id}, blocking=True
            )
            _LOGGER.debug("Turned %s %s (%s)", label, service.split("_")[1], entity_id)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Failed to %s %s (%s): %s — retrying in 10 s", service, label, entity_id, err
            )
            await asyncio.sleep(10)
            try:
                await self.hass.services.async_call(
                    "switch", service, {"entity_id": entity_id}, blocking=True
                )
            except Exception as retry_err:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Retry failed for %s %s: %s", service, label, retry_err
                )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _last_data_or_defaults(self) -> dict[str, Any]:
        if self.data:
            return self.data
        return {
            "solar_production_w": 0.0,
            "home_consumption_w": 0.0,
            "surplus_power_w": 0.0,
            "battery_soc": 0.0,
            "car_plugged_in": False,
            "hot_water_temp": 0.0,
            "hot_water_power_w": 0.0,
            "hot_water_kwh_today": 0.0,
            "forecast_today_kwh": 0.0,
            "mode": MODE_ERROR,
            "hot_water_on": False,
            "car_charger_on": False,
            "hot_water_target_kwh": 8.0,
        }

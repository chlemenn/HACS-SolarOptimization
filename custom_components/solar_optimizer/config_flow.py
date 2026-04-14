"""Config flow for Solar Optimizer."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_API_KEY,
    CONF_AZIMUTH,
    CONF_BATTERY_MAX_SOC,
    CONF_BATTERY_MIN_SOC,
    CONF_BATTERY_SOC,
    CONF_CAR_CHARGER_SWITCH,
    CONF_CAR_MIN_SURPLUS,
    CONF_CAR_PLUGGED_IN,
    CONF_DECLINATION,
    CONF_FORECAST_PREHEAT_THRESHOLD,
    CONF_HOME_CONSUMPTION,
    CONF_HOT_WATER_DAILY_TARGET,
    CONF_HOT_WATER_MIN_SURPLUS,
    CONF_HOT_WATER_POWER,
    CONF_HOT_WATER_SWITCH,
    CONF_HOT_WATER_TEMP,
    CONF_KWP,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PREHEAT_DEADLINE,
    CONF_SOLAR_PRODUCTION,
    CONF_THERMAL_SAFETY_MAX,
    DEFAULT_BATTERY_MAX_SOC,
    DEFAULT_BATTERY_MIN_SOC,
    DEFAULT_CAR_MIN_SURPLUS,
    DEFAULT_FORECAST_PREHEAT_THRESHOLD,
    DEFAULT_HOT_WATER_DAILY_TARGET,
    DEFAULT_HOT_WATER_MIN_SURPLUS,
    DEFAULT_PREHEAT_DEADLINE,
    DEFAULT_THERMAL_SAFETY_MAX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SolarOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the multi-step config flow for Solar Optimizer."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow."""
        self._data: dict = {}

    # ── Step 1: Forecast API params ───────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1 — forecast.solar panel parameters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self._validate_forecast_params(user_input):
                self._data.update(user_input)
                return await self.async_step_sensors()
            errors["base"] = "invalid_forecast_params"

        ha_lat = self.hass.config.latitude
        ha_lon = self.hass.config.longitude

        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=ha_lat): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-90, max=90, step=0.0001, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_LONGITUDE, default=ha_lon): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-180, max=180, step=0.0001, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_DECLINATION, default=30): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=90, step=1, mode=selector.NumberSelectorMode.SLIDER
                    )
                ),
                vol.Required(CONF_AZIMUTH, default=180): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=360, step=1, mode=selector.NumberSelectorMode.SLIDER
                    )
                ),
                vol.Required(CONF_KWP, default=5.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=100, step=0.1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_API_KEY, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    # ── Step 2: Sensor entities ───────────────────────────────────────────────

    async def async_step_sensors(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 2 — sensor entity selection."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_switches()

        schema = vol.Schema(
            {
                vol.Required(CONF_SOLAR_PRODUCTION): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_HOME_CONSUMPTION): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_BATTERY_SOC): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_HOT_WATER_TEMP): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_HOT_WATER_POWER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_CAR_PLUGGED_IN): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "input_boolean", "sensor", "device_tracker"]
                    )
                ),
            }
        )

        return self.async_show_form(step_id="sensors", data_schema=schema)

    # ── Step 3: Switch entities ───────────────────────────────────────────────

    async def async_step_switches(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 3 — switch entity selection."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_thresholds()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOT_WATER_SWITCH): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Required(CONF_CAR_CHARGER_SWITCH): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
            }
        )

        return self.async_show_form(step_id="switches", data_schema=schema)

    # ── Step 4: Thresholds ────────────────────────────────────────────────────

    async def async_step_thresholds(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 4 — threshold configuration."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="Solar Optimizer", data=self._data)

        schema = _threshold_schema()
        return self.async_show_form(step_id="thresholds", data_schema=schema)

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SolarOptimizerOptionsFlow:
        """Return the options flow."""
        return SolarOptimizerOptionsFlow(config_entry)

    @staticmethod
    def _validate_forecast_params(data: dict) -> bool:
        try:
            lat = float(data[CONF_LATITUDE])
            lon = float(data[CONF_LONGITUDE])
            dec = float(data[CONF_DECLINATION])
            az = float(data[CONF_AZIMUTH])
            kwp = float(data[CONF_KWP])
        except (ValueError, KeyError):
            return False
        return (
            -90 <= lat <= 90
            and -180 <= lon <= 180
            and 0 <= dec <= 90
            and 0 <= az <= 360
            and kwp > 0
        )


class SolarOptimizerOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring thresholds after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialise options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Show threshold editing form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = _threshold_schema(current)
        return self.async_show_form(step_id="init", data_schema=schema)


# ── Shared schema helper ──────────────────────────────────────────────────────

def _threshold_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}

    def _default(key, fallback):
        return d.get(key, fallback)

    return vol.Schema(
        {
            vol.Required(
                CONF_HOT_WATER_DAILY_TARGET,
                default=_default(CONF_HOT_WATER_DAILY_TARGET, DEFAULT_HOT_WATER_DAILY_TARGET),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="kWh"
                )
            ),
            vol.Required(
                CONF_THERMAL_SAFETY_MAX,
                default=_default(CONF_THERMAL_SAFETY_MAX, DEFAULT_THERMAL_SAFETY_MAX),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=40, max=90, step=1, mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="°C"
                )
            ),
            vol.Required(
                CONF_HOT_WATER_MIN_SURPLUS,
                default=_default(CONF_HOT_WATER_MIN_SURPLUS, DEFAULT_HOT_WATER_MIN_SURPLUS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=100, max=5000, step=100, mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="W"
                )
            ),
            vol.Required(
                CONF_CAR_MIN_SURPLUS,
                default=_default(CONF_CAR_MIN_SURPLUS, DEFAULT_CAR_MIN_SURPLUS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=500, max=10000, step=100, mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="W"
                )
            ),
            vol.Required(
                CONF_BATTERY_MIN_SOC,
                default=_default(CONF_BATTERY_MIN_SOC, DEFAULT_BATTERY_MIN_SOC),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=50, step=5, mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="%"
                )
            ),
            vol.Required(
                CONF_BATTERY_MAX_SOC,
                default=_default(CONF_BATTERY_MAX_SOC, DEFAULT_BATTERY_MAX_SOC),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=50, max=100, step=5, mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="%"
                )
            ),
            vol.Required(
                CONF_FORECAST_PREHEAT_THRESHOLD,
                default=_default(
                    CONF_FORECAST_PREHEAT_THRESHOLD, DEFAULT_FORECAST_PREHEAT_THRESHOLD
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=20, step=0.5, mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="kWh"
                )
            ),
            vol.Required(
                CONF_PREHEAT_DEADLINE,
                default=_default(CONF_PREHEAT_DEADLINE, DEFAULT_PREHEAT_DEADLINE),
            ): selector.TimeSelector(),
        }
    )

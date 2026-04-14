"""Pure optimization logic for Solar Optimizer.

This module has no Home Assistant dependencies — all inputs come as plain
Python values and the function returns a plain dataclass.  This makes it
straightforward to unit-test without standing up a HA instance.
"""
from __future__ import annotations

from dataclasses import dataclass

from .const import (
    CONF_BATTERY_MIN_SOC,
    CONF_CAR_MIN_SURPLUS,
    CONF_FORECAST_PREHEAT_THRESHOLD,
    CONF_HOT_WATER_DAILY_TARGET,
    CONF_HOT_WATER_MIN_SURPLUS,
    CONF_PREHEAT_DEADLINE,
    CONF_THERMAL_SAFETY_MAX,
    MODE_CHARGING,
    MODE_HEATING,
    MODE_IDLE,
    MODE_PREHEAT,
    MODE_STORING,
)


@dataclass
class OptimizerSnapshot:
    """Immutable snapshot of all sensor values for one decision cycle."""

    solar_production_w: float
    home_consumption_w: float
    hot_water_power_w: float        # live reading from smart plug (0 when off)
    hot_water_switch_on: bool
    hot_water_kwh_today: float
    hot_water_temp: float           # current water temperature in °C
    battery_soc: float              # 0–100 %
    car_plugged_in: bool
    car_charger_on: bool
    force_hot_water: bool           # manual override active
    force_car_charge: bool          # manual override active
    forecast_today_kwh: float       # predicted production for today
    current_hour: int               # 0–23, local time


@dataclass
class OptimizerResult:
    """Desired switch states returned by the optimizer."""

    hot_water_on: bool
    car_charger_on: bool
    mode: str


def compute_actions(snap: OptimizerSnapshot, cfg: dict) -> OptimizerResult:
    """Determine the desired switch states for this cycle.

    Priority order (per spec):
      1. Hot water  — until 8 kWh/day delivered or thermal safety max hit
      2. Car charge — when car is plugged in and enough surplus remains
      3. Battery    — handled by Huawei inverter automatically
      4. Grid       — remainder exported automatically

    Forecast-based pre-heating kicks in when the day's predicted production
    is below the configured threshold AND the deadline has not passed yet.
    """
    daily_target: float = cfg.get(CONF_HOT_WATER_DAILY_TARGET, 8.0)
    thermal_max: float = cfg.get(CONF_THERMAL_SAFETY_MAX, 65.0)
    hw_min_surplus: float = cfg.get(CONF_HOT_WATER_MIN_SURPLUS, 500.0)
    car_min_surplus: float = cfg.get(CONF_CAR_MIN_SURPLUS, 1400.0)
    battery_min: float = cfg.get(CONF_BATTERY_MIN_SOC, 10.0)
    preheat_threshold: float = cfg.get(CONF_FORECAST_PREHEAT_THRESHOLD, 4.0)
    preheat_deadline_str: str = cfg.get(CONF_PREHEAT_DEADLINE, "10:00:00")

    try:
        preheat_deadline_hour = int(preheat_deadline_str.split(":")[0])
    except (ValueError, IndexError):
        preheat_deadline_hour = 10

    surplus_w = snap.solar_production_w - snap.home_consumption_w

    # ── Hot water needs ───────────────────────────────────────────────────────
    hw_needed = (
        snap.hot_water_kwh_today < daily_target
        and snap.hot_water_temp < thermal_max
    )

    # ── Decision: hot water ───────────────────────────────────────────────────
    hot_water_on = False

    if snap.force_hot_water and hw_needed:
        # Manual override ignores surplus check
        hot_water_on = True

    elif hw_needed:
        # Normal: activate on surplus
        if surplus_w >= hw_min_surplus:
            hot_water_on = True
        # Forecast pre-heating: turn on regardless of surplus when today's
        # predicted production is too low AND deadline not yet passed AND
        # battery has enough charge to absorb the draw.
        elif (
            snap.forecast_today_kwh < preheat_threshold
            and snap.current_hour < preheat_deadline_hour
            and snap.battery_soc > battery_min + 10
        ):
            hot_water_on = True

    # ── Remaining surplus after hot water ─────────────────────────────────────
    # When hot water is on we subtract its live power draw (or estimate the
    # threshold if it's just being turned on this cycle).
    if hot_water_on:
        hw_draw = snap.hot_water_power_w if snap.hot_water_switch_on else hw_min_surplus
        remaining_surplus_w = surplus_w - hw_draw
    else:
        remaining_surplus_w = surplus_w

    # ── Decision: car charging ────────────────────────────────────────────────
    car_charger_on = False

    if snap.force_car_charge and snap.car_plugged_in:
        car_charger_on = True
    elif snap.car_plugged_in and remaining_surplus_w >= car_min_surplus:
        car_charger_on = True

    # ── Mode label ────────────────────────────────────────────────────────────
    mode = _derive_mode(
        hot_water_on=hot_water_on,
        car_charger_on=car_charger_on,
        is_preheat=hot_water_on and surplus_w < hw_min_surplus,
        surplus_w=remaining_surplus_w,
        battery_soc=snap.battery_soc,
        battery_max=cfg.get("battery_max_soc", 95.0),
    )

    return OptimizerResult(
        hot_water_on=hot_water_on,
        car_charger_on=car_charger_on,
        mode=mode,
    )


def _derive_mode(
    hot_water_on: bool,
    car_charger_on: bool,
    is_preheat: bool,
    surplus_w: float,
    battery_soc: float,
    battery_max: float,
) -> str:
    if hot_water_on and is_preheat:
        return MODE_PREHEAT
    if hot_water_on:
        return MODE_HEATING
    if car_charger_on:
        return MODE_CHARGING
    if surplus_w > 0 and battery_soc < battery_max:
        return MODE_STORING
    return MODE_IDLE

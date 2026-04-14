"""Sensor platform for Solar Optimizer."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODE_ERROR
from .coordinator import SolarOptimizerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Optimizer sensors."""
    coordinator: SolarOptimizerCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_info = _device_info(entry)

    async_add_entities(
        [
            SolarOptimizerModeSensor(coordinator, entry, device_info),
            SolarOptimizerSurplusSensor(coordinator, entry, device_info),
            SolarOptimizerHotWaterKwhSensor(coordinator, entry, device_info),
            SolarOptimizerForecastSensor(coordinator, entry, device_info),
        ]
    )


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Solar Optimizer",
        manufacturer="Solar Optimizer",
        model="Energy Manager",
        entry_type="service",
    )


class _SolarOptimizerEntity(CoordinatorEntity[SolarOptimizerCoordinator], SensorEntity):
    """Base class for Solar Optimizer sensor entities."""

    def __init__(
        self,
        coordinator: SolarOptimizerCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = device_info


# ── Mode sensor ───────────────────────────────────────────────────────────────

class SolarOptimizerModeSensor(_SolarOptimizerEntity):
    """Exposes the current optimizer mode and all live metrics as attributes."""

    _attr_name = "Solar Optimizer Mode"
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator, entry, device_info):
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_mode"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("mode", MODE_ERROR)

    @property
    def extra_state_attributes(self) -> dict:
        d = self.coordinator.data or {}
        return {
            "solar_production_w": d.get("solar_production_w", 0),
            "home_consumption_w": d.get("home_consumption_w", 0),
            "surplus_power_w": d.get("surplus_power_w", 0),
            "battery_soc": d.get("battery_soc", 0),
            "car_plugged_in": d.get("car_plugged_in", False),
            "hot_water_temp": d.get("hot_water_temp", 0),
            "hot_water_on": d.get("hot_water_on", False),
            "car_charger_on": d.get("car_charger_on", False),
            "hot_water_kwh_today": round(d.get("hot_water_kwh_today", 0), 3),
            "hot_water_target_kwh": d.get("hot_water_target_kwh", 8.0),
            "forecast_today_kwh": round(d.get("forecast_today_kwh", 0), 2),
        }


# ── Surplus power sensor ──────────────────────────────────────────────────────

class SolarOptimizerSurplusSensor(_SolarOptimizerEntity):
    """Current available surplus solar power in watts."""

    _attr_name = "Solar Optimizer Surplus Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator, entry, device_info):
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_surplus_power"

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.data.get("surplus_power_w")
        return round(v, 1) if v is not None else None


# ── Hot water kWh today sensor ────────────────────────────────────────────────

class SolarOptimizerHotWaterKwhSensor(_SolarOptimizerEntity):
    """Energy delivered to the hot water heater today."""

    _attr_name = "Solar Optimizer Hot Water kWh Today"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator, entry, device_info):
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_hot_water_kwh_today"

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.data.get("hot_water_kwh_today")
        return round(v, 3) if v is not None else None


# ── Forecast today sensor ─────────────────────────────────────────────────────

class SolarOptimizerForecastSensor(_SolarOptimizerEntity):
    """Predicted solar production for today from forecast.solar."""

    _attr_name = "Solar Optimizer Forecast Today"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, coordinator, entry, device_info):
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_forecast_today"

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.data.get("forecast_today_kwh")
        return round(v, 2) if v is not None else None

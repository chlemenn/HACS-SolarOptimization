"""Switch platform for Solar Optimizer (overrides + dry-run)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SolarOptimizerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Optimizer override switches."""
    coordinator: SolarOptimizerCoordinator = hass.data[DOMAIN][entry.entry_id]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Solar Optimizer",
        manufacturer="Solar Optimizer",
        model="Energy Manager",
        entry_type="service",
    )

    async_add_entities(
        [
            SolarOptimizerOverrideSwitch(
                coordinator, entry, device_info,
                override_key="force_hot_water",
                name="Solar Optimizer Force Hot Water",
                unique_suffix="force_hot_water",
                icon="mdi:water-boiler-alert",
            ),
            SolarOptimizerOverrideSwitch(
                coordinator, entry, device_info,
                override_key="force_car_charge",
                name="Solar Optimizer Force Car Charge",
                unique_suffix="force_car_charge",
                icon="mdi:car-electric",
            ),
            SolarOptimizerOverrideSwitch(
                coordinator, entry, device_info,
                override_key="dry_run",
                name="Solar Optimizer Dry Run",
                unique_suffix="dry_run",
                icon="mdi:test-tube",
            ),
        ]
    )


class SolarOptimizerOverrideSwitch(
    CoordinatorEntity[SolarOptimizerCoordinator], SwitchEntity
):
    """A switch that sets an override flag on the coordinator."""

    def __init__(
        self,
        coordinator: SolarOptimizerCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
        override_key: str,
        name: str,
        unique_suffix: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._override_key = override_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = device_info
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return self.coordinator.get_override(self._override_key)

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.set_override(self._override_key, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.set_override(self._override_key, False)
        self.async_write_ha_state()

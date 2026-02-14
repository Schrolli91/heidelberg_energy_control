"""Number platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HeidelbergEnergyControlConfigEntry
from .const import COMMAND_MAX_CURRENT, REG_COMMAND_MAX_CURRENT
from .sensor import HeidelbergEntityBase


@dataclass(frozen=True, kw_only=True)
class HeidelbergNumberEntityDescription(NumberEntityDescription):
    """Class describing Heidelberg number entities."""

    register: int
    multiplier: float = 1.0


NUMBER_TYPES: tuple[HeidelbergNumberEntityDescription, ...] = (
    HeidelbergNumberEntityDescription(
        key=COMMAND_MAX_CURRENT,
        translation_key=COMMAND_MAX_CURRENT,
        register=REG_COMMAND_MAX_CURRENT,
        multiplier=10.0,
        native_min_value=6.0,
        native_max_value=16.0,
        native_step=0.1,
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []

    for description in NUMBER_TYPES:
        if description.key == COMMAND_MAX_CURRENT:
            entities.append(HeidelbergNumberProxy(coordinator, entry, description))
        else:
            entities.append(HeidelbergNumber(coordinator, entry, description))

    async_add_entities(entities)


class HeidelbergNumber(HeidelbergEntityBase, NumberEntity):
    """Base class for Heidelberg number entities."""

    entity_description: HeidelbergNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the value directly."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Write value and update coordinator data immediately."""
        modbus_value = int(value * self.entity_description.multiplier)

        await self.coordinator.api.async_write_register(
            self.entity_description.register, modbus_value
        )

        # Optimistic update
        self.coordinator.data[self.entity_description.key] = value
        self.coordinator.async_set_updated_data(self.coordinator.data)


class HeidelbergNumberProxy(HeidelbergEntityBase, NumberEntity, RestoreEntity):
    """Specialized class for Max Current with Proxy-Logic."""

    entity_description: HeidelbergNumberEntityDescription

    async def async_added_to_hass(self) -> None:
        """Restore last state as float."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            if state.state not in ("unknown", "unavailable"):
                self.coordinator.target_current = float(state.state)

    @property
    def native_value(self) -> float:
        """Return the logical target float value."""
        return self.coordinator.target_current

    async def async_set_native_value(self, value: float) -> None:
        """Set value, write if enabled, and refresh UI immediately."""
        self.coordinator.target_current = value
        modbus_value = int(value * self.entity_description.multiplier)

        if self.coordinator.logic_enabled:
            await self.coordinator.api.async_write_register(
                self.entity_description.register, modbus_value
            )
            # Nur wenn wir wirklich schreiben, aktualisieren wir auch
            # den Hardware-Sensor-Wert in der data-Map
            self.coordinator.data[self.entity_description.key] = value

        # In jedem Fall: UI-Refresh triggern, damit Slider (und ggf. Sensor) aktuell sind
        self.coordinator.async_set_updated_data(self.coordinator.data)

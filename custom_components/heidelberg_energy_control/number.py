"""Number platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass

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
from .const import VIRTUAL_TARGET_CURRENT
from .classes.heidelberg_entity_base import HeidelbergEntityBase
from .classes.heidelberg_number import HeidelbergNumber


@dataclass(frozen=True, kw_only=True)
class HeidelbergNumberEntityDescription(NumberEntityDescription):
    """Class describing Heidelberg number entities."""

    # Make these optional so virtual numbers don't need them
    register: int | None = None
    multiplier: float | None = None


NUMBER_TYPES: tuple[HeidelbergNumberEntityDescription, ...] = (
    HeidelbergNumberEntityDescription(
        key=VIRTUAL_TARGET_CURRENT,
        translation_key=VIRTUAL_TARGET_CURRENT,
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
        if description.key == VIRTUAL_TARGET_CURRENT:
            entities.append(HeidelbergNumberVirtual(coordinator, entry, description))
        else:
            entities.append(HeidelbergNumber(coordinator, entry, description))

    async_add_entities(entities)


class HeidelbergNumberVirtual(HeidelbergEntityBase, NumberEntity, RestoreEntity):
    """Generic representation of a number entity using proxy logic."""

    async def async_added_to_hass(self) -> None:
        """Restore state and sync value with coordinator."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            if state.state not in ("unknown", "unavailable"):
                # Pass the restored value to the coordinator dispatcher
                await self.coordinator.async_handle_number_set(
                    self.entity_description.key, float(state.state)
                )

    @property
    def native_value(self) -> float | None:
        """Return value from coordinator storage using the entity key."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Forward slider change to coordinator dispatcher."""
        await self.coordinator.async_handle_number_set(
            self.entity_description.key, value
        )
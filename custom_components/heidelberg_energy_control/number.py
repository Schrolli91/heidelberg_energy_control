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

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_number import HeidelbergNumber
from .classes.heidelberg_number_virtual import HeidelbergNumberVirtual
from .const import VIRTUAL_TARGET_CURRENT


@dataclass(frozen=True, kw_only=True)
class HeidelbergNumberEntityDescription(NumberEntityDescription):
    """Class describing Heidelberg number entities."""

    min_version: str | None = None

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
        min_version="1.0.7" # depends on COMMAND_TARGET_CURRENT
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
        if coordinator.is_supported(description.min_version, description.key):
            if description.key == VIRTUAL_TARGET_CURRENT:
                entities.append(
                    HeidelbergNumberVirtual(coordinator, entry, description)
                )
            else:
                entities.append(HeidelbergNumber(coordinator, entry, description))

    async_add_entities(entities)

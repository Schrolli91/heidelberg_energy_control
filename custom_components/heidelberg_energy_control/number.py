"""Number platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass, replace

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
from .const import DATA_HW_MAX_CURR, VIRTUAL_TARGET_CURRENT
from .core.capabilities import Capability, CoreCapability


@dataclass(frozen=True, kw_only=True)
class HeidelbergNumberEntityDescription(NumberEntityDescription):
    """Class describing Heidelberg number entities."""

    capability: type[Capability]

    # Optional: virtual numbers don't need it
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
        capability=CoreCapability,
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
    loaded_types = {type(c) for c in coordinator.api.capabilities}

    for description in NUMBER_TYPES:
        if description.capability not in loaded_types:
            continue
        if description.key == VIRTUAL_TARGET_CURRENT:
            if not coordinator.supports_virtual_logic:
                continue
            hw_max_current = float(coordinator.static_data.get(DATA_HW_MAX_CURR, 16))
            description = replace(description, native_max_value=hw_max_current)
            entities.append(
                HeidelbergNumberVirtual(coordinator, entry, description)
            )
        else:
            entities.append(HeidelbergNumber(coordinator, entry, description))

    async_add_entities(entities)

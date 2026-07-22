"""Number platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_number import HeidelbergNumber
from .classes.heidelberg_number_virtual import HeidelbergNumberVirtual
from .const import (
    COMMAND_FAILSAFE_CURRENT,
    COMMAND_WATCHDOG_TIMEOUT,
    DATA_HW_MAX_CURR,
    VIRTUAL_TARGET_CURRENT,
)
from .core.capabilities import Capability, CoreCapability, WatchdogCapability


@dataclass(frozen=True, kw_only=True)
class HeidelbergNumberEntityDescription(NumberEntityDescription):
    """Class describing Heidelberg number entities."""

    capability: type[Capability]

    # Optional: display-unit divisor for values on raw wire form.
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
    HeidelbergNumberEntityDescription(
        key=COMMAND_WATCHDOG_TIMEOUT,
        translation_key=COMMAND_WATCHDOG_TIMEOUT,
        native_min_value=0,
        native_max_value=65,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:timer-alert-outline",
        capability=WatchdogCapability,
        multiplier=1000,
    ),
    HeidelbergNumberEntityDescription(
        key=COMMAND_FAILSAFE_CURRENT,
        translation_key=COMMAND_FAILSAFE_CURRENT,
        native_min_value=0.0,
        native_max_value=16.0,
        native_step=0.1,
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:current-ac",
        capability=WatchdogCapability,
        multiplier=10,
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

    hw_max_current = float(coordinator.static_data.get(DATA_HW_MAX_CURR, 16))

    for description in NUMBER_TYPES:
        if description.capability not in loaded_types:
            continue
        if description.key == VIRTUAL_TARGET_CURRENT:
            if not coordinator.supports_virtual_logic:
                continue
            description = replace(description, native_max_value=hw_max_current)
            entities.append(
                HeidelbergNumberVirtual(coordinator, entry, description)
            )
        elif description.key == COMMAND_FAILSAFE_CURRENT:
            description = replace(description, native_max_value=hw_max_current)
            entities.append(HeidelbergNumber(coordinator, entry, description))
        else:
            entities.append(HeidelbergNumber(coordinator, entry, description))

    async_add_entities(entities)

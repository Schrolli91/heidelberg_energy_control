"""Number platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_number import HeidelbergNumber
from .classes.heidelberg_number_virtual import HeidelbergNumberVirtual
from .const import (
    COMMAND_FAILSAFE_CURRENT,
    COMMAND_MAX_POWER_TARGET,
    COMMAND_WATCHDOG_TIMEOUT,
    DATA_HW_MAX_CURR,
    VIRTUAL_TARGET_CURRENT,
)
from .core.capabilities import (
    Capability,
    CoreCapability,
    PowerTargetCapability,
    WatchdogCapability,
)


@dataclass(frozen=True, kw_only=True)
class HeidelbergNumberEntityDescription(NumberEntityDescription):
    """Class describing Heidelberg number entities."""

    capability: type[Capability]

    # Optional: display-unit divisor for values on raw wire form.
    multiplier: float | None = None


# A power target above what the hardware can physically draw is
# unreachable, so the slider is capped at the nominal 3-phase ceiling
# for the installed current limit rather than at the register's 65535 W.
NOMINAL_PHASE_VOLTAGE = 230
PHASE_COUNT = 3


def max_power_target_watts(hw_max_current: float) -> float:
    """Nominal 3-phase power ceiling for a given hardware current limit."""
    return float(round(hw_max_current * NOMINAL_PHASE_VOLTAGE * PHASE_COUNT))


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
    HeidelbergNumberEntityDescription(
        key=COMMAND_MAX_POWER_TARGET,
        translation_key=COMMAND_MAX_POWER_TARGET,
        native_min_value=0,
        native_max_value=11040,
        native_step=100,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:flash-auto",
        capability=PowerTargetCapability,
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
        elif description.key == COMMAND_MAX_POWER_TARGET:
            description = replace(
                description,
                native_max_value=max_power_target_watts(hw_max_current),
            )
            entities.append(HeidelbergNumber(coordinator, entry, description))
        else:
            entities.append(HeidelbergNumber(coordinator, entry, description))

    async_add_entities(entities)

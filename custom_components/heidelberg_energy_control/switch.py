"""Switch platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_switch import HeidelbergSwitch
from .classes.heidelberg_switch_virtual import HeidelbergSwitchVirtual
from .const import COMMAND_REMOTE_LOCK, COMMAND_STANDBY, VIRTUAL_ENABLE
from .core.capabilities import Capability, CoreCapability, StandbyCapability


@dataclass(frozen=True, kw_only=True)
class HeidelbergSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Heidelberg switch entities."""

    capability: type[Capability]

    on_value: int = 1
    off_value: int = 0


SWITCH_TYPES: tuple[HeidelbergSwitchEntityDescription, ...] = (
    HeidelbergSwitchEntityDescription(
        key=COMMAND_REMOTE_LOCK,
        translation_key=COMMAND_REMOTE_LOCK,
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
        on_value=0,
        off_value=1,
        capability=CoreCapability,
    ),
    HeidelbergSwitchEntityDescription(
        key=COMMAND_STANDBY,
        translation_key=COMMAND_STANDBY,
        icon="mdi:sleep",
        entity_category=EntityCategory.CONFIG,
        on_value=0,
        off_value=4,
        capability=StandbyCapability,
    ),
    HeidelbergSwitchEntityDescription(
        key=VIRTUAL_ENABLE,
        translation_key=VIRTUAL_ENABLE,
        icon="mdi:power",
        capability=CoreCapability,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    loaded_types = {type(c) for c in coordinator.api.capabilities}

    for description in SWITCH_TYPES:
        if description.capability not in loaded_types:
            continue
        if description.key == VIRTUAL_ENABLE:
            if not coordinator.supports_virtual_logic:
                continue
            entities.append(HeidelbergSwitchVirtual(coordinator, entry, description))
        else:
            entities.append(HeidelbergSwitch(coordinator, entry, description))

    async_add_entities(entities)

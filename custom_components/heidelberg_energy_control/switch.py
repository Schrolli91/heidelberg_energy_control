"""Switch platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .classes.heidelberg_switch import HeidelbergSwitch
from .classes.heidelberg_switch_virtual import HeidelbergSwitchVirtual
from .const import COMMAND_REMOTE_LOCK, REG_COMMAND_REMOTE_LOCK, VIRTUAL_ENABLE


@dataclass(frozen=True, kw_only=True)
class HeidelbergSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Heidelberg switch entities."""

    # Make these optional so virtual switches don't need them
    register: int | None = None
    on_value: int = 1
    off_value: int = 0


SWITCH_TYPES: tuple[HeidelbergSwitchEntityDescription, ...] = (
    HeidelbergSwitchEntityDescription(
        key=COMMAND_REMOTE_LOCK,
        translation_key=COMMAND_REMOTE_LOCK,
        icon="mdi:lock",
        entity_category=EntityCategory.CONFIG,
        register=REG_COMMAND_REMOTE_LOCK,
        on_value=0,
        off_value=1,
    ),
    HeidelbergSwitchEntityDescription(
        key=VIRTUAL_ENABLE,
        translation_key=VIRTUAL_ENABLE,
        icon="mdi:power",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = []

    for description in SWITCH_TYPES:
        if description.key == VIRTUAL_ENABLE:
            entities.append(HeidelbergSwitchVirtual(coordinator, entry, description))
        else:
            entities.append(HeidelbergSwitch(coordinator, entry, description))

    async_add_entities(entities)

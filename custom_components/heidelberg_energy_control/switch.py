"""Switch platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeidelbergEnergyControlConfigEntry
from .const import VIRTUAL_ENABLE
from .classes.heidelberg_switch_virtual import HeidelbergSwitchVirtual


@dataclass(frozen=True, kw_only=True)
class HeidelbergSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Heidelberg switch entities."""


SWITCH_TYPES: tuple[HeidelbergSwitchEntityDescription, ...] = (
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
            pass
            # entities.append(HeidelbergSwitch(coordinator, entry, description))

    async_add_entities(entities)


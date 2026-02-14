"""Switch platform for Heidelberg Energy Control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HeidelbergEnergyControlConfigEntry
from .const import VIRTUAL_ENABLE
from .classes.heidelberg_entity_base import HeidelbergEntityBase


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


class HeidelbergSwitchVirtual(HeidelbergEntityBase, SwitchEntity, RestoreEntity):
    """Generic representation of a virtual logic switch."""

    async def async_added_to_hass(self) -> None:
        """Restore state and sync with coordinator."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            is_on = state.state == "on"
            # Update coordinator state immediately for logic processing
            await self.coordinator.async_handle_switch_state_change(
                self.entity_description.key, is_on
            )

    @property
    def is_on(self) -> bool:
        """Return the state from the central coordinator data store."""
        return self.coordinator.data.get(self.entity_description.key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on request to coordinator."""
        await self.coordinator.async_handle_switch_state_change(
            self.entity_description.key, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off request to coordinator."""
        await self.coordinator.async_handle_switch_state_change(
            self.entity_description.key, False
        )
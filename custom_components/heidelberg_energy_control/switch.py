"""Switch platform for Heidelberg Energy Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HeidelbergEnergyControlConfigEntry
from .const import COMMAND_MAX_CURRENT, REG_COMMAND_MAX_CURRENT, VIRTUAL_ENABLE
from .sensor import HeidelbergEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeidelbergEnergyControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data
    async_add_entities([HeidelbergEnableSwitch(coordinator, entry)])


class HeidelbergEnableSwitch(HeidelbergEntity, SwitchEntity, RestoreEntity):
    """Representation of an enable switch via logic proxy."""

    def __init__(self, coordinator, entry) -> None:
        """Initialize."""
        description = SwitchEntityDescription(
            key=VIRTUAL_ENABLE,
            translation_key=VIRTUAL_ENABLE,
            icon="mdi:power",
        )
        super().__init__(coordinator, entry, description)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self.coordinator.logic_enabled = state.state == "on"

            # Initialer Sync beim Start
            if self.coordinator.logic_enabled:
                modbus_value = int(self.coordinator.target_current * 10.0)
                await self.coordinator.api.async_write_register(
                    REG_COMMAND_MAX_CURRENT, modbus_value
                )
        else:
            self.coordinator.logic_enabled = False

    @property
    def is_on(self) -> bool:
        """Return true if wallbox is logically enabled."""
        return self.coordinator.logic_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable charging and update UI optimistically."""
        self.coordinator.logic_enabled = True
        modbus_value = int(self.coordinator.target_current * 10.0)

        await self.coordinator.api.async_write_register(
            REG_COMMAND_MAX_CURRENT, modbus_value
        )

        # Optimistic Update
        self.coordinator.data[COMMAND_MAX_CURRENT] = self.coordinator.target_current
        self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable charging and update UI optimistically."""
        self.coordinator.logic_enabled = False

        await self.coordinator.api.async_write_register(REG_COMMAND_MAX_CURRENT, 0)

        # Optimistic Update
        self.coordinator.data[COMMAND_MAX_CURRENT] = 0.0
        self.coordinator.async_set_updated_data(self.coordinator.data)

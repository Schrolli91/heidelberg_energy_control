"""Coordinator for Heidelberg Energy Control integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_TARGET_CURRENT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REG_COMMAND_TARGET_CURRENT,
    VIRTUAL_ENABLE,
    VIRTUAL_TARGET_CURRENT,
)

_LOGGER = logging.getLogger(__name__)

class HeidelbergEnergyControlCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching and proxy logic."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Any,
        versions: dict[str, str],
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.versions = versions
        self.entry = entry

        # Internal state memory
        self.target_current: float = 16.0
        self.logic_enabled: bool = False
        self._initial_fetch_done: bool = False

        # Initialize data dictionary with default states
        self.data: dict[str, Any] = {
            VIRTUAL_ENABLE: False,
            VIRTUAL_TARGET_CURRENT: 16.0,
            COMMAND_TARGET_CURRENT: 0.0,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from hardware and sync virtual states."""
        try:
            # Fetch all registers via API
            data = await self.api.async_get_data()

            if data and not self._initial_fetch_done:
                # Sync logic with hardware state once during startup
                hw_current = data.get(COMMAND_TARGET_CURRENT, 0.0)
                if hw_current > 0:
                    self.target_current = float(hw_current)
                    self.logic_enabled = True
                self._initial_fetch_done = True

            # Ensure virtual states are always present in the data dict
            data[VIRTUAL_ENABLE] = self.logic_enabled
            data[VIRTUAL_TARGET_CURRENT] = self.target_current

            # COMMAND_TARGET_CURRENT remains the raw value from the hardware (0.0 if disabled)
            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with Modbus API: {err}")

    async def _write_current_to_wallbox(self, value: float) -> None:
        """Write value to Modbus and update local hardware state immediately."""
        modbus_value = int(value * 10.0)
        try:
            await self.api.async_write_register(REG_COMMAND_TARGET_CURRENT, modbus_value)
            # Update hardware sensor state (Optimistic UI)
            self.data[COMMAND_TARGET_CURRENT] = value
            self.async_set_updated_data(self.data)
        except Exception as err:
            _LOGGER.error("Failed to write to wallbox register %s: %s", REG_COMMAND_TARGET_CURRENT, err)

    async def async_handle_switch_state_change(self, key: str, is_on: bool) -> None:
        """Handle virtual enable switch and update hardware current."""
        if key == VIRTUAL_ENABLE:
            self.logic_enabled = is_on
            self.data[VIRTUAL_ENABLE] = is_on

            # If enabled -> use target_current, if disabled -> set hardware to 0A
            current_to_write = self.target_current if is_on else 0.0
            await self._write_current_to_wallbox(current_to_write)

            self.async_set_updated_data(self.data)

    async def async_handle_number_set(self, key: str, value: float) -> None:
        """Handle virtual slider changes and update hardware if charging is enabled."""
        if key == VIRTUAL_TARGET_CURRENT:
            # Always store the new 'desired' value
            self.target_current = value
            self.data[VIRTUAL_TARGET_CURRENT] = value

            # Only push to hardware if the charging logic is currently ON
            if self.logic_enabled:
                await self._write_current_to_wallbox(value)
            else:
                _LOGGER.debug("Stored new target %sA, hardware remains at 0A", value)
                self.async_set_updated_data(self.data)
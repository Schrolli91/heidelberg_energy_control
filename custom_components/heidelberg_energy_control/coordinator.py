"""Coordinator for Heidelberg Energy Control integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from packaging import version

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_TARGET_CURRENT,
    DATA_REG_LAYOUT_VER,
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

        # Check if the hardware/firmware supports the virtual logic (min V1.0.7)
        # This prevents locking the wallbox at 0.0A if no UI switch is available
        self.supports_virtual_logic = self.is_supported("1.0.7", "Virtual Enable Logic")

        # Internal state memory for proxy logic
        self.target_current: float = 16.0
        self.logic_enabled: bool = False
        self._initial_fetch_done: bool = False

        # Initialize data dictionary
        self.data: dict[str, Any] = {
            VIRTUAL_ENABLE: False,
            VIRTUAL_TARGET_CURRENT: 16.0,
            COMMAND_TARGET_CURRENT: 0.0,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from hardware and sync virtual states."""
        try:
            # Fetch all registers from the wallbox via Modbus API
            data = await self.api.async_get_data()
            if not data:
                return self.data

            # If virtual logic is not supported, just return raw data (Legacy Mode)
            if not self.supports_virtual_logic:
                return data

            # --- Virtual Logic (only for V1.0.7+) ---
            hw_current = float(data.get(COMMAND_TARGET_CURRENT, 0.0))

            # Initial sync on startup: Adopt the wallbox's current state
            if not self._initial_fetch_done:
                if hw_current > 0:
                    self.target_current = hw_current
                    self.logic_enabled = True
                self._initial_fetch_done = True

            # Bidirectional Synchronization Logic:
            # 1. If hardware is 0, the virtual 'enable' switch must be turned OFF
            if hw_current == 0.0 and self.logic_enabled:
                _LOGGER.info("Wallbox reported 0.0A: Setting virtual enable to OFF")
                self.logic_enabled = False

            # 2. If hardware is > 0 but our switch was OFF (e.g. external override),
            # we must turn the switch ON and update our target slider to match reality
            elif hw_current > 0.0 and not self.logic_enabled:
                _LOGGER.info(
                    "Wallbox reported %sA (external change): Setting virtual enable to ON",
                    hw_current,
                )
                self.logic_enabled = True
                self.target_current = hw_current

            # Ensure virtual states are always synced into the data dict for the generic UI entities
            data[VIRTUAL_ENABLE] = self.logic_enabled
            data[VIRTUAL_TARGET_CURRENT] = self.target_current

            # Note: COMMAND_TARGET_CURRENT remains the raw hardware value (will show 0.0 when logic is off)
            return data

        except Exception as err:
            raise UpdateFailed(f"Error communicating with Modbus API: {err}")

    async def _write_current_to_wallbox(self, value: float) -> None:
        """Internal helper to write a specific Ampere value to the Modbus register."""
        if not self.supports_virtual_logic:
            _LOGGER.error("Firmware too old to support writing to register 261")
            return

        modbus_value = int(value * 10.0)
        try:
            await self.api.async_write_register(
                REG_COMMAND_TARGET_CURRENT, modbus_value
            )

            # Optimistic UI update: Update hardware sensor state immediately in data map
            self.data[COMMAND_TARGET_CURRENT] = value
            self.async_set_updated_data(self.data)
        except Exception as err:
            _LOGGER.error(
                "Failed to write to wallbox register %s: %s",
                REG_COMMAND_TARGET_CURRENT,
                err,
            )

    async def async_handle_switch_state_change(self, key: str, is_on: bool) -> None:
        """Handle UI requests from the virtual enable switch."""
        if not self.supports_virtual_logic:
            return

        if key == VIRTUAL_ENABLE:
            self.logic_enabled = is_on
            self.data[VIRTUAL_ENABLE] = is_on

            # Logic: If ON -> restore last known target, if OFF -> set hardware to 0.0A
            current_to_write = self.target_current if is_on else 0.0
            await self._write_current_to_wallbox(current_to_write)

            # Trigger immediate UI refresh
            self.async_set_updated_data(self.data)

    async def async_handle_number_set(self, key: str, value: float) -> None:
        """Handle UI requests from the virtual target current slider."""
        if not self.supports_virtual_logic:
            return

        if key == VIRTUAL_TARGET_CURRENT:
            # Always store the new 'desired' value, even if wallbox is currently disabled
            self.target_current = value
            self.data[VIRTUAL_TARGET_CURRENT] = value

            # Only push the update to hardware if the charging logic is currently ENABLED
            if self.logic_enabled:
                await self._write_current_to_wallbox(value)
            else:
                _LOGGER.debug(
                    "Stored new target %sA, hardware remains at 0.0A until enabled",
                    value,
                )
                self.async_set_updated_data(self.data)

    def is_supported(self, min_required: str | None, feature_name: str) -> bool:
        """Check if the firmware version supports a specific feature."""

        # Check if min_version is missing in the description
        if min_required is None:
            _LOGGER.warning(
                "Feature '%s' has no min_version defined. Loading it by default, "
                "but please check the documentation",
                feature_name,
            )
            return True

        try:
            curr = version.parse(self.versions.get(DATA_REG_LAYOUT_VER))
            supported = curr >= version.parse(min_required)

            if not supported:
                _LOGGER.info(
                    "Feature '%s' is not supported by your firmware. Required: %s, Found: %s",
                    feature_name,
                    min_required,
                    self.versions.get(DATA_REG_LAYOUT_VER),
                )
            return supported

        except Exception as err:
            _LOGGER.error(
                "Error comparing firmware versions for feature '%s': %s",
                feature_name,
                err,
            )
            return True  # Fallback: load entity to avoid data loss

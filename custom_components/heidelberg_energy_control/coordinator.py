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
from homeassistant.exceptions import HomeAssistantError

from .const import (
    COMMAND_TARGET_CURRENT,
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REG_DEF_TARGET_CURRENT,
    VIRTUAL_ENABLE,
    VIRTUAL_TARGET_CURRENT,
)
from .core.exceptions import (
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
    HeidelbergEnergyControlWriteError,
)

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching and proxy logic."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Any,
        static_data: dict[str, Any],
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
        self.static_data = static_data
        self.entry = entry

        # Check if the hardware/firmware supports the virtual logic (min V1.0.7)
        # This prevents locking the wallbox at 0.0A if no UI switch is available
        self.supports_virtual_logic = self.is_supported("1.0.7", "Virtual Enable Logic")

        # Get hardware limits from static data
        hw_max_current = float(static_data.get(DATA_HW_MAX_CURR, 16))
        default_current = min(16.0, hw_max_current)

        # Internal state memory for proxy logic
        self.target_current: float = default_current
        self.logic_enabled: bool = False
        self._initial_fetch_done: bool = False

        # Initialize data dictionary
        self.data: dict[str, Any] = {
            VIRTUAL_ENABLE: False,
            VIRTUAL_TARGET_CURRENT: default_current,
            COMMAND_TARGET_CURRENT: 0.0,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from hardware and sync virtual states."""
        try:
            # Fetch all registers from the wallbox via Modbus API
            data = await self.api.async_get_data()
            if not data:
                _LOGGER.warning(
                    "Empty data response from wallbox, keeping previous state"
                )
                # TODO: use UpdateFailed to signal unavailability.
                # Do this witch a counter to prevent marking the device as unavailable on every hicups.
                # Maybe only after 3 consecutive failures?
                return self.data

            # If virtual logic is not supported, just return raw data (Legacy Mode)
            if not self.supports_virtual_logic:
                return data

            # --- Virtual Logic (only for V1.0.7+) ---
            hw_current = float(data.get(COMMAND_TARGET_CURRENT, 0.0))

            # Initial sync on startup: Read wallbox current state
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

        except HeidelbergEnergyControlConnectionError as err:
            raise UpdateFailed(
                f"Connection to Modbus gateway failed: {err}",
                retry_after=30,
            ) from err

        except HeidelbergEnergyControlReadError as err:
            raise UpdateFailed(f"Failed to read from Wallbox: {err}") from err

        except Exception as err:
            # Catch unexpected errors and log full traceback
            _LOGGER.exception("Unexpected error in coordinator update")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _write_current_to_wallbox(self, value: float) -> None:
        """Internal helper to write a specific Ampere value."""
        if not self.supports_virtual_logic:
            _LOGGER.error("Firmware too old to support writing to register 261")
            return

        modbus_value = int(value * 10.0)
        try:
            await self.api.async_write_register(
                REG_DEF_TARGET_CURRENT.address, modbus_value
            )

            # Update local state for immediate UI feedback
            self.data[COMMAND_TARGET_CURRENT] = value
            self.async_update_listeners()

        except (
            HeidelbergEnergyControlWriteError,
            HeidelbergEnergyControlConnectionError,
        ) as err:
            _LOGGER.error("Failed to write to wallbox: %s", err)

            # If write fails due to connection, we also want to mark the coordinator as failed
            # This ensures entities reflect the broken state immediately
            self.last_update_success = False

            # Trigger refresh (which will then hit the 30s throttle in _async_update_data if connection is dead)
            await self.async_refresh()

        except Exception as err:
            # Catch unexpected errors and log full traceback
            _LOGGER.exception("Unexpected error during write operation")
            raise HomeAssistantError(f"Failed to set current: {err}") from err

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

            self.async_update_listeners()
        else:
            _LOGGER.warning("Unknown key '%s' in switch state change handler", key)

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
                self.async_update_listeners()
        else:
            _LOGGER.warning("Unknown key '%s' in number set handler", key)

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
            curr_str = self.static_data.get(DATA_REG_LAYOUT_VER)
            if curr_str is None:
                _LOGGER.warning(
                    "Firmware version not found in static data for feature '%s'. Assuming compatibility.",
                    feature_name,
                )
                return True

            curr = version.parse(curr_str)
            supported = curr >= version.parse(min_required)

            if not supported:
                _LOGGER.info(
                    "Feature '%s' is not supported by your firmware. Required: %s, Found: %s",
                    feature_name,
                    min_required,
                    curr_str,
                )
            return supported

        except Exception:
            # Fallback for parsing errors to prevent integration breakage
            _LOGGER.warning(
                "Could not parse version for %s, assuming compatible", feature_name
            )
            return True

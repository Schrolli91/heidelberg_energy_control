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
    COMMAND_WATCHDOG_TIMEOUT,
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
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
        static_data: dict[str, str],
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

        # The virtual enable/target-current UI depends on writing register 261
        # to 0 as "off"; below firmware 1.0.7 there's no way to turn it back on
        # from the UI, so we suppress the virtual layer and pass raw hardware
        # data through instead. Fail-open if the layout version can't be parsed.
        self.supports_virtual_logic = self._parse_supports_virtual_logic(static_data)

        # Get hardware limits from static data
        hw_max_current = float(static_data.get(DATA_HW_MAX_CURR, 16))
        default_current = min(16.0, hw_max_current)

        # Internal state memory for proxy logic
        self.target_current: float = default_current
        self.logic_enabled: bool = False
        self._initial_fetch_done: bool = False
        self._consecutive_empty_responses: int = 0
        self._scan_interval_seconds: int = scan_interval
        self._watchdog_warning_logged: bool = False

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
                self._consecutive_empty_responses += 1
                _LOGGER.warning(
                    "Empty data response from wallbox (consecutive count: %s), keeping previous state",
                    self._consecutive_empty_responses,
                )
                if self._consecutive_empty_responses >= 3:
                    raise UpdateFailed(
                        "Wallbox returned empty data for 3 consecutive updates"
                    )
                return self.data

            self._check_watchdog_headroom(data)

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

            # Reset consecutive empty response counter on successful update
            self._consecutive_empty_responses = 0

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
            await self.api.async_write_command(
                COMMAND_TARGET_CURRENT, modbus_value
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

    def _check_watchdog_headroom(self, data: dict[str, Any]) -> None:
        """Warn once if the poll interval is too slow to keep the watchdog fed.

        The wallbox falls back to the FailSafe current if it doesn't see a
        successful transaction within the watchdog window. A poll interval
        near the timeout gives no room for a single missed poll; warn the
        user once when scan_interval * 1.5 > timeout so they can retune.
        """
        if self._watchdog_warning_logged:
            return
        timeout_seconds = data.get(COMMAND_WATCHDOG_TIMEOUT)
        if not timeout_seconds:  # None or 0 (watchdog disabled)
            return
        headroom_seconds = self._scan_interval_seconds * 1.5
        if headroom_seconds > timeout_seconds:
            _LOGGER.warning(
                "Poll interval %ss leaves no headroom for the wallbox watchdog "
                "(timeout %ss). A single missed poll may trigger the FailSafe "
                "current. Consider a shorter poll interval or a longer watchdog.",
                self._scan_interval_seconds,
                timeout_seconds,
            )
            self._watchdog_warning_logged = True

    @staticmethod
    def _parse_supports_virtual_logic(static_data: dict[str, str]) -> bool:
        """Return True iff the layout version supports the virtual enable layer.

        The virtual layer depends on register 261 semantics that landed in
        firmware 1.0.7. Fail-open on missing or unparseable versions so a
        misreport doesn't disable a feature that would otherwise work.
        """
        layout_str = static_data.get(DATA_REG_LAYOUT_VER)
        if layout_str is None:
            _LOGGER.warning(
                "Layout version not in static data; assuming virtual enable is supported"
            )
            return True
        try:
            return version.parse(layout_str) >= version.parse("1.0.7")
        except Exception:
            _LOGGER.warning(
                "Could not parse layout version %r; assuming virtual enable is supported",
                layout_str,
            )
            return True

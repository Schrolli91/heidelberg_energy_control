"""Standby-mode capability (v1.0.8+).

Owns holding register 258 (standby function control): value 0 enables
the wallbox's built-in standby (default), value 4 disables it so the
device stays awake and remains reachable over Modbus indefinitely.

Landed with layout version 1.0.8, so the whole Amperfied connect-series
line supports it, but Heidelberg Energy Control units on firmware
below 1.0.8 do not.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import COMMAND_STANDBY
from ..exceptions import HeidelbergEnergyControlWriteError
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

_LOGGER = logging.getLogger(__name__)

REG_COMMAND_STANDBY = 258

_STANDBY_ENABLED = 0
_STANDBY_DISABLED = 4

_COMMAND_REGISTERS: dict[str, int] = {
    COMMAND_STANDBY: REG_COMMAND_STANDBY,
}


class StandbyCapability(Capability):
    """Standby-mode control (holding register 258)."""

    key = "standby"
    min_layout_version = "1.0.8"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_COMMAND_STANDBY, 1, RegisterType.HOLDING),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Probe register 258 to confirm the standby block is present.

        Layout version alone is not enough: the Amperfied connect-series
        reports a layout >= 1.0.8 but does not expose register 258.
        Reading the register in isolation avoids the batched-read failure
        that would otherwise poison the 257..262 holding block.
        """
        try:
            result = await client.read_holding_registers(
                address=REG_COMMAND_STANDBY, count=1, device_id=device_id
            )
        except (ModbusException, OSError):
            return False
        return not result.isError()

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        # Switch is "on" when the standby function is enabled (register = 0).
        return {COMMAND_STANDBY: registers[REG_COMMAND_STANDBY] == _STANDBY_ENABLED}

    def supports_write(self, key: str) -> bool:
        return key in _COMMAND_REGISTERS

    async def async_write(
        self, client: Any, device_id: int, key: str, value: int
    ) -> bool:
        address = _COMMAND_REGISTERS[key]
        try:
            result = await client.write_register(
                address=address, value=int(value), device_id=device_id
            )
            if result.isError():
                raise HeidelbergEnergyControlWriteError(
                    f"Failed to write command {key} (register {address})"
                )
            return True
        except (ModbusException, OSError) as err:
            _LOGGER.error(
                "Error on writing command %s (reg %s): %s", key, address, err
            )
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write command {key} (register {address}): {err}"
            ) from err

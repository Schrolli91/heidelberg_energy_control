"""Watchdog + FailSafe capability (v1.0.8+).

The wallbox measures time since the last successful Modbus transaction.
If that exceeds the WatchDog Timeout (register 257, ms; 0 disables the
watchdog, default 15000), the wallbox assumes Home Assistant is gone
and overrides the target current (register 261) with the FailSafe
Current (register 262, deci-amps; 0 or 60..160). When HA resumes
polling, the target-current register takes over again.

Capability passes the raw wire values (ms, deci-amps) through to the
coordinator data dict. The number entities own the display conversion:
their `multiplier` is applied symmetrically — divide on read, multiply
on write — so callers of `self.coordinator.data[key]` see the same
wire-format integer that goes back over Modbus.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import COMMAND_FAILSAFE_CURRENT, COMMAND_WATCHDOG_TIMEOUT
from ..exceptions import HeidelbergEnergyControlWriteError
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

_LOGGER = logging.getLogger(__name__)

REG_WATCHDOG_TIMEOUT = 257
REG_FAILSAFE_CURRENT = 262

_COMMAND_REGISTERS: dict[str, int] = {
    COMMAND_WATCHDOG_TIMEOUT: REG_WATCHDOG_TIMEOUT,
    COMMAND_FAILSAFE_CURRENT: REG_FAILSAFE_CURRENT,
}


class WatchdogCapability(Capability):
    """Watchdog timeout (reg 257) + FailSafe current (reg 262)."""

    key = "watchdog"
    min_layout_version = "1.0.8"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_WATCHDOG_TIMEOUT, 1, RegisterType.HOLDING),
        RegisterDefinition(REG_FAILSAFE_CURRENT, 1, RegisterType.HOLDING),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Probe register 257 to confirm the watchdog block is present.

        Layout version alone is not enough: the Amperfied connect-series
        reports a layout >= 1.0.8 but does not expose registers 257/258.
        Reading the register in isolation avoids the batched-read failure
        that would otherwise poison the whole 257..262 holding block.
        """
        try:
            result = await client.read_holding_registers(
                address=REG_WATCHDOG_TIMEOUT, count=1, device_id=device_id
            )
        except (ModbusException, OSError):
            return False
        return not result.isError()

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        return {
            COMMAND_WATCHDOG_TIMEOUT: registers[REG_WATCHDOG_TIMEOUT],
            COMMAND_FAILSAFE_CURRENT: registers[REG_FAILSAFE_CURRENT],
        }

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

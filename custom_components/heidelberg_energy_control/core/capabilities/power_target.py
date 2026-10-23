"""Maximal power target capability (v2.0.2+).

The connect.solar line can drive its internal phase switch *indirectly*:
instead of naming a current and a phase count, you hand the wallbox a
power ceiling in watts and it decides between 1-phase and 3-phase
operation on its own. That is the automatic phase switch.

    Holding (R/W):
        500   Maximal Power Target Command    0..65535 W, 0 = disabled

    Input (RO):
        5000  Maximal Power Set               reads register 500 back

The spec states register 500 is mutually exclusive with register 501
(manual phase switch) and register 261 (target current). This
integration deliberately exposes 500 and 261 side by side and leaves
the choice to the user, with a warning in the README — nothing here
blocks, overrides or second-guesses a write to 261.

Presence is probed via register **500**, not 5000. Their availability
differs: 5000 is present on every variant from V2.0.2, while 500 exists
only on connect.solar and connect.solar pro. Probing 5000 would hand a
power-target entity to connect.home users whose wallbox has nowhere to
put the value.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import COMMAND_MAX_POWER_TARGET, DATA_MAX_POWER_SET
from ..exceptions import HeidelbergEnergyControlWriteError
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

_LOGGER = logging.getLogger(__name__)

REG_MAX_POWER_TARGET = 500
REG_MAX_POWER_SET = 5000

# Register 500 is a uint16 holding register. The spec prints the range as
# "0..65536", which cannot fit; 65535 is the real ceiling. Writing 0
# disables the power target and is the wallbox default.
POWER_TARGET_MIN = 0
POWER_TARGET_MAX = 65535


class PowerTargetCapability(Capability):
    """Maximal power target (reg 500 R/W, reg 5000 readback)."""

    key = "power_target"
    min_layout_version = "2.0.2"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_MAX_POWER_TARGET, 1, RegisterType.HOLDING),
        RegisterDefinition(REG_MAX_POWER_SET, 1, RegisterType.INPUT),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Probe register 500 to confirm the power-target block is present.

        The layout version only tells us the firmware generation, not the
        product variant: a connect.home reporting V2.0.2 has register 5000
        but not 500. Reading 500 in isolation settles it, and keeps the
        failure out of the batched polled read.
        """
        try:
            result = await client.read_holding_registers(
                address=REG_MAX_POWER_TARGET, count=1, device_id=device_id
            )
        except (ModbusException, OSError):
            return False
        return not result.isError()

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        return {
            COMMAND_MAX_POWER_TARGET: registers[REG_MAX_POWER_TARGET],
            DATA_MAX_POWER_SET: registers[REG_MAX_POWER_SET],
        }

    def supports_write(self, key: str) -> bool:
        return key == COMMAND_MAX_POWER_TARGET

    async def async_write(
        self, client: Any, device_id: int, key: str, value: int
    ) -> bool:
        """Write the power target (watts) to register 500.

        Out-of-range values are rejected before they reach the bus: the
        wallbox would answer an illegal-data-value exception, which the
        batched poll then reports as a dead block rather than as the
        bad write it actually was.
        """
        if not POWER_TARGET_MIN <= value <= POWER_TARGET_MAX:
            raise HeidelbergEnergyControlWriteError(
                f"Refusing to write out-of-range power target {value!r} W "
                f"to register {REG_MAX_POWER_TARGET} "
                f"(allowed {POWER_TARGET_MIN}..{POWER_TARGET_MAX})"
            )
        try:
            result = await client.write_register(
                address=REG_MAX_POWER_TARGET, value=int(value), device_id=device_id
            )
            if result.isError():
                raise HeidelbergEnergyControlWriteError(
                    f"Failed to write command {key} "
                    f"(register {REG_MAX_POWER_TARGET})"
                )
            return True
        except (ModbusException, OSError) as err:
            _LOGGER.error(
                "Error on writing command %s (reg %s): %s",
                key,
                REG_MAX_POWER_TARGET,
                err,
            )
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write command {key} "
                f"(register {REG_MAX_POWER_TARGET}): {err}"
            ) from err

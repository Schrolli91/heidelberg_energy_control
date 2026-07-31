"""Internal MID power-meter capability (v2.0.0+, hardware-optional).

The Amperfied connect-series firmware exposes an optional built-in
MID-certified power meter starting with layout version 2.0.0. Unlike
the v1.0.x energy registers (14, 17-18), which report apparent energy
in VAh and are explicitly not for billing purposes, the MID meter
reports certified Wh.

Presence is not implied by layout version alone: connect.home units
may report layout >= 2.0.0 without the meter fitted. Register 3000
("Int. MID available", 0 or 1) is the probe; a value of 1 means the
block at 3001-3012 is populated, anything else (including an illegal
address response) means "not fitted, skip capability".

Registers owned by this capability:

    3000        MID available flag (probe only, not polled)
    3001-3003   Current L1/L2/L3        (0.1 A on the wire)
    3004-3006   Voltage L1-N/L2-N/L3-N  (V)
    3007        Power forward           (W)
    3008-3009   Energy forward, 32-bit  (Wh; billing-grade)
    3010        Power reverse           (W; spec-noted not-implemented, skipped)
    3011-3012   Energy reverse, 32-bit  (Wh)

The 3001-3012 range is read as a single block per poll. Register 3010
sits inside that block but is not decoded: reading it costs nothing
extra, and once Amperfied enables it we only need to add a decode line.

Energy values are wire-Wh; the capability converts to kWh so all
energy sensors in the integration share one unit.
"""

from __future__ import annotations

from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import (
    DATA_MID_CURRENT_L1,
    DATA_MID_CURRENT_L2,
    DATA_MID_CURRENT_L3,
    DATA_MID_ENERGY_FORWARD,
    DATA_MID_ENERGY_REVERSE,
    DATA_MID_POWER_FORWARD,
    DATA_MID_VOLTAGE_L1,
    DATA_MID_VOLTAGE_L2,
    DATA_MID_VOLTAGE_L3,
)
from ..registers import RegisterDefinition, RegisterType, pack_32bit
from .base import Capability

REG_MID_AVAILABLE = 3000
REG_MID_BLOCK_START = 3001
REG_MID_BLOCK_COUNT = 12  # 3001..3012 inclusive

_MID_PRESENT = 1


class MidMeterCapability(Capability):
    """Internal MID power meter (registers 3000..3012)."""

    key = "mid_meter"
    min_layout_version = "2.0.0"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_MID_BLOCK_START, REG_MID_BLOCK_COUNT, RegisterType.INPUT),
    )

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Probe register 3000 to decide whether the MID meter is fitted.

        Two failure modes to catch: the register isn't mapped (illegal
        address, Modbus exception) or it's mapped but reports 0. Both
        mean "skip capability" so its polled block is never read.
        """
        try:
            result = await client.read_input_registers(
                address=REG_MID_AVAILABLE, count=1, device_id=device_id
            )
        except (ModbusException, OSError):
            return False
        if result.isError() or not result.registers:
            return False
        return result.registers[0] == _MID_PRESENT

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        return {
            DATA_MID_CURRENT_L1: registers[REG_MID_BLOCK_START] / 10.0,
            DATA_MID_CURRENT_L2: registers[REG_MID_BLOCK_START + 1] / 10.0,
            DATA_MID_CURRENT_L3: registers[REG_MID_BLOCK_START + 2] / 10.0,
            DATA_MID_VOLTAGE_L1: registers[REG_MID_BLOCK_START + 3],
            DATA_MID_VOLTAGE_L2: registers[REG_MID_BLOCK_START + 4],
            DATA_MID_VOLTAGE_L3: registers[REG_MID_BLOCK_START + 5],
            DATA_MID_POWER_FORWARD: registers[REG_MID_BLOCK_START + 6],
            DATA_MID_ENERGY_FORWARD: pack_32bit(
                registers[REG_MID_BLOCK_START + 7],
                registers[REG_MID_BLOCK_START + 8],
            )
            / 1000.0,
            DATA_MID_ENERGY_REVERSE: pack_32bit(
                registers[REG_MID_BLOCK_START + 10],
                registers[REG_MID_BLOCK_START + 11],
            )
            / 1000.0,
        }

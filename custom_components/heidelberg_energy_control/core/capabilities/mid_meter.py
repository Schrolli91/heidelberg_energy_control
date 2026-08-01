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
    3010        Power reverse           (W; spec-noted not-implemented)
    3011-3012   Energy reverse, 32-bit  (Wh)

The polled definitions declare two non-contiguous blocks (3001..3009
and 3011..3012). Register 3010 falls in the gap on purpose: the spec
notes it "not yet implemented" for bidirectional operation, and any
partial-MID unit that rejects reg 3010 would otherwise atomically
fail a merged 3001..3012 read — the same failure mode as issue #16
around registers 257/258. Splitting the block isolates the failure
to reverse-energy alone; forward-energy (the billing register) is
still read even if reverse is absent.

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
REG_MID_FORWARD_START = 3001
REG_MID_FORWARD_COUNT = 9   # 3001..3009: currents, voltages, power fwd, energy fwd
REG_MID_REVERSE_START = 3011
REG_MID_REVERSE_COUNT = 2   # 3011..3012: energy reverse (skips 3010 power-reverse)

_MID_PRESENT = 1


class MidMeterCapability(Capability):
    """Internal MID power meter (registers 3000..3012, split around 3010)."""

    key = "mid_meter"
    min_layout_version = "2.0.0"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(
            REG_MID_FORWARD_START, REG_MID_FORWARD_COUNT, RegisterType.INPUT
        ),
        RegisterDefinition(
            REG_MID_REVERSE_START, REG_MID_REVERSE_COUNT, RegisterType.INPUT
        ),
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
            DATA_MID_CURRENT_L1: registers[REG_MID_FORWARD_START] / 10.0,
            DATA_MID_CURRENT_L2: registers[REG_MID_FORWARD_START + 1] / 10.0,
            DATA_MID_CURRENT_L3: registers[REG_MID_FORWARD_START + 2] / 10.0,
            DATA_MID_VOLTAGE_L1: registers[REG_MID_FORWARD_START + 3],
            DATA_MID_VOLTAGE_L2: registers[REG_MID_FORWARD_START + 4],
            DATA_MID_VOLTAGE_L3: registers[REG_MID_FORWARD_START + 5],
            DATA_MID_POWER_FORWARD: registers[REG_MID_FORWARD_START + 6],
            DATA_MID_ENERGY_FORWARD: pack_32bit(
                registers[REG_MID_FORWARD_START + 7],
                registers[REG_MID_FORWARD_START + 8],
            )
            / 1000.0,
            DATA_MID_ENERGY_REVERSE: pack_32bit(
                registers[REG_MID_REVERSE_START],
                registers[REG_MID_REVERSE_START + 1],
            )
            / 1000.0,
        }

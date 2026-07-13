"""Core (v1.0.x) capability.

Owns the original Heidelberg Energy Control register set:
  - static: layout version, hw/sw version, hw current limits
  - polled: charging state, currents, voltages, power, energies,
            locks, target current
  - writes: remote lock (259), target current (261)

Under the definition-based contract, this capability declares which
registers it needs via class-level tuples of `RegisterDefinition`;
the actual Modbus reads are executed by the API's block-merging
`async_read_registers`. The capability then decodes its output from
a `{address: value}` dict, synchronously.
"""

from __future__ import annotations

import logging
from typing import Any

from pymodbus.exceptions import ModbusException

from ...const import (
    CHARGING_STATE_MAP,
    COMMAND_REMOTE_LOCK,
    COMMAND_TARGET_CURRENT,
    DATA_CHARGING_POWER,
    DATA_CHARGING_STATE,
    DATA_CURRENT,
    DATA_CURRENT_L1,
    DATA_CURRENT_L2,
    DATA_CURRENT_L3,
    DATA_ENERGY_SINCE_POWER_ON,
    DATA_EXTERNAL_LOCK_STATE,
    DATA_HW_MAX_CURR,
    DATA_HW_MIN_CURR,
    DATA_HW_VERSION,
    DATA_IS_CHARGING,
    DATA_IS_PLUGGED,
    DATA_PCB_TEMPERATURE,
    DATA_PHASES_ACTIVE,
    DATA_REG_LAYOUT_VER,
    DATA_SW_VERSION,
    DATA_TOTAL_ENERGY,
    DATA_VOLTAGE_L1,
    DATA_VOLTAGE_L2,
    DATA_VOLTAGE_L3,
)
from ..exceptions import (
    HeidelbergEnergyControlAPIError,
    HeidelbergEnergyControlWriteError,
)
from ..registers import RegisterDefinition, RegisterType, pack_32bit
from .base import Capability

_LOGGER = logging.getLogger(__name__)

# Modbus register addresses owned by this capability.
REG_LAYOUT = 4
REG_DATA_START = 5
REG_DATA_COUNT = 14
REG_HW_CURR_START = 100
REG_HW_VERS = 200
REG_SW_VERS = 203
REG_COMMAND_REMOTE_LOCK = 259
REG_COMMAND_TARGET_CURRENT = 261

# Symbolic command keys owned by this capability, mapped to their write registers.
_COMMAND_REGISTERS: dict[str, int] = {
    COMMAND_REMOTE_LOCK: REG_COMMAND_REMOTE_LOCK,
    COMMAND_TARGET_CURRENT: REG_COMMAND_TARGET_CURRENT,
}


def register_to_version(decimal_value: int) -> str:
    """Convert a register value to a semver string (one hex nibble per part)."""
    h = hex(decimal_value)[2:].zfill(3)
    patch = int(h[-1], 16)
    minor = int(h[-2], 16)
    major = int(h[:-2], 16)
    return f"{major}.{minor}.{patch}"


def to_32bit(regs: list[int], idx_high: int) -> int:
    """Combine two 16-bit registers into one 32-bit value (high word first).

    Retained for the pure-function tests carried over from PR A. Under
    the definition-based contract, capabilities index by absolute
    address instead, so they compose 32-bit values inline via
    `pack_32bit(regs[addr], regs[addr + 1])`.
    """
    if idx_high + 1 >= len(regs):
        raise HeidelbergEnergyControlAPIError(
            f"Index {idx_high} out of bounds for 32-bit conversion"
        )
    return (regs[idx_high] << 16) | regs[idx_high + 1]


class CoreCapability(Capability):
    """v1.0.x register set — always loaded."""

    key = "core"
    min_layout_version = None  # No floor; the v1.0.0 device is the floor.

    static_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_LAYOUT, 1, RegisterType.INPUT),
        RegisterDefinition(REG_HW_CURR_START, 2, RegisterType.INPUT),
        RegisterDefinition(REG_HW_VERS, 1, RegisterType.INPUT),
        RegisterDefinition(REG_SW_VERS, 1, RegisterType.INPUT),
    )
    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(REG_DATA_START, REG_DATA_COUNT, RegisterType.INPUT),
        RegisterDefinition(REG_COMMAND_REMOTE_LOCK, 1, RegisterType.HOLDING),
        RegisterDefinition(REG_COMMAND_TARGET_CURRENT, 1, RegisterType.HOLDING),
    )

    def decode_static(self, registers: dict[int, int]) -> dict[str, Any]:
        return {
            DATA_REG_LAYOUT_VER: register_to_version(registers[REG_LAYOUT]),
            DATA_HW_VERSION: register_to_version(registers[REG_HW_VERS]),
            DATA_SW_VERSION: register_to_version(registers[REG_SW_VERS]),
            DATA_HW_MAX_CURR: registers[REG_HW_CURR_START],
            DATA_HW_MIN_CURR: registers[REG_HW_CURR_START + 1],
        }

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        # Currents and voltages live in the 5..18 data block.
        curr_l1 = registers[REG_DATA_START + 1] / 10.0
        curr_l2 = registers[REG_DATA_START + 2] / 10.0
        curr_l3 = registers[REG_DATA_START + 3] / 10.0

        active_phases = sum(1 for i in [curr_l1, curr_l2, curr_l3] if i > 0.1)
        charge_current = round(
            (curr_l1 + curr_l2 + curr_l3) / max(1, active_phases), 2
        )

        state_reg = registers[REG_DATA_START]
        power_reg = registers[REG_DATA_START + 9]

        return {
            DATA_CHARGING_STATE: CHARGING_STATE_MAP.get(
                state_reg, f"Unknown ({state_reg})"
            ),
            DATA_PHASES_ACTIVE: active_phases,
            DATA_CURRENT: charge_current,
            DATA_CURRENT_L1: curr_l1,
            DATA_CURRENT_L2: curr_l2,
            DATA_CURRENT_L3: curr_l3,
            DATA_PCB_TEMPERATURE: registers[REG_DATA_START + 4] / 10.0,
            DATA_VOLTAGE_L1: registers[REG_DATA_START + 5],
            DATA_VOLTAGE_L2: registers[REG_DATA_START + 6],
            DATA_VOLTAGE_L3: registers[REG_DATA_START + 7],
            DATA_CHARGING_POWER: power_reg,
            DATA_ENERGY_SINCE_POWER_ON: pack_32bit(
                registers[REG_DATA_START + 10], registers[REG_DATA_START + 11]
            )
            / 1000.0,
            DATA_TOTAL_ENERGY: pack_32bit(
                registers[REG_DATA_START + 12], registers[REG_DATA_START + 13]
            )
            / 1000.0,
            DATA_EXTERNAL_LOCK_STATE: registers[REG_DATA_START + 8] == 0,
            DATA_IS_PLUGGED: state_reg >= 4,
            DATA_IS_CHARGING: power_reg > 0,
            COMMAND_REMOTE_LOCK: registers[REG_COMMAND_REMOTE_LOCK] == 0,
            COMMAND_TARGET_CURRENT: registers[REG_COMMAND_TARGET_CURRENT] / 10.0,
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
            _LOGGER.error("Error on writing command %s (reg %s): %s", key, address, err)
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write command {key} (register {address}): {err}"
            ) from err

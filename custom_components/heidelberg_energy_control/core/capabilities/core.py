"""Core (v1.0.x) capability.

Owns the original Heidelberg Energy Control register set:
  - static: layout version, hw/sw version, hw current limits
  - polled: charging state, currents, voltages, power, energies, locks,
            target current
  - writes: remote lock (259), target current (261)
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
    REG_COMMAND_REMOTE_LOCK,
    REG_COMMAND_TARGET_CURRENT,
    REG_DATA_COUNT,
    REG_DATA_START,
    REG_HW_CURR_START,
    REG_HW_VERS,
    REG_LAYOUT,
    REG_SW_VERS,
)
from ..exceptions import (
    HeidelbergEnergyControlAPIError,
    HeidelbergEnergyControlReadError,
    HeidelbergEnergyControlWriteError,
)
from .base import Capability

_LOGGER = logging.getLogger(__name__)

_WRITE_ADDRESSES = frozenset({REG_COMMAND_REMOTE_LOCK, REG_COMMAND_TARGET_CURRENT})


def register_to_version(decimal_value: int) -> str:
    """Convert a register value to a semver string (one hex nibble per part)."""
    h = hex(decimal_value)[2:].zfill(3)
    patch = int(h[-1], 16)
    minor = int(h[-2], 16)
    major = int(h[:-2], 16)
    return f"{major}.{minor}.{patch}"


def to_32bit(regs: list[int], idx_high: int) -> int:
    """Combine two 16-bit registers into one 32-bit value (high word first)."""
    if idx_high + 1 >= len(regs):
        raise HeidelbergEnergyControlAPIError(
            f"Index {idx_high} out of bounds for 32-bit conversion"
        )
    return (regs[idx_high] << 16) | regs[idx_high + 1]


class CoreCapability(Capability):
    """v1.0.x register set — always loaded."""

    key = "core"
    min_layout_version = None  # No floor; the v1.0.0 device is the floor.

    async def async_read_static(
        self, client: Any, device_id: int
    ) -> dict[str, Any]:
        try:
            layout_result = await client.read_input_registers(
                address=REG_LAYOUT, count=1, device_id=device_id
            )
            if layout_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read LAYOUT register"
                )

            hw_vers_result = await client.read_input_registers(
                address=REG_HW_VERS, count=1, device_id=device_id
            )
            if hw_vers_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read HW_VERSION register"
                )

            sw_vers_result = await client.read_input_registers(
                address=REG_SW_VERS, count=1, device_id=device_id
            )
            if sw_vers_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read SW_VERSION register"
                )

            hw_curr_result = await client.read_input_registers(
                address=REG_HW_CURR_START, count=2, device_id=device_id
            )
            if hw_curr_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read HW_CURRENT register"
                )

            return {
                DATA_REG_LAYOUT_VER: register_to_version(layout_result.registers[0]),
                DATA_HW_VERSION: register_to_version(hw_vers_result.registers[0]),
                DATA_SW_VERSION: register_to_version(sw_vers_result.registers[0]),
                DATA_HW_MAX_CURR: hw_curr_result.registers[0],
                DATA_HW_MIN_CURR: hw_curr_result.registers[1],
            }
        except (ModbusException, OSError, IndexError) as err:
            _LOGGER.error("Error fetching static wallbox data: %s", err)
            raise HeidelbergEnergyControlReadError(
                f"Failed to fetch static wallbox data: {err}"
            ) from err

    async def async_read_polled(
        self, client: Any, device_id: int
    ) -> dict[str, Any]:
        try:
            data = await client.read_input_registers(
                address=REG_DATA_START,
                count=REG_DATA_COUNT,
                device_id=device_id,
            )
            if data.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read data registers"
                )

            remote_lock = await client.read_holding_registers(
                address=REG_COMMAND_REMOTE_LOCK,
                count=1,
                device_id=device_id,
            )
            if remote_lock.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read remote lock register"
                )

            target_current = await client.read_holding_registers(
                address=REG_COMMAND_TARGET_CURRENT,
                count=1,
                device_id=device_id,
            )
            if target_current.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read remote lock register"
                )

            data_regs = data.registers
            remote_lock_regs = remote_lock.registers
            target_current_regs = target_current.registers

            if not data_regs or len(data_regs) < REG_DATA_COUNT:
                _LOGGER.error(
                    "Data register incomplete: expected %d registers, got %d",
                    REG_DATA_COUNT,
                    len(data_regs) if data_regs else 0,
                )
                raise HeidelbergEnergyControlReadError("Data register incomplete")

            curr_l1 = data_regs[1] / 10.0
            curr_l2 = data_regs[2] / 10.0
            curr_l3 = data_regs[3] / 10.0

            active_phases = sum(1 for i in [curr_l1, curr_l2, curr_l3] if i > 0.1)
            charge_current = round(
                (curr_l1 + curr_l2 + curr_l3) / max(1, active_phases), 2
            )

            return {
                DATA_CHARGING_STATE: CHARGING_STATE_MAP.get(
                    data_regs[0], f"Unknown ({data_regs[0]})"
                ),
                DATA_PHASES_ACTIVE: active_phases,
                DATA_CURRENT: charge_current,
                DATA_CURRENT_L1: curr_l1,
                DATA_CURRENT_L2: curr_l2,
                DATA_CURRENT_L3: curr_l3,
                DATA_PCB_TEMPERATURE: data_regs[4] / 10.0,
                DATA_VOLTAGE_L1: data_regs[5],
                DATA_VOLTAGE_L2: data_regs[6],
                DATA_VOLTAGE_L3: data_regs[7],
                DATA_CHARGING_POWER: data_regs[9],
                DATA_ENERGY_SINCE_POWER_ON: to_32bit(data_regs, 10) / 1000.0,
                DATA_TOTAL_ENERGY: to_32bit(data_regs, 12) / 1000.0,
                DATA_EXTERNAL_LOCK_STATE: data_regs[8] == 0,
                DATA_IS_PLUGGED: data_regs[0] >= 4,
                DATA_IS_CHARGING: data_regs[9] > 0,
                COMMAND_REMOTE_LOCK: remote_lock_regs[0] == 0,
                COMMAND_TARGET_CURRENT: target_current_regs[0] / 10.0,
            }

        except (ModbusException, OSError, IndexError) as err:
            _LOGGER.error("Error fetching wallbox data: %s", err)
            raise HeidelbergEnergyControlReadError(
                f"Failed to fetch wallbox data: {err}"
            ) from err

    def supports_write(self, address: int) -> bool:
        return address in _WRITE_ADDRESSES

    async def async_write(
        self, client: Any, device_id: int, address: int, value: int
    ) -> bool:
        try:
            result = await client.write_register(
                address=address, value=int(value), device_id=device_id
            )
            if result.isError():
                raise HeidelbergEnergyControlWriteError(
                    f"Failed to write register {address}"
                )
            return True
        except (ModbusException, OSError) as err:
            _LOGGER.error("Error on writing Register %s: %s", address, err)
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write register {address}: {err}"
            ) from err

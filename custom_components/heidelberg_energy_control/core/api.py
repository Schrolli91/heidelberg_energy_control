"""API for Heidelberg Energy Control wallbox via Modbus."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Dict

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from ..const import (
    CHARGING_STATE_MAP,
    DATA_CHARGING_POWER,
    DATA_CHARGING_STATE,
    DATA_CURRENT,
    DATA_CURRENT_L1,
    DATA_CURRENT_L2,
    DATA_CURRENT_L3,
    DATA_ENERGY_SINCE_POWER_ON,
    DATA_EXTERNAL_LOCK_STATE,
    DATA_HW_MIN_CURR,
    DATA_HW_MAX_CURR,
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
    REG_DEF_CHARGING_POWER,
    REG_DEF_CHARGING_STATE,
    REG_DEF_CURRENT_L1,
    REG_DEF_CURRENT_L2,
    REG_DEF_CURRENT_L3,
    REG_DEF_ENERGY_SINCE_POWER_ON,
    REG_DEF_EXTERNAL_LOCK_STATE,
    REG_DEF_HW_CURR,
    REG_DEF_HW_VERS,
    REG_DEF_LAYOUT,
    REG_DEF_PCB_TEMPERATURE,
    REG_DEF_REMOTE_LOCK,
    REG_DEF_SW_VERS,
    REG_DEF_TARGET_CURRENT,
    REG_DEF_TOTAL_ENERGY,
    REG_DEF_VOLTAGE_L1,
    REG_DEF_VOLTAGE_L2,
    REG_DEF_VOLTAGE_L3,
    RegisterDefinition,
    RegisterType,
    COMMAND_REMOTE_LOCK,
    COMMAND_TARGET_CURRENT,
)
from .exceptions import (
    HeidelbergEnergyControlAPIError,
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
    HeidelbergEnergyControlWriteError,
)

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlAPI:
    """API class for Heidelberg Energy Control wallbox."""

    def __init__(self, host: str, port: int, device_id: int) -> None:
        """Initialize the API."""
        self._host = host
        self._port = port
        self._device_id = device_id
        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=5,
        )

    async def connect(self) -> None:
        """Connect to the wallbox (no-op if already connected)."""
        if self._client.connected:
            return
        try:
            result = await self._client.connect()
            if not result:
                raise HeidelbergEnergyControlConnectionError(
                    "Failed to connect to the wallbox"
                )
        except (ModbusException, OSError) as err:
            _LOGGER.error("Modbus connection error: %s", err)
            raise HeidelbergEnergyControlConnectionError(
                f"Failed to connect to the wallbox: {err}"
            ) from err

    async def disconnect(self) -> None:
        """Disconnect from the wallbox."""
        if self._client.connected:
            self._client.close()

    async def async_read_registers(
        self, definitions: List[RegisterDefinition]
    ) -> Dict[int, int]:
        """Read multiple register blocks efficiently.

        Args:
            definitions: List of register definitions to read.

        Returns:
            Dict mapping register address to value.
        """
        await self.connect()

        result = {}

        # Sort definitions by type then address to maximize consecutive reads
        sorted_defs = sorted(definitions, key=lambda d: (d.type.value, d.address))

        i = 0
        while i < len(sorted_defs):
            current_def = sorted_defs[i]

            # Start a new block
            start_addr = current_def.address
            end_addr = current_def.address + current_def.count
            merge_count = 1

            # Check if we can merge with next definitions
            while i + merge_count < len(sorted_defs):
                next_def = sorted_defs[i + merge_count]
                # Check if consecutive and same type
                if (
                    next_def.address == end_addr
                    and next_def.type == current_def.type
                ):
                    end_addr += next_def.count
                    merge_count += 1
                else:
                    break

            # Calculate total count for the merged block
            total_count = end_addr - start_addr

            # Perform read
            if current_def.type == RegisterType.INPUT:
                read_func = self._client.read_input_registers
            else:
                read_func = self._client.read_holding_registers

            read_result = await read_func(
                address=start_addr, count=total_count, device_id=self._device_id
            )

            if read_result.isError():
                raise HeidelbergEnergyControlReadError(
                    f"Failed to read registers at {start_addr}"
                )

            # Map results to individual addresses
            offset = 0
            for j in range(merge_count):
                def_obj = sorted_defs[i + j]
                for k in range(def_obj.count):
                    result[def_obj.address + k] = read_result.registers[offset + k]
                offset += def_obj.count

            i += merge_count

        return result

    async def async_get_static_data(self) -> dict[str, Any] | None:
        """Read the static data and return if successful."""
        try:
            definitions = [
                REG_DEF_LAYOUT,
                REG_DEF_HW_VERS,
                REG_DEF_SW_VERS,
                REG_DEF_HW_CURR,
            ]
            registers = await self.async_read_registers(definitions)

            return {
                DATA_REG_LAYOUT_VER: self._register_to_version(
                    registers[REG_DEF_LAYOUT.address]
                ),
                DATA_HW_VERSION: self._register_to_version(
                    registers[REG_DEF_HW_VERS.address]
                ),
                DATA_SW_VERSION: self._register_to_version(
                    registers[REG_DEF_SW_VERS.address]
                ),
                DATA_HW_MAX_CURR: registers[REG_DEF_HW_CURR.address],
                DATA_HW_MIN_CURR: registers[REG_DEF_HW_CURR.address + 1],
            }
        except (ModbusException, OSError, IndexError, KeyError) as err:
            _LOGGER.error("Error fetching static wallbox data: %s", err)
            raise HeidelbergEnergyControlReadError(
                f"Failed to fetch static wallbox data: {err}"
            ) from err

    async def async_write_register(self, address: int, value: int) -> bool:
        """Write a value to a specific register (FC06)."""
        write_start = time.perf_counter()
        await self.connect()
        try:
            result = await self._client.write_register(
                address=address, value=int(value), device_id=self._device_id
            )
            if result.isError():
                raise HeidelbergEnergyControlWriteError(
                    f"Failed to write register {address}"
                )

            _LOGGER.debug(
                "Write complete: WRITE: %.3fs",
                time.perf_counter() - write_start,
            )
            return True
        except (ModbusException, OSError) as err:
            _LOGGER.error("Error on writing Register %s: %s", address, err)
            raise HeidelbergEnergyControlWriteError(
                f"Failed to write register {address}: {err}"
            ) from err

    async def async_get_data(self) -> dict[str, Any]:
        """Read all relevant registers in one call and map to constants."""
        all_start = time.perf_counter()
        await self.connect()

        try:
            # Define registers to read (detailed definitions)
            definitions = [
                REG_DEF_CHARGING_STATE,
                REG_DEF_CURRENT_L1,
                REG_DEF_CURRENT_L2,
                REG_DEF_CURRENT_L3,
                REG_DEF_PCB_TEMPERATURE,
                REG_DEF_VOLTAGE_L1,
                REG_DEF_VOLTAGE_L2,
                REG_DEF_VOLTAGE_L3,
                REG_DEF_EXTERNAL_LOCK_STATE,
                REG_DEF_CHARGING_POWER,
                REG_DEF_ENERGY_SINCE_POWER_ON,
                REG_DEF_TOTAL_ENERGY,
                REG_DEF_REMOTE_LOCK,
                REG_DEF_TARGET_CURRENT,
            ]

            # Read all registers efficiently
            read_start = time.perf_counter()
            registers = await self.async_read_registers(definitions)
            read_duration = time.perf_counter() - read_start

            _LOGGER.debug(
                "Fetch complete: Total: %.3fs",
                read_duration,
            )

            active_phases = sum(
                1
                for i in [
                    registers[REG_DEF_CURRENT_L1.address] / 10.0,
                    registers[REG_DEF_CURRENT_L2.address] / 10.0,
                    registers[REG_DEF_CURRENT_L3.address] / 10.0,
                ]
                if i > 0.1
            )
            charge_current = round(
                (
                    registers[REG_DEF_CURRENT_L1.address] / 10.0
                    + registers[REG_DEF_CURRENT_L2.address] / 10.0
                    + registers[REG_DEF_CURRENT_L3.address] / 10.0
                )
                / max(1, active_phases),
                2,
            )

            return {
                DATA_CHARGING_STATE: CHARGING_STATE_MAP.get(
                    registers[REG_DEF_CHARGING_STATE.address],
                    f"Unknown ({registers[REG_DEF_CHARGING_STATE.address]})",
                ),
                DATA_PHASES_ACTIVE: active_phases,
                DATA_CURRENT: charge_current,
                DATA_CURRENT_L1: registers[REG_DEF_CURRENT_L1.address] / 10.0,
                DATA_CURRENT_L2: registers[REG_DEF_CURRENT_L2.address] / 10.0,
                DATA_CURRENT_L3: registers[REG_DEF_CURRENT_L3.address] / 10.0,
                DATA_PCB_TEMPERATURE: registers[REG_DEF_PCB_TEMPERATURE.address] / 10.0,
                DATA_VOLTAGE_L1: registers[REG_DEF_VOLTAGE_L1.address],
                DATA_VOLTAGE_L2: registers[REG_DEF_VOLTAGE_L2.address],
                DATA_VOLTAGE_L3: registers[REG_DEF_VOLTAGE_L3.address],
                DATA_CHARGING_POWER: registers[REG_DEF_CHARGING_POWER.address],
                DATA_ENERGY_SINCE_POWER_ON: self._to_32bit_from_map(
                    registers, REG_DEF_ENERGY_SINCE_POWER_ON.address
                )
                / 1000.0,
                DATA_TOTAL_ENERGY: self._to_32bit_from_map(
                    registers, REG_DEF_TOTAL_ENERGY.address
                )
                / 1000.0,
                DATA_EXTERNAL_LOCK_STATE: registers[REG_DEF_EXTERNAL_LOCK_STATE.address]
                == 0,
                DATA_IS_PLUGGED: registers[REG_DEF_CHARGING_STATE.address] >= 4,
                DATA_IS_CHARGING: registers[REG_DEF_CHARGING_POWER.address] > 0,
                COMMAND_REMOTE_LOCK: registers[REG_DEF_REMOTE_LOCK.address] == 0,
                COMMAND_TARGET_CURRENT: registers[REG_DEF_TARGET_CURRENT.address]
                / 10.0,
            }

        except (ModbusException, OSError, IndexError, KeyError) as err:
            _LOGGER.error("Error fetching wallbox data: %s", err)
            raise HeidelbergEnergyControlReadError(
                f"Failed to fetch wallbox data: {err}"
            ) from err

    def _to_32bit_from_map(self, regs: Dict[int, int], addr_high: int) -> int:
        """Helper to combine two 16-bit registers from a map to 32-bit."""
        if addr_high + 1 not in regs:
            raise HeidelbergEnergyControlAPIError(
                f"Address {addr_high} or {addr_high + 1} not found for 32-bit conversion"
            )
        return (regs[addr_high] << 16) | regs[addr_high + 1]

    def _register_to_version(self, decimal_value: int) -> str:
        """Convert register decimal value to semver string."""
        h = hex(decimal_value)[2:].zfill(3)
        patch = int(h[-1], 16)
        minor = int(h[-2], 16)
        major = int(h[:-2], 16)
        return f"{major}.{minor}.{patch}"

"""API for Heidelberg Energy Control wallbox via Modbus."""

from __future__ import annotations

import logging
import time
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from ..const import (
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
    DATA_IS_CHARGING,
    DATA_IS_PLUGGED,
    DATA_PCB_TEMPERATURE,
    DATA_PHASES_ACTIVE,
    DATA_TOTAL_ENERGY,
    DATA_VOLTAGE_L1,
    DATA_VOLTAGE_L2,
    DATA_VOLTAGE_L3,
    REG_COMMAND_COUNT,
    REG_COMMAND_START,
    REG_DATA_COUNT,
    REG_DATA_START,
    REG_HW_COUNT,
    REG_HW_START,
)

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlAPI:
    """API class for Heidelberg Energy Control wallbox."""

    def __init__(self, host: str, port: int, device_id: int) -> None:
        """Initialize the API."""
        self._host = host
        self._port = port
        self._device_id = device_id
        self._client = AsyncModbusTcpClient(host, port=port)

    async def connect(self) -> bool:
        """Connect to the wallbox."""
        if self._client.connected:
            return True
        try:
            return await self._client.connect()
        except ModbusException as err:
            _LOGGER.error("Modbus connection error: %s", err)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the wallbox."""
        if self._client.connected:
            self._client.close()

    async def test_connection(self) -> dict[str, str] | None:
        """Test connection and return versions if successful."""
        try:
            result = await self._client.read_input_registers(
                address=REG_HW_START,
                count=REG_HW_COUNT,
                device_id=self._device_id,
            )

            if result.isError():
                return None

            regs = result.registers
            return {
                "hw_version": f"{regs[0]}",
                "sw_version": f"{regs[3]}",
            }
        except Exception:
            return None

    async def async_write_register(self, address: int, value: int) -> bool:
        """Write a value to a specific register (FC06)."""
        write_start = time.perf_counter()
        try:
            if not self._client.connected:
                if not await self.connect():
                    return False

            result = await self._client.write_register(
                address=address, value=int(value), device_id=self._device_id
            )

            if result.isError():
                _LOGGER.error(
                    "Modbus Error on writing Register %s: %s", address, result
                )
                return False

            write_duration = time.perf_counter() - write_start
            _LOGGER.debug(
                "Write complete: WRITE: %.3fs",
                write_duration,
            )

            return True
        except Exception as err:
            _LOGGER.error("Errnr on writing Register %s: %s", address, err)
            return False

    async def async_get_data(self) -> dict[str, Any]:
        """Read all relevant registers in one call and map to constants."""
        all_start = time.perf_counter()

        try:
            if not self._client.connected:
                if not await self.connect():
                    return {}

            data_start = time.perf_counter()
            data = await self._client.read_input_registers(
                address=REG_DATA_START,
                count=REG_DATA_COUNT,
                device_id=self._device_id,
            )
            data_duration = time.perf_counter() - data_start
            if data.isError():
                _LOGGER.error("Modbus DATA read error: %s", data)
                return {}

            cmd_start = time.perf_counter()
            command = await self._client.read_holding_registers(
                address=REG_COMMAND_START,
                count=REG_COMMAND_COUNT,
                device_id=self._device_id,
            )
            cmd_duration = time.perf_counter() - cmd_start
            if command.isError():
                _LOGGER.error("Modbus COMMAND read error: %s", command)
                return {}

            data_regs = data.registers
            command_regs = command.registers

            if len(data_regs) < REG_DATA_COUNT:
                _LOGGER.warning("Data Register incomplete (got: %s)", len(data_regs))
                return {}

            if len(command_regs) < REG_COMMAND_COUNT:
                _LOGGER.warning(
                    "Command Register incomplete (got: %s)", len(command_regs)
                )
                return {}

            all_duration = time.perf_counter() - all_start
            _LOGGER.debug(
                "Fetch complete: DATA: %.3fs | CMD: %.3fs | Total: %.3fs",
                data_duration,
                cmd_duration,
                all_duration,
            )

            curr_l1 = data_regs[1] / 10.0
            curr_l2 = data_regs[2] / 10.0
            curr_l3 = data_regs[3] / 10.0

            active_phases = sum(1 for i in [curr_l1, curr_l2, curr_l3] if i > 0.1)

            return {
                # DATA
                DATA_CHARGING_STATE: CHARGING_STATE_MAP.get(
                    data_regs[0], f"Unknown ({data_regs[0]})"
                ),
                DATA_PHASES_ACTIVE: active_phases,
                DATA_CURRENT: round(curr_l1 + curr_l2 + curr_l3, 2),
                DATA_CURRENT_L1: curr_l1,
                DATA_CURRENT_L2: curr_l2,
                DATA_CURRENT_L3: curr_l3,
                DATA_PCB_TEMPERATURE: data_regs[4] / 10.0,
                DATA_VOLTAGE_L1: data_regs[5],
                DATA_VOLTAGE_L2: data_regs[6],
                DATA_VOLTAGE_L3: data_regs[7],
                DATA_CHARGING_POWER: data_regs[9],
                DATA_ENERGY_SINCE_POWER_ON: self._to_32bit(data_regs, 10) / 1000.0,
                DATA_TOTAL_ENERGY: self._to_32bit(data_regs, 12) / 1000.0,
                # Binary Sensors
                DATA_EXTERNAL_LOCK_STATE: data_regs[8]
                == 0,  # 0 = Locked / 1 = Unlocked
                DATA_IS_PLUGGED: data_regs[0] >= 4,
                DATA_IS_CHARGING: data_regs[9] > 0,
                # COMMAND
                COMMAND_REMOTE_LOCK: command_regs[2] == 0,  # 0 = Locked / 1 = Unlocked
                COMMAND_TARGET_CURRENT: command_regs[4] / 10.0,
            }

        except Exception as err:
            _LOGGER.error("Error fetching wallbox data: %s", err)
            return {}

    def _to_32bit(self, regs: list[int], idx_high: int) -> int:
        """Helper to combine two 16-bit registers to 32-bit."""
        try:
            return (regs[idx_high] << 16) | regs[idx_high + 1]
        except IndexError:
            return 0

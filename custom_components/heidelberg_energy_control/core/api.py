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
    REG_DATA_COUNT,
    REG_DATA_START,
    REG_HW_CURR_START,
    REG_HW_VERS,
    REG_SW_VERS,
    REG_LAYOUT,
    REG_COMMAND_REMOTE_LOCK,
    REG_COMMAND_TARGET_CURRENT,
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

    async def async_get_static_data(self) -> dict[str, str] | None:
        """Read the static data and return if successful."""
        await self.connect()
        try:
            # Read layout version
            layout_result = await self._client.read_input_registers(
                address=REG_LAYOUT, count=1, device_id=self._device_id
            )
            if layout_result.isError():
                raise HeidelbergEnergyControlReadError("Failed to read LAYOUT register")

            # Read hardware version
            hw_vers_result = await self._client.read_input_registers(
                address=REG_HW_VERS, count=1, device_id=self._device_id
            )
            if hw_vers_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read HW_VERSION register"
                )

            # Read software version
            sw_vers_result = await self._client.read_input_registers(
                address=REG_SW_VERS, count=1, device_id=self._device_id
            )
            if sw_vers_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read SW_VERSION register"
                )

            # Read hardware current limits
            hw_curr_result = await self._client.read_input_registers(
                address=REG_HW_CURR_START, count=2, device_id=self._device_id
            )
            if hw_curr_result.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read HW_CURRENT register"
                )

            return {
                DATA_REG_LAYOUT_VER: self._register_to_version(
                    layout_result.registers[0]
                ),
                DATA_HW_VERSION: self._register_to_version(hw_vers_result.registers[0]),
                DATA_SW_VERSION: self._register_to_version(sw_vers_result.registers[0]),
                DATA_HW_MAX_CURR: hw_curr_result.registers[0],
                DATA_HW_MIN_CURR: hw_curr_result.registers[1],
            }
        except (ModbusException, OSError, IndexError) as err:
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
            # Read input registers (data)
            data_start = time.perf_counter()
            data = await self._client.read_input_registers(
                address=REG_DATA_START, count=REG_DATA_COUNT, device_id=self._device_id
            )
            if data.isError():
                raise HeidelbergEnergyControlReadError("Failed to read data registers")

            data_duration = time.perf_counter() - data_start

            # Read holding registers (commands/settings)
            cmd_start = time.perf_counter()
            remote_lock = await self._client.read_holding_registers(
                address=REG_COMMAND_REMOTE_LOCK,
                count=1,
                device_id=self._device_id,
            )
            if remote_lock.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read remote lock register"
                )
            target_current = await self._client.read_holding_registers(
                address=REG_COMMAND_TARGET_CURRENT,
                count=1,
                device_id=self._device_id,
            )
            if target_current.isError():
                raise HeidelbergEnergyControlReadError(
                    "Failed to read remote lock register"
                )

            cmd_duration = time.perf_counter() - cmd_start

            data_regs = data.registers
            remote_lock_regs = remote_lock.registers
            target_current_regs = target_current.registers

            if not data_regs or len(data_regs) < REG_DATA_COUNT:
                raise HeidelbergEnergyControlReadError("Data register incomplete")


            _LOGGER.debug(
                "Fetch complete: DATA: %.3fs | CMD: %.3fs | Total: %.3fs",
                data_duration,
                cmd_duration,
                time.perf_counter() - all_start,
            )

            curr_l1 = data_regs[1] / 10.0
            curr_l2 = data_regs[2] / 10.0
            curr_l3 = data_regs[3] / 10.0

            active_phases = sum(1 for i in [curr_l1, curr_l2, curr_l3] if i > 0.1)
            charge_current = round(
                (curr_l1 + curr_l2 + curr_l3) / max(1, active_phases), 2
            )

            return {
                # DATA
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
                DATA_ENERGY_SINCE_POWER_ON: self._to_32bit(data_regs, 10) / 1000.0,
                DATA_TOTAL_ENERGY: self._to_32bit(data_regs, 12) / 1000.0,
                # Binary Sensors
                DATA_EXTERNAL_LOCK_STATE: data_regs[8]
                == 0,  # 0 = Locked / 1 = Unlocked
                DATA_IS_PLUGGED: data_regs[0] >= 4,
                DATA_IS_CHARGING: data_regs[9] > 0,
                # COMMAND
                COMMAND_REMOTE_LOCK: remote_lock_regs[0] == 0,  # 0 = Locked / 1 = Unlocked
                COMMAND_TARGET_CURRENT: target_current_regs[0] / 10.0,
            }

        except (ModbusException, OSError, IndexError) as err:
            _LOGGER.error("Error fetching wallbox data: %s", err)
            raise HeidelbergEnergyControlReadError(
                f"Failed to fetch wallbox data: {err}"
            ) from err

    def _to_32bit(self, regs: list[int], idx_high: int) -> int:
        """Helper to combine two 16-bit registers to 32-bit."""
        if idx_high + 1 >= len(regs):
            raise HeidelbergEnergyControlAPIError(
                f"Index {idx_high} out of bounds for 32-bit conversion"
            )
        return (regs[idx_high] << 16) | regs[idx_high + 1]

    def _register_to_version(self, decimal_value: int) -> str:
        """Convert register decimal value to semver string."""
        h = hex(decimal_value)[2:].zfill(3)
        patch = int(h[-1], 16)
        minor = int(h[-2], 16)
        major = int(h[:-2], 16)
        return f"{major}.{minor}.{patch}"

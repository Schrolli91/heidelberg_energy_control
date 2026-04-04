"""Constants for the Heidelberg Energy Control integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from homeassistant.const import Platform

# ##### General #####
DOMAIN = "heidelberg_energy_control"
DEVICE_MANUFACTURER = "Heidelberg"
DEVICE_MODEL = "Energy Control"

# ##### Configuration #####
# Configuration keys
CONF_DEVICE_ID = "device_id"
# Update interval for coordinator
DEFAULT_SCAN_INTERVAL = 10

# Platforms
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# ##### Modbus Register Definitions #####
class RegisterType(Enum):
    INPUT = "input"
    HOLDING = "holding"

@dataclass(frozen=True)
class RegisterDefinition:
    """Definition of a register block."""
    address: int
    count: int
    type: RegisterType

# Static Data Registers (read once at startup)
REG_DEF_LAYOUT = RegisterDefinition(address=4, count=1, type=RegisterType.INPUT)
REG_DEF_HW_VERS = RegisterDefinition(address=200, count=1, type=RegisterType.INPUT)
REG_DEF_SW_VERS = RegisterDefinition(address=203, count=1, type=RegisterType.INPUT)
REG_DEF_HW_CURR = RegisterDefinition(address=100, count=2, type=RegisterType.INPUT)

# Dynamic Data Registers (read frequently)
# Detailed Data Registers (unpacked from block 5-18)
REG_DEF_CHARGING_STATE = RegisterDefinition(address=5, count=1, type=RegisterType.INPUT)
REG_DEF_CURRENT_L1 = RegisterDefinition(address=6, count=1, type=RegisterType.INPUT)
REG_DEF_CURRENT_L2 = RegisterDefinition(address=7, count=1, type=RegisterType.INPUT)
REG_DEF_CURRENT_L3 = RegisterDefinition(address=8, count=1, type=RegisterType.INPUT)
REG_DEF_PCB_TEMPERATURE = RegisterDefinition(address=9, count=1, type=RegisterType.INPUT)
REG_DEF_VOLTAGE_L1 = RegisterDefinition(address=10, count=1, type=RegisterType.INPUT)
REG_DEF_VOLTAGE_L2 = RegisterDefinition(address=11, count=1, type=RegisterType.INPUT)
REG_DEF_VOLTAGE_L3 = RegisterDefinition(address=12, count=1, type=RegisterType.INPUT)
REG_DEF_EXTERNAL_LOCK_STATE = RegisterDefinition(address=13, count=1, type=RegisterType.INPUT)
REG_DEF_CHARGING_POWER = RegisterDefinition(address=14, count=1, type=RegisterType.INPUT)
# 32-bit values require 2 registers
REG_DEF_ENERGY_SINCE_POWER_ON = RegisterDefinition(address=15, count=2, type=RegisterType.INPUT)
REG_DEF_TOTAL_ENERGY = RegisterDefinition(address=17, count=2, type=RegisterType.INPUT)

# Command registers
REG_DEF_REMOTE_LOCK = RegisterDefinition(address=259, count=1, type=RegisterType.HOLDING)
REG_DEF_TARGET_CURRENT = RegisterDefinition(address=261, count=1, type=RegisterType.HOLDING)



# ##### Data Keys #####
# Init Data
DATA_REG_LAYOUT_VER = "reg_layout_ver"
DATA_HW_VERSION = "hw_version"
DATA_SW_VERSION = "sw_version"
DATA_HW_MIN_CURR = "hw_min_current"
DATA_HW_MAX_CURR = "hw_max_current"
# Sensors
DATA_CHARGING_STATE = "charging_state"
DATA_CHARGING_POWER = "charging_power"
DATA_PHASES_ACTIVE = "phases_active"
DATA_CURRENT = "current"
DATA_CURRENT_L1 = "current_l1"
DATA_CURRENT_L2 = "current_l2"
DATA_CURRENT_L3 = "current_l3"
DATA_PCB_TEMPERATURE = "pcb_temperature"
DATA_VOLTAGE_L1 = "voltage_l1"
DATA_VOLTAGE_L2 = "voltage_l2"
DATA_VOLTAGE_L3 = "voltage_l3"
DATA_EXTERNAL_LOCK_STATE = "external_lock_state"
DATA_ENERGY_SINCE_POWER_ON = "energy_since_power_on"
DATA_TOTAL_ENERGY = "total_energy"
DATA_SESSION_ENERGY = "session_energy"
# Binary Sensors
DATA_IS_PLUGGED = "is_plugged"
DATA_IS_CHARGING = "is_charging"
# Hardware Command
COMMAND_REMOTE_LOCK = "remote_lock_command"
COMMAND_TARGET_CURRENT = "max_current_command"
# Virtual
VIRTUAL_ENABLE = "virtual_enable"
VIRTUAL_TARGET_CURRENT = "virtual_current"

# ##### Map for charging state #####
# Values from the heidelberg modbus docs
CHARGING_STATE_MAP = {
    2: "A",
    3: "A",
    4: "B",
    5: "B",
    6: "C",
    7: "C",
    8: "D",
    9: "E",
    10: "F",
    11: "E",
}

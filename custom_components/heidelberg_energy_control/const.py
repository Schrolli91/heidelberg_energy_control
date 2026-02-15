"""Constants for the Heidelberg Energy Control integration."""

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

# ##### Data Keys #####
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
REG_COMMAND_REMOTE_LOCK = 259
COMMAND_TARGET_CURRENT = "max_current_command"
REG_COMMAND_TARGET_CURRENT = 261
# Virtual
VIRTUAL_ENABLE = "virtual_enable"
VIRTUAL_TARGET_CURRENT = "virtual_current"

# ##### Modbus registers #####
REG_LAYOUT = 4 # Modbus Register-Layouts Version
REG_DATA_START = 5
REG_DATA_COUNT = 14
REG_COMMAND_START = 257
REG_COMMAND_COUNT = 6
REG_HW_START = 200
REG_HW_COUNT = 4

# ##### Map for charging state #####
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

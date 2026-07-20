"""Demonstrative tests for the dict-based capability decode contract.

Under the definition-based Capability shape (added in this PR), a
capability declares which registers it needs via class-level tuples
of `RegisterDefinition`, and its `decode_polled` / `decode_static`
methods are synchronous functions of a `{address: value}` dict.

These tests exercise the pattern against `CoreCapability` so future
contributors have a working example to copy. Additional per-
capability tests will follow the same pattern when connect-series
capabilities are added.
"""

from __future__ import annotations

from custom_components.heidelberg_energy_control.const import (
    COMMAND_REMOTE_LOCK,
    COMMAND_TARGET_CURRENT,
    DATA_CHARGING_STATE,
    DATA_CURRENT_L1,
    DATA_HW_MAX_CURR,
    DATA_HW_MIN_CURR,
    DATA_HW_VERSION,
    DATA_IS_CHARGING,
    DATA_PHASES_ACTIVE,
    DATA_REG_LAYOUT_VER,
    DATA_SW_VERSION,
    DATA_TOTAL_ENERGY,
)
from custom_components.heidelberg_energy_control.core.capabilities.core import (
    REG_COMMAND_REMOTE_LOCK,
    REG_COMMAND_TARGET_CURRENT,
    REG_DATA_START,
    REG_HW_CURR_START,
    REG_HW_VERS,
    REG_LAYOUT,
    REG_SW_VERS,
    CoreCapability,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


# ---------- decode_static: purely functional ----------


def test_decode_static_reads_only_from_dict_lookups():
    """Given a hand-built register dict, decode_static returns a static dict."""
    regs = {
        REG_LAYOUT: 0x107,
        REG_HW_VERS: 0x100,
        REG_SW_VERS: 0x107,
        REG_HW_CURR_START: 16,
        REG_HW_CURR_START + 1: 6,
    }

    cap = CoreCapability()
    result = cap.decode_static(regs)

    assert result == {
        DATA_REG_LAYOUT_VER: "1.0.7",
        DATA_HW_VERSION: "1.0.0",
        DATA_SW_VERSION: "1.0.7",
        DATA_HW_MAX_CURR: 16,
        DATA_HW_MIN_CURR: 6,
    }


def test_decode_static_ignores_unrelated_addresses():
    """Extra keys in the registers dict don't affect the output."""
    regs = {
        REG_LAYOUT: 0x204,
        REG_HW_VERS: 0x003,
        REG_SW_VERS: 0x003,
        REG_HW_CURR_START: 16,
        REG_HW_CURR_START + 1: 6,
        # Unrelated addresses that a future capability might contribute.
        999: 42,
        1000: 7,
    }
    cap = CoreCapability()
    result = cap.decode_static(regs)

    assert result[DATA_REG_LAYOUT_VER] == "2.0.4"
    assert 999 not in result  # decoded output is keyed by DATA_* strings, not addresses


# ---------- decode_polled: purely functional ----------


def test_decode_polled_returns_full_output_from_dict():
    """Hand-built dict → full polled output, no async, no Modbus client."""
    # 3-phase actively charging: 16A × 230V × 3 ≈ 11040 W. Total energy
    # 32-bit high=188 low=24832 → 12345600 Wh → 12345.6 kWh.
    regs = {
        REG_DATA_START + 0: 7,       # charging state (mapped to "C")
        REG_DATA_START + 1: 160,     # L1 = 16.0 A
        REG_DATA_START + 2: 160,     # L2 = 16.0 A
        REG_DATA_START + 3: 160,     # L3 = 16.0 A
        REG_DATA_START + 4: 345,     # PCB temp 34.5 °C
        REG_DATA_START + 5: 230,     # voltage L1
        REG_DATA_START + 6: 231,     # voltage L2
        REG_DATA_START + 7: 229,     # voltage L3
        REG_DATA_START + 8: 1,       # external lock (1 = unlocked → False)
        REG_DATA_START + 9: 11040,   # charging power
        REG_DATA_START + 10: 0,      # energy_since_power_on high
        REG_DATA_START + 11: 5000,   # energy_since_power_on low
        REG_DATA_START + 12: 188,    # total energy high
        REG_DATA_START + 13: 24832,  # total energy low
        REG_COMMAND_REMOTE_LOCK: 1,  # unlocked → False
        REG_COMMAND_TARGET_CURRENT: 160,  # 16.0 A
    }

    cap = CoreCapability()
    result = cap.decode_polled(regs)

    assert result[DATA_CHARGING_STATE] == "C"
    assert result[DATA_PHASES_ACTIVE] == 3
    assert result[DATA_CURRENT_L1] == 16.0
    assert result[DATA_TOTAL_ENERGY] == 12345.6
    assert result[DATA_IS_CHARGING] is True
    # Bidirectional value: capability returns raw deci-amps (160 = 16.0 A).
    assert result[COMMAND_TARGET_CURRENT] == 160
    assert result[COMMAND_REMOTE_LOCK] is False


# ---------- register declaration ----------


def test_core_declares_expected_definitions():
    """Class-level definitions tell the API what to read."""
    assert CoreCapability.static_definitions == (
        RegisterDefinition(REG_LAYOUT, 1, RegisterType.INPUT),
        RegisterDefinition(REG_HW_CURR_START, 2, RegisterType.INPUT),
        RegisterDefinition(REG_HW_VERS, 1, RegisterType.INPUT),
        RegisterDefinition(REG_SW_VERS, 1, RegisterType.INPUT),
    )
    # Polled defs: one input block for data, plus two holding registers
    # for the command state.
    assert CoreCapability.polled_definitions == (
        RegisterDefinition(REG_DATA_START, 14, RegisterType.INPUT),
        RegisterDefinition(REG_COMMAND_REMOTE_LOCK, 1, RegisterType.HOLDING),
        RegisterDefinition(REG_COMMAND_TARGET_CURRENT, 1, RegisterType.HOLDING),
    )

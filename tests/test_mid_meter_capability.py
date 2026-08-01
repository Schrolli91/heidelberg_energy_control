"""Tests for MidMeterCapability (registers 3000..3012, v2.0.0+, hardware-optional).

Three things to pin:
  1. Version gate at 2.0.0.
  2. Polled block declares 3001..3012 in one read (3000 is probe-only).
  3. decode_polled maps every field to the right DATA_* key with the
     right unit conversion (deci-amps → A, wire-Wh → kWh, W raw).
  4. Probe returns True only when register 3000 reads back the value 1
     — a value of 0, an illegal-address response, a ModbusException, or
     an OSError all mean "not fitted, skip capability".
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pymodbus.exceptions import ModbusException

from custom_components.heidelberg_energy_control.const import (
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
from custom_components.heidelberg_energy_control.core.capabilities.mid_meter import (
    REG_MID_AVAILABLE,
    REG_MID_FORWARD_COUNT,
    REG_MID_FORWARD_START,
    REG_MID_REVERSE_COUNT,
    REG_MID_REVERSE_START,
    MidMeterCapability,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


# ---------- version gate & polled definitions ----------


def test_mid_gated_at_2_0_0():
    assert MidMeterCapability.min_layout_version == "2.0.0"


def test_mid_declares_two_input_blocks_split_around_3010():
    """The 3001..3012 range is split into 3001..3009 + 3011..3012.

    Register 3010 (reverse power, "not yet implemented" per spec) is
    excluded on purpose: keeping it in one merged read would let an
    illegal-address rejection of 3010 kill the whole batch, taking
    down the billing register 3008..3009 with it.
    """
    assert MidMeterCapability.polled_definitions == (
        RegisterDefinition(
            REG_MID_FORWARD_START, REG_MID_FORWARD_COUNT, RegisterType.INPUT
        ),
        RegisterDefinition(
            REG_MID_REVERSE_START, REG_MID_REVERSE_COUNT, RegisterType.INPUT
        ),
    )
    assert REG_MID_FORWARD_START == 3001
    assert REG_MID_FORWARD_COUNT == 9
    assert REG_MID_REVERSE_START == 3011
    assert REG_MID_REVERSE_COUNT == 2


# ---------- decode_polled ----------


def _sample_registers() -> dict[int, int]:
    """MID block with distinct values per field to make aliasing bugs obvious.

    Reg 3010 (reverse power) is intentionally absent — the capability's
    split-block layout skips it, so the decode path must never index it.
    """
    return {
        3001: 123,   # L1: 12.3 A
        3002: 45,    # L2: 4.5 A
        3003: 67,    # L3: 6.7 A
        3004: 230,   # V1
        3005: 231,   # V2
        3006: 232,   # V3
        3007: 4200,  # Power forward, W
        3008: 0,     # Energy forward high word
        3009: 5678,  # Energy forward low word → 5.678 kWh
        3011: 0,     # Energy reverse high word
        3012: 12345, # Energy reverse low word → 12.345 kWh
    }


def test_decode_polled_scales_currents_by_10():
    result = MidMeterCapability().decode_polled(_sample_registers())
    assert result[DATA_MID_CURRENT_L1] == 12.3
    assert result[DATA_MID_CURRENT_L2] == 4.5
    assert result[DATA_MID_CURRENT_L3] == 6.7


def test_decode_polled_voltages_are_raw_volts():
    result = MidMeterCapability().decode_polled(_sample_registers())
    assert result[DATA_MID_VOLTAGE_L1] == 230
    assert result[DATA_MID_VOLTAGE_L2] == 231
    assert result[DATA_MID_VOLTAGE_L3] == 232


def test_decode_polled_power_is_raw_watts():
    result = MidMeterCapability().decode_polled(_sample_registers())
    assert result[DATA_MID_POWER_FORWARD] == 4200


def test_decode_polled_energies_are_kwh_from_32bit_pair():
    result = MidMeterCapability().decode_polled(_sample_registers())
    assert result[DATA_MID_ENERGY_FORWARD] == 5.678
    assert result[DATA_MID_ENERGY_REVERSE] == 12.345


def test_decode_polled_energy_forward_uses_high_word_first():
    """32-bit composition rule: reg n = high word, reg n+1 = low word."""
    regs = _sample_registers()
    regs[3008] = 1  # high word contributes 65536 Wh
    regs[3009] = 0
    result = MidMeterCapability().decode_polled(regs)
    assert result[DATA_MID_ENERGY_FORWARD] == 65.536


def test_decode_polled_ignores_unrelated_addresses():
    regs = _sample_registers()
    regs[999] = 42
    regs[3010] = 9999  # reverse-power slot — not in any declared block, not decoded
    result = MidMeterCapability().decode_polled(regs)
    assert set(result.keys()) == {
        DATA_MID_CURRENT_L1,
        DATA_MID_CURRENT_L2,
        DATA_MID_CURRENT_L3,
        DATA_MID_VOLTAGE_L1,
        DATA_MID_VOLTAGE_L2,
        DATA_MID_VOLTAGE_L3,
        DATA_MID_POWER_FORWARD,
        DATA_MID_ENERGY_FORWARD,
        DATA_MID_ENERGY_REVERSE,
    }


# ---------- probe ----------


async def test_probe_true_when_register_3000_reads_one():
    cap = MidMeterCapability()
    client = MagicMock()
    ok = MagicMock()
    ok.isError = MagicMock(return_value=False)
    ok.registers = [1]
    client.read_input_registers = AsyncMock(return_value=ok)

    assert await cap.async_probe(client, device_id=1) is True
    client.read_input_registers.assert_awaited_once_with(
        address=REG_MID_AVAILABLE, count=1, device_id=1
    )


async def test_probe_false_when_flag_is_zero():
    """Reg 3000 is mapped and readable but reports 'no MID fitted'."""
    cap = MidMeterCapability()
    client = MagicMock()
    ok = MagicMock()
    ok.isError = MagicMock(return_value=False)
    ok.registers = [0]
    client.read_input_registers = AsyncMock(return_value=ok)

    assert await cap.async_probe(client, device_id=1) is False


async def test_probe_false_on_illegal_address_response():
    cap = MidMeterCapability()
    client = MagicMock()
    err = MagicMock()
    err.isError = MagicMock(return_value=True)
    err.registers = []
    client.read_input_registers = AsyncMock(return_value=err)

    assert await cap.async_probe(client, device_id=1) is False


async def test_probe_false_on_modbus_exception():
    cap = MidMeterCapability()
    client = MagicMock()
    client.read_input_registers = AsyncMock(side_effect=ModbusException("boom"))

    assert await cap.async_probe(client, device_id=1) is False


async def test_probe_false_on_oserror():
    cap = MidMeterCapability()
    client = MagicMock()
    client.read_input_registers = AsyncMock(side_effect=OSError("network down"))

    assert await cap.async_probe(client, device_id=1) is False


# ---------- capability owns no writes ----------


def test_mid_owns_no_writes():
    cap = MidMeterCapability()
    assert cap.supports_write("anything") is False

"""Characterization tests for the Modbus decoding layer.

These tests pin today's wire-format contract: given a known set of raw
register values, async_get_data() and async_get_static_data() must return
exactly the dicts they return today. Any future refactor (capability
modules, per-feature splits, etc.) must keep these tests green.

Parametrized over multiple firmware/layout variants so a single regression
shows up against every captured fixture, not just one.
"""

from __future__ import annotations

import pytest

from custom_components.heidelberg_energy_control.const import (
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
from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlAPIError,
)

from .conftest import build_mock_modbus_client, load_fixture


# ---------- variant definitions ----------

# Each variant carries: (fixture stem, expected static dict, expected polled dict).
# Add new firmware captures by appending a pytest.param tuple here.

VARIANT_V1_0_7 = pytest.param(
    "wallbox_v1_0_7",
    {
        DATA_REG_LAYOUT_VER: "1.0.7",
        DATA_HW_VERSION: "1.0.0",
        DATA_SW_VERSION: "1.0.7",
        DATA_HW_MAX_CURR: 16,
        DATA_HW_MIN_CURR: 6,
    },
    {
        DATA_CHARGING_STATE: "C",
        DATA_PHASES_ACTIVE: 3,
        DATA_CURRENT: 16.0,
        DATA_CURRENT_L1: 16.0,
        DATA_CURRENT_L2: 16.0,
        DATA_CURRENT_L3: 16.0,
        DATA_PCB_TEMPERATURE: 34.5,
        DATA_VOLTAGE_L1: 230,
        DATA_VOLTAGE_L2: 231,
        DATA_VOLTAGE_L3: 229,
        DATA_CHARGING_POWER: 11040,
        DATA_ENERGY_SINCE_POWER_ON: 5.0,
        DATA_TOTAL_ENERGY: 12345.6,
        DATA_EXTERNAL_LOCK_STATE: False,
        DATA_IS_PLUGGED: True,
        DATA_IS_CHARGING: True,
        COMMAND_REMOTE_LOCK: False,
        # Deci-amps at the wire level; number entity divides by 10 for display.
        COMMAND_TARGET_CURRENT: 160,
    },
    id="v1.0.7-synthetic",
)

VARIANT_V2_0_4 = pytest.param(
    "wallbox_v2_0_4",
    {
        DATA_REG_LAYOUT_VER: "2.0.4",
        DATA_HW_VERSION: "0.0.3",
        DATA_SW_VERSION: "0.0.3",
        DATA_HW_MAX_CURR: 16,
        DATA_HW_MIN_CURR: 6,
    },
    {
        DATA_CHARGING_STATE: "C",
        DATA_PHASES_ACTIVE: 0,
        DATA_CURRENT: 0.0,
        DATA_CURRENT_L1: 0.0,
        DATA_CURRENT_L2: 0.0,
        DATA_CURRENT_L3: 0.0,
        DATA_PCB_TEMPERATURE: 36.2,
        DATA_VOLTAGE_L1: 237,
        DATA_VOLTAGE_L2: 1,
        DATA_VOLTAGE_L3: 1,
        DATA_CHARGING_POWER: 1,
        DATA_ENERGY_SINCE_POWER_ON: 0.0,
        DATA_TOTAL_ENERGY: 3.615,
        DATA_EXTERNAL_LOCK_STATE: False,
        DATA_IS_PLUGGED: True,
        DATA_IS_CHARGING: True,  # power_reg > 0 → True even at 1 W (sensor noise)
        COMMAND_REMOTE_LOCK: False,
        COMMAND_TARGET_CURRENT: 60,
    },
    id="v2.0.4-real",
)

VARIANTS = [VARIANT_V1_0_7, VARIANT_V2_0_4]


# ---------- helper ----------


def _make_api(fixture_name: str) -> HeidelbergEnergyControlAPI:
    """Build an API instance backed by a fixture's mock modbus client."""
    instance = HeidelbergEnergyControlAPI(host="1.2.3.4", port=502, device_id=1)
    instance._client = build_mock_modbus_client(load_fixture(fixture_name))
    return instance


# ---------- pure functions ----------


async def test_register_to_version_decodes_nibbles():
    """Each hex nibble of the register is one semver component."""
    api = HeidelbergEnergyControlAPI(host="x", port=1, device_id=1)
    assert api._register_to_version(0x107) == "1.0.7"
    assert api._register_to_version(0x100) == "1.0.0"
    assert api._register_to_version(0x108) == "1.0.8"
    assert api._register_to_version(0x204) == "2.0.4"


async def test_to_32bit_combines_high_low_word():
    """High word is the first register, low word the second."""
    api = HeidelbergEnergyControlAPI(host="x", port=1, device_id=1)
    assert api._to_32bit([0x0001, 0x2345], 0) == 0x12345
    assert api._to_32bit([0x0000, 0x0000], 0) == 0
    assert api._to_32bit([0xFFFF, 0xFFFF], 0) == 0xFFFFFFFF


async def test_to_32bit_raises_when_index_out_of_bounds():
    """Off-by-one at the end of the register list must raise, not silently read OOB."""
    api = HeidelbergEnergyControlAPI(host="x", port=1, device_id=1)
    with pytest.raises(HeidelbergEnergyControlAPIError):
        api._to_32bit([0x0001], 0)


# ---------- parametrized: static + polled dict equality across all variants ----------


@pytest.mark.parametrize(("fixture_name", "expected_static", "expected_polled"), VARIANTS)
async def test_static_data_decoding(fixture_name, expected_static, expected_polled):
    """Static data: layout version, hw/sw version strings, hw current limits."""
    api = _make_api(fixture_name)
    assert await api.async_get_static_data() == expected_static


@pytest.mark.parametrize(("fixture_name", "expected_static", "expected_polled"), VARIANTS)
async def test_polled_data_decoding_full_dict(fixture_name, expected_static, expected_polled):
    """Polled data: complete dict equality against each captured fixture."""
    api = _make_api(fixture_name)
    assert await api.async_get_data() == expected_polled


# ---------- variant-specific property checks ----------
# These pin specific decoding rules and use the v1.0.7 fixture (non-zero values
# across the board) so the assertions are meaningful. The v2.0.4 fixture is
# idle / single-phase and would make most of these vacuous.


async def test_polled_data_currents_decoded_as_deciamps():
    """L1 phase current is a sensor-only value → capability divides for display (amps).

    COMMAND_TARGET_CURRENT is bidirectional (has a number entity) → capability
    leaves it as raw deci-amps; the entity applies its multiplier symmetrically.
    """
    api = _make_api("wallbox_v1_0_7")
    result = await api.async_get_data()
    assert result[DATA_CURRENT_L1] == 16.0
    assert result[COMMAND_TARGET_CURRENT] == 160


async def test_polled_data_charging_state_mapped_to_letter():
    """Charging state register is mapped through CHARGING_STATE_MAP."""
    api = _make_api("wallbox_v1_0_7")
    result = await api.async_get_data()
    assert result[DATA_CHARGING_STATE] == "C"


async def test_polled_data_lock_state_inverted():
    """External and remote lock registers: 0=Locked, 1=Unlocked."""
    api = _make_api("wallbox_v1_0_7")
    result = await api.async_get_data()
    assert result[DATA_EXTERNAL_LOCK_STATE] is False
    assert result[COMMAND_REMOTE_LOCK] is False

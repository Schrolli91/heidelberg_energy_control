"""Tests for PowerTargetCapability (registers 500 / 5000, v2.0.2+).

The maximal power target is the *automatic* phase switch: write a power
ceiling in watts to holding register 500 and the wallbox picks 1-phase or
3-phase operation itself. Input register 5000 reads the value back.

Two behaviours carry most of the design weight here:

  * **The probe targets register 500, not 5000.** Their availability
    differs — 5000 exists on every connect variant from V2.0.2, while 500
    is connect.solar / connect.solar pro only. Probing 5000 would load the
    capability on a connect.home and hand the user a power-target entity
    whose writes have nowhere to land.

  * **Register 500 is deliberately *not* interlocked with register 261.**
    The spec calls them mutually exclusive; this integration exposes both
    and documents the choice instead of enforcing it. Nothing in the write
    path may start blocking or rewriting 261.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.exceptions import ModbusException

from custom_components.heidelberg_energy_control.const import (
    COMMAND_MAX_POWER_TARGET,
    COMMAND_TARGET_CURRENT,
    DATA_MAX_POWER_SET,
)
from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.capabilities.power_target import (
    POWER_TARGET_MAX,
    REG_MAX_POWER_SET,
    REG_MAX_POWER_TARGET,
    PowerTargetCapability,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlWriteError,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


# ---------- version gate & polled definitions ----------


def test_power_target_gated_at_2_0_2():
    """Register 500 lands with layout V2.0.2 — not 2.0.1 (that is reg 501)."""
    assert PowerTargetCapability.min_layout_version == "2.0.2"


def test_declares_holding_500_and_input_5000():
    assert PowerTargetCapability.polled_definitions == (
        RegisterDefinition(REG_MAX_POWER_TARGET, 1, RegisterType.HOLDING),
        RegisterDefinition(REG_MAX_POWER_SET, 1, RegisterType.INPUT),
    )


def test_register_addresses_match_spec():
    assert REG_MAX_POWER_TARGET == 500
    assert REG_MAX_POWER_SET == 5000


# ---------- probe ----------


async def test_probe_reads_register_500_not_5000():
    """The whole connect.home-vs-connect.solar distinction rests on this."""
    cap = PowerTargetCapability()
    client = MagicMock()
    ok = MagicMock()
    ok.isError = MagicMock(return_value=False)
    client.read_holding_registers = AsyncMock(return_value=ok)
    client.read_input_registers = AsyncMock()

    assert await cap.async_probe(client, device_id=1) is True
    client.read_holding_registers.assert_awaited_once_with(
        address=REG_MAX_POWER_TARGET, count=1, device_id=1
    )
    client.read_input_registers.assert_not_awaited()


async def test_probe_false_on_illegal_address_response():
    cap = PowerTargetCapability()
    client = MagicMock()
    err = MagicMock()
    err.isError = MagicMock(return_value=True)
    client.read_holding_registers = AsyncMock(return_value=err)

    assert await cap.async_probe(client, device_id=1) is False


async def test_probe_false_on_modbus_exception():
    cap = PowerTargetCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=ModbusException("boom"))

    assert await cap.async_probe(client, device_id=1) is False


async def test_probe_false_on_oserror():
    cap = PowerTargetCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=OSError("network down"))

    assert await cap.async_probe(client, device_id=1) is False


# ---------- decode_polled ----------


def test_decode_polled_maps_both_registers():
    cap = PowerTargetCapability()
    result = cap.decode_polled({REG_MAX_POWER_TARGET: 4100, REG_MAX_POWER_SET: 4100})
    assert result == {
        COMMAND_MAX_POWER_TARGET: 4100,
        DATA_MAX_POWER_SET: 4100,
    }


def test_decode_polled_passes_zero_through_as_disabled():
    """0 W is the wallbox default and means "power target off" — not None."""
    cap = PowerTargetCapability()
    result = cap.decode_polled({REG_MAX_POWER_TARGET: 0, REG_MAX_POWER_SET: 0})
    assert result[COMMAND_MAX_POWER_TARGET] == 0
    assert result[DATA_MAX_POWER_SET] == 0


def test_decode_polled_reports_command_and_readback_independently():
    """5000 can lag 500 right after a write; both are surfaced verbatim."""
    cap = PowerTargetCapability()
    result = cap.decode_polled({REG_MAX_POWER_TARGET: 6000, REG_MAX_POWER_SET: 4100})
    assert result[COMMAND_MAX_POWER_TARGET] == 6000
    assert result[DATA_MAX_POWER_SET] == 4100


def test_decode_polled_ignores_unrelated_addresses():
    cap = PowerTargetCapability()
    result = cap.decode_polled(
        {REG_MAX_POWER_TARGET: 1400, REG_MAX_POWER_SET: 1400, 999: 42}
    )
    assert result == {
        COMMAND_MAX_POWER_TARGET: 1400,
        DATA_MAX_POWER_SET: 1400,
    }


# ---------- write dispatch ----------


def test_supports_write_matches_only_power_target_key():
    cap = PowerTargetCapability()
    assert cap.supports_write(COMMAND_MAX_POWER_TARGET) is True
    assert cap.supports_write("nope") is False


def test_does_not_claim_target_current_writes():
    """Register 261 stays with the core capability — no interlock here."""
    cap = PowerTargetCapability()
    assert cap.supports_write(COMMAND_TARGET_CURRENT) is False


@pytest.mark.parametrize("watts", [0, 1400, 4100, 6000, POWER_TARGET_MAX])
async def test_async_write_forwards_in_range_values_to_register_500(watts):
    cap = PowerTargetCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=False)
    client.write_register = AsyncMock(return_value=write_result)

    ok = await cap.async_write(
        client, device_id=1, key=COMMAND_MAX_POWER_TARGET, value=watts
    )

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_MAX_POWER_TARGET, value=watts, device_id=1
    )


@pytest.mark.parametrize("watts", [-1, POWER_TARGET_MAX + 1, 100000])
async def test_async_write_rejects_out_of_range_without_touching_the_bus(watts):
    cap = PowerTargetCapability()
    client = MagicMock()
    client.write_register = AsyncMock()

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await cap.async_write(
            client, device_id=1, key=COMMAND_MAX_POWER_TARGET, value=watts
        )

    client.write_register.assert_not_awaited()


async def test_async_write_raises_on_modbus_error_response():
    cap = PowerTargetCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=True)
    client.write_register = AsyncMock(return_value=write_result)

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await cap.async_write(
            client, device_id=1, key=COMMAND_MAX_POWER_TARGET, value=4100
        )


async def test_async_write_wraps_modbus_exception():
    cap = PowerTargetCapability()
    client = MagicMock()
    client.write_register = AsyncMock(side_effect=ModbusException("boom"))

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await cap.async_write(
            client, device_id=1, key=COMMAND_MAX_POWER_TARGET, value=4100
        )


# ---------- end-to-end dispatch through the API ----------


def _api_with_power_target_loaded() -> tuple[HeidelbergEnergyControlAPI, MagicMock]:
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._capabilities.append(PowerTargetCapability())

    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.close = MagicMock()

    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=False)
    client.write_register = AsyncMock(return_value=write_result)

    api._client = client
    return api, client


async def test_api_write_command_dispatches_power_target_to_register_500():
    api, client = _api_with_power_target_loaded()

    ok = await api.async_write_command(COMMAND_MAX_POWER_TARGET, 4100)

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_MAX_POWER_TARGET, value=4100, device_id=1
    )


# ---------- variant gating: connect.home has 5000 but not 500 ----------


def _variant_client(*, has_register_500: bool) -> MagicMock:
    """Mock a V2.0.2 wallbox, with or without the solar-only register 500.

    Both variants expose input register 5000; only connect.solar exposes
    holding register 500. Everything else answers illegal-address so the
    other optional capabilities simply don't load.
    """
    client = MagicMock()
    client.connected = False

    async def _connect() -> bool:
        client.connected = True
        return True

    client.connect = AsyncMock(side_effect=_connect)
    client.close = MagicMock()

    def _response(registers, is_error=False):
        rr = MagicMock()
        rr.isError = MagicMock(return_value=is_error)
        rr.registers = registers if registers else []
        return rr

    input_reads = {
        (4, 1): [0x202],  # layout 2.0.2
        (100, 2): [16, 6],
        (200, 1): [3],
        (203, 1): [3],
        (5, 14): [7, 0, 0, 0, 362, 237, 1, 1, 1, 1, 0, 0, 0, 3615],
        (5000, 1): [0],
    }

    async def _read_input(address, count, device_id):
        registers = input_reads.get((address, count))
        if registers is None:
            return _response(None, is_error=True)
        return _response(registers)

    async def _read_holding(address, count, device_id):
        if address == REG_MAX_POWER_TARGET and count == 1:
            if not has_register_500:
                return _response(None, is_error=True)
            return _response([0])
        if address == 259 and count == 1:
            return _response([1])
        if address == 261 and count == 1:
            return _response([60])
        return _response(None, is_error=True)

    client.read_input_registers = AsyncMock(side_effect=_read_input)
    client.read_holding_registers = AsyncMock(side_effect=_read_holding)
    return client


async def test_capability_loads_on_solar_variant_exposing_register_500():
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._client = _variant_client(has_register_500=True)

    await api.async_get_static_data()

    assert "power_target" in {cap.key for cap in api.capabilities}


async def test_capability_skipped_when_only_readback_5000_exists():
    """connect.home at V2.0.2: 5000 is readable, 500 is not — must not load."""
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._client = _variant_client(has_register_500=False)

    await api.async_get_static_data()

    assert "power_target" not in {cap.key for cap in api.capabilities}


async def test_polled_reads_omit_500_and_5000_when_capability_skipped():
    """A skipped capability must keep its registers out of the polled blocks."""
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    client = _variant_client(has_register_500=False)
    api._client = client

    await api.async_get_static_data()
    client.read_holding_registers.reset_mock()
    client.read_input_registers.reset_mock()

    await api.async_get_data()

    for call in client.read_holding_registers.await_args_list:
        address, count = call.kwargs["address"], call.kwargs["count"]
        assert REG_MAX_POWER_TARGET not in range(address, address + count)
    for call in client.read_input_registers.await_args_list:
        address, count = call.kwargs["address"], call.kwargs["count"]
        assert REG_MAX_POWER_SET not in range(address, address + count)


# ---------- derived UI ceiling ----------


def test_max_power_target_watts_tracks_hardware_current_limit():
    from custom_components.heidelberg_energy_control.number import (
        max_power_target_watts,
    )

    assert max_power_target_watts(16.0) == 11040.0  # 16 A x 230 V x 3
    assert max_power_target_watts(32.0) == 22080.0

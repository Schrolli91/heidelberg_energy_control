"""Regression tests for probing optional holding registers at setup.

Issue #16 (upstream): the Amperfied connect-series reports layout
version >= 1.0.8 but does not expose holding registers 257 (watchdog
timeout) or 258 (standby control). Previously both capabilities loaded
on any 1.0.8+ device, and the API's block-read coalescing merged the
per-poll reads of 257 + 258 + 259 into a single Modbus transaction.
Register 257 being absent then failed the whole batch atomically,
producing "Failed to read 3 holding register(s) at 257" every poll.

The fix: WatchdogCapability and StandbyCapability implement
``async_probe`` — a single-register read at setup that decides
whether the capability actually loads. On connect-series hardware
the probe fails, the capability is skipped, and its polled_definitions
never enter the coalescing pool.

These tests pin that behavior:
  1. Probe returns True when the register read succeeds
  2. Probe returns False on isError() (illegal address response)
  3. Probe returns False on ModbusException
  4. Probe returns False on OSError
  5. End-to-end: async_get_static_data skips capabilities whose probe
     returned False, so their registers are never read during polling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pymodbus.exceptions import ModbusException

from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.capabilities.standby import (
    REG_COMMAND_STANDBY,
    StandbyCapability,
)
from custom_components.heidelberg_energy_control.core.capabilities.watchdog import (
    REG_WATCHDOG_TIMEOUT,
    WatchdogCapability,
)


# ---------- probe: watchdog ----------


async def test_watchdog_probe_true_when_register_readable():
    cap = WatchdogCapability()
    client = MagicMock()
    ok = MagicMock()
    ok.isError = MagicMock(return_value=False)
    client.read_holding_registers = AsyncMock(return_value=ok)

    assert await cap.async_probe(client, device_id=1) is True
    client.read_holding_registers.assert_awaited_once_with(
        address=REG_WATCHDOG_TIMEOUT, count=1, device_id=1
    )


async def test_watchdog_probe_false_on_illegal_address_response():
    """pymodbus returns a response object with isError() True — not a raised exception."""
    cap = WatchdogCapability()
    client = MagicMock()
    err = MagicMock()
    err.isError = MagicMock(return_value=True)
    client.read_holding_registers = AsyncMock(return_value=err)

    assert await cap.async_probe(client, device_id=1) is False


async def test_watchdog_probe_false_on_modbus_exception():
    cap = WatchdogCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=ModbusException("boom"))

    assert await cap.async_probe(client, device_id=1) is False


async def test_watchdog_probe_false_on_oserror():
    cap = WatchdogCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=OSError("network down"))

    assert await cap.async_probe(client, device_id=1) is False


# ---------- probe: standby ----------


async def test_standby_probe_true_when_register_readable():
    cap = StandbyCapability()
    client = MagicMock()
    ok = MagicMock()
    ok.isError = MagicMock(return_value=False)
    client.read_holding_registers = AsyncMock(return_value=ok)

    assert await cap.async_probe(client, device_id=1) is True
    client.read_holding_registers.assert_awaited_once_with(
        address=REG_COMMAND_STANDBY, count=1, device_id=1
    )


async def test_standby_probe_false_on_illegal_address_response():
    cap = StandbyCapability()
    client = MagicMock()
    err = MagicMock()
    err.isError = MagicMock(return_value=True)
    client.read_holding_registers = AsyncMock(return_value=err)

    assert await cap.async_probe(client, device_id=1) is False


async def test_standby_probe_false_on_modbus_exception():
    cap = StandbyCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=ModbusException("boom"))

    assert await cap.async_probe(client, device_id=1) is False


async def test_standby_probe_false_on_oserror():
    cap = StandbyCapability()
    client = MagicMock()
    client.read_holding_registers = AsyncMock(side_effect=OSError("network down"))

    assert await cap.async_probe(client, device_id=1) is False


# ---------- end-to-end: connect-series scenario ----------


def _connect_series_client() -> MagicMock:
    """Mock a connect-series wallbox: layout 2.0.4, no 257/258, has 259 and 261.

    Serves the core-capability static reads (regs 4, 100/101, 200, 203),
    then responds with isError()=True to any read of holding 257 or 258.
    All other holding reads succeed with dummy data.
    """
    client = MagicMock()
    client.connected = False

    async def _connect() -> bool:
        client.connected = True
        return True

    client.connect = AsyncMock(side_effect=_connect)
    client.close = MagicMock()

    def _make_response(registers, is_error=False):
        rr = MagicMock()
        rr.isError = MagicMock(return_value=is_error)
        rr.registers = registers if registers else []
        return rr

    input_reads = {
        (4, 1): [0x204],       # layout 2.0.4 — passes 1.0.8 gate for both caps
        (100, 2): [16, 6],
        (200, 1): [3],
        (203, 1): [3],
        (5, 14): [7, 0, 0, 0, 362, 237, 1, 1, 1, 1, 0, 0, 0, 3615],
    }

    async def _read_input(address, count, device_id):
        return _make_response(input_reads.get((address, count), []))

    async def _read_holding(address, count, device_id):
        # Register 257 (watchdog) and 258 (standby) don't exist on connect-series
        # — either as single-register probes or as part of any coalesced batch
        # that includes them. Register 259 (remote lock) does exist.
        if address <= 258 < address + count or address == 257:
            return _make_response(None, is_error=True)
        if address == 259 and count == 1:
            return _make_response([1])
        if address == 261 and count == 1:
            return _make_response([60])
        return _make_response(None, is_error=True)

    client.read_input_registers = AsyncMock(side_effect=_read_input)
    client.read_holding_registers = AsyncMock(side_effect=_read_holding)
    return client


async def test_static_setup_skips_watchdog_and_standby_on_connect_series():
    """Regression for issue #16: setup completes and neither capability loads."""
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._client = _connect_series_client()

    static = await api.async_get_static_data()

    assert static is not None
    loaded_keys = {cap.key for cap in api.capabilities}
    assert "watchdog" not in loaded_keys
    assert "standby" not in loaded_keys
    # Core capability always loads.
    assert "core" in loaded_keys


async def test_polled_reads_omit_unavailable_registers_on_connect_series():
    """After setup, async_get_data must not read registers 257 or 258.

    This is the direct regression check for issue #16: with the fix, the
    coalesced holding-register read is `259..261` (or subsets), never
    starting at 257 or including 258. Reads issued during setup (probes)
    are expected to touch 257 and 258 by design, so we only inspect the
    reads that happen *after* setup completes.
    """
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    client = _connect_series_client()
    api._client = client

    await api.async_get_static_data()
    client.read_holding_registers.reset_mock()

    await api.async_get_data()

    assert client.read_holding_registers.await_count > 0, (
        "sanity check: polling should still read the core capability's registers"
    )
    for call in client.read_holding_registers.await_args_list:
        address = call.kwargs["address"]
        count = call.kwargs["count"]
        assert 257 not in range(address, address + count), (
            f"regression: holding read {address}..{address + count - 1} "
            f"included register 257 (should be probed absent on connect-series)"
        )
        assert 258 not in range(address, address + count), (
            f"regression: holding read {address}..{address + count - 1} "
            f"included register 258 (should be probed absent on connect-series)"
        )

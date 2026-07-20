"""Tests for WatchdogCapability (registers 257 + 262, v1.0.8+).

Watchdog Timeout (reg 257, ms; 0 disables) and FailSafe Current
(reg 262, deci-amps) together form the wallbox's safety net for
Modbus comms loss. When HA stops polling, the wallbox waits for
the timeout, then overrides register 261's target current with
the failsafe value.

Both registers are R/W, so tests cover decode direction (raw ms
for timeout, /10 for amps) and write direction (raw int for
timeout, deci-amps int for amps).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heidelberg_energy_control.const import (
    COMMAND_FAILSAFE_CURRENT,
    COMMAND_REMOTE_LOCK,
    COMMAND_WATCHDOG_TIMEOUT,
)
from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.capabilities.watchdog import (
    REG_FAILSAFE_CURRENT,
    REG_WATCHDOG_TIMEOUT,
    WatchdogCapability,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlWriteError,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


# ---------- version gate & polled definitions ----------


def test_watchdog_gated_at_1_0_8():
    assert WatchdogCapability.min_layout_version == "1.0.8"


def test_watchdog_declares_both_holding_registers():
    assert WatchdogCapability.polled_definitions == (
        RegisterDefinition(REG_WATCHDOG_TIMEOUT, 1, RegisterType.HOLDING),
        RegisterDefinition(REG_FAILSAFE_CURRENT, 1, RegisterType.HOLDING),
    )


# ---------- decode_polled ----------


def test_decode_polled_returns_raw_wire_values():
    """Both are bidirectional; capability passes raw ms and deci-amps through."""
    cap = WatchdogCapability()
    result = cap.decode_polled(
        {REG_WATCHDOG_TIMEOUT: 15000, REG_FAILSAFE_CURRENT: 80}
    )
    assert result == {
        COMMAND_WATCHDOG_TIMEOUT: 15000,
        COMMAND_FAILSAFE_CURRENT: 80,
    }


def test_decode_polled_watchdog_disabled():
    """Timeout 0 means the watchdog is disabled on the wallbox."""
    cap = WatchdogCapability()
    result = cap.decode_polled(
        {REG_WATCHDOG_TIMEOUT: 0, REG_FAILSAFE_CURRENT: 0}
    )
    assert result[COMMAND_WATCHDOG_TIMEOUT] == 0
    assert result[COMMAND_FAILSAFE_CURRENT] == 0


def test_decode_polled_ignores_unrelated_addresses():
    cap = WatchdogCapability()
    result = cap.decode_polled(
        {REG_WATCHDOG_TIMEOUT: 15000, REG_FAILSAFE_CURRENT: 60, 999: 42}
    )
    assert result == {
        COMMAND_WATCHDOG_TIMEOUT: 15000,
        COMMAND_FAILSAFE_CURRENT: 60,
    }


# ---------- write dispatch: capability-level ----------


def test_supports_write_matches_both_watchdog_keys():
    cap = WatchdogCapability()
    assert cap.supports_write(COMMAND_WATCHDOG_TIMEOUT) is True
    assert cap.supports_write(COMMAND_FAILSAFE_CURRENT) is True
    assert cap.supports_write(COMMAND_REMOTE_LOCK) is False


async def test_async_write_timeout_forwards_ms_to_register_257():
    cap = WatchdogCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=False)
    client.write_register = AsyncMock(return_value=write_result)

    ok = await cap.async_write(
        client, device_id=1, key=COMMAND_WATCHDOG_TIMEOUT, value=20000
    )

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_WATCHDOG_TIMEOUT, value=20000, device_id=1
    )


async def test_async_write_failsafe_forwards_deciamps_to_register_262():
    cap = WatchdogCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=False)
    client.write_register = AsyncMock(return_value=write_result)

    # Number entity does the *10 conversion; capability receives deci-amps.
    ok = await cap.async_write(
        client, device_id=1, key=COMMAND_FAILSAFE_CURRENT, value=80
    )

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_FAILSAFE_CURRENT, value=80, device_id=1
    )


async def test_async_write_raises_on_modbus_error_response():
    cap = WatchdogCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=True)
    client.write_register = AsyncMock(return_value=write_result)

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await cap.async_write(
            client, device_id=1, key=COMMAND_WATCHDOG_TIMEOUT, value=15000
        )


# ---------- end-to-end: dispatch via api.async_write_command ----------


def _api_with_watchdog_loaded() -> tuple[HeidelbergEnergyControlAPI, MagicMock]:
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._capabilities.append(WatchdogCapability())

    client = MagicMock()
    client.connected = True

    async def _noop_connect() -> bool:
        return True

    client.connect = AsyncMock(side_effect=_noop_connect)
    client.close = MagicMock()

    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=False)
    client.write_register = AsyncMock(return_value=write_result)

    api._client = client
    return api, client


async def test_api_dispatch_watchdog_timeout():
    api, client = _api_with_watchdog_loaded()

    ok = await api.async_write_command(COMMAND_WATCHDOG_TIMEOUT, 15000)

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_WATCHDOG_TIMEOUT, value=15000, device_id=1
    )


async def test_api_dispatch_failsafe_current():
    api, client = _api_with_watchdog_loaded()

    ok = await api.async_write_command(COMMAND_FAILSAFE_CURRENT, 60)

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_FAILSAFE_CURRENT, value=60, device_id=1
    )

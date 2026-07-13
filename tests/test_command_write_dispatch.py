"""Tests for symbolic command-write dispatch on the API.

Under the capability contract, callers name commands by symbolic key
(e.g. `COMMAND_TARGET_CURRENT`) rather than raw Modbus addresses. The
API dispatches the write to whichever loaded capability claims the
key; that capability translates the key to its owning register
internally.

These tests pin:
  - a known command key is dispatched to the owning capability and
    reaches the underlying Modbus write with the mapped register
  - an unknown key raises `HeidelbergEnergyControlWriteError`
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heidelberg_energy_control.const import (
    COMMAND_REMOTE_LOCK,
    COMMAND_TARGET_CURRENT,
)
from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.capabilities.core import (
    REG_COMMAND_REMOTE_LOCK,
    REG_COMMAND_TARGET_CURRENT,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlWriteError,
)


def _api_with_mock_client() -> tuple[HeidelbergEnergyControlAPI, MagicMock]:
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
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


async def test_target_current_command_writes_register_261():
    """COMMAND_TARGET_CURRENT is dispatched to CoreCapability → register 261."""
    api, client = _api_with_mock_client()

    result = await api.async_write_command(COMMAND_TARGET_CURRENT, 160)

    assert result is True
    client.write_register.assert_awaited_once_with(
        address=REG_COMMAND_TARGET_CURRENT, value=160, device_id=1
    )


async def test_remote_lock_command_writes_register_259():
    """COMMAND_REMOTE_LOCK is dispatched to CoreCapability → register 259."""
    api, client = _api_with_mock_client()

    result = await api.async_write_command(COMMAND_REMOTE_LOCK, 0)

    assert result is True
    client.write_register.assert_awaited_once_with(
        address=REG_COMMAND_REMOTE_LOCK, value=0, device_id=1
    )


async def test_unknown_command_key_raises_write_error():
    """Unknown symbolic key → no capability claims it → WriteError."""
    api, _ = _api_with_mock_client()

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await api.async_write_command("not_a_real_command", 1)

"""Tests for StandbyCapability (register 258, v1.0.8+).

Standby control lives on holding register 258:
  - value 0  = standby function ENABLED (device sleeps after 10 min idle)
  - value 4  = standby function DISABLED (device always awake)

The switch entity is "on" when standby is enabled, matching the
literal register semantics (Matthias's original PR #31 design).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heidelberg_energy_control.const import (
    COMMAND_REMOTE_LOCK,
    COMMAND_STANDBY,
)
from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.capabilities.standby import (
    REG_COMMAND_STANDBY,
    StandbyCapability,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlWriteError,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


# ---------- version gate & polled definitions ----------


def test_standby_gated_at_1_0_8():
    assert StandbyCapability.min_layout_version == "1.0.8"


def test_standby_declares_holding_register_258():
    assert StandbyCapability.polled_definitions == (
        RegisterDefinition(REG_COMMAND_STANDBY, 1, RegisterType.HOLDING),
    )


# ---------- decode_polled: dict-based ----------


def test_decode_polled_maps_zero_to_enabled():
    cap = StandbyCapability()
    result = cap.decode_polled({REG_COMMAND_STANDBY: 0})
    assert result == {COMMAND_STANDBY: True}


def test_decode_polled_maps_four_to_disabled():
    cap = StandbyCapability()
    result = cap.decode_polled({REG_COMMAND_STANDBY: 4})
    assert result == {COMMAND_STANDBY: False}


def test_decode_polled_ignores_unrelated_addresses():
    cap = StandbyCapability()
    result = cap.decode_polled({REG_COMMAND_STANDBY: 0, 999: 42})
    assert result == {COMMAND_STANDBY: True}


# ---------- write dispatch: capability-level ----------


def test_supports_write_matches_only_standby_key():
    cap = StandbyCapability()
    assert cap.supports_write(COMMAND_STANDBY) is True
    assert cap.supports_write(COMMAND_REMOTE_LOCK) is False
    assert cap.supports_write("nope") is False


async def test_async_write_forwards_value_to_register_258():
    cap = StandbyCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=False)
    client.write_register = AsyncMock(return_value=write_result)

    ok = await cap.async_write(client, device_id=1, key=COMMAND_STANDBY, value=4)

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_COMMAND_STANDBY, value=4, device_id=1
    )


async def test_async_write_raises_on_modbus_error_response():
    cap = StandbyCapability()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError = MagicMock(return_value=True)
    client.write_register = AsyncMock(return_value=write_result)

    with pytest.raises(HeidelbergEnergyControlWriteError):
        await cap.async_write(client, device_id=1, key=COMMAND_STANDBY, value=0)


# ---------- end-to-end: dispatch via api.async_write_command ----------


def _api_with_standby_loaded() -> tuple[HeidelbergEnergyControlAPI, MagicMock]:
    """Build an API instance with Core + Standby capabilities pre-loaded."""
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    api._capabilities.append(StandbyCapability())

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


async def test_api_async_write_command_dispatches_standby_to_register_258():
    """COMMAND_STANDBY on the api routes to StandbyCapability → register 258."""
    api, client = _api_with_standby_loaded()

    ok = await api.async_write_command(COMMAND_STANDBY, 4)

    assert ok is True
    client.write_register.assert_awaited_once_with(
        address=REG_COMMAND_STANDBY, value=4, device_id=1
    )

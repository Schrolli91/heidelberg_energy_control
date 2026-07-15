"""Tests for the block-merging read path in HeidelbergEnergyControlAPI.

Pins:
  - consecutive same-type register definitions merge into a single Modbus read
  - non-consecutive addresses become separate reads
  - different register types (input vs holding) never merge
  - duplicate definitions are deduplicated, not read twice
  - error responses and Modbus exceptions surface as ReadError
  - the returned dict is keyed by absolute address
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlReadError,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


def _api_with_mock_client() -> tuple[HeidelbergEnergyControlAPI, MagicMock]:
    """Build an API instance backed by a fully mocked client.

    The client is pre-configured as connected; individual tests set
    read_input_registers / read_holding_registers side_effects.
    """
    api = HeidelbergEnergyControlAPI(host="x", port=502, device_id=1)
    client = MagicMock()
    client.connected = True

    async def _noop_connect() -> bool:
        return True

    client.connect = AsyncMock(side_effect=_noop_connect)
    client.close = MagicMock()
    api._client = client
    return api, client


def _ok(registers: list[int]) -> MagicMock:
    rr = MagicMock()
    rr.isError = MagicMock(return_value=False)
    rr.registers = registers
    return rr


def _err() -> MagicMock:
    rr = MagicMock()
    rr.isError = MagicMock(return_value=True)
    rr.registers = []
    return rr


# ---------- happy path: single read for consecutive defs ----------


async def test_consecutive_input_definitions_merge_into_one_read():
    """Three defs at 5, 6, 7 → one read of (5, 3)."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=_ok([100, 110, 120]))

    result = await api.async_read_registers(
        [
            RegisterDefinition(5, 1, RegisterType.INPUT),
            RegisterDefinition(6, 1, RegisterType.INPUT),
            RegisterDefinition(7, 1, RegisterType.INPUT),
        ]
    )

    assert result == {5: 100, 6: 110, 7: 120}
    client.read_input_registers.assert_awaited_once_with(
        address=5, count=3, device_id=1
    )


async def test_consecutive_definitions_with_multi_register_counts():
    """A def of count=2 followed by a def at the next address merges."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=_ok([0xAAAA, 0xBBBB, 0xCCCC]))

    result = await api.async_read_registers(
        [
            RegisterDefinition(15, 2, RegisterType.INPUT),
            RegisterDefinition(17, 1, RegisterType.INPUT),
        ]
    )

    assert result == {15: 0xAAAA, 16: 0xBBBB, 17: 0xCCCC}
    client.read_input_registers.assert_awaited_once_with(
        address=15, count=3, device_id=1
    )


# ---------- non-consecutive: separate reads ----------


async def test_non_consecutive_input_definitions_become_separate_reads():
    """Defs at 5 and 100 (with a gap) issue two reads."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(
        side_effect=[_ok([100]), _ok([16, 6])]
    )

    result = await api.async_read_registers(
        [
            RegisterDefinition(100, 2, RegisterType.INPUT),
            RegisterDefinition(5, 1, RegisterType.INPUT),
        ]
    )

    assert result == {5: 100, 100: 16, 101: 6}
    assert client.read_input_registers.await_count == 2


# ---------- type separation: input and holding never merge ----------


async def test_input_and_holding_definitions_never_merge():
    """Same address in different types → two separate reads."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=_ok([1]))
    client.read_holding_registers = AsyncMock(return_value=_ok([2]))

    result = await api.async_read_registers(
        [
            RegisterDefinition(259, 1, RegisterType.INPUT),
            RegisterDefinition(259, 1, RegisterType.HOLDING),
        ]
    )

    # Same address key in the result — HOLDING overwrites INPUT since it
    # sorts after 'input' alphabetically. This is fine because in practice
    # capabilities don't declare the same address in both types.
    assert 259 in result
    client.read_input_registers.assert_awaited_once()
    client.read_holding_registers.assert_awaited_once()


# ---------- deduplication ----------


async def test_duplicate_definitions_deduplicated():
    """Two identical defs → one read, not two."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=_ok([42]))

    result = await api.async_read_registers(
        [
            RegisterDefinition(4, 1, RegisterType.INPUT),
            RegisterDefinition(4, 1, RegisterType.INPUT),
        ]
    )

    assert result == {4: 42}
    client.read_input_registers.assert_awaited_once_with(
        address=4, count=1, device_id=1
    )


# ---------- empty input ----------


async def test_empty_definitions_returns_empty_dict_without_reading():
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock()

    result = await api.async_read_registers([])

    assert result == {}
    client.read_input_registers.assert_not_awaited()


# ---------- error propagation ----------


async def test_modbus_error_response_raises_read_error():
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=_err())

    with pytest.raises(HeidelbergEnergyControlReadError):
        await api.async_read_registers(
            [RegisterDefinition(5, 1, RegisterType.INPUT)]
        )


async def test_modbus_exception_wrapped_as_read_error():
    from pymodbus.exceptions import ModbusException

    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(side_effect=ModbusException("boom"))

    with pytest.raises(HeidelbergEnergyControlReadError):
        await api.async_read_registers(
            [RegisterDefinition(5, 1, RegisterType.INPUT)]
        )

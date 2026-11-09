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
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusError,
)

from custom_components.heidelberg_energy_control.core.api import (
    HeidelbergEnergyControlAPI,
)
from custom_components.heidelberg_energy_control.core.exceptions import (
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


def _api_with_mock_client() -> tuple[HeidelbergEnergyControlAPI, MagicMock]:
    """Build an API instance backed by a mocked ModbusUnit."""
    client = MagicMock()
    api = HeidelbergEnergyControlAPI(client)
    return api, client


# ---------- happy path: single read for consecutive defs ----------


async def test_consecutive_input_definitions_merge_into_one_read():
    """Three defs at 5, 6, 7 → one read of (5, 3)."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=[100, 110, 120])

    result = await api.async_read_registers(
        [
            RegisterDefinition(5, 1, RegisterType.INPUT),
            RegisterDefinition(6, 1, RegisterType.INPUT),
            RegisterDefinition(7, 1, RegisterType.INPUT),
        ]
    )

    assert result == {5: 100, 6: 110, 7: 120}
    client.read_input_registers.assert_awaited_once_with(
        address=5, count=3
    )


async def test_consecutive_definitions_with_multi_register_counts():
    """A def of count=2 followed by a def at the next address merges."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(return_value=[0xAAAA, 0xBBBB, 0xCCCC])

    result = await api.async_read_registers(
        [
            RegisterDefinition(15, 2, RegisterType.INPUT),
            RegisterDefinition(17, 1, RegisterType.INPUT),
        ]
    )

    assert result == {15: 0xAAAA, 16: 0xBBBB, 17: 0xCCCC}
    client.read_input_registers.assert_awaited_once_with(
        address=15, count=3
    )


# ---------- non-consecutive: separate reads ----------


async def test_non_consecutive_input_definitions_become_separate_reads():
    """Defs at 5 and 100 (with a gap) issue two reads."""
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(
        side_effect=[[100], [16, 6]]
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
    client.read_input_registers = AsyncMock(return_value=[1])
    client.read_holding_registers = AsyncMock(return_value=[2])

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
    client.read_input_registers = AsyncMock(return_value=[42])

    result = await api.async_read_registers(
        [
            RegisterDefinition(4, 1, RegisterType.INPUT),
            RegisterDefinition(4, 1, RegisterType.INPUT),
        ]
    )

    assert result == {4: 42}
    client.read_input_registers.assert_awaited_once_with(
        address=4, count=1
    )


# ---------- empty input ----------


async def test_empty_definitions_returns_empty_dict_without_reading():
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock()

    result = await api.async_read_registers([])

    assert result == {}
    client.read_input_registers.assert_not_awaited()


# ---------- error propagation ----------


async def test_modbus_exception_raises_read_error():
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(side_effect=IllegalDataAddressError())

    with pytest.raises(HeidelbergEnergyControlReadError):
        await api.async_read_registers(
            [RegisterDefinition(5, 1, RegisterType.INPUT)]
        )


async def test_modbus_error_wrapped_as_read_error():
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(side_effect=ModbusError("boom"))

    with pytest.raises(HeidelbergEnergyControlReadError):
        await api.async_read_registers(
            [RegisterDefinition(5, 1, RegisterType.INPUT)]
        )


async def test_connection_error_keeps_connection_error_type():
    api, client = _api_with_mock_client()
    client.read_input_registers = AsyncMock(
        side_effect=ModbusConnectionError("offline")
    )

    with pytest.raises(HeidelbergEnergyControlConnectionError):
        await api.async_read_registers(
            [RegisterDefinition(5, 1, RegisterType.INPUT)]
        )

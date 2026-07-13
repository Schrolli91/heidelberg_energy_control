"""Shared fixtures for the Heidelberg Energy Control test suite."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the integration as a custom_component in every test."""
    yield


def load_fixture(name: str) -> dict[str, list[int]]:
    """Load a wallbox register-capture JSON fixture by stem name."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def build_mock_modbus_client(fixture: dict[str, list[int]]) -> MagicMock:
    """Build an AsyncModbusTcpClient mock that serves the given fixture.

    Maps (address, count) for both input and holding reads to the recorded
    register lists. Unknown reads return an error response so tests fail
    loudly on un-recorded register accesses.
    """
    client = MagicMock()
    client.connected = False

    async def _connect() -> bool:
        client.connected = True
        return True

    client.connect = AsyncMock(side_effect=_connect)
    client.close = MagicMock(side_effect=lambda: setattr(client, "connected", False))

    input_reads = {
        (4, 1): fixture["input_4_layout"],
        (5, 14): fixture["input_5_18_data"],
        (100, 2): fixture["input_100_101_hw_curr"],
        (200, 1): fixture["input_200_hw_vers"],
        (203, 1): fixture["input_203_sw_vers"],
    }
    holding_reads = {
        (259, 1): fixture["holding_259_remote_lock"],
        (261, 1): fixture["holding_261_target_current"],
    }

    def _response(registers: list[int] | None):
        rr = MagicMock()
        if registers is None:
            rr.isError = MagicMock(return_value=True)
            rr.registers = []
        else:
            rr.isError = MagicMock(return_value=False)
            rr.registers = registers
        return rr

    async def _read_input(address, count, device_id):
        return _response(input_reads.get((address, count)))

    async def _read_holding(address, count, device_id):
        return _response(holding_reads.get((address, count)))

    async def _write_register(address, value, device_id):
        return _response([value])

    client.read_input_registers = AsyncMock(side_effect=_read_input)
    client.read_holding_registers = AsyncMock(side_effect=_read_holding)
    client.write_register = AsyncMock(side_effect=_write_register)

    return client


@pytest.fixture
def mock_api() -> MagicMock:
    """Minimal API mock for coordinator-level tests.

    Tests configure async_get_data's return value or side_effect per case.
    async_write_command is an AsyncMock that records calls for assertion.
    """
    api = MagicMock()
    api.async_get_data = AsyncMock(return_value={})
    api.async_write_command = AsyncMock(return_value=True)
    api.disconnect = AsyncMock()
    return api

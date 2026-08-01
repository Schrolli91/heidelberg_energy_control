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

    # Flatten each fixture block into a {address: value} map. The API's
    # block-merging read path can request any window over these addresses;
    # the mock slices the requested range out of the map. A read that
    # includes any address not in the map fails, mimicking the wallbox
    # returning an illegal-address error for the whole batch.
    input_map: dict[int, int] = {}
    input_blocks: list[tuple[int, str]] = [
        (4, "input_4_layout"),
        (5, "input_5_18_data"),
        (19, "input_19_20_session"),
        (100, "input_100_101_hw_curr"),
        (200, "input_200_hw_vers"),
        (203, "input_203_sw_vers"),
        (3000, "input_3000_mid_available"),
        (3001, "input_3001_3009_mid_forward"),
        (3011, "input_3011_3012_mid_reverse"),
    ]
    for start, fixture_key in input_blocks:
        if fixture_key in fixture:
            for offset, value in enumerate(fixture[fixture_key]):
                input_map[start + offset] = value

    holding_map: dict[int, int] = {}
    holding_blocks: list[tuple[int, str]] = [
        (259, "holding_259_remote_lock"),
        (261, "holding_261_target_current"),
    ]
    for start, fixture_key in holding_blocks:
        if fixture_key in fixture:
            for offset, value in enumerate(fixture[fixture_key]):
                holding_map[start + offset] = value

    def _slice(register_map: dict[int, int], address: int, count: int) -> list[int] | None:
        window = [register_map.get(address + i) for i in range(count)]
        if any(v is None for v in window):
            return None
        return window

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
        return _response(_slice(input_map, address, count))

    async def _read_holding(address, count, device_id):
        return _response(_slice(holding_map, address, count))

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

"""Round-trip tests for read/write symmetry on number entities.

Under the multiplier-symmetry contract:
  - capability decode returns raw wire values (deci-amps, ms)
  - number entity divides by multiplier on `native_value` (read)
  - number entity multiplies by multiplier on `async_set_native_value` (write)
  - sensor entities with a `multiplier` do the same divide-on-read

The intent: what a user sees in the UI (`native_value`) is the same
number the entity would round-trip back to hardware if they set that
value with the slider.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.heidelberg_energy_control.classes.heidelberg_number import (
    HeidelbergNumber,
)
from custom_components.heidelberg_energy_control.classes.heidelberg_sensor import (
    HeidelbergSensor,
)
from custom_components.heidelberg_energy_control.const import COMMAND_TARGET_CURRENT


def _mock_coordinator(data: dict) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    # Entity base __init__ builds DeviceInfo from static_data — needs all three
    # version fields to concatenate the "v" prefix without a TypeError.
    coord.static_data = {
        "reg_layout_ver": "1.0.8",
        "hw_version": "1.0.0",
        "sw_version": "1.0.8",
    }
    coord.api = MagicMock()
    coord.api.async_write_command = AsyncMock(return_value=True)
    coord.async_set_updated_data = MagicMock()
    return coord


def _make_number_entity(coord, multiplier: float) -> HeidelbergNumber:
    entry = MagicMock()
    entry.entry_id = "test"
    desc = MagicMock()
    desc.key = COMMAND_TARGET_CURRENT
    desc.multiplier = multiplier
    return HeidelbergNumber(coord, entry, desc)


def test_number_native_value_divides_by_multiplier():
    """Raw deci-amps in coordinator data → amps displayed to user."""
    coord = _mock_coordinator({COMMAND_TARGET_CURRENT: 160})
    entity = _make_number_entity(coord, multiplier=10)
    assert entity.native_value == 16.0


def test_number_native_value_none_when_data_missing():
    coord = _mock_coordinator({})
    entity = _make_number_entity(coord, multiplier=10)
    assert entity.native_value is None


def test_number_native_value_passthrough_when_multiplier_is_none():
    """A None multiplier means the wire value is already the display value."""
    coord = _mock_coordinator({COMMAND_TARGET_CURRENT: 42})
    entity = _make_number_entity(coord, multiplier=None)
    assert entity.native_value == 42


async def test_number_write_multiplies_and_stores_raw():
    """User sets 12.0 A → API receives 120 deci-amps → data holds 120."""
    coord = _mock_coordinator({COMMAND_TARGET_CURRENT: 0})
    entity = _make_number_entity(coord, multiplier=10)

    await entity.async_set_native_value(12.0)

    coord.api.async_write_command.assert_awaited_once_with(
        COMMAND_TARGET_CURRENT, 120
    )
    assert coord.data[COMMAND_TARGET_CURRENT] == 120


async def test_number_write_passthrough_when_multiplier_is_none():
    """A None multiplier means the display value is already the wire value."""
    coord = _mock_coordinator({COMMAND_TARGET_CURRENT: 0})
    entity = _make_number_entity(coord, multiplier=None)

    await entity.async_set_native_value(42.0)

    coord.api.async_write_command.assert_awaited_once_with(
        COMMAND_TARGET_CURRENT, 42
    )
    assert coord.data[COMMAND_TARGET_CURRENT] == 42


async def test_number_round_trip_read_after_write():
    """Set 8.5 A, then read: entity shows 8.5 A back."""
    coord = _mock_coordinator({COMMAND_TARGET_CURRENT: 0})
    entity = _make_number_entity(coord, multiplier=10)

    await entity.async_set_native_value(8.5)

    assert entity.native_value == 8.5


def test_sensor_native_value_divides_by_multiplier():
    """Diagnostic sensor mirrors the number entity's divide-on-read."""
    coord = _mock_coordinator({COMMAND_TARGET_CURRENT: 160})
    entry = MagicMock()
    entry.entry_id = "test"
    desc = MagicMock()
    desc.key = COMMAND_TARGET_CURRENT
    desc.multiplier = 10
    entity = HeidelbergSensor(coord, entry, desc)
    assert entity.native_value == 16.0


def test_sensor_native_value_passthrough_when_multiplier_is_none():
    """A None multiplier means the wire value is already the display value."""
    coord = _mock_coordinator({"data_current_l1": 16.0})
    entry = MagicMock()
    entry.entry_id = "test"
    desc = MagicMock()
    desc.key = "data_current_l1"
    desc.multiplier = None
    entity = HeidelbergSensor(coord, entry, desc)
    assert entity.native_value == 16.0

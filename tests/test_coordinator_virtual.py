"""Tests for the virtual enable / target current state machine.

The coordinator runs bidirectional sync between two virtual entities
(VIRTUAL_ENABLE switch + VIRTUAL_TARGET_CURRENT number) and hardware
register 261. This logic is firmware-1.0.7-gated; on older firmware
the coordinator returns raw API data unchanged and refuses writes.

These tests pin the seven scenarios that define the contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.heidelberg_energy_control.const import (
    COMMAND_TARGET_CURRENT,
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
    VIRTUAL_ENABLE,
    VIRTUAL_TARGET_CURRENT,
)
from custom_components.heidelberg_energy_control.coordinator import (
    HeidelbergEnergyControlCoordinator,
)


def _make_coordinator(
    hass, mock_api, layout_version: str = "1.0.7"
) -> HeidelbergEnergyControlCoordinator:
    entry = MagicMock()
    entry.options = {}
    static_data = {
        DATA_REG_LAYOUT_VER: layout_version,
        DATA_HW_MAX_CURR: 16,
    }
    return HeidelbergEnergyControlCoordinator(
        hass=hass, api=mock_api, static_data=static_data, entry=entry
    )


# ---------- initial sync at first refresh ----------


async def test_initial_sync_hw_zero_keeps_switch_off(hass, mock_api):
    """Wallbox reports 0 A on startup → virtual switch stays off, slider keeps default."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {COMMAND_TARGET_CURRENT: 0.0}

    await coord._async_update_data()

    assert coord.logic_enabled is False
    assert coord.target_current == 16.0  # hw_max_current default
    assert coord._initial_fetch_done is True


async def test_initial_sync_hw_nonzero_enables_switch_and_seeds_slider(hass, mock_api):
    """Wallbox reports 12 A on startup → virtual switch ON, slider catches up to 12 A."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {COMMAND_TARGET_CURRENT: 12.0}

    result = await coord._async_update_data()

    assert coord.logic_enabled is True
    assert coord.target_current == 12.0
    assert result[VIRTUAL_ENABLE] is True
    assert result[VIRTUAL_TARGET_CURRENT] == 12.0


# ---------- bidirectional sync after startup ----------


async def test_external_hw_drop_to_zero_flips_switch_off(hass, mock_api):
    """If hw_current goes to 0 externally, the virtual switch flips off."""
    coord = _make_coordinator(hass, mock_api)
    coord.logic_enabled = True
    coord.target_current = 12.0
    coord._initial_fetch_done = True

    mock_api.async_get_data.return_value = {COMMAND_TARGET_CURRENT: 0.0}
    result = await coord._async_update_data()

    assert coord.logic_enabled is False
    assert result[VIRTUAL_ENABLE] is False
    assert coord.target_current == 12.0  # slider value preserved


async def test_external_hw_nonzero_with_switch_off_flips_switch_on(hass, mock_api):
    """If hw_current goes >0 while the switch was off, the switch flips on and slider catches up."""
    coord = _make_coordinator(hass, mock_api)
    coord.logic_enabled = False
    coord.target_current = 10.0
    coord._initial_fetch_done = True

    mock_api.async_get_data.return_value = {COMMAND_TARGET_CURRENT: 14.0}
    result = await coord._async_update_data()

    assert coord.logic_enabled is True
    assert coord.target_current == 14.0
    assert result[VIRTUAL_ENABLE] is True
    assert result[VIRTUAL_TARGET_CURRENT] == 14.0


# ---------- UI-driven writes ----------


async def test_switch_off_writes_zero_to_hardware(hass, mock_api):
    """Turning the virtual switch off writes 0 A to register 261."""
    coord = _make_coordinator(hass, mock_api)
    coord.logic_enabled = True
    coord.target_current = 12.0

    await coord.async_handle_switch_state_change(VIRTUAL_ENABLE, False)

    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_TARGET_CURRENT, 0
    )
    assert coord.logic_enabled is False
    assert coord.target_current == 12.0  # preserved for restore


async def test_switch_on_restores_last_target(hass, mock_api):
    """Turning the virtual switch on writes the slider's stored target."""
    coord = _make_coordinator(hass, mock_api)
    coord.logic_enabled = False
    coord.target_current = 12.5

    await coord.async_handle_switch_state_change(VIRTUAL_ENABLE, True)

    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_TARGET_CURRENT, 125
    )
    assert coord.logic_enabled is True


async def test_slider_while_enabled_writes_to_hardware(hass, mock_api):
    """Setting the slider while the switch is on writes immediately."""
    coord = _make_coordinator(hass, mock_api)
    coord.logic_enabled = True

    await coord.async_handle_number_set(VIRTUAL_TARGET_CURRENT, 10.0)

    mock_api.async_write_command.assert_awaited_once_with(
        COMMAND_TARGET_CURRENT, 100
    )
    assert coord.target_current == 10.0


async def test_slider_while_disabled_stores_but_does_not_write(hass, mock_api):
    """Setting the slider while the switch is off updates stored target; no hw write."""
    coord = _make_coordinator(hass, mock_api)
    coord.logic_enabled = False

    await coord.async_handle_number_set(VIRTUAL_TARGET_CURRENT, 10.0)

    mock_api.async_write_command.assert_not_awaited()
    assert coord.target_current == 10.0
    assert coord.data[VIRTUAL_TARGET_CURRENT] == 10.0


# ---------- legacy-firmware fallback ----------


async def test_old_firmware_returns_raw_data_unchanged(hass, mock_api):
    """On firmware < 1.0.7, virtual layer is bypassed; raw data flows through."""
    coord = _make_coordinator(hass, mock_api, layout_version="1.0.6")
    raw = {"some_key": "some_value"}
    mock_api.async_get_data.return_value = dict(raw)

    result = await coord._async_update_data()

    assert result == raw
    assert VIRTUAL_ENABLE not in result
    assert VIRTUAL_TARGET_CURRENT not in result


async def test_old_firmware_refuses_switch_writes(hass, mock_api):
    """On firmware < 1.0.7, switch state changes are no-ops at the api layer."""
    coord = _make_coordinator(hass, mock_api, layout_version="1.0.6")

    await coord.async_handle_switch_state_change(VIRTUAL_ENABLE, True)
    await coord.async_handle_number_set(VIRTUAL_TARGET_CURRENT, 12.0)

    mock_api.async_write_command.assert_not_awaited()


# ---------- empty-response tolerance ----------


async def test_empty_responses_tolerated_up_to_three(hass, mock_api):
    """Up to two consecutive empty responses keep previous state."""
    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {}

    # Two empty responses: previous state preserved
    result1 = await coord._async_update_data()
    result2 = await coord._async_update_data()
    assert result1 == coord.data
    assert result2 == coord.data
    assert coord._consecutive_empty_responses == 2


async def test_empty_responses_raise_update_failed_on_third(hass, mock_api):
    """Three consecutive empty responses raise UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coord = _make_coordinator(hass, mock_api)
    mock_api.async_get_data.return_value = {}

    await coord._async_update_data()
    await coord._async_update_data()
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

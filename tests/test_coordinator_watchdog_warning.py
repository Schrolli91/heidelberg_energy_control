"""Tests for the coordinator's watchdog-headroom warning.

If the poll interval is close to (or exceeds) the wallbox's watchdog
timeout, a single missed poll will trigger the FailSafe current. The
coordinator watches for that config mismatch on each successful update
and logs a one-shot warning so the user can retune before it bites.

The watchdog timeout is stored in the coordinator data as raw
milliseconds (wire format); the headroom check converts to seconds
locally for the like-for-like comparison against the scan interval.

Rules:
  - Watchdog disabled (timeout = 0) or unknown → no warning.
  - scan_interval * 1.5 <= timeout_s → no warning (fine).
  - scan_interval * 1.5  > timeout_s → warn, but only once per
    coordinator lifetime.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.heidelberg_energy_control.const import (
    COMMAND_TARGET_CURRENT,
    COMMAND_WATCHDOG_TIMEOUT,
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
)
from custom_components.heidelberg_energy_control.coordinator import (
    HeidelbergEnergyControlCoordinator,
)


def _make_coordinator(
    hass, mock_api, scan_interval: int = 10
) -> HeidelbergEnergyControlCoordinator:
    entry = MagicMock()
    entry.options = {"scan_interval": scan_interval}
    return HeidelbergEnergyControlCoordinator(
        hass=hass,
        api=mock_api,
        static_data={
            DATA_REG_LAYOUT_VER: "1.0.8",
            DATA_HW_MAX_CURR: 16,
        },
        entry=entry,
    )


async def test_no_warning_when_watchdog_disabled(hass, mock_api, caplog):
    """Timeout 0 (disabled) → no warning even at a slow poll interval."""
    coord = _make_coordinator(hass, mock_api, scan_interval=30)
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0.0,
        COMMAND_WATCHDOG_TIMEOUT: 0,
    }

    await coord._async_update_data()

    assert "watchdog" not in caplog.text.lower()


async def test_no_warning_when_poll_headroom_is_sufficient(hass, mock_api, caplog):
    """5s poll * 1.5 = 7.5s < 15s default watchdog → no warning."""
    coord = _make_coordinator(hass, mock_api, scan_interval=5)
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0.0,
        COMMAND_WATCHDOG_TIMEOUT: 15000,
    }

    await coord._async_update_data()

    assert "watchdog" not in caplog.text.lower()


async def test_warning_when_poll_too_slow_for_watchdog(hass, mock_api, caplog):
    """30s poll vs 15s watchdog → warn."""
    coord = _make_coordinator(hass, mock_api, scan_interval=30)
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0.0,
        COMMAND_WATCHDOG_TIMEOUT: 15000,
    }

    await coord._async_update_data()

    assert "watchdog" in caplog.text.lower()
    assert "failsafe" in caplog.text.lower()


async def test_warning_fires_only_once(hass, mock_api, caplog):
    coord = _make_coordinator(hass, mock_api, scan_interval=30)
    mock_api.async_get_data.return_value = {
        COMMAND_TARGET_CURRENT: 0.0,
        COMMAND_WATCHDOG_TIMEOUT: 15000,
    }

    await coord._async_update_data()
    caplog.clear()
    await coord._async_update_data()

    assert "watchdog" not in caplog.text.lower()

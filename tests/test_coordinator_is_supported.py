"""Tests for coordinator.is_supported() — firmware-version gating semantics.

These behaviors are part of the public contract used by every platform's
async_setup_entry to decide whether to instantiate an entity. They must
not regress.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.heidelberg_energy_control.const import (
    DATA_HW_MAX_CURR,
    DATA_REG_LAYOUT_VER,
)
from custom_components.heidelberg_energy_control.coordinator import (
    HeidelbergEnergyControlCoordinator,
)


def _make_coordinator(
    hass, static_data: dict[str, str | int]
) -> HeidelbergEnergyControlCoordinator:
    """Build a coordinator with the given static data, no real polling."""
    entry = MagicMock()
    entry.options = {}
    api = MagicMock()
    return HeidelbergEnergyControlCoordinator(
        hass=hass, api=api, static_data=static_data, entry=entry
    )


async def test_is_supported_returns_true_when_min_version_none(hass, caplog):
    """A missing min_version on an entity description means 'always load'."""
    coord = _make_coordinator(hass, {DATA_REG_LAYOUT_VER: "1.0.7", DATA_HW_MAX_CURR: 16})

    assert coord.is_supported(None, "some_feature") is True
    assert "no min_version defined" in caplog.text


async def test_is_supported_returns_true_when_layout_version_missing(hass, caplog):
    """If we couldn't read the layout version, fail open and warn."""
    coord = _make_coordinator(hass, {DATA_HW_MAX_CURR: 16})

    assert coord.is_supported("1.0.7", "some_feature") is True
    assert "version not found" in caplog.text.lower()


async def test_is_supported_returns_true_when_layout_version_unparseable(hass, caplog):
    """Unparseable version strings fall back to 'supported' rather than crashing."""
    coord = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "not-a-version", DATA_HW_MAX_CURR: 16}
    )

    assert coord.is_supported("1.0.7", "some_feature") is True
    assert "could not parse version" in caplog.text.lower()


@pytest.mark.parametrize(
    ("current", "required", "expected"),
    [
        ("1.0.0", "1.0.7", False),
        ("1.0.6", "1.0.7", False),
        ("1.0.7", "1.0.7", True),
        ("1.0.8", "1.0.7", True),
        ("2.0.4", "1.0.7", True),
    ],
)
async def test_is_supported_version_comparison(hass, current, required, expected):
    """Standard semver comparison: current >= required."""
    coord = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: current, DATA_HW_MAX_CURR: 16}
    )

    assert coord.is_supported(required, "feature") is expected


async def test_supports_virtual_logic_gated_by_1_0_7(hass):
    """supports_virtual_logic is the gate that prevents bricking older firmware."""
    coord_old = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "1.0.6", DATA_HW_MAX_CURR: 16}
    )
    coord_new = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "1.0.7", DATA_HW_MAX_CURR: 16}
    )

    assert coord_old.supports_virtual_logic is False
    assert coord_new.supports_virtual_logic is True

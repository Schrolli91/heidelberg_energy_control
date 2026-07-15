"""Tests for the virtual-enable gate on the coordinator.

`is_supported()` is gone (replaced by capability-based gating on
entity descriptions). The one version check that stayed on the
coordinator is `supports_virtual_logic` — the virtual enable/target-
current UI depends on register 261 semantics that landed in firmware
1.0.7. Below that, writing 0 to register 261 would brick remote
control since there's no UI to turn it back on, so the coordinator
suppresses the virtual layer and passes raw hardware data through.

These tests pin:
  - True when layout >= 1.0.7
  - False when layout < 1.0.7
  - Fail-open (True) when layout version is missing
  - Fail-open (True) when layout version is unparseable
"""

from __future__ import annotations

from unittest.mock import MagicMock

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


async def test_supports_virtual_logic_true_at_1_0_7(hass):
    coord = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "1.0.7", DATA_HW_MAX_CURR: 16}
    )
    assert coord.supports_virtual_logic is True


async def test_supports_virtual_logic_true_above_1_0_7(hass):
    coord = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "2.0.4", DATA_HW_MAX_CURR: 16}
    )
    assert coord.supports_virtual_logic is True


async def test_supports_virtual_logic_false_below_1_0_7(hass):
    coord = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "1.0.6", DATA_HW_MAX_CURR: 16}
    )
    assert coord.supports_virtual_logic is False


async def test_supports_virtual_logic_fail_open_when_layout_missing(hass, caplog):
    """If the layout version couldn't be read, assume the feature works.

    A misreport shouldn't disable functionality on hardware that would
    otherwise be fine.
    """
    coord = _make_coordinator(hass, {DATA_HW_MAX_CURR: 16})
    assert coord.supports_virtual_logic is True
    assert "layout version not in static data" in caplog.text.lower()


async def test_supports_virtual_logic_fail_open_when_layout_unparseable(hass, caplog):
    """Unparseable version strings fall back to 'supported' rather than crashing."""
    coord = _make_coordinator(
        hass, {DATA_REG_LAYOUT_VER: "not-a-version", DATA_HW_MAX_CURR: 16}
    )
    assert coord.supports_virtual_logic is True
    assert "could not parse layout version" in caplog.text.lower()

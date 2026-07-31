"""Tests for SessionEnergyCapability (registers 19..20, v2.0.0+).

Pins:
  1. Version gate at 2.0.0.
  2. Polled block declares 19..20 in one input read.
  3. decode_polled combines the pair high-word-first and converts
     wire VAh to kWh (divide by 1000).
  4. No probe override — presence is inferred from the version gate,
     matching every other v2.0.0+ input register in the spec.
  5. No writes.
"""

from __future__ import annotations

from custom_components.heidelberg_energy_control.const import DATA_SESSION_ENERGY
from custom_components.heidelberg_energy_control.core.capabilities.session_energy import (
    REG_SESSION_ENERGY_COUNT,
    REG_SESSION_ENERGY_START,
    SessionEnergyCapability,
)
from custom_components.heidelberg_energy_control.core.registers import (
    RegisterDefinition,
    RegisterType,
)


def test_session_energy_gated_at_2_0_0():
    assert SessionEnergyCapability.min_layout_version == "2.0.0"


def test_session_energy_declares_input_pair_19_20():
    assert SessionEnergyCapability.polled_definitions == (
        RegisterDefinition(
            REG_SESSION_ENERGY_START, REG_SESSION_ENERGY_COUNT, RegisterType.INPUT
        ),
    )
    assert REG_SESSION_ENERGY_START == 19
    assert REG_SESSION_ENERGY_COUNT == 2


def test_decode_polled_combines_high_word_first_and_converts_to_kwh():
    cap = SessionEnergyCapability()
    # 65536 + 1000 = 66536 VAh → 66.536 kWh
    result = cap.decode_polled({19: 1, 20: 1000})
    assert result == {DATA_SESSION_ENERGY: 66.536}


def test_decode_polled_zero_when_session_empty():
    cap = SessionEnergyCapability()
    assert cap.decode_polled({19: 0, 20: 0}) == {DATA_SESSION_ENERGY: 0.0}


def test_decode_polled_low_word_only():
    """Values under 65536 VAh live entirely in the low word."""
    cap = SessionEnergyCapability()
    assert cap.decode_polled({19: 0, 20: 1234}) == {DATA_SESSION_ENERGY: 1.234}


def test_decode_polled_ignores_unrelated_addresses():
    cap = SessionEnergyCapability()
    result = cap.decode_polled({19: 0, 20: 500, 21: 42, 999: 999})
    assert result == {DATA_SESSION_ENERGY: 0.5}


def test_session_energy_owns_no_writes():
    cap = SessionEnergyCapability()
    assert cap.supports_write("anything") is False

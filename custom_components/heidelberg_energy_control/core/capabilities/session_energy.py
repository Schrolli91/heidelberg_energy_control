"""Hardware session-energy capability (v2.0.0+).

The v1.0.x integration derived session energy from `DATA_TOTAL_ENERGY`
deltas around the plug-in edge — it worked but reset detection lived
on the HA side, so any restart or edge miss lost the session.

Layout version 2.0.0 adds registers 19-20: a 32-bit "energy during
charge cycle" counter the wallbox itself resets when the vehicle
disconnects. When this capability is loaded, its value replaces the
derived one under the same entity (the setup routing in sensor.py
picks the hardware-backed sensor class over the derived one).

The wire unit is VAh (apparent energy, same as the v1.0.x total).
The capability converts to kWh so the entity's unit stays consistent
with the derived path.
"""

from __future__ import annotations

from typing import Any

from ...const import DATA_SESSION_ENERGY
from ..registers import RegisterDefinition, RegisterType, pack_32bit
from .base import Capability

REG_SESSION_ENERGY_START = 19
REG_SESSION_ENERGY_COUNT = 2  # 19..20 (32-bit)


class SessionEnergyCapability(Capability):
    """Session energy from hardware register 19..20."""

    key = "session_energy"
    min_layout_version = "2.0.0"

    polled_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(
            REG_SESSION_ENERGY_START, REG_SESSION_ENERGY_COUNT, RegisterType.INPUT
        ),
    )

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        return {
            DATA_SESSION_ENERGY: pack_32bit(
                registers[REG_SESSION_ENERGY_START],
                registers[REG_SESSION_ENERGY_START + 1],
            )
            / 1000.0,
        }

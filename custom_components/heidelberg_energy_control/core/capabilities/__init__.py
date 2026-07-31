"""Capability modules for the Heidelberg Energy Control integration."""

from __future__ import annotations

from .base import Capability
from .core import CoreCapability
from .mid_meter import MidMeterCapability
from .session_energy import SessionEnergyCapability
from .standby import StandbyCapability
from .watchdog import WatchdogCapability

CAPABILITIES: tuple[type[Capability], ...] = (
    CoreCapability,
    StandbyCapability,
    WatchdogCapability,
    SessionEnergyCapability,
    MidMeterCapability,
)

__all__ = [
    "CAPABILITIES",
    "Capability",
    "CoreCapability",
    "MidMeterCapability",
    "SessionEnergyCapability",
    "StandbyCapability",
    "WatchdogCapability",
]

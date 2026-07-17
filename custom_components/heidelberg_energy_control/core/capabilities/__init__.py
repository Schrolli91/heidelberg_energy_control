"""Capability modules for the Heidelberg Energy Control integration."""

from __future__ import annotations

from .base import Capability
from .core import CoreCapability
from .watchdog import WatchdogCapability

CAPABILITIES: tuple[type[Capability], ...] = (CoreCapability, WatchdogCapability)

__all__ = ["CAPABILITIES", "Capability", "CoreCapability", "WatchdogCapability"]

"""Capability modules for the Heidelberg Energy Control integration."""

from __future__ import annotations

from .base import Capability
from .core import CoreCapability
from .standby import StandbyCapability

CAPABILITIES: tuple[type[Capability], ...] = (CoreCapability, StandbyCapability)

__all__ = ["CAPABILITIES", "Capability", "CoreCapability", "StandbyCapability"]

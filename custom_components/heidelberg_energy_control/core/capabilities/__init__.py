"""Capability modules for the Heidelberg Energy Control integration."""

from __future__ import annotations

from .base import Capability
from .core import CoreCapability

CAPABILITIES: tuple[type[Capability], ...] = (CoreCapability,)

__all__ = ["CAPABILITIES", "Capability", "CoreCapability"]

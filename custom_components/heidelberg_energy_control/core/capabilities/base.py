"""Capability base class.

A capability owns a group of related Modbus registers (e.g. v1.0.x core
data, MID power meter, phase switch). Each integration loads the
capabilities whose `min_layout_version` is satisfied by the wallbox and
whose runtime probe passes, then aggregates their reads/writes into the
flat dicts the coordinator expects.
"""

from __future__ import annotations

from typing import Any


class Capability:
    """Base class for a register-group capability.

    Subclasses override the read/write hooks they actually use; the
    defaults are no-ops so a capability that only contributes static
    data, or only handles one write, stays minimal.
    """

    key: str = ""
    min_layout_version: str | None = None

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Runtime check after the version gate passes.

        Default: always supported. Override when presence depends on a
        register read (e.g. MID-available probe).
        """
        return True

    async def async_read_static(
        self, client: Any, device_id: int
    ) -> dict[str, Any]:
        """Return this capability's contribution to the static-data dict."""
        return {}

    async def async_read_polled(
        self, client: Any, device_id: int
    ) -> dict[str, Any]:
        """Return this capability's contribution to the polled-data dict."""
        return {}

    def supports_write(self, address: int) -> bool:
        """Return True if this capability owns writes to the given register."""
        return False

    async def async_write(
        self, client: Any, device_id: int, address: int, value: int
    ) -> bool:
        """Perform a write owned by this capability."""
        raise NotImplementedError

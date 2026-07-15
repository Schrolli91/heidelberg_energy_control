"""Capability base class.

A capability owns a group of related Modbus registers (e.g. v1.0.x
core data, MID power meter, phase switch). Each capability declares
its register needs as immutable tuples of `RegisterDefinition`; the
API collects definitions from every loaded capability and coalesces
consecutive same-type reads into single block transactions. The
capability then decodes its part of the response synchronously from
a `{address: value}` dict.

Subclasses override only the hooks they actually use. Defaults are
no-ops so a capability that only contributes static data, or only
handles one write, stays minimal.
"""

from __future__ import annotations

from typing import Any

from ..registers import RegisterDefinition


class Capability:
    """Base class for a register-group capability."""

    key: str = ""
    min_layout_version: str | None = None

    static_definitions: tuple[RegisterDefinition, ...] = ()
    polled_definitions: tuple[RegisterDefinition, ...] = ()

    async def async_probe(self, client: Any, device_id: int) -> bool:
        """Runtime check after the version gate passes.

        Default: always supported. Override when presence depends on a
        register read (e.g. MID-available probe).
        """
        return True

    def decode_static(self, registers: dict[int, int]) -> dict[str, Any]:
        """Build this capability's contribution to the static-data dict.

        `registers` contains the values for every address in
        `static_definitions`, plus possibly more (definitions from
        other capabilities that were batched together). Access by
        absolute address; unrelated keys are ignored.
        """
        return {}

    def decode_polled(self, registers: dict[int, int]) -> dict[str, Any]:
        """Build this capability's contribution to the polled-data dict."""
        return {}

    def supports_write(self, key: str) -> bool:
        """Return True if this capability owns writes for the given command key."""
        return False

    async def async_write(
        self, client: Any, device_id: int, key: str, value: int
    ) -> bool:
        """Perform a write owned by this capability, addressed by command key."""
        raise NotImplementedError

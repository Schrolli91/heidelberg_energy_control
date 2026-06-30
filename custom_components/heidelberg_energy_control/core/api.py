"""API for Heidelberg Energy Control wallbox via Modbus.

Owns the Modbus client and connection lifecycle, then delegates all
register access to a set of `Capability` modules. Each capability
contributes static and polled data and declares the writes it owns;
the API aggregates their results into the flat dicts the coordinator
expects.

Adding a new register group means adding a capability module under
`capabilities/`, not editing this file.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from packaging import version
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from ..const import DATA_REG_LAYOUT_VER
from .capabilities import CAPABILITIES, Capability
from .capabilities.core import register_to_version, to_32bit
from .exceptions import (
    HeidelbergEnergyControlAPIError,
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
    HeidelbergEnergyControlWriteError,
)

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlAPI:
    """API class for Heidelberg Energy Control wallbox."""

    def __init__(self, host: str, port: int, device_id: int) -> None:
        """Initialize the API."""
        self._host = host
        self._port = port
        self._device_id = device_id
        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=5,
        )
        # Core capability is always present (no version floor). Additional
        # capabilities are gated by min_layout_version + runtime probe and
        # added during async_get_static_data().
        self._capabilities: list[Capability] = [CAPABILITIES[0]()]
        self._loaded: bool = False

    async def connect(self) -> None:
        """Connect to the wallbox (no-op if already connected)."""
        if self._client.connected:
            return
        try:
            result = await self._client.connect()
            if not result:
                raise HeidelbergEnergyControlConnectionError(
                    "Failed to connect to the wallbox"
                )
        except (ModbusException, OSError) as err:
            _LOGGER.error("Modbus connection error: %s", err)
            raise HeidelbergEnergyControlConnectionError(
                f"Failed to connect to the wallbox: {err}"
            ) from err

    async def disconnect(self) -> None:
        """Disconnect from the wallbox."""
        if self._client.connected:
            self._client.close()

    @property
    def capabilities(self) -> list[Capability]:
        """Loaded capabilities, in registration order."""
        return list(self._capabilities)

    async def async_get_static_data(self) -> dict[str, Any] | None:
        """Read static data via the core capability, then load the rest.

        Layout version is needed to gate the remaining capabilities by
        `min_layout_version`, so the core capability is read first and
        unconditionally — its `min_layout_version` is None.
        """
        await self.connect()

        static: dict[str, Any] = {}
        # Core is pre-loaded in __init__; read its static data first so we
        # know the layout version before gating the rest.
        core_cap = self._capabilities[0]
        static.update(await core_cap.async_read_static(self._client, self._device_id))

        layout_str = static.get(DATA_REG_LAYOUT_VER)

        # Probe + load the remaining capabilities (PR B will populate these).
        for cls in CAPABILITIES[1:]:
            cap = cls()
            if not self._version_gate_passes(cap, layout_str):
                continue
            try:
                if not await cap.async_probe(self._client, self._device_id):
                    continue
                static.update(
                    await cap.async_read_static(self._client, self._device_id)
                )
            except HeidelbergEnergyControlAPIError as err:
                _LOGGER.warning(
                    "Capability %r failed to load, skipping: %s", cap.key, err
                )
                continue
            self._capabilities.append(cap)

        self._loaded = True
        return static

    async def async_write_register(self, address: int, value: int) -> bool:
        """Write a value to a specific register (FC06).

        Dispatches to whichever loaded capability claims the address.
        """
        write_start = time.perf_counter()
        await self.connect()
        for cap in self._capabilities:
            if cap.supports_write(address):
                result = await cap.async_write(
                    self._client, self._device_id, address, value
                )
                _LOGGER.debug(
                    "Write complete: WRITE: %.3fs",
                    time.perf_counter() - write_start,
                )
                return result

        raise HeidelbergEnergyControlWriteError(
            f"No capability owns writes to register {address}"
        )

    async def async_get_data(self) -> dict[str, Any]:
        """Read polled data from every loaded capability and merge."""
        all_start = time.perf_counter()
        await self.connect()

        merged: dict[str, Any] = {}
        for cap in self._capabilities:
            merged.update(
                await cap.async_read_polled(self._client, self._device_id)
            )

        _LOGGER.debug(
            "Fetch complete: Total: %.3fs",
            time.perf_counter() - all_start,
        )
        return merged

    # --- helpers retained for backwards compatibility with existing tests ---

    def _register_to_version(self, decimal_value: int) -> str:
        return register_to_version(decimal_value)

    def _to_32bit(self, regs: list[int], idx_high: int) -> int:
        return to_32bit(regs, idx_high)

    # --- internal ---

    @staticmethod
    def _version_gate_passes(cap: Capability, layout_str: str | None) -> bool:
        """Apply the capability's min_layout_version gate. Fail-open on parse errors."""
        if cap.min_layout_version is None or layout_str is None:
            return True
        try:
            return version.parse(layout_str) >= version.parse(cap.min_layout_version)
        except Exception:
            _LOGGER.warning(
                "Could not parse layout version %r; assuming capability %r supported",
                layout_str,
                cap.key,
            )
            return True

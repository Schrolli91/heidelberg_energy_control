"""API for Heidelberg Energy Control wallbox via Home Assistant Modbus.

Uses a Modbus unit managed by Home Assistant, then delegates all
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

from modbus_connection import ModbusConnectionError, ModbusError, ModbusUnit
from packaging import version

from ..const import DATA_REG_LAYOUT_VER
from .capabilities import CAPABILITIES, Capability
from .capabilities.core import register_to_version, to_32bit
from .exceptions import (
    HeidelbergEnergyControlAPIError,
    HeidelbergEnergyControlConnectionError,
    HeidelbergEnergyControlReadError,
    HeidelbergEnergyControlWriteError,
)
from .registers import RegisterDefinition, RegisterType

_LOGGER = logging.getLogger(__name__)


class HeidelbergEnergyControlAPI:
    """API class for Heidelberg Energy Control wallbox."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Initialize the API with a unit managed by Home Assistant."""
        self._unit = unit
        # Preserve the timeout previously configured on the pymodbus client.
        unit.require_timeout(5)
        # Core capability is always present (no version floor). Additional
        # capabilities are gated by min_layout_version + runtime probe and
        # added during async_get_static_data().
        self._capabilities: list[Capability] = [CAPABILITIES[0]()]
        self._loaded: bool = False

    @property
    def capabilities(self) -> list[Capability]:
        """Loaded capabilities, in registration order."""
        return list(self._capabilities)

    async def async_read_registers(
        self, definitions: list[RegisterDefinition]
    ) -> dict[int, int]:
        """Read every register described by `definitions` in as few Modbus calls as possible.

        Sorts definitions by (type, address) and coalesces consecutive
        same-type reads into single block transactions. Returns a dict
        keyed by absolute register address, so a capability that
        declared `RegisterDefinition(15, 2, INPUT)` decodes as
        `regs[15]` and `regs[16]`.

        Duplicate definitions are tolerated (the merge simply reads
        the address once). Non-consecutive addresses become separate
        block reads.
        """
        result: dict[int, int] = {}
        if not definitions:
            return result

        # Deduplicate first so overlapping definitions don't split a block.
        unique = list({(d.type, d.address, d.count): d for d in definitions}.values())
        sorted_defs = sorted(unique, key=lambda d: (d.type.value, d.address))

        i = 0
        while i < len(sorted_defs):
            current = sorted_defs[i]
            start_addr = current.address
            end_addr = current.address + current.count
            merge_count = 1

            while i + merge_count < len(sorted_defs):
                nxt = sorted_defs[i + merge_count]
                if nxt.type == current.type and nxt.address == end_addr:
                    end_addr += nxt.count
                    merge_count += 1
                else:
                    break

            total_count = end_addr - start_addr
            try:
                if current.type == RegisterType.INPUT:
                    registers = await self._unit.read_input_registers(
                        address=start_addr, count=total_count
                    )
                else:
                    registers = await self._unit.read_holding_registers(
                        address=start_addr, count=total_count
                    )
            except (ModbusError, OSError) as err:
                if isinstance(err, ModbusConnectionError):
                    raise HeidelbergEnergyControlConnectionError(
                        f"Modbus connection failed: {err}"
                    ) from err
                raise HeidelbergEnergyControlReadError(
                    f"Failed to read {total_count} {current.type.value} register(s) at {start_addr}: {err}"
                ) from err

            for offset in range(total_count):
                result[start_addr + offset] = registers[offset]

            i += merge_count

        return result

    async def async_get_static_data(self) -> dict[str, Any] | None:
        """Read static data via the core capability, then load the rest.

        Layout version is needed to gate the remaining capabilities by
        `min_layout_version`, so the core capability is read first and
        unconditionally — its `min_layout_version` is None. Additional
        capabilities are probed and version-gated, then have their own
        static registers read individually (batching across all
        capabilities isn't useful here because static reads only
        happen once at setup).
        """
        core_cap = self._capabilities[0]
        core_regs = await self.async_read_registers(list(core_cap.static_definitions))
        static: dict[str, Any] = dict(core_cap.decode_static(core_regs))

        layout_str = static.get(DATA_REG_LAYOUT_VER)

        for cls in CAPABILITIES[1:]:
            cap = cls()
            if not self._version_gate_passes(cap, layout_str):
                continue
            try:
                if not await cap.async_probe(self._unit):
                    continue
                if cap.static_definitions:
                    cap_regs = await self.async_read_registers(
                        list(cap.static_definitions)
                    )
                    static.update(cap.decode_static(cap_regs))
            except HeidelbergEnergyControlAPIError as err:
                _LOGGER.warning(
                    "Capability %r failed to load, skipping: %s", cap.key, err
                )
                continue
            self._capabilities.append(cap)

        self._loaded = True
        return static

    async def async_write_command(self, key: str, value: int) -> bool:
        """Write a value for a symbolic command key (FC06).

        Dispatches to whichever loaded capability claims the key. The
        capability translates the key to its owning register internally;
        callers never see raw addresses.
        """
        write_start = time.perf_counter()
        for cap in self._capabilities:
            if cap.supports_write(key):
                result = await cap.async_write(self._unit, key, value)
                _LOGGER.debug(
                    "Write complete: WRITE: %.3fs",
                    time.perf_counter() - write_start,
                )
                return result

        raise HeidelbergEnergyControlWriteError(
            f"No capability owns writes for command {key!r}"
        )

    async def async_get_data(self) -> dict[str, Any]:
        """Batch-read every loaded capability's polled registers and merge decodes.

        Definitions are collected across all capabilities and handed to
        `async_read_registers`, which coalesces consecutive same-type
        blocks into single Modbus transactions. Each capability then
        decodes its own slice from the resulting {address: value} dict.
        """
        all_start = time.perf_counter()
        all_defs: list[RegisterDefinition] = []
        for cap in self._capabilities:
            all_defs.extend(cap.polled_definitions)

        registers = await self.async_read_registers(all_defs)

        merged: dict[str, Any] = {}
        for cap in self._capabilities:
            merged.update(cap.decode_polled(registers))

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

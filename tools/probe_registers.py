#!/usr/bin/env python3
"""Read-only Modbus register probe for Heidelberg / Amperfied connect wallboxes.

Answers two questions the integration can't answer from the outside:

  1. What does the wallbox actually expose? Every register the integration
     cares about is read individually, so one missing register reports as
     one absent register instead of poisoning a whole coalesced block.
  2. Which capabilities would load? The verdict section replays the real
     gating logic from `core/api.py` — version gate first, then probe —
     so it predicts what Home Assistant will do with this device.

This script only ever reads (FC03 / FC04). It never writes.

Usage:
    python3 tools/probe_registers.py --host wlwb-home.local
    python3 tools/probe_registers.py --host 192.168.20.50 --port 502 --device-id 1

Requires only `pymodbus` — no Home Assistant, so it runs anywhere:

    pip install 'pymodbus>=3.11.2'

IMPORTANT: many wallboxes and RTU gateways accept exactly one Modbus TCP
connection at a time. If Home Assistant is polling the device, this script
will fail to connect. Disable the integration's config entry (or stop Home
Assistant) first, run the probe, then re-enable it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

try:
    from pymodbus.client import AsyncModbusTcpClient
except ImportError:  # pragma: no cover - dependency hint only
    sys.exit("pymodbus is required:  pip install 'pymodbus>=3.11.2'")


HOLDING = "holding"
INPUT = "input"

ABSENT = object()


def register_to_version(value: int) -> str:
    """Convert a layout register value to semver — one hex nibble per part.

    Mirrors `core.capabilities.core.register_to_version` exactly, duplicated
    so this script stays importable without Home Assistant installed.
    """
    h = hex(value)[2:].zfill(3)
    return f"{int(h[:-2], 16)}.{int(h[-2], 16)}.{int(h[-1], 16)}"


def _phase(value: int) -> str:
    return {0: "switching in progress", 1: "1-phase", 3: "3-phase"}.get(
        value, f"unknown ({value})"
    )


def _strategy(value: int) -> str:
    return {0: "Default / Manual", 1: "Automatic Solar (Eco)", 2: "not used"}.get(
        value, f"unknown ({value})"
    )


def _onoff(value: int) -> str:
    return {0: "no", 1: "yes"}.get(value, f"unknown ({value})")


# (group, kind, address, label, spec availability, decoder)
REGISTERS: list[tuple[str, str, int, str, str, object]] = [
    ("Core / static", INPUT, 4, "Layout version", "all", register_to_version),
    ("Core / static", INPUT, 100, "HW max current (A)", "all", None),
    ("Core / static", INPUT, 101, "HW min current (A)", "all", None),
    ("Core / static", INPUT, 200, "HW version", "all", register_to_version),
    ("Core / static", INPUT, 203, "SW version", "all", register_to_version),

    ("Core / polled", INPUT, 5, "Charging state", "all", None),
    ("Core / polled", INPUT, 14, "Charging power (W)", "all", None),
    ("Core / polled", INPUT, 17, "Total energy (hi)", "all", None),

    ("Session energy", INPUT, 19, "Energy charge cycle (hi)", ">= 2.0.0", None),

    ("Per-phase power", INPUT, 21, "Power L1 (W)", ">= 2.0.3", None),
    ("Per-phase power", INPUT, 22, "Power L2 (W)", ">= 2.0.3", None),
    ("Per-phase power", INPUT, 23, "Power L3 (W)", ">= 2.0.3", None),

    ("Watchdog / control", HOLDING, 257, "Watchdog timeout (ms)", ">= 1.0.8", None),
    ("Watchdog / control", HOLDING, 258, "Standby control", ">= 1.0.8", None),
    ("Watchdog / control", HOLDING, 259, "Remote lock", "all", None),
    ("Watchdog / control", HOLDING, 261, "Target current (0.1 A)", "all", None),
    ("Watchdog / control", HOLDING, 262, "FailSafe current (0.1 A)", ">= 1.0.8", None),

    ("MID meter", INPUT, 3000, "MID available", ">= 2.0.0", _onoff),
    ("MID meter", INPUT, 3001, "MID current L1 (0.1 A)", ">= 2.0.0", None),
    ("MID meter", INPUT, 3008, "MID energy forward (hi)", ">= 2.0.0", None),

    ("Phase switch", HOLDING, 500, "Maximal power target (W)", "solar >= 2.0.2", None),
    ("Phase switch", HOLDING, 501, "Phase switch control", "solar >= 2.0.1", _phase),
    ("Phase switch", HOLDING, 502, "Charging mgmt strategy", ">= 2.0.2", _strategy),
    ("Phase switch", HOLDING, 503, "Duration time phase sw (s)", "solar >= 2.0.2", None),
    ("Phase switch", HOLDING, 504, "Waiting time phase sw (s)", "solar >= 2.0.2", None),
    ("Phase switch", HOLDING, 505, "Disconnect simulation", "solar >= 2.0.2", _onoff),
    ("Phase switch", INPUT, 5000, "Maximal power set (W)", ">= 2.0.2", None),
    ("Phase switch", INPUT, 5001, "Phase switch state", "solar >= 2.0.1", _phase),
    ("Phase switch", INPUT, 5002, "Status mgmt strategy", ">= 2.0.2", _strategy),
    ("Phase switch", INPUT, 5003, "Status disconnect sim", ">= 2.0.2", _onoff),
]


# (capability key, min layout version, probe kind, probe address, needs value 1)
CAPABILITIES: list[tuple[str, str | None, str, int, bool]] = [
    ("core", None, INPUT, 4, False),
    ("standby", "1.0.8", HOLDING, 258, False),
    ("watchdog", "1.0.8", HOLDING, 257, False),
    ("session_energy", "2.0.0", INPUT, 19, False),
    ("mid_meter", "2.0.0", INPUT, 3000, True),
    ("power_target", "2.0.2", HOLDING, 500, False),
]


def version_gate_passes(min_required: str | None, layout: str | None) -> bool:
    """Replicate the integration's fail-open version gate."""
    if min_required is None:
        return True
    if layout is None:
        return True  # unparseable version defaults to supported
    def parts(v: str) -> tuple[int, ...]:
        return tuple(int(p) for p in v.split("."))
    try:
        return parts(layout) >= parts(min_required)
    except ValueError:
        return True


async def read_one(client, kind: str, address: int, device_id: int):
    """Read a single register. Returns the value, or ABSENT."""
    fn = client.read_input_registers if kind == INPUT else client.read_holding_registers
    try:
        result = await fn(address=address, count=1, device_id=device_id)
    except Exception:
        return ABSENT
    if result.isError() or not result.registers:
        return ABSENT
    return result.registers[0]


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Modbus register probe (never writes).",
    )
    parser.add_argument("--host", required=True, help="wallbox hostname or IP")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--device-id", type=int, default=1, help="Modbus unit id")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        help="seconds between reads, to be gentle on RTU gateways",
    )
    args = parser.parse_args()

    print(f"Probing {args.host}:{args.port} (device id {args.device_id})")
    print("Read-only: FC03/FC04 only, no writes.\n")

    client = AsyncModbusTcpClient(args.host, port=args.port)
    await client.connect()
    if not client.connected:
        print(f"Could not connect to {args.host}:{args.port}.")
        print(
            "\nMany wallboxes allow only ONE Modbus TCP connection. If Home "
            "Assistant is polling this device, disable the integration's "
            "config entry (or stop Home Assistant), then run this again."
        )
        return 1

    values: dict[tuple[str, int], object] = {}
    current_group = None
    for group, kind, address, label, availability, decoder in REGISTERS:
        if group != current_group:
            print(f"\n--- {group} ---")
            print(f"  {'reg':>6}  {'':<7} {'status':<8} {'value':<26} spec")
            current_group = group
        value = await read_one(client, kind, address, args.device_id)
        values[(kind, address)] = value
        if value is ABSENT:
            shown, status = "-", "ABSENT"
        else:
            status = "present"
            shown = str(value)
            if decoder is not None:
                shown = f"{value}  ({decoder(value)})"
        print(f"  {address:>6}  {kind:<7} {status:<8} {shown:<26} {availability}")
        await asyncio.sleep(args.delay)

    client.close()

    # ---- verdict: what would Home Assistant load? ----
    layout_raw = values.get((INPUT, 4))
    layout = register_to_version(layout_raw) if layout_raw is not ABSENT else None

    print("\n\n=== Capability verdict ===")
    print(f"Layout version reported: {layout or 'UNREADABLE'}")
    print("(An unreadable/unparseable version fails open — treated as supported.)\n")
    print(f"  {'capability':<16} {'min':<8} {'gate':<8} {'probe':<10} result")
    for key, min_version, kind, address, needs_one in CAPABILITIES:
        gate = version_gate_passes(min_version, layout)
        probed = values.get((kind, address), ABSENT)
        if not gate:
            probe_str, loads = "not run", False
        elif probed is ABSENT:
            probe_str, loads = "absent", False
        elif needs_one and probed != 1:
            probe_str, loads = f"={probed}", False
        else:
            probe_str, loads = "ok", True
        print(
            f"  {key:<16} {min_version or '-':<8} {'pass' if gate else 'BLOCK':<8} "
            f"{probe_str:<10} {'LOADS' if loads else 'skipped'}"
        )

    print(
        "\nNote: 'gate BLOCK' means the version check rejected the capability "
        "before probing — the register may still exist on the device."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

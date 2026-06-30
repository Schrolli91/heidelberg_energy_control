"""Capture register values from a live wallbox for use as a test fixture.

Usage:
    python scripts/capture_fixture.py --host 192.168.1.50 --port 502 --device-id 1 \
        --out tests/fixtures/wallbox_<version>.json

The captured JSON is consumed by tests/test_api_decoding.py to verify that
async_get_data() and async_get_static_data() decode wire bytes identically
across refactors. Register values are non-sensitive; commit them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pymodbus.client import AsyncModbusTcpClient


READS: list[tuple[str, str, int, int]] = [
    # (label, fn, address, count)
    ("input_4_layout", "input", 4, 1),
    ("input_5_18_data", "input", 5, 14),
    ("input_100_101_hw_curr", "input", 100, 2),
    ("input_200_hw_vers", "input", 200, 1),
    ("input_203_sw_vers", "input", 203, 1),
    ("holding_259_remote_lock", "holding", 259, 1),
    ("holding_261_target_current", "holding", 261, 1),
]


async def capture(host: str, port: int, device_id: int) -> dict[str, list[int]]:
    """Read every register the integration touches today."""
    client = AsyncModbusTcpClient(host, port=port, timeout=5)
    if not await client.connect():
        raise RuntimeError(f"Could not connect to {host}:{port}")

    result: dict[str, list[int]] = {}
    try:
        for label, fn, address, count in READS:
            if fn == "input":
                rr = await client.read_input_registers(
                    address=address, count=count, device_id=device_id
                )
            else:
                rr = await client.read_holding_registers(
                    address=address, count=count, device_id=device_id
                )
            if rr.isError():
                raise RuntimeError(f"Read failed: {label}")
            result[label] = list(rr.registers)
    finally:
        client.close()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--device-id", type=int, default=1)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = asyncio.run(capture(args.host, args.port, args.device_id))
    payload = json.dumps(data, indent=2) + "\n"

    if args.out is None:
        sys.stdout.write(payload)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload)
        print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

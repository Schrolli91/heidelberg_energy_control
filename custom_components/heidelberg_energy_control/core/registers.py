"""Register-block metadata used by capabilities to declare their reads.

Capabilities describe the registers they need via `RegisterDefinition`
tuples rather than issuing Modbus reads themselves. The API collects
definitions from every loaded capability and coalesces consecutive
same-type reads into single block transactions, keeping bus load
down without the capabilities knowing about each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RegisterType(Enum):
    """Modbus register type (function code family)."""

    INPUT = "input"       # FC04
    HOLDING = "holding"   # FC03


@dataclass(frozen=True)
class RegisterDefinition:
    """Definition of one contiguous register block a capability needs.

    A definition of `RegisterDefinition(address=15, count=2, type=INPUT)`
    means "read input registers 15 and 16." The API returns a dict
    keyed by absolute address, so a capability decoding a 32-bit value
    would do `pack_32bit(regs[15], regs[16])`.
    """

    address: int
    count: int
    type: RegisterType


def pack_32bit(high: int, low: int) -> int:
    """Compose a 32-bit value from two 16-bit words, high word first."""
    return (high << 16) | low

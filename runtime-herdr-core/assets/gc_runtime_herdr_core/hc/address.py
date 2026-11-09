"""hc terminal addresses: ``t`` and a counter, written t1..t9, t10..t9z,
t100..t9zz, ... After the first digit (1-9) the counter uses 30 symbols:
the digits and the consonants but ``l`` (hc ``crates/herdr-core/src/terminals.rs``
``address`` and ``parse_id``), so ``t1b`` (20) follows ``t19``."""

from __future__ import annotations

from typing import Final, Optional

SYMBOLS: Final = "0123456789bcdfghjkmnpqrstvwxyz"


def address_of(n: int) -> str:
    """The address hc writes for counter ``n`` (from 1)."""
    if n < 1:
        raise ValueError("terminal counters start at 1")
    rest, size, length = n - 1, 9, 0
    while rest >= size:
        rest -= size
        size *= 30
        length += 1
    tail = []
    for _ in range(length):
        tail.append(SYMBOLS[rest % 30])
        rest //= 30
    return "t" + str(rest + 1) + "".join(reversed(tail))


def parse_address(address: str) -> Optional[int]:
    """The counter of an hc address; None when ``address`` is not id-shaped."""
    if len(address) < 2 or address[0] != "t" or address[1] not in "123456789":
        return None
    if any(ch not in SYMBOLS for ch in address[1:]):
        return None
    values = [SYMBOLS.index(ch) for ch in address[1:]]
    rest = values[0] - 1
    before, size = 0, 9
    for value in values[1:]:
        rest = rest * 30 + value
        before += size
        size *= 30
    return before + rest + 1

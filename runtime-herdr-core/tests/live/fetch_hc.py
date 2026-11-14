"""Fetch the pinned herdr-core for the live tier and print its path.

    python tests/live/fetch_hc.py <directory>

The release manifest must agree with ``assets/hc-pin.json`` and the archive's
sha256 must equal the pin's before anything is written (the pack's own
install path). Refuses outside a GitHub Actions runner or a declared
throwaway host, like every part of the live tier.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List

HERE = Path(__file__).resolve().parent
for _entry in (HERE.parents[1] / "assets", HERE):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from gc_runtime_herdr_core.herdrcore.pin import PinError, load_pin  # noqa: E402
from livekit.fetch import FetchError, fetch_pinned  # noqa: E402
from livekit.guard import REFUSED_EXIT, Refused, clearance  # noqa: E402


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: fetch_hc.py <directory>\n")
        return 2
    try:
        clearance(os.environ)
    except Refused as err:
        sys.stderr.write(f"fetch_hc.py: {err}\n")
        return REFUSED_EXIT
    try:
        pin = load_pin()
        binary = fetch_pinned(pin, os.path.abspath(argv[1]))
    except (PinError, FetchError) as err:
        sys.stderr.write(f"fetch_hc.py: {err}\n")
        return 1
    sys.stderr.write(f"fetch_hc.py: herdr-core {pin.version} verified against the pinned sha256\n")
    print(binary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

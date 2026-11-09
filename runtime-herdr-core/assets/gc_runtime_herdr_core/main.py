"""Entry dispatch for ``gc-runtime-herdr-core``.

    gc-runtime-herdr-core <op> [args...]   one RPP op, per-op transport
    gc-runtime-herdr-core x-version         the pack's name and version (JSON)

This is the only module that reads the process environment: it hands a
snapshot to the per-op runner, which builds each op's request from it.
The handshake is static and reads no state; an op missing
from :data:`OPS` answers exit 2, the RPP "unknown operation".
"""

from __future__ import annotations

import os
import sys
from typing import Final, Sequence

from . import PACK_NAME, PACK_VERSION
from .rpp.jsonval import dumps
from .rpp.ops import OpTable, handshake_op
from .rpp.perop import run_per_op
from .rpp.wire import Handshake

DEBUG_ENV: Final = "GC_HERDR_CORE_DEBUG"
"""``1`` adds a redacted traceback to unexpected failures on stderr."""

HANDSHAKE: Final = Handshake(capabilities=(), locality="local")
"""What this build declares. A capability token is declared only together
with the ops that implement it and the tests that prove them."""

OPS: Final[OpTable] = {"protocol": handshake_op(HANDSHAKE)}


def _version() -> int:
    python = ".".join(str(part) for part in sys.version_info[:3])
    line = dumps({"pack": PACK_NAME, "version": PACK_VERSION, "python": python})
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    return 0


def main(argv: Sequence[str], *, started: float) -> int:
    """Run the command ``argv`` names; ``started`` is when the process began."""
    if len(argv) > 1 and argv[1] == "x-version":
        return _version()
    return run_per_op(
        argv,
        os.environ,
        OPS,
        started=started,
        stdin=sys.stdin.buffer,
        stdout=sys.stdout.buffer,
        stderr=sys.stderr,
        debug=os.environ.get(DEBUG_ENV) == "1",
    )

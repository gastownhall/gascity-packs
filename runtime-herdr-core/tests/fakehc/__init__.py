"""fake-hc: the herdr-core double the unit tier talks to.

Tests never build, install or run a real herdr-core: its holder-loss sweep
can kill unrelated processes on the host.
"""

from __future__ import annotations

from .server import Call, FakeHc

__all__ = ["Call", "FakeHc"]

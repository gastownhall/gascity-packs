"""A city core started outside the pack is refused.

Whoever starts a core fixes its environment, cgroup and lifetime. A core
started by a bare ``hc server start`` (here: on the city's own discovery
tuple, but with the whole caller environment) must make ``start`` refuse
with the ``restart-core`` fix, and nothing may run on it.
"""

from __future__ import annotations

import os
import subprocess

from livekit import crash
from livekit.hcrpc import HcRpc
from livekit.pack import Pack
from livekit.scratch import Scratch


def test_start_refuses_a_core_started_outside_the_pack(scratch: Scratch) -> None:
    paths = scratch.paths()
    os.makedirs(os.path.dirname(paths.socket), mode=0o700, exist_ok=True)
    env = dict(os.environ)
    env.update(scratch.hc_cli_env(paths.session, paths.socket))
    env["GC_HC_LIVE_FOREIGN"] = "1"
    done = subprocess.run(
        [scratch.hc_bin, "server", "start"], env=env, capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stderr
    assert crash.wait_until(HcRpc(paths.socket).answers, 15), "the foreign core never answered"
    crash.core_status(scratch)

    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    refused = pack.start_agent("live-f")
    assert refused.code == 1, refused.stdout + refused.stderr
    assert "restart-core" in refused.stderr, refused.stderr
    assert pack.observe("live-f").state == "absent"

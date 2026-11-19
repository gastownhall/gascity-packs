"""An agent's own ``hc`` while the city's core is down.

The pack puts an ``hc`` shim first on every agent's PATH. With the core down
it must refuse rather than let hc's CLI autostart a second core on the
agent's own state directory and credentials. A holder may restart its
crashed core (hc's holder waits a 3 s grace first, and the probe runs well
inside it, so refusal is the expected outcome); then the agent's ``hc``
reaches the city's own core. Either way: no hc core or holder carries the
agent's environment (the run's mark, which the pack's allowlisted core and a
holder-restarted core never carry), ``core.lock`` still names the city's
socket, a second pack session is not refused as foreign, and no program
ended.
"""

from __future__ import annotations

import os
import signal

from livekit import crash
from livekit.hcrpc import HcRpc
from livekit.pack import Pack
from livekit.scratch import Scratch

HOLDER_GRACE_S = 3.0
"""How long an hc holder waits before it restarts a crashed core (``HC_HOLDER_GRACE_MS``)."""


def test_in_agent_hc_with_the_core_down(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    assert pack.start_agent("live-h").code == 0
    report = scratch.agent_report("live-h", timeout_s=30)
    paths = scratch.paths()
    rpc = HcRpc(paths.socket)
    core = crash.core_status(scratch).pid
    scratch.ownership.signal(core, signal.SIGKILL)
    assert crash.wait_until(lambda: not scratch.ownership.alive(core), 10), "the core outlived SIGKILL"

    probe = scratch.run_hc_in_agent("live-h", timeout_s=60)
    restarted = rpc.answers()
    scratch.note("in-agent hc with the core down", {"code": probe.code, "stderr": probe.stderr[-300:], "core restarted": restarted})

    assert probe.argv0.endswith("/hc") and "/shim/" in probe.argv0, f"the agent's hc is not the pack's shim: {probe.argv0}"
    if probe.code != 0:
        assert "down" in probe.stderr, probe.stderr
    else:
        assert restarted, "the agent's hc succeeded, but no core answers on the city's socket"
    with open(paths.core_lock, encoding="utf-8") as handle:
        assert handle.read().strip() == paths.socket
    agent_state = os.path.join(scratch.base, "agent-state", "herdr-core")
    assert not os.path.exists(agent_state), "the agent's hc started a core on the agent's own state directory"
    from_agent = scratch.ownership.runtime_from_agents()
    assert from_agent == [], f"an hc core or holder runs on the agent's environment: {from_agent}"
    assert scratch.ownership.alive(report.pid), "the agent ended when its core died"

    # Whatever answers now (or the core the next start brings up) is the
    # pack's own: a core from the agent's environment would be refused.
    crash.wait_until(rpc.answers, HOLDER_GRACE_S + 2)
    second = pack.start_agent("live-h2")
    assert second.code == 0, f"a second session was refused after the agent's hc ran: {second.stderr}"
    assert scratch.ownership.runtime_from_agents() == []

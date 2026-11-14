"""A kept terminal's replacement shell is not the agent.

With ``terminal.keep`` set (by a client other than the pack, as a person in
the Herdr app could), a holder loss makes hc start a fresh shell in the same
terminal. The pack must read that box as dead, not running, so gc kills the
corpse and starts the session again: keep/restart is a death.
"""

from __future__ import annotations

from livekit import crash
from livekit.hcrpc import HcRpc
from livekit.pack import Pack
from livekit.scratch import Scratch


def test_a_kept_terminal_restarted_after_holder_loss_reads_dead(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    assert pack.start_agent("live-k").code == 0
    first = pack.wait_state("live-k", ("running",), 15)
    assert first.state == "running"
    address = first.object["id"]
    rpc = HcRpc(scratch.paths().socket)
    agent_pid = rpc.terminal(address).pid
    rpc.keep(address, True)
    assert rpc.terminal(address).keep

    crash.kill_holders(scratch, "K1")

    def restarted() -> bool:
        try:
            view = rpc.terminal(address)
        except (OSError, ValueError):
            return False
        return view.state == "live" and view.pid is not None and view.pid != agent_pid

    assert crash.wait_until(restarted, 30), f"hc did not restart the kept terminal: {rpc.terminal(address)}"
    scratch.note("kept terminal after holder loss", {"old_pid": agent_pid, "new_pid": rpc.terminal(address).pid})
    dead = pack.wait_state("live-k", ("dead",), 30)
    assert dead.state == "dead", f"a kept terminal's new shell reads {dead.state}, not dead"
    assert not pack.is_running("live-k")
    again = pack.restart_after_death("live-k")
    assert again.state == "running" and again.object["id"] != address

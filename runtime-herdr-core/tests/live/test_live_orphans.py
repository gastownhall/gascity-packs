"""What an agent leaves behind when its holder dies.

The launcher removes ``HC_SCOPE``, so hc's holder-loss sweep no longer reaps
an agent's detached children; the pack does, by identity: killing the dead
box's object scans for its ``GC_INSTANCE_TOKEN`` and kills what carries it,
except city infrastructure (gc's infrastructure argv) and its subtree.
The agent starts ``setsid sleep 9999`` and a fenced proxy stand-in; after a
holder SIGKILL and gc's reaction (kill the object), the sleep is gone and the
stand-in still runs.
"""

from __future__ import annotations

from livekit import crash
from livekit.pack import Pack
from livekit.scratch import Scratch


def test_holder_loss_orphans_are_reaped_and_infrastructure_is_fenced(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    assert pack.start_agent("live-p", GC_HC_LIVE_SPAWN="orphan").code == 0
    report = scratch.agent_report("live-p", timeout_s=30, want=("orphan",))
    sleep, fenced = report.orphan["sleep"], report.orphan["fenced"]
    assert "HC_SCOPE" not in crash.environ_of(scratch, sleep)

    crash.kill_holders(scratch, "K1")
    dead = pack.wait_state("live-p", ("dead",), 30)
    assert dead.state == "dead", f"the box reads {dead.state} after its holder died"
    crash.wait_until(lambda: False, crash.SETTLE_S)
    assert scratch.ownership.alive(sleep), "the sleep died with the holder: the sweep reached a stripped agent's tree"

    killed = pack.kill_object("live-p", dead.object)
    assert (killed.code, killed.stdout.strip()) == (0, "killed"), killed.stderr
    assert crash.wait_until(lambda: not scratch.ownership.alive(sleep), 10), "the agent's orphan survived the corpse kill"
    assert scratch.ownership.alive(fenced), "the corpse kill reached fenced infrastructure"

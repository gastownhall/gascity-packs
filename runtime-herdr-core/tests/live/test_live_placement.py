"""Each lane really is the placement it names: on the systemd lane hc runs the
core in an ``hc-serve-*`` unit and the holders in ``hc-hold-*`` units, and the
pack re-scopes agents under ``gascity-agents.slice``; on the plain lane hc
places nothing in units. A lane that silently ran the other placement would
make every other result mean something else."""

from __future__ import annotations

from livekit import crash
from livekit.pack import Pack
from livekit.scratch import Scratch
from livekit.units import AGENT_SLICE, in_slice, is_holder_unit


def test_the_lane_places_the_core_holders_and_agents_as_named(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    answer = pack.start_agent("live-l")
    assert answer.code == 0, answer.stderr
    report = scratch.agent_report("live-l", timeout_s=30)
    status = crash.core_status(scratch)
    core_unit = crash.unit_or_none(scratch, status.pid) or ""
    holder_units = {pid: crash.unit_or_none(scratch, pid) or "" for pid in status.holders}
    agent_cgroup = crash.cgroup_of(scratch, report.pid)
    scratch.note("placement", {"core": core_unit, "holders": holder_units, "agent": agent_cgroup, "warnings": answer.stderr[-300:]})
    if scratch.lane == "systemd":
        assert core_unit.startswith("hc-serve-"), f"the core is not in an hc-serve unit: {core_unit}"
        assert all(is_holder_unit(u) for u in holder_units.values()), holder_units
        assert in_slice(agent_cgroup, AGENT_SLICE), f"the agent was not re-scoped: {agent_cgroup}"
    else:
        assert not core_unit.startswith("hc-serve-"), f"the plain lane placed the core in {core_unit}"
        assert not any(is_holder_unit(u) for u in holder_units.values()), holder_units

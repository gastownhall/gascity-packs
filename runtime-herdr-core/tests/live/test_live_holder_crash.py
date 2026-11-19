"""Holder crashes must not take down the city infrastructure an agent started.

An agent's shell starts the city's store, its watchdog and bd's proxy
routinely (gc's managed-store autostart, bd's proxy), detached in sessions
of their own. Two things can kill them when an hc holder dies: hc's
holder-loss sweep (every process carrying the terminal's ``HC_SCOPE``) and,
under systemd, a kill of the holder's whole cgroup (systemd-oomd). Each case
turns the pack's defences on or off (:mod:`livekit.cases`), kills the holder
(K1: the holder process; K2: its unit), and checks the infrastructure:

* it survives, the store still answers, the pack reads both sessions dead,
  and gc's reaction (kill the corpse's tree by identity, start again) brings
  them back without touching the infrastructure; the core is not restarted;
* in the negative control (no launcher at all) it is swept: proof the test
  can fail.

The stand-ins carry gc's real infrastructure argv; a real managed store
started through a city is exercised by the scratch-city soak.
"""

from __future__ import annotations

import os
from typing import Dict, List

import pytest

from livekit import crash
from livekit.cases import ROLES, Run, in_holder_cgroup, matrix, witness_expectation
from livekit.guard import LANE_ENV
from livekit.hcrpc import HcRpc
from livekit.pack import Pack
from livekit.scratch import AGENT, AgentReport, Scratch
from livekit.units import AGENT_SLICE, INFRA_SLICE, in_slice, is_holder_unit

_LANE = os.environ.get(LANE_ENV, "")
RUNS: List[Run] = [r for r in matrix() if not _LANE or r.lane == _LANE]
DEADLINE_S = 30.0


def _start_sessions(scratch: Scratch, run: Run) -> Pack:
    pack = Pack(scratch, rescope=run.case.rescope)
    extra: Dict[str, str] = {"GC_HC_LIVE_SPAWN": "infra"}
    if run.case.infra_scope and run.lane == "systemd":
        extra["GC_HC_LIVE_INFRA_UNIT"] = scratch.infra_unit(run.id.replace("-", "_"))
    if run.case.strip:
        for name, more in (("live-a1", extra), ("live-a2", {})):
            answer = pack.start_agent(name, **more)
            assert answer.code == 0, f"start {name}: {answer.stderr}"
        return pack
    # No launcher: plain hc programs on the city's core (brought up by one
    # pack session), so each keeps HC_SCOPE and the holder's cgroup.
    extra["GC_HC_LIVE_SPAWN"] = "infra,witness"
    answer = pack.start_agent("live-c0")
    assert answer.code == 0, f"start live-c0: {answer.stderr}"
    rpc = HcRpc(scratch.paths().socket)
    for name, more in (("live-a1", extra), ("live-a2", {})):
        env = dict(scratch.agent_env(name, **more), PATH=os.environ.get("PATH", "/usr/bin:/bin"))
        rpc.run([scratch.python, str(AGENT)], cwd=scratch.work, env=env, name=name)
    return pack


def _check_placement(scratch: Scratch, run: Run, report: AgentReport) -> None:
    for role in ROLES:
        pid = report.infra[role]
        env = crash.environ_of(scratch, pid)
        assert ("HC_SCOPE" in env) == (not run.case.strip), f"{role}: HC_SCOPE present={'HC_SCOPE' in env}"
        expected = in_holder_cgroup(run.case, role, run.lane)
        if expected is None:
            continue
        cgroup = crash.cgroup_of(scratch, pid)
        unit = crash.unit_or_none(scratch, pid) or ""
        assert is_holder_unit(unit) == expected, f"{role} runs in {cgroup} (in the holder's unit expected: {expected})"
        if run.case.infra_scope and role in ("watchdog", "dolt"):
            assert in_slice(cgroup, INFRA_SLICE), f"{role} is not under {INFRA_SLICE}: {cgroup}"
    if report.witness is not None:
        assert "HC_SCOPE" not in crash.environ_of(scratch, report.witness), "the witness carries HC_SCOPE"
        if run.lane == "systemd":
            unit = crash.unit_or_none(scratch, report.witness) or ""
            assert is_holder_unit(unit), f"the witness is not in the holder's unit: {unit}"
    if run.lane == "systemd" and run.case.rescope:
        agent = crash.cgroup_of(scratch, report.pid)
        assert in_slice(agent, AGENT_SLICE), f"the agent was not re-scoped: {agent}"


def _check_witness(scratch: Scratch, run: Run, report: AgentReport) -> None:
    assert report.witness is not None
    witness = report.witness
    if witness_expectation(run.kill) == "dies":
        died = crash.wait_until(lambda: not scratch.ownership.alive(witness), DEADLINE_S)
        assert died, f"{run.kill} did not reach the holder's cgroup: the witness outside the sweep survived"
    else:
        crash.wait_until(lambda: False, crash.SETTLE_S)  # let any sweep finish
        assert scratch.ownership.alive(witness), f"the witness outside the sweep died under {run.kill}"
    scratch.note("witness", f"{witness_expectation(run.kill)} under {run.kill}, as expected")


@pytest.mark.parametrize("run", RUNS, ids=[r.id for r in RUNS])
def test_holder_crash(scratch: Scratch, run: Run) -> None:
    if run.deferred is not None:
        pytest.skip(run.deferred)
    pack = _start_sessions(scratch, run)
    want = ("infra",) if run.case.strip else ("infra", "witness")
    report = scratch.agent_report("live-a1", timeout_s=30, want=want)
    status = crash.core_status(scratch)
    if run.lane == "systemd":
        units = crash.holder_units(scratch, status)
        assert all(is_holder_unit(u) for u in units.values()), f"hc did not place its holders in units: {units}"
    _check_placement(scratch, run, report)
    assert scratch.ping_store(report.store_socket), "the store stand-in does not answer before the kill"

    killed = crash.kill_holders(scratch, run.kill)
    scratch.note("killed", killed)

    if run.expect == "swept":
        gone = crash.wait_until(lambda: not any(crash.alive(scratch, report.infra).values()), DEADLINE_S)
        assert gone, (
            f"negative control did not fail: infrastructure without the launcher survived {run.kill}: "
            f"{crash.alive(scratch, report.infra)}"
        )
        scratch.note("negative control", f"infrastructure swept by {run.kill}, as expected")
        _check_witness(scratch, run, report)
        return

    for name in ("live-a1", "live-a2"):
        seen = pack.wait_state(name, ("dead", "absent"), DEADLINE_S)
        assert seen.state in ("dead", "absent"), f"{name} still reads {seen.state} after the holder died"
    crash.wait_until(lambda: False, crash.SETTLE_S)  # let any sweep finish
    assert all(crash.alive(scratch, report.infra).values()), f"infrastructure died: {crash.alive(scratch, report.infra)}"
    assert scratch.ping_store(report.store_socket), "the store stand-in stopped answering"
    for name in ("live-a1", "live-a2"):
        assert pack.restart_after_death(name).state == "running"
    assert all(crash.alive(scratch, report.infra).values()), "restarting the sessions killed the infrastructure"
    assert scratch.ping_store(report.store_socket)
    assert HcRpc(scratch.paths().socket).status().pid == status.pid, "the core was restarted"

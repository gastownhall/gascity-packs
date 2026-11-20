"""gc's own start ladder over the pack: the un-welded start and its queued
first turn, against the pinned hc.

The pinned gc runs its per-city controller over a scratch city
(:mod:`livekit.city`). gc's fresh start runs the pack's ``provision`` and
``launch``, writes the launch's identity, publishes the ready prompt, runs
its dialog pass over the pack's ``watch-startup``, ``peek`` and
``send-keys``, and queues the first turn, which its nudge queue delivers
through the pack's ``nudge`` once the agent takes input. The harness only
observes (the agent's input log, the pack's test op log, hc's own reads) and
plays the person: it releases the agent's own question.

(a) a startup dialog at launch never receives the first turn: gc answers it
    first, and the turn is typed once, at the prompt;
(b) a first turn the agent refuses (its OSC 7501 ``blocked``) is answered
    ``pending_interaction``, types nothing, stays queued, and is typed exactly
    once after the person answers.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Dict, List

from livekit.city import CityAgent, Controller, OpLine, of_session, write_city
from livekit.hcrpc import HcRpc
from livekit.pack import Pack
from livekit.scratch import Scratch

LAUNCH_S = 180.0
"""How long the controller may take to come up and launch the session."""
FIRST_TURN_S = 180.0
REFUSAL_S = 240.0
"""The queue tries a turn the quiet gate holds back after its 2-minute starvation bypass."""
AFTER_RELEASE_S = 240.0
DUPLICATE_S = 20.0
"""A duplicate send would land within this."""


def _token() -> str:
    return f"live-turn-{uuid.uuid4().hex[:12]}"


def _launched(ctl: Controller, agent: str) -> List[OpLine]:
    return [line for line in of_session(ctl.ops(), agent) if line.op == "launch" and line.exit == 0]


def _ordered(lines: List[OpLine]) -> List[OpLine]:
    return sorted(lines, key=lambda line: line.begun_ms)


def _typed(scratch: Scratch, agent: str, token: str) -> int:
    return sum(line.text.count(token) for line in scratch.input_lines(agent))


def test_a_trust_dialog_at_launch_never_receives_the_first_turn(scratch: Scratch, gc_bin: str) -> None:
    token = _token()
    agent = CityAgent(name="turn-dialog", mode="trust", first_turn=f"first turn {token}")
    write_city(scratch, [agent])
    ctl = Controller(scratch, gc_bin)
    ctl.start()
    try:
        ctl.wait_for("the session's launch", lambda: bool(_launched(ctl, agent.name)), LAUNCH_S)
        ctl.wait_for("the first turn", lambda: _typed(scratch, agent.name, token) > 0, FIRST_TURN_S)
        time.sleep(DUPLICATE_S)
        ops = _ordered(of_session(ctl.ops(), agent.name))
    finally:
        problems = ctl.stop()
    lines = scratch.input_lines(agent.name)
    names = [line.op for line in ops]
    scratch.note("trust dialog", {"ops": names, "input": [(line.phase, line.text[:80]) for line in lines]})
    assert problems == [], problems
    assert "start" not in names, f"gc used the welded start: {names}"
    assert "provision" in names and "launch" in names, names
    assert names.index("provision") < names.index("launch"), names
    keys = [i for i, line in enumerate(ops) if line.op == "send-keys"]
    nudges = [i for i, line in enumerate(ops) if line.op == "nudge"]
    assert keys, f"gc's dialog pass sent no keys: {names}"
    assert nudges and keys[0] < nudges[0], f"a nudge came before the dialog was answered: {names}"
    dialog = [line for line in lines if line.phase == "dialog"]
    assert dialog, "the dialog took no input"
    assert all(token not in line.text for line in dialog), f"the first turn reached the dialog: {dialog}"
    at_prompt = sum(line.text.count(token) for line in lines if line.phase == "prompt")
    assert at_prompt == 1, f"the first turn was typed {at_prompt} times at the prompt: {lines}"


def test_a_refused_first_turn_is_handed_back_and_delivered_exactly_once(scratch: Scratch, gc_bin: str) -> None:
    token = _token()
    agent = CityAgent(name="turn-blocked", mode="blocked", first_turn=f"first turn {token}")
    write_city(scratch, [agent])
    ctl = Controller(scratch, gc_bin)
    ctl.start()
    timeline: Dict[str, float] = {}
    try:
        ctl.wait_for("the session's launch", lambda: bool(_launched(ctl, agent.name)), LAUNCH_S)
        session = _launched(ctl, agent.name)[0].session
        address = Pack(scratch).observe(session).object["id"]
        rpc = HcRpc(scratch.paths().socket)
        ctl.wait_for("hc to read the agent blocked", lambda: rpc.status_word(address) == "blocked", 60.0)
        timeline["launched"] = time.time()

        def refused() -> bool:
            return any(line.op == "nudge" and line.exit == 80 for line in of_session(ctl.ops(), agent.name))

        ctl.wait_for("a refused first turn", refused, REFUSAL_S, step_s=1.0)
        timeline["first refusal"] = time.time()
        assert _typed(scratch, agent.name, token) == 0, "a refused turn was typed"
        Path(os.path.join(scratch.work, f"{agent.name}.release")).touch()
        timeline["released"] = time.time()
        ctl.wait_for("the first turn after the release", lambda: _typed(scratch, agent.name, token) > 0, AFTER_RELEASE_S, step_s=1.0)
        timeline["typed"] = time.time()
        time.sleep(DUPLICATE_S)
        ops = _ordered(of_session(ctl.ops(), agent.name))
        counts = ctl.nudge_counts(agent.name)
    finally:
        problems = ctl.stop()
    nudges = [line for line in ops if line.op == "nudge"]
    refusals = [line for line in nudges if line.exit == 80]
    gaps = [round((b.begun_ms - a.begun_ms) / 1000.0, 2) for a, b in zip(refusals, refusals[1:])]
    scratch.note(
        "refused first turn",
        {
            "refusals": len(refusals),
            "refusal gaps (s)": gaps[:20],
            "nudges": [(line.exit, line.outcome) for line in nudges][:40],
            "timeline (s)": {k: round(v - timeline["launched"], 1) for k, v in timeline.items()},
            "queue": counts,
        },
    )
    assert problems == [], problems
    assert "start" not in [line.op for line in ops], "gc used the welded start"
    assert refusals, "no send was refused while the agent asked its own question"
    assert all(line.outcome == "pending_interaction" for line in refusals), [(r.exit, r.outcome) for r in refusals]
    assert nudges[-1].exit == 0, f"the last send was not a delivery: {[(n.exit, n.outcome) for n in nudges]}"
    assert _typed(scratch, agent.name, token) == 1, "the first turn was not typed exactly once"
    assert counts["dead"] == 0, f"gc dead-lettered a send: {counts}"

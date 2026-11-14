"""A nudge queued while a person types is typed exactly once.

hc holds a ``send`` until the person at the terminal has been quiet for about
3 s, and a held send cannot be cancelled. A person types every second for
60 s, longer than gc's nudge-queue retry delay. The harness plays gc's queue:
it nudges, and redelivers after the queue's delay whenever the pack answers
anything but a delivery, as gc does. Whatever the pack answers, the agent's
input log must show the text exactly once, after the person stops; and
``observe`` must keep answering within its 4 s while the nudge is held.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Dict, List

from livekit.human import Human
from livekit.pack import OpAnswer, Pack
from livekit.scratch import Scratch

HUMAN_S = 60.0
RETRY_DELAY_S = 15.0
"""gc's nudge queue retry delay."""
MAX_ATTEMPTS = 5
OBSERVE_BUDGET_S = 4.0


def _delivered(answer: OpAnswer) -> bool:
    """Exit 0 is a delivery (``delivered``, or ``delivered_unobserved`` in one
    line); exit 80 names a non-success word and exit 1 an unknown outcome,
    both of which gc's queue redelivers."""
    return answer.code == 0


def test_a_nudge_held_by_a_typing_person_is_typed_exactly_once(scratch: Scratch) -> None:
    pack = Pack(scratch, rescope=scratch.lane == "systemd")
    assert pack.start_agent("live-n").code == 0
    seen = pack.wait_state("live-n", ("running",), 15)
    scratch.agent_report("live-n", timeout_s=30)
    human = Human(scratch, seen.object["id"])
    token = f"live-nudge-{uuid.uuid4().hex[:12]}"
    attempts: List[Dict[str, object]] = []
    try:
        typing = threading.Thread(target=human.type_for, args=(HUMAN_S,), daemon=True)
        typing.start()
        time.sleep(3.0)
        assert human.attached(), "hc attach exited"

        def queue() -> None:
            for _ in range(MAX_ATTEMPTS):
                answer = pack.nudge("live-n", token)
                attempts.append(
                    {"at": round(time.time(), 1), "exit": answer.code, "answer": (answer.stdout.strip() or answer.stderr.strip())[:200]}
                )
                if _delivered(answer):
                    return
                time.sleep(RETRY_DELAY_S)

        sender = threading.Thread(target=queue, daemon=True)
        sender.start()
        time.sleep(1.0)
        slowest = 0.0
        while sender.is_alive() and typing.is_alive():
            began = time.monotonic()
            assert pack.observe("live-n").state == "running"
            slowest = max(slowest, time.monotonic() - began)
            time.sleep(2.0)
        typing.join()
        sender.join(timeout=MAX_ATTEMPTS * (RETRY_DELAY_S + 60))
        stopped = human.last_key or time.time()
        end = time.monotonic() + 30
        while token not in scratch.input_text("live-n") and time.monotonic() < end:
            time.sleep(0.5)
        time.sleep(RETRY_DELAY_S + 5)  # a late duplicate would land by now
    finally:
        human.leave()
    lines = [line for line in scratch.input_lines("live-n") if token in line.text]
    scratch.note("exactly-once", {"attempts": attempts, "observe_slowest_s": round(slowest, 2), "typed": len(lines)})
    assert slowest < OBSERVE_BUDGET_S, f"observe took {slowest:.1f} s while the nudge was held"
    assert attempts and attempts[-1]["exit"] == 0, f"the queue never got a delivery: {attempts}"
    count = sum(line.text.count(token) for line in lines)
    assert count == 1, f"the nudge was typed {count} times: {attempts}"
    assert lines[0].at >= stopped - 0.5, "the nudge was typed while the person was still typing"

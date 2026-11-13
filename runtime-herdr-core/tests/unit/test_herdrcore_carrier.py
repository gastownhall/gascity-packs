"""carrier.ops with idle-boundary: gc drives the box only through the pack's
own ops, reads its idle boundary from ``peek <name> 120``, and keeps the
session's ready prompt with ``set-meta``/``get-meta``
(GC_READY_PROMPT_PREFIX)."""

from __future__ import annotations

import json
import time

from cityharness import City

READY_PROMPT_KEY = "GC_READY_PROMPT_PREFIX"


def wait_for_screen(city: City, name: str, text: str, timeout: float = 5.0) -> str:
    end = time.monotonic() + timeout
    shown = ""
    while time.monotonic() < end:
        done = city.run("peek", name, "120")
        assert done.code == 0, done.stderr
        shown = done.text
        if text in shown:
            return shown
        time.sleep(0.05)
    raise AssertionError(f"peek never showed {text!r}: {shown!r}")


def test_peek_120_shows_the_started_agents_output(city: City) -> None:
    config = {"command": "echo GC_RPP_IDLE_READ_mc-a; exec cat"}
    assert city.start("mc-a", json.dumps(config)).code == 0
    assert city.run("is-running", "mc-a").text.strip() == "true"
    wait_for_screen(city, "mc-a", "GC_RPP_IDLE_READ_mc-a")


def test_the_ready_prompt_round_trips_byte_for_byte(city: City) -> None:
    assert city.start("mc-a", json.dumps({"command": "cat"})).code == 0
    for prompt in ("› ", "❯ ", "λ>  ", "$ "):
        stored = city.run("set-meta", "mc-a", READY_PROMPT_KEY, stdin=prompt.encode("utf-8"))
        assert stored.code == 0, stored.stderr
        got = city.run("get-meta", "mc-a", READY_PROMPT_KEY)
        assert got.code == 0 and got.stdout == prompt.encode("utf-8")


def test_stop_drops_the_ready_prompt(city: City) -> None:
    # A new incarnation must not recover the previous one's prompt.
    assert city.start("mc-a", json.dumps({"command": "cat"})).code == 0
    assert city.run("set-meta", "mc-a", READY_PROMPT_KEY, stdin="› ".encode("utf-8")).code == 0
    assert city.run("stop", "mc-a").code == 0
    assert city.run("get-meta", "mc-a", READY_PROMPT_KEY).stdout == b""
    assert city.start("mc-a", json.dumps({"command": "cat"})).code == 0
    assert city.run("get-meta", "mc-a", READY_PROMPT_KEY).stdout == b""

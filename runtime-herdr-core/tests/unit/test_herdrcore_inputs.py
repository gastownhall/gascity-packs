"""nudge, send-keys, interrupt and the first turn, with RPP v0 outcomes:
delivered or gone exit 0, every refusal and every unknown outcome exits 1."""

from __future__ import annotations

import json
import time
from typing import List, Optional

import pytest
from cityharness import City, Result, in_thread
from fakehc.terminal import key_bytes

from gc_runtime_herdr_core.herdrcore.inputs import translate_key, translate_keys


def wait_for(predicate: "object", timeout: float = 10.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


@pytest.mark.parametrize(
    "key, names",
    [
        ("Enter", ["enter"]),
        ("Escape", ["esc"]),
        ("BSpace", ["backspace"]),
        ("Tab", ["tab"]),
        ("BTab", ["shift+tab"]),
        ("Down", ["down"]),
        ("PPage", ["pageup"]),
        ("NPage", ["pagedown"]),
        ("DC", ["delete"]),
        ("F5", ["f5"]),
        ("C-c", ["ctrl+c"]),
        ("M-x", ["alt+x"]),
        ("C-M-a", ["ctrl+alt+a"]),
        ("C-Up", ["ctrl+up"]),
        ("y", ["y"]),
        ("1", ["1"]),
        ("Y", ["shift+y"]),
        ("ok go", ["o", "k", "space", "g", "o"]),
        ("/", ["/"]),
    ],
)
def test_tmux_keys_map_to_hc_names(key: str, names: List[str]) -> None:
    assert translate_key(key) == names
    # Every name is one hc's key parser accepts (fake-hc follows keys.rs).
    assert all(key_bytes(name) is not None for name in names)


@pytest.mark.parametrize("key", ["!", "é", "C-!", "", "Hello!"])
def test_keys_with_no_hc_spelling_are_rejected(key: str) -> None:
    assert translate_key(key) is None


def test_one_untranslatable_key_rejects_the_whole_request() -> None:
    assert translate_keys(["Down", "!", "Enter"]) == (None, "!")


def started(city: City, config: Optional[dict] = None) -> str:  # type: ignore[type-arg]
    doc = config or {"command": "cat"}
    done = city.start("mc-a", json.dumps(doc))
    assert done.code == 0, done.stderr
    return city.address("mc-a")


def test_nudge_types_once_and_exits_0(city: City) -> None:
    address = started(city)
    assert city.run("nudge", "mc-a", stdin=b"hello agent").code == 0
    assert city.fake.input_log(address) == ["hello agent"]  # type: ignore[union-attr]
    assert city.run("nudge", "nobody", stdin=b"x").code == 0  # gone


def test_nudge_refused_while_blocked_types_nothing(city: City) -> None:
    address = started(city)
    city.fake.set_status(address, "blocked", kind="permission")  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"go on")
    assert done.code == 1 and "pending interaction" in done.stderr
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


def test_a_send_hc_holds_past_the_deadline_is_delivered_and_typed_once(city: City) -> None:
    # A person keeps typing: hc holds the send and types it once they stop.
    # Written is delivered (tmux's send-keys is fire-and-forget too), so
    # gc's queue never sends the same text again.
    address = started(city)
    city.fake.hold_input(address)  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"check your mail", deadline_ms=7000)
    assert done.code == 0, done.stderr
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]
    city.fake.release_input(address)  # type: ignore[union-attr]
    wait_for(lambda: city.fake.input_log(address) == ["check your mail"])  # type: ignore[union-attr]
    time.sleep(0.3)
    assert city.fake.input_log(address) == ["check your mail"]  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.send") == 1  # type: ignore[union-attr]


def test_a_reply_lost_after_the_write_is_delivered(city: City) -> None:
    address = started(city)
    city.fake.drop_reply("terminal.send")  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"hello")
    assert done.code == 0, done.stderr
    assert city.fake.input_log(address) == ["hello"]  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.send") == 1  # type: ignore[union-attr]


def test_nothing_written_is_not_sent(city: City) -> None:
    address = started(city)
    city.fake.set_generation(2)  # type: ignore[union-attr]  # the gate refuses before the send is written
    done = city.run("nudge", "mc-a", stdin=b"hello")
    assert done.code == 1 and "not sent" in done.stderr
    city.fake.set_generation(1)  # type: ignore[union-attr]
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


@pytest.mark.parametrize("kind, phrase", [("unavailable", "not sent"), ("blocked", "pending interaction"), ("status_mismatch", "not sent")])
def test_definitive_refusals_are_not_sent(city: City, kind: str, phrase: str) -> None:
    address = started(city)
    city.fake.fail_next("terminal.send", kind)  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"hello")
    assert done.code == 1 and phrase in done.stderr
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


@pytest.mark.parametrize("kind", ["not_found", "finished"])
def test_a_gone_terminal_answers_0(city: City, kind: str) -> None:
    started(city)
    city.fake.fail_next("terminal.send", kind)  # type: ignore[union-attr]
    assert city.run("nudge", "mc-a", stdin=b"hello").code == 0


def test_keys_timeout_after_write_exits_1(city: City) -> None:
    address = started(city)
    city.fake.hold_input(address)  # type: ignore[union-attr]
    done = city.run("send-keys", "mc-a", "Enter", deadline_ms=3000)
    assert done.code == 1 and "unconfirmed" in done.stderr
    city.fake.release_input(address)  # type: ignore[union-attr]


def test_send_keys_translates_and_rejects(city: City) -> None:
    address = started(city)
    assert city.run("send-keys", "mc-a", "Down", "Enter").code == 0
    assert city.fake.key_log(address) == ["down", "enter"]  # type: ignore[union-attr]
    rejected = city.run("send-keys", "mc-a", "Down", "!")
    assert rejected.code == 1 and "rejected" in rejected.stderr
    assert city.fake.key_log(address) == ["down", "enter"]  # type: ignore[union-attr]


def test_interrupt_timeout_after_write_exits_1_and_is_not_retried(city: City) -> None:
    started(city)
    city.fake.delay_reply("terminal.interrupt", 5.0)  # type: ignore[union-attr]
    done = city.run("interrupt", "mc-a", deadline_ms=3000)
    assert done.code == 1 and "unconfirmed" in done.stderr
    assert city.fake.call_count("terminal.interrupt") == 1  # type: ignore[union-attr]


def test_interrupt_and_clear_scrollback_answer_0(city: City) -> None:
    started(city, {"command": "sleep 60"})
    assert city.run("interrupt", "mc-a").code == 0
    assert city.run("interrupt", "nobody").code == 0
    assert city.run("clear-scrollback", "nobody").code == 0


def test_driving_ops_with_the_core_down_exit_1(city: City) -> None:
    started(city)
    fault = {"GC_RPP_FAULT": "unavailable"}
    for op, args, stdin in (("nudge", (), b"x"), ("send-keys", ("Enter",), b""), ("interrupt", (), b"")):
        done = city.run(op, "mc-a", *args, stdin=stdin, extra=fault)
        assert done.code == 1, op


def test_first_turn_is_typed_once_the_prompt_shows(city: City) -> None:
    config = {"command": "printf 'booting\\n'; sleep 0.3; printf 'READY> \\n'; exec cat", "nudge": "first task", "ready_prompt_prefix": "READY>"}
    done = city.start("mc-a", json.dumps(config))
    assert done.code == 0, done.stderr
    address = city.address("mc-a")
    assert city.fake.input_log(address) == ["first task"]  # type: ignore[union-attr]
    screen = city.fake.terminal_env(address)  # type: ignore[union-attr]
    assert screen  # the terminal exists with its environment


def test_first_turn_refused_is_recorded_and_not_typed(city: City) -> None:
    city.fake.fail_next("terminal.send", "blocked")  # type: ignore[union-attr]
    config = {"command": "printf 'READY>\\n'; exec cat", "nudge": "first task", "ready_prompt_prefix": "READY>"}
    done = city.start("mc-a", json.dumps(config))
    assert done.code == 0, done.stderr
    assert "first turn" in done.stderr
    address = city.address("mc-a")
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]
    marker = city.run("get-meta", "mc-a", "GC_STARTUP_DELIVERY_UNCONFIRMED")
    assert b"pending interaction" in marker.stdout


def test_nudge_held_does_not_block_a_stop(city: City) -> None:
    address = started(city)
    city.fake.hold_input(address)  # type: ignore[union-attr]
    results: List[Result] = []
    thread = in_thread(lambda: results.append(city.run("nudge", "mc-a", stdin=b"held", deadline_ms=10000)))
    wait_for(lambda: city.fake.call_count("terminal.send") == 1)  # type: ignore[union-attr]
    stopped = city.run("stop", "mc-a")
    assert stopped.code == 0, stopped.stderr
    assert city.terminals() == []
    thread.join(timeout=20)
    assert results and results[0].code == 0  # written: delivered as far as gc is concerned


def test_a_held_nudge_answers_well_before_gc_stops_waiting(city: City) -> None:
    # A held send is delivered, so the answer must reach gc: a reply cut
    # off by gc's own deadline reads as a failure and the queue resends.
    from gc_runtime_herdr_core.herdrcore.inputs import NUDGE_SEND_RESERVE_S

    assert NUDGE_SEND_RESERVE_S >= 5.0
    address = started(city)
    city.fake.hold_input(address)  # type: ignore[union-attr]
    began = time.monotonic()
    done = city.run("nudge", "mc-a", stdin=b"x", deadline_ms=6500)
    elapsed = time.monotonic() - began
    assert done.code == 0, done.stderr
    assert elapsed < 6.5 - NUDGE_SEND_RESERVE_S + 1.0, elapsed
    city.fake.release_input(address)  # type: ignore[union-attr]

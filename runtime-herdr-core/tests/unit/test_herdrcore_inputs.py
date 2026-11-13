"""nudge, send-keys, interrupt, clear-scrollback and the first turn, with
typed input outcomes: exit 0 for a delivery, exit 80 and one outcome line for
every other outcome, exit 1 when the outcome is unknown."""

from __future__ import annotations

import json
import time
from typing import List, Mapping, Optional, Tuple

import pytest
from cityharness import City, Result, in_thread
from fakehc.terminal import key_bytes

from gc_runtime_herdr_core.herdrcore import lifecycle
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


def answer(done: Result) -> Tuple[int, Optional[str]]:
    """A driving op's exit code and outcome word (None: no line).

    Every answer is one gc reads as typed: exit 0 prints nothing or one
    success line, exit 80 exactly one line with a non-success word."""
    word: Optional[str] = None
    if done.stdout:
        lines = done.stdout.split(b"\n")
        assert lines[-1] == b"" and len(lines) == 2, done.stdout
        word = str(json.loads(lines[0])["outcome"])
    if done.code == 0:
        assert word in (None, "delivered", "delivered_unobserved"), done.stdout
    elif done.code == 80:
        assert word in NON_SUCCESS, done.stdout
    else:
        assert word is None, done.stdout
    return done.code, word


NON_SUCCESS = {"unconfirmed", "not_sent", "rejected", "busy", "pending_interaction", "unavailable", "gone"}
DRIVING: Tuple[Tuple[str, Tuple[str, ...], bytes], ...] = (
    ("nudge", (), b"gc-input"),
    ("send-keys", ("Enter",), b""),
    ("clear-scrollback", (), b""),
    ("interrupt", (), b""),
)


def test_nudge_to_a_program_that_never_reports_status_is_delivered(city: City) -> None:
    address = started(city)
    assert answer(city.run("nudge", "mc-a", stdin=b"hello agent")) == (0, None)
    assert city.fake.input_log(address) == ["hello agent"]  # type: ignore[union-attr]


def test_nudge_seen_starting_the_turn_is_delivered(city: City) -> None:
    address = started(city)
    city.fake.set_status(address, "idle")  # type: ignore[union-attr]
    city.fake.work_on_send(address)  # type: ignore[union-attr]
    assert answer(city.run("nudge", "mc-a", stdin=b"go")) == (0, None)


def test_nudge_not_seen_starting_the_turn_is_delivered_unobserved(city: City) -> None:
    # The program reports its status, but did not go working within hc's window.
    address = started(city)
    city.fake.set_status(address, "idle")  # type: ignore[union-attr]
    assert answer(city.run("nudge", "mc-a", stdin=b"go")) == (0, "delivered_unobserved")
    assert city.fake.input_log(address) == ["go"]  # type: ignore[union-attr]


@pytest.mark.parametrize("op, args, stdin", DRIVING)
def test_a_name_no_box_holds_is_gone(city: City, op: str, args: Tuple[str, ...], stdin: bytes) -> None:
    started(city)
    assert answer(city.run(op, "nobody", *args, stdin=stdin)) == (80, "gone")


@pytest.mark.parametrize("op, args, stdin", DRIVING)
def test_a_dead_box_is_gone_and_gets_nothing(city: City, op: str, args: Tuple[str, ...], stdin: bytes) -> None:
    # gone is "no running box holds the name": a finished record is a dead box.
    started(city, {"command": "exit 0", "lifecycle": "one_shot"})
    wait_for(lambda: all(t["state"] == "finished" for t in city.terminals()))
    assert city.run("observe", "mc-a").text.find('"dead"') >= 0
    assert answer(city.run(op, "mc-a", *args, stdin=stdin)) == (80, "gone")


def test_nudge_refused_while_blocked_is_pending_interaction_and_types_nothing(city: City) -> None:
    address = started(city)
    city.fake.set_status(address, "blocked", kind="permission")  # type: ignore[union-attr]
    assert answer(city.run("nudge", "mc-a", stdin=b"go on")) == (80, "pending_interaction")
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


def test_a_send_hc_holds_past_the_deadline_is_delivered_unobserved_and_typed_once(city: City) -> None:
    # A person keeps typing: hc holds the send and types it once they stop.
    # Written is delivered (tmux's send-keys is fire-and-forget too), so
    # gc's queue never sends the same text again.
    address = started(city)
    city.fake.hold_input(address)  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"check your mail", deadline_ms=7000)
    assert answer(done) == (0, "delivered_unobserved"), done.stderr
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]
    city.fake.release_input(address)  # type: ignore[union-attr]
    wait_for(lambda: city.fake.input_log(address) == ["check your mail"])  # type: ignore[union-attr]
    time.sleep(0.3)
    assert city.fake.input_log(address) == ["check your mail"]  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.send") == 1  # type: ignore[union-attr]


def test_a_reply_lost_after_the_write_is_delivered_unobserved(city: City) -> None:
    address = started(city)
    city.fake.drop_reply("terminal.send")  # type: ignore[union-attr]
    assert answer(city.run("nudge", "mc-a", stdin=b"hello")) == (0, "delivered_unobserved")
    assert city.fake.input_log(address) == ["hello"]  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.send") == 1  # type: ignore[union-attr]


def test_a_send_the_core_stopped_reading_part_way_is_not_sent(city: City) -> None:
    # hc acts on no part of a request: a nudge the socket's buffers cut short
    # types nothing, so gc's queue may send it again.
    address = started(city)
    city.fake.stall_reading(1 << 16)  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"x" * (4 << 20), deadline_ms=7000)
    assert answer(done) == (80, "not_sent"), done.stderr
    city.fake.resume_reading()  # type: ignore[union-attr]
    wait_for(lambda: city.fake.open_connections == 0)  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.send") == 0  # type: ignore[union-attr]
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


@pytest.mark.parametrize("op, args, stdin", DRIVING)
def test_a_core_the_gate_refuses_is_an_untyped_failure(city: City, op: str, args: Tuple[str, ...], stdin: bytes) -> None:
    address = started(city)
    city.fake.set_generation(2)  # type: ignore[union-attr]  # the gate refuses before anything is written
    done = city.run(op, "mc-a", *args, stdin=stdin)
    assert answer(done) == (1, None) and "hc version unsupported" in done.stderr
    city.fake.set_generation(1)  # type: ignore[union-attr]
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "kind, word",
    [("unavailable", "not_sent"), ("blocked", "pending_interaction"), ("status_mismatch", "busy"), ("not_found", "gone"), ("finished", "gone")],
)
def test_hcs_refusals_map_to_gcs_words(city: City, kind: str, word: str) -> None:
    address = started(city)
    city.fake.fail_next("terminal.send", kind)  # type: ignore[union-attr]
    assert answer(city.run("nudge", "mc-a", stdin=b"hello")) == (80, word)
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]


@pytest.mark.parametrize("kind", ["config", "invalid_params", "internal", "a_kind_hc_has_not_got"])
def test_any_other_refusal_is_an_untyped_failure_naming_it(city: City, kind: str) -> None:
    started(city)
    city.fake.fail_next("terminal.send", kind)  # type: ignore[union-attr]
    done = city.run("nudge", "mc-a", stdin=b"hello")
    assert answer(done) == (1, None) and kind in done.stderr


@pytest.mark.parametrize("op, args, stdin", DRIVING)
def test_driving_ops_with_the_core_down_are_unavailable(city: City, op: str, args: Tuple[str, ...], stdin: bytes) -> None:
    address = started(city)
    done = city.run(op, "mc-a", *args, stdin=stdin, extra={"GC_RPP_FAULT": "unavailable"})
    assert answer(done) == (80, "unavailable"), done.stderr
    assert city.fake.input_log(address) == [] and city.fake.key_log(address) == []  # type: ignore[union-attr]


def test_send_keys_translates_and_delivers(city: City) -> None:
    address = started(city)
    assert answer(city.run("send-keys", "mc-a", "Down", "Enter")) == (0, None)
    assert city.fake.key_log(address) == ["down", "enter"]  # type: ignore[union-attr]


@pytest.mark.parametrize("name", ["mc-a", "nobody"])
def test_a_key_with_no_herdr_core_spelling_is_rejected(city: City, name: str) -> None:
    address = started(city)
    done = city.run("send-keys", name, "Down", "!")
    assert answer(done) == (80, "rejected")
    assert "'!'" in json.loads(done.stdout)["detail"]
    assert city.fake.key_log(address) == []  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.keys") == 0  # type: ignore[union-attr]


def test_keys_timeout_after_write_exits_1(city: City) -> None:
    address = started(city)
    city.fake.hold_input(address)  # type: ignore[union-attr]
    done = city.run("send-keys", "mc-a", "Enter", deadline_ms=3000)
    assert answer(done) == (1, None) and "unknown" in done.stderr
    city.fake.release_input(address)  # type: ignore[union-attr]


def test_keys_reply_lost_after_write_exits_1(city: City) -> None:
    started(city)
    city.fake.drop_reply("terminal.keys")  # type: ignore[union-attr]
    done = city.run("send-keys", "mc-a", "Enter")
    assert answer(done) == (1, None) and "unknown" in done.stderr
    assert city.fake.call_count("terminal.keys") == 1  # type: ignore[union-attr]


def test_keys_refused_as_unavailable_is_not_sent(city: City) -> None:
    started(city)
    city.fake.fail_next("terminal.keys", "unavailable")  # type: ignore[union-attr]
    assert answer(city.run("send-keys", "mc-a", "Enter")) == (80, "not_sent")


def test_interrupt_timeout_after_write_exits_1_and_is_not_retried(city: City) -> None:
    started(city)
    city.fake.delay_reply("terminal.interrupt", 5.0)  # type: ignore[union-attr]
    done = city.run("interrupt", "mc-a", deadline_ms=3000)
    assert answer(done) == (1, None) and "unknown" in done.stderr
    assert city.fake.call_count("terminal.interrupt") == 1  # type: ignore[union-attr]


def test_interrupt_is_delivered_whatever_hc_observed(city: City) -> None:
    started(city, {"command": "sleep 60"})
    assert answer(city.run("interrupt", "mc-a")) == (0, None)


def test_interrupt_without_a_name_is_gone(city: City) -> None:
    assert answer(city.run("interrupt", "")) == (80, "gone")


def test_clear_scrollback_is_a_delivered_no_op(city: City) -> None:
    address = started(city)
    assert answer(city.run("clear-scrollback", "mc-a")) == (0, None)
    assert city.fake.input_log(address) == [] and city.fake.key_log(address) == []  # type: ignore[union-attr]


def test_clear_scrollback_reply_lost_after_write_exits_1(city: City) -> None:
    started(city)
    city.fake.drop_reply("terminal.get")  # type: ignore[union-attr]
    city.fake.drop_reply("terminal.get")  # type: ignore[union-attr]  # a read is retried once
    done = city.run("clear-scrollback", "mc-a")
    assert answer(done) == (1, None) and "unknown" in done.stderr


# --- conformance faults (GC_RPP_FAULT, declared conformance-faults) ------------------------


def faulted(city: City, fault: str, op: str, args: Tuple[str, ...] = (), stdin: bytes = b"") -> Result:
    return city.run(op, "mc-a", *args, stdin=stdin, extra={"GC_RPP_FAULT": fault})


def test_fault_blocked_refuses_a_nudge_and_types_nothing(city: City) -> None:
    address = started(city)
    assert answer(faulted(city, "blocked", "nudge", stdin=b"go")) == (80, "pending_interaction")
    assert city.fake.input_log(address) == []  # type: ignore[union-attr]
    assert city.fake.call_count("terminal.send") == 0  # type: ignore[union-attr]
    # Keys answer an agent's question: hc does not refuse them.
    assert answer(faulted(city, "blocked", "send-keys", ("Enter",))) == (0, None)


def test_fault_lose_reply_delivers_a_nudge_once_and_leaves_key_ops_unknown(city: City) -> None:
    # The input is typed, then the reply is lost: a written nudge is
    # delivered (never typed again), a key op's outcome is unknown.
    address = started(city)
    assert answer(faulted(city, "lose_reply", "nudge", stdin=b"once")) == (0, "delivered_unobserved")
    assert city.fake.input_log(address) == ["once"]  # type: ignore[union-attr]
    for op, args in (("send-keys", ("Enter",)), ("clear-scrollback", ()), ("interrupt", ())):
        done = faulted(city, "lose_reply", op, args)
        assert answer(done) == (1, None), (op, done.stderr)


def test_fault_hold_send_answers_a_held_nudge_delivered(city: City) -> None:
    address = started(city)
    assert answer(faulted(city, "hold_send", "nudge", stdin=b"held")) == (0, "delivered_unobserved")
    assert city.fake.input_log(address) == ["held"]  # type: ignore[union-attr]


def test_fault_dead_reads_dead_and_every_driving_op_is_gone(city: City) -> None:
    address = started(city)
    observed = json.loads(faulted(city, "dead", "observe").stdout)
    assert observed["state"] == "dead"
    for op, args, stdin in DRIVING:
        assert answer(faulted(city, "dead", op, args, stdin)) == (80, "gone"), op
    assert city.fake.input_log(address) == [] and city.fake.key_log(address) == []  # type: ignore[union-attr]
    assert json.loads(city.run("observe", "mc-a").stdout)["state"] == "running"


@pytest.mark.parametrize("fault", ["", "unavailable", "blocked", "lose_reply", "hold_send", "dead"])
def test_no_answer_prints_a_non_success_word_on_exit_0(city: City, fault: str) -> None:
    started(city)
    for name in ("mc-a", "nobody"):
        for op, args, stdin in DRIVING:
            done = city.run(op, name, *args, stdin=stdin, extra={"GC_RPP_FAULT": fault} if fault else None)
            answer(done)  # asserts the shape


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


def withheld(city: City, config: Mapping[str, object], **kwargs: object) -> str:
    """Start with ``config``; what the start warned, once sure nothing was typed and the strand is recorded."""
    done = city.start("mc-a", json.dumps({**config, "nudge": "first task"}), **kwargs)
    assert done.code == 0, done.stderr
    assert city.fake.input_log(city.address("mc-a")) == []  # type: ignore[union-attr]
    marker = city.run("get-meta", "mc-a", "GC_STARTUP_DELIVERY_UNCONFIRMED")
    assert b"the first turn was withheld" in marker.stdout
    return done.stderr


def typed(city: City, config: Mapping[str, object], **kwargs: object) -> Tuple[float, str]:
    """Start with ``config``; how long the start took and what it warned,
    once sure the first turn was typed and nothing recorded."""
    began = time.monotonic()
    done = city.start("mc-a", json.dumps({**config, "nudge": "first task"}), **kwargs)
    elapsed = time.monotonic() - began
    assert done.code == 0, done.stderr
    assert city.fake.input_log(city.address("mc-a")) == ["first task"]  # type: ignore[union-attr]
    assert city.run("get-meta", "mc-a", "GC_STARTUP_DELIVERY_UNCONFIRMED").stdout == b""
    return elapsed, done.stderr


def typed_after(city: City, config: Mapping[str, object], **kwargs: object) -> float:
    """Start with ``config``; how long the start took, once sure the first turn was typed and nothing recorded."""
    return typed(city, config, **kwargs)[0]


def test_a_menus_cursor_row_is_no_prompt(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    # The selected option carries the prompt glyph: it is never read as
    # ready, so the turn waits out the wait; a menu gc does not know as a
    # dialog then gets it, as gc's providers type it.
    monkeypatch.setattr(lifecycle, "READY_WAIT_S", 1.5)
    config = {"command": "printf '❯ 1. Pick one\\n  2. Or this\\n'; exec cat", "ready_prompt_prefix": "❯ "}
    assert typed_after(city, config) >= 1.5


def test_a_settled_dialog_with_no_prompt_prefix_withholds_the_first_turn(city: City) -> None:
    # gc answers it only once start returns, so start does not wait it out.
    config = {"command": "printf 'Do you trust the files in this folder?\\n❯ 1. Yes, proceed\\n  2. No, exit\\n'; exec cat"}
    assert "the first turn was withheld: the agent shows a startup dialog" in withheld(city, config)


def test_a_settled_dialog_withholds_the_first_turn_whatever_the_prompt_prefix(city: City) -> None:
    config = {
        "command": "printf 'Do you trust the files in this folder?\\n❯ 1. Yes, proceed\\n  2. No, exit\\n'; exec cat",
        "ready_prompt_prefix": "❯ ",
    }
    assert "the first turn was withheld: the agent shows a startup dialog" in withheld(city, config)


@pytest.mark.parametrize(
    "screen, extra",
    [
        ("Rate limit reached\\n1. Keep trying\\n2. Stop\\n", {}),  # gc's provider rate-limit screen
        ("rate limit\\n❯ 1. Retry\\n  2. Wait\\n", {"ready_prompt_prefix": "❯ "}),  # a mention beside a cursor row
    ],
)
def test_a_rate_limit_menu_withholds_the_first_turn(city: City, screen: str, extra: Mapping[str, object]) -> None:
    # gc's startup pass answers it "Stop" once start returns: typed first,
    # the turn's Enter would pick "Keep trying", and gc would never see it.
    config = {"command": f"printf '{screen}'; exec cat", **extra}
    assert "the first turn was withheld: the agent shows a startup dialog" in withheld(city, config)


def test_a_boot_slower_than_the_wait_gets_its_turn_typed(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    # gc's providers type the turn on a probe that timed out; nothing in gc
    # types it later for an exec runtime.
    monkeypatch.setattr(lifecycle, "READY_WAIT_S", 1.0)
    config = {"command": "printf 'booting\\n'; exec cat", "ready_prompt_prefix": "READY>"}
    elapsed, warned = typed(city, config)
    assert elapsed >= 1.0
    assert "the first turn was typed without readiness: the wait ran out" in warned


def test_a_delay_the_deadline_cuts_types_the_first_turn_at_the_waits_end(city: City) -> None:
    # 9 s less the 5 s reserve leave a wait of up to 4 s, which the screen
    # settles in, and which ends before the delay.
    config = {"command": "printf 'booting\\n'; exec cat", "ready_delay_ms": 6000}
    _, warned = typed(city, config, deadline_ms=9000)
    assert "the first turn was typed without readiness: the op's deadline cut the wait short" in warned


def test_a_wait_the_deadline_leaves_no_time_withholds_the_first_turn(city: City) -> None:
    # With 5 s or less left there is no wait, so no screen settles: a dialog
    # may not be drawn yet, and a turn typed into it would pick its option.
    warned = withheld(city, {"command": "printf 'booting\\n'; exec cat"}, deadline_ms=4500)
    assert "the first turn was withheld: the op's deadline ended the wait before the agent's screen settled" in warned


def test_a_delay_past_the_wait_types_the_first_turn_at_its_end(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    # gc cuts a delay to its probe timeout, and types the turn then.
    monkeypatch.setattr(lifecycle, "READY_WAIT_S", 1.0)
    config = {"command": "printf 'booting\\n'; exec cat", "ready_delay_ms": 5000, "nudge": "first task"}
    done = city.start("mc-a", json.dumps(config))
    assert done.code == 0, done.stderr
    assert city.fake.input_log(city.address("mc-a")) == ["first task"]  # type: ignore[union-attr]


def test_a_status_line_mentioning_rate_limits_under_a_prompt_is_ready(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "READY_WAIT_S", 5.0)  # a miss shows as a slow start
    config = {"command": "printf 'READY> \\n  rate limit: 40%% used\\n'; exec cat", "ready_prompt_prefix": "READY>"}
    assert typed_after(city, config) < 4.0


def test_a_tip_mentioning_rate_limits_gets_the_turn_at_the_waits_end(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    # A bare mention with no menu is no dialog gc knows: it delays the turn, never withholds it.
    monkeypatch.setattr(lifecycle, "READY_WAIT_S", 1.5)
    config = {"command": "printf 'Welcome\\nTip: avoid hitting the rate limit by...\\n'; exec cat", "ready_prompt_prefix": "❯ "}
    assert typed_after(city, config) >= 1.5


def test_a_prompt_with_a_non_breaking_space_is_ready(city: City, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lifecycle, "READY_WAIT_S", 5.0)  # a miss fails fast
    config = {"command": "printf '❯\u00a0Try it\\n'; exec cat", "nudge": "first task", "ready_prompt_prefix": "❯ "}
    done = city.start("mc-a", json.dumps(config))
    assert done.code == 0, done.stderr
    assert city.fake.input_log(city.address("mc-a")) == ["first task"]  # type: ignore[union-attr]


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

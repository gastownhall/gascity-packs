"""Reading hc terminal records as gc boxes: intact, broken, the newest record
of a name, and the box object."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from gc_runtime_herdr_core.hc.parse import parse_terminal
from gc_runtime_herdr_core.hc.types import Terminal
from gc_runtime_herdr_core.herdrcore.naming import is_object_nonce, terminal_name
from gc_runtime_herdr_core.herdrcore.records import box_object, for_session, is_broken, is_intact, newest


def record(
    address: str = "t1",
    *,
    state: str = "live",
    pid: Optional[int] = 100,
    labels: Optional[Dict[str, str]] = None,
    reason: Optional[str] = None,
    keep: bool = False,
    created_ms: int = 1_700_000_000_000,
) -> Terminal:
    doc: Dict[str, Any] = {
        "address": address,
        "labels": {"gc.session": "mc-a", "gc.pid": "100"} if labels is None else labels,
        "argv": ["python3"],
        "cwd": "/",
        "state": state,
        "created_ms": created_ms,
        "screen": "exact",
        "cols": 200,
        "rows": 120,
        "pid": pid,
        "reason": reason,
        "keep": keep,
    }
    return parse_terminal(doc)


def test_a_live_record_running_the_started_program_is_intact() -> None:
    assert is_intact(record())
    assert not is_broken(record())


@pytest.mark.parametrize(
    "terminal",
    [
        record(pid=None, reason="holder_lost", keep=True),  # waiting for a new shell
        record(pid=200),  # a kept terminal's replacement shell: another pid
        record(reason="signaled", keep=True),
        record(reason="stopped_by_restart"),
        record(reason="spawn_pending", pid=None, keep=True),
    ],
)
def test_live_but_not_the_started_program_is_broken(terminal: Terminal) -> None:
    assert not is_intact(terminal) and is_broken(terminal)


def test_finished_is_neither_intact_nor_broken() -> None:
    done = record(state="finished", reason="exited")
    assert not is_intact(done) and not is_broken(done)


def test_before_the_pid_label_is_written() -> None:
    assert is_intact(record(labels={"gc.session": "mc-a"}))
    assert not is_intact(record(labels={"gc.session": "mc-a"}, keep=True))


def test_the_newest_record_holds_the_name() -> None:
    old = record("t3", created_ms=1, state="finished")
    new = record("t7", created_ms=2)
    same_ms = record("t9", created_ms=2)
    other = record("t4", created_ms=5, labels={"gc.session": "mc-b"})
    assert newest([old, new, other], "mc-a") is new
    assert newest([old, new, same_ms], "mc-a") is same_ms
    assert [t.address for t in for_session([old, new, other], "mc-a")] == ["t7", "t3"]
    assert newest([other], "mc-a") is None


def test_the_box_object_is_the_address_and_creation_time() -> None:
    obj = box_object(record("t12", created_ms=1_700_000_000_123))
    assert obj.id == "t12" and obj.created == "2023-11-14T22:13:20.123Z"


def test_terminal_names_fit_hc_and_never_look_like_an_address() -> None:
    names = {terminal_name("c" * 64, f"mc-{n}") for n in range(200)}
    assert len(names) == 200
    for name in names:
        assert len(name) == 21 and name[0] == "g" and name == name.lower()
        assert set(name[1:]) <= set("abcdefghijklmnopqrstuvwxyz234567")
    assert terminal_name("a" * 64, "x") != terminal_name("b" * 64, "x")
    assert is_object_nonce("0" * 32) and not is_object_nonce("../x") and not is_object_nonce("A" * 32)


@pytest.mark.parametrize(
    "address, n",
    [("t1", 1), ("t9", 9), ("t10", 10), ("t19", 19), ("t1b", 20), ("t1z", 39), ("t20", 40), ("t9z", 279), ("t100", 280), ("t9zz", 8379), ("t1000", 8380), ("t65jk", 148377)],
)
def test_hc_addresses_parse_as_hc_writes_them(address: str, n: int) -> None:
    # hc's own vectors (terminals.rs address tests).
    from gc_runtime_herdr_core.hc.address import address_of, parse_address

    assert parse_address(address) == n
    assert address_of(n) == address


def test_ties_break_on_the_address_counter() -> None:
    older = record("t19", created_ms=5)
    newer = record("t1b", created_ms=5)  # 20, after t19
    assert newest([newer, older], "mc-a") is newer
    assert newest([older, newer], "mc-a") is newer

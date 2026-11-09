"""hc replies parsed at the edge: tolerant of unknown fields, strict on required ones."""

from __future__ import annotations

import copy
from typing import Dict

import pytest

from gc_runtime_herdr_core.hc.parse import (
    parse_hello,
    parse_interrupt,
    parse_keys,
    parse_list,
    parse_read,
    parse_remove,
    parse_send,
    parse_status,
    parse_stop,
    parse_terminal,
)
from gc_runtime_herdr_core.rpp.jsonval import JsonShapeError

TERMINAL: Dict[str, object] = {
    "address": "t7",
    "labels": {"gc.session": "mc-mayor"},
    "argv": ["/usr/bin/python3", "-I"],
    "cwd": "/w",
    "state": "live",
    "created_ms": 1762682400123,
    "screen": "exact",
    "cols": 200,
    "rows": 120,
}


def terminal(**overrides: object) -> Dict[str, object]:
    out = copy.deepcopy(TERMINAL)
    out.update(overrides)
    return out


def test_minimal_terminal_takes_schema_defaults() -> None:
    t = parse_terminal(terminal())
    assert t.address == "t7"
    assert dict(t.labels) == {"gc.session": "mc-mayor"}
    assert t.is_live and not t.is_finished
    assert t.created_ms == 1762682400123
    assert t.name is None and t.pid is None and t.foreground is None
    assert t.keep is False and t.reported is False and t.turn == 0
    assert t.status is None and dict(t.records) == {} and t.status_ms is None
    assert t.reason is None and t.exit_code is None and t.signal is None


def test_full_terminal() -> None:
    t = parse_terminal(
        terminal(
            name="gabc",
            pid=4242,
            foreground={"pid": 4243, "name": "node", "argv": ["node", "claude"], "cwd": "/w"},
            reason="holder_lost",
            keep=True,
            reported=True,
            status={"state": "blocked", "kind": "permission", "app": "claude", "progress": 40, "title": "t", "msg": "m"},
            records={"sub": {"state": "working"}},
            status_ms=1762682400999,
            turn=4,
            state="finished",
            exit_code=None,
            signal=9,
            finished_ms=1762682401000,
            parent="t3",
            some_future_field={"x": 1},
        )
    )
    assert t.pid == 4242
    assert t.foreground is not None and t.foreground.argv == ("node", "claude")
    assert t.reason == "holder_lost" and t.keep is True and t.is_finished
    assert t.status is not None and t.status.state == "blocked" and t.status.kind == "permission"
    assert t.status.app == "claude" and t.status.progress == 40
    assert not hasattr(t.status, "msg") and not hasattr(t.status, "title")  # text is never carried
    assert t.records["sub"].state == "working"
    assert t.status_ms == 1762682400999 and t.turn == 4 and t.signal == 9


@pytest.mark.parametrize("field", ["address", "labels", "argv", "cwd", "state", "created_ms", "screen", "cols", "rows"])
def test_required_terminal_fields(field: str) -> None:
    doc = terminal()
    del doc[field]
    with pytest.raises(JsonShapeError, match=field):
        parse_terminal(doc)


@pytest.mark.parametrize(
    ("field", "value"),
    [("created_ms", True), ("created_ms", 1.5), ("pid", "4242"), ("keep", 1), ("labels", {"k": 1}), ("argv", "sh")],
)
def test_mistyped_terminal_fields(field: str, value: object) -> None:
    with pytest.raises(JsonShapeError, match=field):
        parse_terminal(terminal(**{field: value}))


def test_shape_errors_name_the_field_never_the_value() -> None:
    with pytest.raises(JsonShapeError) as caught:
        parse_terminal(terminal(labels={"gc.secret": 12345678901}))
    assert "12345678901" not in str(caught.value)


def test_list_tolerates_hc_190_missing_machines() -> None:
    listed = parse_list({"terminals": [terminal()], "hidden_finished": 2})
    assert [t.address for t in listed.terminals] == ["t7"]
    assert listed.hidden_finished == 2
    assert parse_list({"terminals": [], "hidden_finished": 0, "machines": []}).terminals == ()


def test_hello() -> None:
    h = parse_hello(
        {
            "generation": 1,
            "version": "0.1.19",
            "core": {"id": "c0ffee", "name": "host"},
            "framed": False,
            "methods": ["hello", "terminal.run"],
            "features": ["status", "events"],
            "later": True,
        }
    )
    assert h.generation == 1 and h.version == "0.1.19" and h.core.id == "c0ffee"
    assert h.methods == ("hello", "terminal.run") and h.features == ("status", "events")
    with pytest.raises(JsonShapeError, match="version"):
        parse_hello({"generation": 1, "core": {"id": "a", "name": "b"}, "framed": False, "methods": [], "features": []})


def test_send_started_is_tri_state() -> None:
    assert parse_send({"turn": 3}).started is None
    assert parse_send({"turn": 3, "started": None, "status": None}).started is None
    sent = parse_send({"turn": 3, "started": True, "status": "idle"})
    assert sent.started is True and sent.turn == 3 and sent.status == "idle"
    assert parse_send({"turn": 3, "started": False}).started is False


def test_small_results() -> None:
    assert parse_keys({"turn": 2, "status": None}).turn == 2
    assert parse_interrupt({"outcome": "stopped", "key": "esc"}).outcome == "stopped"
    read = parse_read({"text": "a\nb", "how": "screen", "complete": True})
    assert read.text == "a\nb" and read.how == "screen" and read.complete and read.why is None
    assert parse_remove({"removed": "t7"}).removed == "t7"
    assert parse_stop({"stopped": True}).stopped is True
    status = parse_status(
        {
            "core": {"id": "c", "name": "h"},
            "version": "0.1.19",
            "pid": 99,
            "uptime_ms": 5,
            "holders": [{"pid": 100, "instance": "abcd", "current": True, "terminals": 2}],
            "holder": None,
            "live": 2,
            "finished": 1,
            "installed_by": None,
        }
    )
    assert status.pid == 99 and status.holders[0].pid == 100 and status.holder is None
    assert status.installed_by is None


def test_top_level_must_be_an_object() -> None:
    with pytest.raises(JsonShapeError):
        parse_terminal(["t7"])


def test_closed_vocabularies_narrow_and_unknown_words_read_none() -> None:
    lost = parse_terminal(terminal(reason="holder_lost", status={"state": "working"}))
    assert lost.end_reason == "holder_lost"
    assert lost.status is not None and lost.status.word == "working"
    future = parse_terminal(terminal(reason="parked_by_app", status={"state": "thinking"}))
    assert future.reason == "parked_by_app" and future.end_reason is None  # kept, but not a known word
    assert future.status is not None and future.status.word is None
    assert parse_terminal(terminal()).end_reason is None

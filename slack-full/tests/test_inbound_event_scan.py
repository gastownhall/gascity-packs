"""Tests for find_latest_inbound_for_session's escalating scan windows.

The gc events endpoint returns events oldest-first with no descending
order, and ``limit`` keeps the OLDEST slice of the window — so the scan
starts narrow (a newest-slice view) and widens only when nothing
matched. These tests pin the window ladder, the wide-window fallback
for long-idle sessions, and the never-silent truncation warning.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from gc_mock import GcMock  # type: ignore  # noqa: E402

PACK_DIR = TESTS_DIR.parent
SCRIPTS_DIR = PACK_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def gc_mock() -> "GcMock":
    g = GcMock(city_name="test-city")
    yield g
    g.close()


@pytest.fixture(autouse=True)
def _isolate_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    gc_mock: "GcMock",
) -> None:
    monkeypatch.setenv("GC_API_BASE_URL", gc_mock.url)
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setenv("SLACK_WORKSPACE_ID", "T0TESTWS")
    monkeypatch.setenv("GC_SESSION_ID", "gc-test-session")
    monkeypatch.delenv("GC_SLACK_ADAPTER_ENV", raising=False)


def _import_common():
    sys.modules.pop("slack_intake_common", None)
    import slack_intake_common  # type: ignore

    return slack_intake_common


def _events_calls(gc_mock: "GcMock") -> list[dict[str, str]]:
    return [c.query for c in gc_mock.calls() if c.path.endswith("/events")]


def test_recent_inbound_resolves_in_first_window(gc_mock: "GcMock") -> None:
    common = _import_common()
    gc_mock.register_inbound_event(
        target_session="gc-test-session", conversation_id="D0RECENT",
    )

    event = common.find_latest_inbound_for_session("gc-test-session")

    assert event is not None
    assert event["payload"]["conversation_id"] == "D0RECENT"
    calls = _events_calls(gc_mock)
    assert len(calls) == 1, f"expected single narrow-window query, got {calls}"
    assert calls[0].get("since") == common._INBOUND_SCAN_WINDOWS[0]


def test_old_inbound_found_via_widened_window(gc_mock: "GcMock") -> None:
    # Latest inbound is 3h old: outside 10m and 2h, inside 48h. The old
    # single-shot 2h scan returned None here and reply-current fell back
    # to a non-threaded channel publish.
    common = _import_common()
    gc_mock.register_inbound_event(
        target_session="gc-test-session",
        conversation_id="D0OVERNIGHT",
        age_seconds=3 * 3600,
    )

    event = common.find_latest_inbound_for_session("gc-test-session")

    assert event is not None
    assert event["payload"]["conversation_id"] == "D0OVERNIGHT"
    sinces = [c.get("since") for c in _events_calls(gc_mock)]
    assert sinces == list(common._INBOUND_SCAN_WINDOWS), (
        f"expected full ladder before the wide-window hit, got {sinces}"
    )


def test_no_inbound_returns_none_after_all_windows(gc_mock: "GcMock") -> None:
    common = _import_common()

    assert common.find_latest_inbound_for_session("gc-test-session") is None
    sinces = [c.get("since") for c in _events_calls(gc_mock)]
    assert sinces == list(common._INBOUND_SCAN_WINDOWS)


def test_latest_match_wins_within_a_window(gc_mock: "GcMock") -> None:
    common = _import_common()
    gc_mock.register_inbound_event(
        target_session="gc-test-session", conversation_id="D0OLDER", age_seconds=120,
    )
    gc_mock.register_inbound_event(
        target_session="other-session", conversation_id="D0NOISE", age_seconds=60,
    )
    gc_mock.register_inbound_event(
        target_session="gc-test-session", conversation_id="D0NEWEST", age_seconds=5,
    )

    event = common.find_latest_inbound_for_session("gc-test-session")

    assert event is not None
    assert event["payload"]["conversation_id"] == "D0NEWEST"


def test_truncated_scan_warns_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The server reporting total > len(items) means the oldest-first
    # limit cut off the newest events — exactly the ones the scan is
    # after. That must never pass silently.
    common = _import_common()

    def fake_request(method: str, url: str, body: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"items": [], "total": 750}

    monkeypatch.setattr(common, "_request", fake_request)

    assert common.find_latest_inbound_for_session("gc-test-session") is None
    err = capsys.readouterr().err
    assert "truncated to 0/750" in err
    assert err.count("warning: inbound event scan") == len(common._INBOUND_SCAN_WINDOWS)


def test_thread_lookup_returns_root_for_threaded_inbound(gc_mock: "GcMock") -> None:
    # gp-i62: the transcript entry for a thread-reply inbound carries the
    # thread root in ReplyToMessageID (adapter stamps Slack's thread_ts
    # there). The full event→transcript chain must surface it so
    # reply-current can inherit the thread.
    common = _import_common()
    gc_mock.register_inbound_event(
        target_session="gc-test-session", conversation_id="C0THREADED",
    )
    gc_mock.register_transcript_entry(
        conversation_id="C0THREADED",
        provider_message_id="1786291407.960839",
        reply_to_message_id="1786250478.963679",
    )

    match = common.find_latest_inbound_thread_for_session("gc-test-session")

    assert match is not None
    mid, thread_root, conv = match
    assert mid == "1786291407.960839"
    assert thread_root == "1786250478.963679"
    assert conv["conversation_id"] == "C0THREADED"


def test_thread_lookup_returns_empty_root_for_plain_inbound(gc_mock: "GcMock") -> None:
    common = _import_common()
    gc_mock.register_inbound_event(
        target_session="gc-test-session", conversation_id="C0PLAIN",
    )
    gc_mock.register_transcript_entry(
        conversation_id="C0PLAIN",
        provider_message_id="1786291407.960839",
    )

    match = common.find_latest_inbound_thread_for_session("gc-test-session")

    assert match is not None
    mid, thread_root, conv = match
    assert mid == "1786291407.960839"
    assert thread_root == ""
    assert conv["conversation_id"] == "C0PLAIN"


# --------------------------------------------------------------------------
# gp-x4jak: agent-scoped inbounds and newest-first servers.
#
# Live shape (fartnadofalls, 2026-10-14): the mayor's own channel delivers
# through a durable agent binding, so gc stamps those events with
# target_agent="gasburger.mayor" and an empty target_session. Only the
# shared bind-room fanout (#cityhall) carried target_session. The scan
# matched only the room events, and every reply-current landed in #cityhall.
# --------------------------------------------------------------------------


@pytest.fixture
def newest_first_gc(monkeypatch: pytest.MonkeyPatch) -> "GcMock":
    g = GcMock(city_name="test-city", events_newest_first=True)
    monkeypatch.setenv("GC_API_BASE_URL", g.url)
    yield g
    g.close()


def test_agent_scoped_seat_inbound_beats_older_room_fanout(
    newest_first_gc: "GcMock", monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GC_ALIAS", "gasburger.mayor")
    common = _import_common()
    newest_first_gc.register_inbound_event(
        target_session="gc-test-session", conversation_id="C0CITYHALL",
        age_seconds=300, stamp=True,
    )
    newest_first_gc.register_inbound_event(
        target_session="", target_agent="gasburger.mayor",
        conversation_id="C0MAYOR", age_seconds=30, stamp=True,
    )

    event = common.find_latest_inbound_for_session("gc-test-session")

    assert event is not None
    assert event["payload"]["conversation_id"] == "C0MAYOR"


def test_newer_room_fanout_still_wins_over_older_seat_inbound(
    newest_first_gc: "GcMock", monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The fix picks the newest inbound for the session, not "never the room".
    monkeypatch.setenv("GC_ALIAS", "gasburger.mayor")
    common = _import_common()
    newest_first_gc.register_inbound_event(
        target_session="", target_agent="gasburger.mayor",
        conversation_id="C0MAYOR", age_seconds=300, stamp=True,
    )
    newest_first_gc.register_inbound_event(
        target_session="gc-test-session", conversation_id="C0CITYHALL",
        age_seconds=30, stamp=True,
    )

    event = common.find_latest_inbound_for_session("gc-test-session")

    assert event is not None
    assert event["payload"]["conversation_id"] == "C0CITYHALL"


def test_newest_first_server_returns_newest_match(newest_first_gc: "GcMock") -> None:
    # Current gc serves seq DESC; matches[-1] there is the OLDEST match.
    common = _import_common()
    for conv, age in (("D0OLDEST", 240), ("D0MIDDLE", 120), ("D0NEWEST", 5)):
        newest_first_gc.register_inbound_event(
            target_session="gc-test-session", conversation_id=conv,
            age_seconds=age, stamp=True,
        )

    event = common.find_latest_inbound_for_session("gc-test-session")

    assert event is not None
    assert event["payload"]["conversation_id"] == "D0NEWEST"


def test_agent_scoped_inbound_for_another_seat_is_ignored(
    gc_mock: "GcMock", monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GC_ALIAS", "helios/canola")
    common = _import_common()
    gc_mock.register_inbound_event(
        target_session="", target_agent="gasburger.mayor", conversation_id="C0MAYOR",
    )
    # Same seat name, but addressed to a different session: not ours.
    gc_mock.register_inbound_event(
        target_session="other-session", target_agent="helios/canola",
        conversation_id="C0OTHER",
    )

    assert common.find_latest_inbound_for_session("gc-test-session") is None


def test_other_session_resolves_its_seat_via_session_list(
    gc_mock: "GcMock", monkeypatch: pytest.MonkeyPatch,
) -> None:
    # --session <id> for another session must not borrow the caller's alias.
    monkeypatch.setenv("GC_ALIAS", "gasburger.mayor")
    common = _import_common()
    gc_mock.register_session(session_id="fa-canola", alias="helios/canola")
    gc_mock.register_inbound_event(
        target_session="", target_agent="gasburger.mayor", conversation_id="C0MAYOR",
    )
    gc_mock.register_inbound_event(
        target_session="", target_agent="helios/canola", conversation_id="C0CANOLA",
    )

    event = common.find_latest_inbound_for_session("fa-canola")

    assert event is not None
    assert event["payload"]["conversation_id"] == "C0CANOLA"

"""Tests for ``gc slack status`` — adapter / binding / event-count diagnostics.

The script is read-only: it issues GETs against gc's extmsg + events
APIs and renders the result in human or JSON form. Tests stub out the
HTTP layer (``slack_intake_common._request``) and assert both the
collected-status structure and the rendered output.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

PACK_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PACK_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setenv("GC_API_BASE_URL", "http://127.0.0.1:8372")
    monkeypatch.setenv("SLACK_WORKSPACE_ID", "T0TESTWS")
    monkeypatch.delenv("GC_SLACK_ADAPTER_ENV", raising=False)


def _import_modules():
    for name in ("slack_chat_status", "slack_intake_common"):
        sys.modules.pop(name, None)
    import slack_intake_common  # type: ignore
    import slack_chat_status  # type: ignore
    return slack_chat_status, slack_intake_common


def _make_router(routes: dict[str, Any]):
    """Return a fake _request that dispatches by URL substring.

    The fake matches the longest substring registered in ``routes`` so
    callers can register both '/extmsg/adapters' and
    '/events?type=extmsg.inbound' without one swallowing the other.

    Convenience: a bare list under an ``events?`` key is wrapped in
    ``{"items": list}`` automatically so test fixtures can stay terse
    and the wrapping shape lives in one place — matching what the live
    /events endpoint returns.
    """
    captured: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, body=None, *, csrf: bool = True,
                     timeout: float = 30.0):
        captured.append({"method": method, "url": url, "csrf": csrf})
        for needle, response in sorted(routes.items(), key=lambda kv: -len(kv[0])):
            if needle in url:
                if isinstance(response, Exception):
                    raise response
                if needle.startswith("events?") and isinstance(response, list):
                    return {"items": response, "total": len(response)}
                return response
        raise AssertionError(f"unexpected URL in test: {url}")

    return fake_request, captured


def test_summary_lists_registered_adapter(monkeypatch: pytest.MonkeyPatch,
                                          capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    fake, _ = _make_router({
        "/extmsg/adapters": {"items": [
            {"provider": "slack", "account_id": "T0TESTWS", "name": "slack-adapter"}
        ]},
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Adapters:" in out
    assert "slack/T0TESTWS" in out
    assert "(name=slack-adapter)" in out
    assert "inbound:  0" in out
    assert "outbound: 0" in out


def test_summary_warns_when_no_adapter_registered(monkeypatch: pytest.MonkeyPatch,
                                                  capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    fake, _ = _make_router({
        "/extmsg/adapters": {"items": []},
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Adapters:" in out
    assert "(none registered" in out


def test_session_flag_pulls_bindings_only_for_that_session(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    fake, captured = _make_router({
        "/extmsg/adapters": {"items": []},
        "/extmsg/bindings?session_id=gc-83347": {"items": [
            {"Conversation": {"conversation_id": "D0B0TTS550F", "kind": "dm"},
             "Status": "active"}
        ]},
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main(["--session", "gc-83347"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Session gc-83347:" in out
    assert "D0B0TTS550F" in out
    assert "kind=dm" in out
    assert "status=active" in out

    binding_urls = [c["url"] for c in captured if "/extmsg/bindings" in c["url"]]
    assert binding_urls == [
        "http://127.0.0.1:8372/v0/city/test-city/extmsg/bindings?session_id=gc-83347"
    ]


def test_session_with_no_binding_says_so(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    fake, _ = _make_router({
        "/extmsg/adapters": {"items": []},
        "/extmsg/bindings?session_id=gc-99999": {"items": []},
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main(["--session", "gc-99999"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Session gc-99999:" in out
    assert "bindings: (none)" in out


def test_no_session_flag_skips_binding_lookup(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --session we shouldn't call /extmsg/bindings at all
    (it 400s without the query param)."""
    status_mod, common = _import_modules()
    fake, captured = _make_router({
        "/extmsg/adapters": {"items": []},
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main([])
    assert rc == 0
    assert all("/extmsg/bindings" not in c["url"] for c in captured)


def test_since_param_is_propagated_to_events_query(
        monkeypatch: pytest.MonkeyPatch) -> None:
    status_mod, common = _import_modules()
    fake, captured = _make_router({
        "/extmsg/adapters": {"items": []},
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main(["--since", "5m", "--limit", "200"])
    assert rc == 0

    event_urls = [c["url"] for c in captured if "/events?" in c["url"]]
    assert len(event_urls) == 2
    for url in event_urls:
        assert "since=5m" in url
        assert "limit=200" in url


def test_event_counts_include_both_directions(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    inbound = [{"ts": "2026-05-02T17:30:01Z",
                "payload": {"conversation_id": "C0X", "target_session": "gc-1"}}
               for _ in range(3)]
    outbound = [{"ts": "2026-05-02T17:30:02Z",
                 "payload": {"conversation_id": "C0Y", "session": "gc-2"}}
                for _ in range(7)]
    fake, _ = _make_router({
        "/extmsg/adapters": {"items": []},
        "events?type=extmsg.inbound": inbound,
        "events?type=extmsg.outbound": outbound,
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "inbound:  3" in out
    assert "outbound: 7" in out
    assert "Recent activity:" in out
    assert "C0X" in out
    assert "C0Y" in out


def test_session_filter_narrows_recent_activity(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    inbound = [
        {"ts": "2026-05-02T17:30:01Z",
         "payload": {"conversation_id": "C0A", "target_session": "gc-keep"}},
        {"ts": "2026-05-02T17:30:02Z",
         "payload": {"conversation_id": "C0B", "target_session": "gc-other"}},
    ]
    outbound = [
        {"ts": "2026-05-02T17:30:03Z",
         "payload": {"conversation_id": "C0A", "session": "gc-keep"}},
        {"ts": "2026-05-02T17:30:04Z",
         "payload": {"conversation_id": "C0B", "session": "gc-other"}},
    ]
    fake, _ = _make_router({
        "/extmsg/adapters": {"items": []},
        "/extmsg/bindings?session_id=gc-keep": {"items": []},
        "events?type=extmsg.inbound": inbound,
        "events?type=extmsg.outbound": outbound,
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main(["--session", "gc-keep"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "inbound:  1" in out
    assert "outbound: 1" in out
    assert "C0A" in out
    assert "C0B" not in out


def test_json_output_is_machine_readable(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    status_mod, common = _import_modules()
    fake, _ = _make_router({
        "/extmsg/adapters": {"items": [
            {"provider": "slack", "account_id": "T0TESTWS"}
        ]},
        "events?type=extmsg.inbound": [{"ts": "t", "payload": {}}],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main(["--json"])
    out = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(out)
    assert parsed["adapters"] == [{"provider": "slack", "account_id": "T0TESTWS"}]
    assert parsed["events"]["inbound"] and parsed["events"]["outbound"] == []
    assert parsed["session"] == ""
    assert parsed["bindings"] == []


def test_adapter_lookup_failure_degrades_gracefully(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A 500 from /extmsg/adapters shouldn't abort — status should
    still render the events sections."""
    status_mod, common = _import_modules()
    fake, _ = _make_router({
        "/extmsg/adapters": common.GCAPIError("simulated adapter API down"),
        "events?type=extmsg.inbound": [],
        "events?type=extmsg.outbound": [],
    })
    monkeypatch.setattr(common, "_request", fake)

    rc = status_mod.main([])
    out = capsys.readouterr().out

    assert rc == 0
    assert "(none registered" in out
    assert "Events" in out


def test_invalid_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    status_mod, _common = _import_modules()
    with pytest.raises(SystemExit):
        status_mod.main(["--limit", "0"])

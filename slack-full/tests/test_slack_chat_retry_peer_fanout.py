"""Tests for ``gc slack retry-peer-fanout``.

The script discovers ``extmsg.peer_fanout_failed`` events, deduplicates
against prior successful ``extmsg.peer_fanout_retried`` events, then
issues a retry request per remaining candidate via the gc HTTP API.
Tests cover:

  * one-success — a single failed delivery retries cleanly;
  * one-still-fail — the retry endpoint reports failure and the script
    surfaces it without aborting the loop;
  * no-eligible-events — no failed events => no-op;
  * idempotence — a previously-succeeded retry is skipped on re-run.
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
    for name in ("slack_chat_retry_peer_fanout", "slack_intake_common"):
        sys.modules.pop(name, None)
    import slack_intake_common  # type: ignore
    import slack_chat_retry_peer_fanout  # type: ignore
    return slack_chat_retry_peer_fanout, slack_intake_common


def _failed_event(seq: int, *, conversation_id: str = "C0ROOM01",
                  target_session: str = "gc-peer1",
                  reason: str = "session unreachable") -> dict[str, Any]:
    return {
        "seq": seq,
        "type": "extmsg.peer_fanout_failed",
        "ts": "2026-05-05T12:00:00Z",
        "subject": f"slack/{conversation_id}",
        "payload": {
            "provider": "slack",
            "conversation_id": conversation_id,
            "account_id": "T0TESTWS",
            "scope_id": "test-city",
            "kind": "room",
            "target_session": target_session,
            "actor_display_name": "alice",
            "actor_kind": "human",
            "text": "ping",
            "reason": reason,
        },
    }


def _retried_event(seq: int, *, original_seq: int, success: bool,
                   conversation_id: str = "C0ROOM01",
                   target_session: str = "gc-peer1") -> dict[str, Any]:
    return {
        "seq": seq,
        "type": "extmsg.peer_fanout_retried",
        "ts": "2026-05-05T12:00:01Z",
        "subject": f"slack/{conversation_id}",
        "payload": {
            "provider": "slack",
            "conversation_id": conversation_id,
            "target_session": target_session,
            "original_seq": original_seq,
            "success": success,
            "error": "" if success else "still failing",
        },
    }


def _make_router(routes: dict[str, Any]):
    """Dispatch fake _request by URL substring; longest match wins."""
    captured: list[dict[str, Any]] = []

    def fake_request(method: str, url: str, body=None, *, csrf: bool = True,
                     timeout: float = 30.0):
        captured.append({"method": method, "url": url, "body": body, "csrf": csrf})
        for needle, response in sorted(routes.items(), key=lambda kv: -len(kv[0])):
            if needle in url:
                if isinstance(response, Exception):
                    raise response
                if callable(response):
                    return response(method=method, url=url, body=body)
                return response
        raise AssertionError(f"unexpected URL: {url}")

    return fake_request, captured


def test_one_success(monkeypatch: pytest.MonkeyPatch,
                     capsys: pytest.CaptureFixture) -> None:
    retry_mod, common = _import_modules()

    failed = [_failed_event(101)]
    retried: list[dict[str, Any]] = []

    routes = {
        "events?type=extmsg.peer_fanout_failed": {"items": failed,
                                                  "total": len(failed)},
        "events?type=extmsg.peer_fanout_retried": {"items": retried,
                                                   "total": len(retried)},
        "/extmsg/peer-fanout/retry": {"success": True, "error": ""},
    }
    fake, captured = _make_router(routes)
    monkeypatch.setattr(common, "_request", fake)
    monkeypatch.setattr(retry_mod, "_cooldown", lambda _s: None)

    rc = retry_mod.main([])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 1
    assert out["attempts"] == 1
    assert out["successes"] == 1
    assert out["failures"] == 0
    assert out["skipped"] == 0

    posts = [c for c in captured
             if c["method"] == "POST" and "/extmsg/peer-fanout/retry" in c["url"]]
    assert len(posts) == 1
    body = posts[0]["body"]
    assert body["original_seq"] == 101
    assert body["target_session"] == "gc-peer1"
    assert body["text"] == "ping"
    assert body["conversation"]["conversation_id"] == "C0ROOM01"


def test_one_still_fail_surfaces_without_aborting(
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture) -> None:
    retry_mod, common = _import_modules()

    failed = [_failed_event(101), _failed_event(102, target_session="gc-peer2")]
    routes = {
        "events?type=extmsg.peer_fanout_failed": {"items": failed,
                                                  "total": len(failed)},
        "events?type=extmsg.peer_fanout_retried": {"items": []},
    }

    def retry_handler(*, method: str, url: str, body: Any) -> dict[str, Any]:
        if body["target_session"] == "gc-peer1":
            return {"success": True, "error": ""}
        return {"success": False, "error": "rate_limited"}

    routes["/extmsg/peer-fanout/retry"] = retry_handler

    fake, captured = _make_router(routes)
    monkeypatch.setattr(common, "_request", fake)
    monkeypatch.setattr(retry_mod, "_cooldown", lambda _s: None)

    rc = retry_mod.main([])
    assert rc == 0  # script does not abort on individual failure

    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 2
    assert out["attempts"] == 2
    assert out["successes"] == 1
    assert out["failures"] == 1
    assert out["skipped"] == 0

    posts = [c for c in captured
             if c["method"] == "POST" and "/extmsg/peer-fanout/retry" in c["url"]]
    assert len(posts) == 2


def test_no_eligible_events_is_noop(monkeypatch: pytest.MonkeyPatch,
                                    capsys: pytest.CaptureFixture) -> None:
    retry_mod, common = _import_modules()

    routes = {
        "events?type=extmsg.peer_fanout_failed": {"items": [], "total": 0},
        "events?type=extmsg.peer_fanout_retried": {"items": [], "total": 0},
    }
    fake, captured = _make_router(routes)
    monkeypatch.setattr(common, "_request", fake)
    monkeypatch.setattr(retry_mod, "_cooldown", lambda _s: None)

    rc = retry_mod.main([])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 0
    assert out["attempts"] == 0
    assert out["successes"] == 0

    # No retry POST should fire when there is nothing to do.
    posts = [c for c in captured
             if c["method"] == "POST" and "/extmsg/peer-fanout/retry" in c["url"]]
    assert posts == []


def test_idempotent_skip_when_prior_retry_succeeded(
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture) -> None:
    retry_mod, common = _import_modules()

    failed = [_failed_event(101)]
    # A prior retry already succeeded for original_seq=101.
    retried = [_retried_event(150, original_seq=101, success=True)]

    routes = {
        "events?type=extmsg.peer_fanout_failed": {"items": failed},
        "events?type=extmsg.peer_fanout_retried": {"items": retried},
    }
    fake, captured = _make_router(routes)
    monkeypatch.setattr(common, "_request", fake)
    monkeypatch.setattr(retry_mod, "_cooldown", lambda _s: None)

    rc = retry_mod.main([])
    assert rc == 0

    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 1
    assert out["attempts"] == 0
    assert out["skipped"] == 1

    posts = [c for c in captured
             if c["method"] == "POST" and "/extmsg/peer-fanout/retry" in c["url"]]
    assert posts == []


def test_conversation_filter(monkeypatch: pytest.MonkeyPatch,
                             capsys: pytest.CaptureFixture) -> None:
    retry_mod, common = _import_modules()

    failed = [
        _failed_event(101, conversation_id="C0ROOM01"),
        _failed_event(102, conversation_id="C0ROOM02"),
    ]
    routes = {
        "events?type=extmsg.peer_fanout_failed": {"items": failed},
        "events?type=extmsg.peer_fanout_retried": {"items": []},
        "/extmsg/peer-fanout/retry": {"success": True, "error": ""},
    }
    fake, captured = _make_router(routes)
    monkeypatch.setattr(common, "_request", fake)
    monkeypatch.setattr(retry_mod, "_cooldown", lambda _s: None)

    rc = retry_mod.main(["--conversation", "C0ROOM02"])
    assert rc == 0

    posts = [c for c in captured
             if c["method"] == "POST" and "/extmsg/peer-fanout/retry" in c["url"]]
    assert len(posts) == 1
    assert posts[0]["body"]["conversation"]["conversation_id"] == "C0ROOM02"


def test_max_caps_attempts(monkeypatch: pytest.MonkeyPatch,
                           capsys: pytest.CaptureFixture) -> None:
    retry_mod, common = _import_modules()

    failed = [_failed_event(seq, target_session=f"gc-peer{seq}")
              for seq in (101, 102, 103)]
    routes = {
        "events?type=extmsg.peer_fanout_failed": {"items": failed},
        "events?type=extmsg.peer_fanout_retried": {"items": []},
        "/extmsg/peer-fanout/retry": {"success": True, "error": ""},
    }
    fake, captured = _make_router(routes)
    monkeypatch.setattr(common, "_request", fake)
    monkeypatch.setattr(retry_mod, "_cooldown", lambda _s: None)

    rc = retry_mod.main(["--max", "2"])
    assert rc == 0

    posts = [c for c in captured
             if c["method"] == "POST" and "/extmsg/peer-fanout/retry" in c["url"]]
    assert len(posts) == 2

    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 3
    assert out["attempts"] == 2

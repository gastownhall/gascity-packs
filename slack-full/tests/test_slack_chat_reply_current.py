"""Tests for slack reply-current's gc-vs-adapter publish path.

The behavior under test: by default, replies should route through gc's
``/extmsg/outbound`` so peer fanout + transcript recording fire. Only the
explicit ``--via adapter`` opt-in skips gc and hits the local adapter.
"""

from __future__ import annotations

import argparse
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
    monkeypatch.setenv("GC_SESSION_ID", "gc-test-session")
    monkeypatch.delenv("GC_SLACK_ADAPTER_ENV", raising=False)


def _import_modules():
    for name in ("slack_chat_reply_current", "slack_intake_common"):
        sys.modules.pop(name, None)
    import slack_intake_common  # type: ignore
    import slack_chat_reply_current  # type: ignore
    return slack_chat_reply_current, slack_intake_common


def test_default_via_routes_through_gc_outbound(monkeypatch: pytest.MonkeyPatch) -> None:
    rc, common = _import_modules()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, body: dict[str, Any] | None = None,
                     *, csrf: bool = True, timeout: float = 30.0) -> dict[str, Any]:
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        captured["csrf"] = csrf
        return {"Receipt": {"Delivered": True, "MessageID": "1700000.000100"}}

    monkeypatch.setattr(common, "_request", fake_request)
    monkeypatch.setattr(common, "find_latest_inbound_for_session", lambda _sid: None)
    monkeypatch.setattr(common, "look_up_binding", lambda _sid: None)

    exit_code = rc.main([
        "--session", "gc-test-session",
        "--conversation-id", "D0123ROOM",
        "--body", "*hello*",
    ])
    assert exit_code == 0
    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound"
    assert captured["csrf"] is True
    assert captured["body"]["session_id"] == "gc-test-session"
    assert captured["body"]["conversation"] == {
        "scope_id": "test-city",
        "provider": "slack",
        "account_id": "T0TESTWS",
        "conversation_id": "D0123ROOM",
        "kind": "dm",
    }
    assert captured["body"]["text"] == "*hello*"


def test_via_adapter_keeps_direct_adapter_path(monkeypatch: pytest.MonkeyPatch) -> None:
    rc, common = _import_modules()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, body: dict[str, Any] | None = None,
                     *, csrf: bool = True, timeout: float = 30.0) -> dict[str, Any]:
        captured["method"] = method
        captured["url"] = url
        captured["body"] = body
        captured["csrf"] = csrf
        return {"delivered": True, "message_id": "1700000.000200"}

    monkeypatch.setattr(common, "_request", fake_request)
    monkeypatch.setattr(common, "find_latest_inbound_for_session", lambda _sid: None)
    monkeypatch.setattr(common, "look_up_binding", lambda _sid: None)

    exit_code = rc.main([
        "--session", "gc-test-session",
        "--conversation-id", "D0123ROOM",
        "--body", "diag",
        "--via", "adapter",
    ])
    assert exit_code == 0
    assert captured["url"].endswith("/publish")
    # gc-5rz Phase A: the supervised adapter is reached via the gc /svc
    # proxy, which requires X-GC-Request on private mutation endpoints
    # — so even the adapter-direct path carries csrf=True.
    assert captured["csrf"] is True
    assert "/extmsg/" not in captured["url"]


def test_idempotency_and_reply_to_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    rc, common = _import_modules()
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, body: dict[str, Any] | None = None,
                     *, csrf: bool = True, timeout: float = 30.0) -> dict[str, Any]:
        captured["body"] = body
        return {"Receipt": {"Delivered": True}}

    monkeypatch.setattr(common, "_request", fake_request)
    monkeypatch.setattr(common, "find_latest_inbound_for_session", lambda _sid: None)
    monkeypatch.setattr(common, "look_up_binding", lambda _sid: None)

    rc.main([
        "--session", "gc-test-session",
        "--conversation-id", "D0123ROOM",
        "--body", "x",
        "--reply-to", "1700000.000100",
        "--idempotency-key", "key-42",
    ])
    assert captured["body"]["reply_to_message_id"] == "1700000.000100"
    assert captured["body"]["idempotency_key"] == "key-42"


def test_reply_current_exits_nonzero_on_adapter_delivered_false(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Mirror gpk-5sk's gate for the reply-current CLI on the adapter route.

    Added in response to Copilot review on PR #14 — the prior commit landed
    the delivered-false gate without a regression test for this CLI.
    """
    rc, common = _import_modules()

    def fake_request(method: str, url: str, body: dict[str, Any] | None = None,
                     *, csrf: bool = True, timeout: float = 30.0) -> dict[str, Any]:
        return {"delivered": False, "failure_kind": "rate_limited"}

    monkeypatch.setattr(common, "_request", fake_request)
    monkeypatch.setattr(common, "find_latest_inbound_for_session", lambda _sid: None)
    monkeypatch.setattr(common, "look_up_binding", lambda _sid: None)

    exit_code = rc.main([
        "--session", "gc-test-session",
        "--conversation-id", "D0123ROOM",
        "--body", "rejected",
        "--via", "adapter",
    ])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "delivered=false" in err
    assert "failure_kind=rate_limited" in err


def test_reply_current_exits_nonzero_on_gc_outbound_delivered_false(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Same gate via the default gc /extmsg/outbound route (capitalized shape)."""
    rc, common = _import_modules()

    def fake_request(method: str, url: str, body: dict[str, Any] | None = None,
                     *, csrf: bool = True, timeout: float = 30.0) -> dict[str, Any]:
        return {"Receipt": {"Delivered": False, "FailureKind": "not_found"}}

    monkeypatch.setattr(common, "_request", fake_request)
    monkeypatch.setattr(common, "find_latest_inbound_for_session", lambda _sid: None)
    monkeypatch.setattr(common, "look_up_binding", lambda _sid: None)

    exit_code = rc.main([
        "--session", "gc-test-session",
        "--conversation-id", "D0123ROOM",
        "--body", "x",
    ])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "delivered=false" in err
    assert "failure_kind=not_found" in err

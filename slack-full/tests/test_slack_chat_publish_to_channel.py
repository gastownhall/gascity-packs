"""Tests for ``gc slack publish-to-channel``.

Covers exit-code behavior on the adapter receipt's ``delivered`` field,
argument plumbing, and ``--via`` routing (gc first so bind-room peers see
the post, adapter-direct only when gc refuses for lack of a binding). Added in response to Copilot review on PR #14
(gpk-bf3 iteration) — the prior commit landed the delivered-false gate
without a regression test for this specific CLI.
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
    monkeypatch.setenv("GC_SESSION_ID", "gc-default-session")
    monkeypatch.delenv("GC_SLACK_ADAPTER_ENV", raising=False)


def _import_modules():
    for name in ("slack_chat_publish_to_channel", "slack_intake_common"):
        sys.modules.pop(name, None)
    import slack_intake_common  # type: ignore
    import slack_chat_publish_to_channel  # type: ignore
    return slack_chat_publish_to_channel, slack_intake_common


def test_publish_to_channel_success_returns_zero(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    pub, common = _import_modules()
    captured: dict[str, Any] = {}

    def fake_publish(**kwargs):
        captured.update(kwargs)
        return {"delivered": True, "message_id": "1700.001"}

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_publish)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--via", "adapter",
        "--body", "ok",
    ])
    assert rc == 0
    assert captured["conversation_id"] == "C0CHAN01"
    assert captured["text"] == "ok"
    out = json.loads(capsys.readouterr().out)
    assert out["conversation_id"] == "C0CHAN01"


def test_publish_to_channel_exits_nonzero_on_delivered_false(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Adapter HTTP-200 with delivered=false must surface as exit 1.

    Regression test for the latent defect tracked by gpk-5sk and the
    follow-up Copilot review on PR #14. Without this gate, the PL
    stamps loop_close_posted_at on the bead even when slack rejected
    the post (auth, channel renamed, scope change).
    """
    pub, common = _import_modules()

    def fake_publish(**_kwargs):
        return {"delivered": False, "failure_kind": "auth"}

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_publish)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--via", "adapter",
        "--body", "rejected",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "delivered=false" in err
    assert "failure_kind=auth" in err


def test_publish_to_channel_exits_nonzero_on_schema_mismatch(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Unknown response shape must fail closed (not silently treated as success)."""
    pub, common = _import_modules()

    def fake_publish(**_kwargs):
        return {"some_other_field": "value"}

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_publish)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--via", "adapter",
        "--body", "x",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "schema_mismatch" in err


def test_publish_to_channel_requires_workspace_id(
        monkeypatch: pytest.MonkeyPatch) -> None:
    pub, _ = _import_modules()
    monkeypatch.setenv("SLACK_WORKSPACE_ID", "")
    with pytest.raises(SystemExit) as exc:
        pub.main([
            "--conversation-id", "C0CHAN01",
            "--session", "gc-1",
        "--via", "adapter",
            "--body", "x",
        ])
    assert "SLACK_WORKSPACE_ID" in str(exc.value)


def test_publish_to_channel_rejects_both_body_and_body_file() -> None:
    pub, _ = _import_modules()
    with pytest.raises(SystemExit) as exc:
        pub.main([
            "--conversation-id", "C0CHAN01",
            "--session", "gc-1",
        "--via", "adapter",
            "--body", "a",
            "--body-file", "/dev/null",
        ])
    assert "OR" in str(exc.value)


# --------------------------------------------------------------------------
# Accidental-mrkdwn guard (gp-o42) — tilde pairs must not strike through.
# --------------------------------------------------------------------------

def test_publish_to_channel_guards_tildes_by_default(
        monkeypatch: pytest.MonkeyPatch) -> None:
    pub, common = _import_modules()
    import slack_mrkdwn
    captured: dict[str, Any] = {}

    def fake_publish(**kwargs):
        captured.update(kwargs)
        return {"delivered": True, "message_id": "1700.001"}

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_publish)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--via", "adapter",
        "--body", "~$58.5k out, ~$16.5k left",
    ])
    assert rc == 0
    assert captured["text"] == \
        "~$58.5k out, ~$16.5k left".replace("~", slack_mrkdwn.TILDE_SUBSTITUTE)


def test_publish_to_channel_raw_flag_skips_guard(
        monkeypatch: pytest.MonkeyPatch) -> None:
    pub, common = _import_modules()
    captured: dict[str, Any] = {}

    def fake_publish(**kwargs):
        captured.update(kwargs)
        return {"delivered": True, "message_id": "1700.001"}

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_publish)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--via", "adapter",
        "--body", "~$58.5k out, ~$16.5k left",
        "--raw",
    ])
    assert rc == 0
    assert captured["text"] == "~$58.5k out, ~$16.5k left"


# --------------------------------------------------------------------------
# --via routing — a post into a bind-room must reach peers through gc.
# --------------------------------------------------------------------------

UNBOUND_422 = (
    "POST http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound -> 422: "
    '{"detail":"no active binding for conversation slack/C0CHAN01"}')


def _stub_paths(monkeypatch: pytest.MonkeyPatch, common, *, gc=None, adapter=None):
    """Stub both publish paths and record which ones ran, in order."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_gc(**kwargs):
        calls.append(("gc", kwargs))
        if isinstance(gc, Exception):
            raise gc
        return gc if gc is not None else {
            "receipt": {"delivered": True, "message_id": "1700.002"}}

    def fake_adapter(**kwargs):
        calls.append(("adapter", kwargs))
        return adapter if adapter is not None else {
            "delivered": True, "message_id": "1700.003"}

    monkeypatch.setattr(common, "publish_via_gc_outbound", fake_gc)
    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_adapter)
    return calls


def test_default_publishes_through_gc_so_peers_see_it(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    pub, common = _import_modules()
    calls = _stub_paths(monkeypatch, common)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--thread-ts", "1700.000",
        "--idempotency-key", "k-1",
        "--body", "hello room",
    ])
    assert rc == 0
    assert [name for name, _ in calls] == ["gc"]
    sent = calls[0][1]
    assert sent == {
        "session_id": "gc-1",
        "scope_id": "test-city",
        "provider": "slack",
        "account_id": "T0TESTWS",
        "conversation_id": "C0CHAN01",
        "kind": "room",
        "text": "hello room",
        "reply_to_message_id": "1700.000",
        "idempotency_key": "k-1",
    }
    out = json.loads(capsys.readouterr().out)
    assert out["via"] == "gc"


@pytest.mark.parametrize("detail", [
    UNBOUND_422,
    ("POST http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound -> 422: "
     '{"detail":"session \\"gc-1\\" does not own binding for conversation '
     'slack/C0CHAN01 (bound to gc-2)"}'),
    ("POST http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound failed: "
     "<urlopen error [Errno 111] Connection refused>"),
])
def test_auto_falls_back_to_adapter_only_when_gc_posted_nothing(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
        detail: str) -> None:
    pub, common = _import_modules()
    calls = _stub_paths(monkeypatch, common, gc=common.GCAPIError(detail))

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--thread-ts", "1700.000",
        "--body", "for the mayor",
    ])
    assert rc == 0
    assert [name for name, _ in calls] == ["gc", "adapter"]
    assert calls[1][1]["conversation_id"] == "C0CHAN01"
    assert calls[1][1]["thread_ts"] == "1700.000"
    assert calls[1][1]["text"] == "for the mayor"
    captured = capsys.readouterr()
    assert json.loads(captured.out)["via"] == "adapter"
    assert "will not see this post" in captured.err


@pytest.mark.parametrize("detail", [
    "POST http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound timed out after 30.0s",
    ("POST http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound -> 422: "
     '{"detail":"adapter publish: slack: rate_limited"}'),
    "POST http://127.0.0.1:8372/v0/city/test-city/extmsg/outbound -> 500: boom",
])
def test_auto_does_not_double_post_when_gc_may_have_posted(
        monkeypatch: pytest.MonkeyPatch, detail: str) -> None:
    """A timeout or a post-publish failure must not re-post through the adapter."""
    pub, common = _import_modules()
    calls = _stub_paths(monkeypatch, common, gc=common.GCAPIError(detail))

    with pytest.raises(SystemExit) as exc:
        pub.main([
            "--conversation-id", "C0CHAN01",
            "--session", "gc-1",
            "--body", "x",
        ])
    assert [name for name, _ in calls] == ["gc"]
    assert "gc publish failed" in str(exc.value)
    assert "second copy" in str(exc.value)


def test_via_gc_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    pub, common = _import_modules()
    calls = _stub_paths(monkeypatch, common, gc=common.GCAPIError(UNBOUND_422))

    with pytest.raises(SystemExit) as exc:
        pub.main([
            "--conversation-id", "C0CHAN01",
            "--session", "gc-1",
            "--via", "gc",
            "--body", "x",
        ])
    assert [name for name, _ in calls] == ["gc"]
    assert "no active binding" in str(exc.value)


def test_via_adapter_skips_gc(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    pub, common = _import_modules()
    calls = _stub_paths(monkeypatch, common)

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--via", "adapter",
        "--body", "x",
    ])
    assert rc == 0
    assert [name for name, _ in calls] == ["adapter"]
    assert json.loads(capsys.readouterr().out)["via"] == "adapter"


def test_gc_path_exits_nonzero_on_delivered_false(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """The delivered gate reads gc's wrapped receipt, and a refused post is not retried."""
    pub, common = _import_modules()
    calls = _stub_paths(monkeypatch, common, gc={
        "receipt": {"delivered": False, "failure_kind": "auth"}})

    rc = pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--body", "x",
    ])
    assert rc == 1
    assert [name for name, _ in calls] == ["gc"]
    assert "failure_kind=auth" in capsys.readouterr().err

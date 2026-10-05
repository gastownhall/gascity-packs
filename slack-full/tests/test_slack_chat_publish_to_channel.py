"""Tests for ``gc slack publish-to-channel``.

Covers exit-code behavior on the adapter receipt's ``delivered`` field,
plus argument plumbing. Added in response to Copilot review on PR #14
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
            "--body", "x",
        ])
    assert "SLACK_WORKSPACE_ID" in str(exc.value)


def test_publish_to_channel_rejects_both_body_and_body_file() -> None:
    pub, _ = _import_modules()
    with pytest.raises(SystemExit) as exc:
        pub.main([
            "--conversation-id", "C0CHAN01",
            "--session", "gc-1",
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
        "--body", "~$58.5k out, ~$16.5k left",
        "--raw",
    ])
    assert rc == 0
    assert captured["text"] == "~$58.5k out, ~$16.5k left"


# --------------------------------------------------------------------------
# Retry safety: the client budget must outlast /publish's readback, and an
# unkeyed publish must still dedupe when the operator retries a timeout.
# --------------------------------------------------------------------------

def _key_collector(monkeypatch: pytest.MonkeyPatch, common) -> list[str]:
    """Stub the adapter POST and record each call's idempotency key."""
    keys: list[str] = []

    def fake_publish(**kwargs):
        keys.append(kwargs.get("idempotency_key", ""))
        return {"delivered": True, "message_id": "1700.001"}

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", fake_publish)
    return keys


def test_publish_to_channel_auto_derives_stable_idempotency_key(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """With no --idempotency-key, the key is derived and stable.

    Two identical invocations — the shape of an operator retrying after the
    client gave up on a publish the adapter actually completed — must send
    the SAME key, so the adapter replays the receipt instead of posting a
    duplicate. A per-invocation random key would satisfy "a key was sent"
    while leaving the duplicate window exactly as wide as it was.
    """
    pub, common = _import_modules()
    keys = _key_collector(monkeypatch, common)

    argv = ["--conversation-id", "C0CHAN01", "--session", "gc-1", "--body", "ok"]
    assert pub.main(argv) == 0
    assert pub.main(argv) == 0
    assert keys[0] != ""
    assert keys[0] == keys[1]
    assert keys[0].startswith("publish-to-channel:")


def test_publish_to_channel_derived_key_varies_with_target_and_body(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Distinct logical publishes must not collapse onto one key."""
    pub, common = _import_modules()
    keys = _key_collector(monkeypatch, common)

    base = ["--session", "gc-1", "--conversation-id", "C0CHAN01"]
    assert pub.main(base + ["--body", "first"]) == 0
    assert pub.main(base + ["--body", "second"]) == 0
    assert pub.main(["--session", "gc-1", "--conversation-id", "C0CHAN02",
                     "--body", "first"]) == 0
    assert pub.main(base + ["--body", "first", "--thread-ts", "1700.900"]) == 0
    assert len(set(keys)) == len(keys), f"keys collided: {keys}"


def test_publish_to_channel_derived_key_fingerprints_the_sent_body(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The fingerprint runs on the post-guard body, not the raw argv.

    The guarded and --raw renderings of one input are different messages.
    Fingerprinting before the accidental-mrkdwn guard would give them one
    key, so sending both would silently drop the second.
    """
    pub, common = _import_modules()
    keys = _key_collector(monkeypatch, common)

    body = "~$58.5k out, ~$16.5k left"
    base = ["--session", "gc-1", "--conversation-id", "C0CHAN01", "--body", body]
    assert pub.main(base) == 0
    assert pub.main(base + ["--raw"]) == 0
    assert keys[0] != keys[1]


def test_publish_to_channel_explicit_idempotency_key_wins(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit key is passed through untouched — the duplicate escape hatch."""
    pub, common = _import_modules()
    keys = _key_collector(monkeypatch, common)

    assert pub.main([
        "--conversation-id", "C0CHAN01",
        "--session", "gc-1",
        "--body", "ok",
        "--idempotency-key", "key-42",
    ]) == 0
    assert keys == ["key-42"]


def test_publish_adapter_timeout_outlasts_the_readback_worst_case(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The client budget must exceed what /publish is designed to spend.

    /publish costs slackPostTimeout + attempts*clientTimeout +
    (attempts-1)*delay = 22.4s in the worst case (adapter/publish_readback.go,
    pinned Go-side by TestSlackReadbackTimingDefaults). A client that gives up
    first does not cancel the adapter goroutine, so the post lands anyway and
    the operator sees a spurious error. Pinned as literals: raising the
    adapter's budget without raising this one re-opens the window.
    """
    _pub, common = _import_modules()
    assert common.SLACK_PUBLISH_WORST_CASE_SECONDS == 22.4
    assert common.PUBLISH_ADAPTER_TIMEOUT == 30.0
    assert common.PUBLISH_ADAPTER_TIMEOUT > common.SLACK_PUBLISH_WORST_CASE_SECONDS

    seen: dict[str, Any] = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return b'{"delivered": true}'

    def fake_urlopen(_req, **kwargs):
        seen.update(kwargs)
        return _Resp()

    monkeypatch.setattr(common.urllib.request, "urlopen", fake_urlopen)

    common.publish_to_channel_via_adapter(
        session_id="gc-1",
        conversation_id="C0CHAN01",
        text="ok",
    )
    # Not just declared — actually handed to the socket.
    assert seen["timeout"] == common.PUBLISH_ADAPTER_TIMEOUT

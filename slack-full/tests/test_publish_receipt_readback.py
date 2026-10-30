"""Accepted Slack posts must survive an unconfirmed readback in every CLI."""

import importlib
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))


@pytest.mark.parametrize("script", ["publish", "publish_to_channel", "reply_current"])
@pytest.mark.parametrize("shape", ["adapter", "lower", "upper"])
@pytest.mark.parametrize("state", ["legacy", "missing_metadata", "unconfirmed", "unavailable", "auth", "confirmed"])
def test_accepted_publish_receipt(monkeypatch, capsys, tmp_path, script, shape, state):
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setenv("SLACK_WORKSPACE_ID", "TTEST")
    common = importlib.import_module("slack_intake_common")
    cli = importlib.reload(importlib.import_module("slack_chat_" + script))
    metadata = {"receipt_store": "test-warning"}
    if state not in ("confirmed", "missing_metadata"):
        metadata["readback"] = "readback_" + ("unconfirmed" if state == "legacy" else state)
    receipt = {"delivered": state not in ("legacy", "missing_metadata"), "message_id": "1700.001", "metadata": metadata}
    if state in ("legacy", "missing_metadata"):
        receipt["failure_kind"] = "auth"  # must not trigger the mention-only fallback
    if shape == "upper":
        keys = {"delivered": "Delivered", "message_id": "MessageID", "metadata": "Metadata", "failure_kind": "FailureKind"}
        result = {"Receipt": {keys[k]: v for k, v in receipt.items()}}
    elif shape == "lower":
        result = {"receipt": receipt}
    else:
        result = receipt
    calls = []

    def publish(**kwargs):
        calls.append(kwargs)
        return result

    monkeypatch.setattr(common, "publish_to_channel_via_adapter", publish)
    monkeypatch.setattr(common, "publish_via_gc_outbound", publish)
    monkeypatch.setattr(common, "publish_via_adapter", publish)
    monkeypatch.setattr(common, "look_up_binding", lambda _: {
        "scope_id": "test-city", "provider": "slack", "account_id": "TTEST",
        "conversation_id": "C123", "kind": "room"})
    monkeypatch.setattr(common, "find_latest_inbound_for_session", lambda _: None)
    if script == "reply_current":
        monkeypatch.setattr(cli, "_maybe_company_reply", lambda _: None)
    args = ["--session", "gc-test", "--body", "test body"]
    if script != "publish":
        args += ["--conversation-id", "C123"]
    args += ["--thread-ts" if script == "publish_to_channel" else "--reply-to", "1690.5"]
    assert cli.main(args) == 0
    output = capsys.readouterr()
    printed = json.loads(output.out)
    assert printed["result"] == result  # upstream retains the full receipt envelope
    assert len(calls) == 1
    if state == "confirmed":
        assert "unconfirmed" not in output.err
    else:
        assert "unconfirmed" in output.err
        assert "1700.001" in output.err

"""End-to-end pipeline tests for slack-pack.

Wires ``GcMock`` and ``SlackMock`` together to exercise the full
``slack-pack script -> gc /extmsg/* -> http_adapter -> Slack`` round-trip
without running the real gc binary. Existing tests in this directory
mock the HTTP layer at the script level (patched ``_request``); these
tests don't — they let scripts make real HTTP calls against the in-
process mocks. That catches a different class of bug (URL/path
construction errors, header omissions, response-shape mismatches) that
script-level mocking can't.

Coverage rationale (gastownhall/gascity#1817 + #1802 context):

  * #1817 (http_adapter CSRF gap): we cannot directly pin gc's
    ``HTTPAdapter.Publish`` behavior here — that lives in gascity, not
    gascity-packs. But the SlackMock's CSRF gate (require_gc_request)
    documents the contract gc owes the adapter, and ``GcMock`` honors
    it by always setting ``X-GC-Request: true`` when forwarding. A
    regression there would surface as ``Delivered: false /
    FailureKind: adapter`` — visible in this test.
  * #1802 (binding fallback): the slack-pack script's binding lookup
    via ``GET /extmsg/bindings?session_id=<sid>`` is exercised here
    against the GcMock; if the script changes the lookup shape, the
    test breaks.

These tests are scenario-level and intentionally narrow — one happy
path per pipeline. The matrix of error/edge cases stays in the
existing per-script unit tests, which patch ``_request`` and run
faster.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from gc_mock import GcMock  # type: ignore  # noqa: E402
from slack_mock import SlackMock  # type: ignore  # noqa: E402

PACK_DIR = TESTS_DIR.parent
SCRIPTS_DIR = PACK_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def slack_mock() -> "SlackMock":
    m = SlackMock(require_gc_request=True)
    yield m
    m.close()


@pytest.fixture
def gc_mock(slack_mock: SlackMock) -> "GcMock":
    g = GcMock(city_name="test-city")
    g.set_adapter_callback(slack_mock.url)
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


def _import_publish_module():
    for name in ("slack_chat_publish", "slack_intake_common"):
        sys.modules.pop(name, None)
    import slack_chat_publish  # type: ignore

    return slack_chat_publish


def _import_reply_current_module():
    for name in ("slack_chat_reply_current", "slack_intake_common"):
        sys.modules.pop(name, None)
    import slack_chat_reply_current  # type: ignore

    return slack_chat_reply_current


def test_publish_round_trip_through_gc_to_slack(
    gc_mock: GcMock, slack_mock: SlackMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Full pipeline: slack_chat_publish.py → GcMock → SlackMock.

    Pins:
      * The publish script's binding lookup shape (GET /extmsg/bindings).
      * The publish script's outbound payload shape (POST /extmsg/outbound).
      * GcMock's adapter forwarding sets X-GC-Request: true (the post-#1817
        contract); SlackMock's CSRF gate fails the test if it's missing.
      * thread_ts and idempotency_key propagate through both legs.
    """
    gc_mock.register_binding(
        "gc-test-session",
        conversation_id="C0123ROOM",
        kind="room",
    )

    pub = _import_publish_module()
    exit_code = pub.main([
        "--session", "gc-test-session",
        "--body", "*hello from e2e*",
        "--reply-to", "1700000000.000100",
        "--idempotency-key", "k-e2e-1",
    ])
    assert exit_code is None or exit_code == 0  # main may return None on success

    captured_stdout = capsys.readouterr().out
    parsed = json.loads(captured_stdout)
    assert parsed["session_id"] == "gc-test-session"
    assert parsed["conversation_id"] == "C0123ROOM"
    assert parsed["via"] == "gc"
    assert parsed["result"]["Receipt"]["Delivered"] is True

    # gc-leg assertions: binding lookup + outbound POST.
    gc_calls = gc_mock.calls()
    paths = [c.path for c in gc_calls]
    assert "/v0/city/test-city/extmsg/bindings" in paths, (
        f"expected binding lookup, got paths={paths!r}"
    )
    binding_call = next(c for c in gc_calls if c.path.endswith("/extmsg/bindings"))
    assert binding_call.method == "GET"
    assert binding_call.query.get("session_id") == "gc-test-session"

    outbound_call = next(c for c in gc_calls if c.path.endswith("/extmsg/outbound"))
    assert outbound_call.method == "POST"
    body = outbound_call.body
    assert body["session_id"] == "gc-test-session"
    assert body["text"] == "*hello from e2e*"
    assert body["reply_to_message_id"] == "1700000000.000100"
    assert body["idempotency_key"] == "k-e2e-1"
    conv = body["conversation"]
    assert conv["scope_id"] == "test-city"
    assert conv["provider"] == "slack"
    assert conv["account_id"] == "T0TESTWS"
    assert conv["conversation_id"] == "C0123ROOM"
    assert conv["kind"] == "room"
    # The script sends X-GC-Request on its own POST to gc. Python's
    # BaseHTTPRequestHandler title-cases header names ("X-Gc-Request"),
    # so do a case-insensitive lookup.
    gc_req_header = next(
        (v for k, v in outbound_call.headers.items() if k.lower() == "x-gc-request"),
        None,
    )
    assert gc_req_header in ("1", "true"), (
        f"script must send X-GC-Request to gc, got headers={outbound_call.headers!r}"
    )

    # adapter-leg assertions: SlackMock saw the publish, with X-GC-Request: true.
    slack_calls = slack_mock.calls()
    assert len(slack_calls) == 1, f"expected 1 Slack publish, got {len(slack_calls)}"
    sc = slack_calls[0]
    assert sc.channel == "C0123ROOM"
    assert sc.text == "*hello from e2e*"
    assert sc.thread_ts == "1700000000.000100"
    assert sc.idempotency_key == "k-e2e-1"
    # This is the #1817 regression pin: gc must set X-GC-Request when forwarding
    # to the adapter callback. SlackMock has require_gc_request=True; if gc
    # forgot the header, the request would have 403'd and slack_calls would
    # be empty.
    assert sc.gc_request == "true", (
        f"gc → adapter leg must carry X-GC-Request: true (post-#1817), got {sc.gc_request!r}"
    )


def test_publish_fails_loudly_when_no_binding(
    gc_mock: GcMock, slack_mock: SlackMock
) -> None:
    """Publish without a registered binding fails fast (no silent send-into-the-void)."""
    pub = _import_publish_module()
    # No register_binding() call — the session has no active binding.
    with pytest.raises(SystemExit) as exc_info:
        pub.main([
            "--session", "gc-test-session",
            "--body", "should not be sent",
        ])
    msg = str(exc_info.value)
    assert "no active extmsg binding" in msg, (
        f"expected fail-fast message, got: {msg!r}"
    )
    # SlackMock should have received nothing.
    assert slack_mock.calls() == [], (
        "publish without binding must not reach the adapter; "
        f"got {slack_mock.calls()!r}"
    )


def test_reply_current_publishes_via_group_membership_fallback(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Pin the gastownhall/gascity#1802 group-fallback contract from the slack-pack side.

    Setup mirrors a session that is a participant in a multi-session
    extmsg-group bound to a Slack channel, but does NOT itself hold a
    direct binding to that conversation. Pre-#1831 gc returned
    FailureKind=auth on outbound from such a session; #1831 added a
    fallback to authorize via group membership.

    The test exercises this from slack-pack's vantage point:

      * GcMock is configured with enforce_authorization=True so its
        /extmsg/outbound mirrors gc's authorization chain — direct
        binding first, then group membership, then unauthorized.
      * No binding is registered for the session.
      * A group membership IS registered for (session, conversation).
      * reply-current is invoked with --conversation-id explicit (which
        bypasses the script-level binding lookup so the request actually
        reaches /extmsg/outbound — the gc-side path under test).
      * Assert: GcMock authorizes via "group_membership", SlackMock
        receives the publish, and the script's stdout shows
        Receipt.AuthVia="group_membership".
    """
    # Bring up isolated mocks for this test (the autouse fixture wires
    # the default ones with enforce_authorization=False, which would
    # paper over the auth contract under test).
    slack = SlackMock(require_gc_request=True)
    gc = GcMock(city_name="test-city", enforce_authorization=True)
    gc.set_adapter_callback(slack.url)

    monkeypatch.setenv("GC_API_BASE_URL", gc.url)
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setenv("SLACK_WORKSPACE_ID", "T0TESTWS")
    monkeypatch.setenv("GC_SESSION_ID", "gc-test-session")

    try:
        # NO register_binding(). The session has no direct binding.
        gc.register_group_membership(
            "gc-test-session", conversation_id="C0GROUPCHAN"
        )

        rc = _import_reply_current_module()
        exit_code = rc.main([
            "--session", "gc-test-session",
            "--conversation-id", "C0GROUPCHAN",
            "--kind", "room",
            "--body", "publishing via group fallback",
        ])
        assert exit_code is None or exit_code == 0

        out = json.loads(capsys.readouterr().out)
        assert out["conversation_id"] == "C0GROUPCHAN"
        receipt = out["result"]["Receipt"]
        assert receipt["Delivered"] is True
        assert receipt["AuthVia"] == "group_membership", (
            f"expected publish to authorize via group membership "
            f"(post-#1831 fallback), got AuthVia={receipt.get('AuthVia')!r} "
            "(this surfaces a regression that drops the group-fallback path)"
        )

        # adapter leg: SlackMock saw the publish.
        slack_calls = slack.calls()
        assert len(slack_calls) == 1
        assert slack_calls[0].channel == "C0GROUPCHAN"
        assert slack_calls[0].text == "publishing via group fallback"
        assert slack_calls[0].gc_request == "true"
    finally:
        slack.close()
        gc.close()


def test_outbound_returns_auth_failure_when_session_lacks_binding_and_group(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Negative case: no binding AND no group membership → Delivered: false / FailureKind: auth.

    This pins the response shape slack-pack consumers must handle. Surfaces
    a regression that, e.g., changes the FailureKind label or returns 403
    instead of a typed Receipt envelope. The script itself currently just
    prints whatever gc returns (no exit code change) — that's a known
    behavior gap, but at least the wire contract is locked here.
    """
    slack = SlackMock(require_gc_request=True)
    gc = GcMock(city_name="test-city", enforce_authorization=True)
    gc.set_adapter_callback(slack.url)

    monkeypatch.setenv("GC_API_BASE_URL", gc.url)
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.setenv("SLACK_WORKSPACE_ID", "T0TESTWS")
    monkeypatch.setenv("GC_SESSION_ID", "gc-test-session")

    try:
        # Neither binding nor group membership registered.
        rc = _import_reply_current_module()
        rc.main([
            "--session", "gc-test-session",
            "--conversation-id", "C0LONELY",
            "--kind", "room",
            "--body", "should fail at gc auth",
        ])

        out = json.loads(capsys.readouterr().out)
        receipt = out["result"]["Receipt"]
        assert receipt["Delivered"] is False
        assert receipt["FailureKind"] == "auth", (
            f"expected FailureKind=auth, got {receipt!r}"
        )
        assert "no active binding" in receipt.get("FailureMessage", "")

        # SlackMock should have received nothing (gc rejected before forwarding).
        assert slack.calls() == [], (
            f"unauthorized publish must not reach the adapter; got {slack.calls()!r}"
        )
    finally:
        slack.close()
        gc.close()


def test_reply_current_thread_current_pulls_thread_ts_from_transcript(
    gc_mock: GcMock,
    slack_mock: SlackMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pin the --thread-current resolution chain end-to-end.

    ``--thread-current`` is the protocol used to thread a reply under the
    most recent inbound message in this session's bound conversation.
    The resolution chain is:

      1. GET /events?type=extmsg.inbound&limit=50  → find latest inbound event
      2. extract conversation_id + provider from the event payload
      3. GET /extmsg/transcript?provider=&conversation_id=&kind=room  → list entries
      4. (if empty) GET …&kind=dm  → fall through
      5. take the latest entry where Kind==inbound, use its
         ProviderMessageID as the ``thread_ts`` on the publish

    A regression in the script (e.g. dropping the room→dm fallback, or
    reading the wrong field name) is caught here. A regression in gc
    (e.g. transcript schema changes) is also caught — the test would
    surface as "thread_ts wasn't propagated to SlackMock".
    """
    gc_mock.register_inbound_event(
        target_session="gc-test-session",
        conversation_id="C0THREADCHAN",
        provider="slack",
        kind="room",
    )
    # Seed two transcript entries: an outbound followed by the inbound we
    # want resolved. --thread-current should walk in reverse and pick
    # the inbound one.
    gc_mock.register_transcript_entry(
        conversation_id="C0THREADCHAN",
        kind="room",
        provider_message_id="1700000000.000099",
        message_kind="outbound",
    )
    gc_mock.register_transcript_entry(
        conversation_id="C0THREADCHAN",
        kind="room",
        provider_message_id="1700000000.000777",
        message_kind="inbound",
    )

    rc = _import_reply_current_module()
    exit_code = rc.main([
        "--session", "gc-test-session",
        "--thread-current",
        "--body", "threading under the inbound",
    ])
    assert exit_code is None or exit_code == 0
    capsys.readouterr()  # drain stdout

    # Slack-side: the publish should carry thread_ts pulled from the
    # latest *inbound* transcript entry (000777, not 000099).
    slack_calls = slack_mock.calls()
    assert len(slack_calls) == 1, (
        f"expected 1 publish, got {len(slack_calls)}: {slack_calls!r}"
    )
    sc = slack_calls[0]
    assert sc.channel == "C0THREADCHAN"
    assert sc.thread_ts == "1700000000.000777", (
        f"--thread-current must propagate the latest inbound's ProviderMessageID "
        f"(1700000000.000777) as thread_ts; got {sc.thread_ts!r}"
    )

    # gc-side: confirm the transcript GET was issued (with kind=room first,
    # since the seed put the entries there — no dm fallback expected).
    transcript_calls = [
        c for c in gc_mock.calls()
        if c.path.endswith("/extmsg/transcript")
    ]
    assert transcript_calls, (
        "expected at least one /extmsg/transcript GET, "
        f"got paths={[c.path for c in gc_mock.calls()]!r}"
    )
    # First transcript call must be kind=room (the room-first heuristic).
    first_transcript = transcript_calls[0]
    assert first_transcript.query.get("kind") == "room", (
        f"first transcript lookup must use kind=room; got query={first_transcript.query!r}"
    )
    assert first_transcript.query.get("conversation_id") == "C0THREADCHAN"


def test_reply_current_resolves_conversation_from_inbound_event(
    gc_mock: GcMock, slack_mock: SlackMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """reply-current's inbound-event lookup → conversation envelope → publish.

    Pipeline:
      1. A synthetic extmsg.inbound event is seeded in GcMock targeting our
         session (modeling: a Slack message arrived, the slack-pack adapter
         forwarded it to gc /extmsg/inbound, and gc emitted the event).
      2. reply-current is invoked with only --body — no --conversation-id.
      3. The script issues GET /events?type=extmsg.inbound&limit=50, finds
         the matching event, extracts conversation_id, and publishes back
         through GcMock → SlackMock.

    Pins:
      * The event-stream query shape (GET /events?type=extmsg.inbound).
      * That reply-current's resolution chain reaches the inbound-event
        path (rather than falling through to the binding-lookup or
        SystemExit branches).
      * That the kind is auto-detected from the channel-id prefix (C0… → room).
      * That the resolved conversation_id propagates through to the Slack
        publish.
    """
    gc_mock.register_inbound_event(
        target_session="gc-test-session",
        conversation_id="C0RIGCHAN",  # 'C' prefix → room
        provider="slack",
        kind="room",
    )

    rc = _import_reply_current_module()
    exit_code = rc.main([
        "--session", "gc-test-session",
        "--body", "threaded reply via inbound resolution",
    ])
    assert exit_code is None or exit_code == 0

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["session_id"] == "gc-test-session"
    assert parsed["conversation_id"] == "C0RIGCHAN"
    assert parsed["result"]["Receipt"]["Delivered"] is True

    # gc-leg: events query happened, then the outbound POST.
    gc_calls = gc_mock.calls()
    paths = [c.path for c in gc_calls]
    assert "/v0/city/test-city/events" in paths, (
        f"expected events lookup, got paths={paths!r}"
    )
    events_call = next(c for c in gc_calls if c.path.endswith("/events"))
    assert events_call.method == "GET"
    assert events_call.query.get("type") == "extmsg.inbound"

    outbound = next(c for c in gc_calls if c.path.endswith("/extmsg/outbound"))
    conv = outbound.body["conversation"]
    assert conv["conversation_id"] == "C0RIGCHAN"
    # 'C' prefix should auto-detect to room (the script's
    # _slack_kind_from_channel_id helper).
    assert conv["kind"] == "room", (
        f"expected room kind from C-prefix channel id, got {conv['kind']!r}"
    )

    # adapter-leg: SlackMock saw the publish with the resolved conversation_id.
    slack_calls = slack_mock.calls()
    assert len(slack_calls) == 1
    assert slack_calls[0].channel == "C0RIGCHAN"
    assert slack_calls[0].text == "threaded reply via inbound resolution"
    assert slack_calls[0].gc_request == "true", (
        "gc → adapter leg must carry X-GC-Request: true (post-#1817)"
    )

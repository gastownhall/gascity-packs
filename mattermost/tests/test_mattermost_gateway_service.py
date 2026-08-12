from __future__ import annotations

import json
import pathlib
import re
import struct
import tempfile
import threading
import time
import unittest
from typing import Any
from unittest import mock

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import mattermost_gateway_service as gateway_service
import mattermost_intake_common as common


def mm_id(label: str) -> str:
    """Build a deterministic, syntactically valid 26-char Mattermost id."""
    normalized = re.sub(r"[^a-z0-9]", "", str(label).lower())
    return (normalized + "0" * 26)[:26]


TEAM_ID = mm_id("team1")
ROOM_CHANNEL = mm_id("room22")
OTHER_CHANNEL = mm_id("room23")
DM_CHANNEL = mm_id("dm55")
ROOT_POST = mm_id("root222")
BOT_USER_ID = mm_id("bot999")
BOT_USERNAME = "gcbot"


def make_post(
    post_id: str,
    *,
    channel_id: str,
    message: str = "",
    team_id: str = "",
    root_id: str = "",
    user_id: str = "",
    from_username: str = "alice",
    channel_type: str = "",
    mentions: list[str] | None = None,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a post shaped like `normalize_posted_event` output."""
    post: dict[str, Any] = {
        "id": post_id,
        "channel_id": channel_id,
        "root_id": root_id,
        "team_id": team_id,
        "message": message,
        "user_id": user_id or mm_id(f"user{post_id}"),
        "channel_type": channel_type,
        "mentions": list(mentions or []),
    }
    if from_username is not None:
        post["from_username"] = from_username
        post["sender_name"] = from_username
    if props is not None:
        post["props"] = props
    return post


class _ScriptedWebSocket:
    """Stand-in for GatewayWebSocket driven by a scripted list of events."""

    def __init__(self, events: list[Any], stop_event: threading.Event, url: str = "", headers: dict[str, str] | None = None) -> None:
        self._events = list(events)
        self._stop_event = stop_event
        self.url = url
        self.headers = dict(headers or {})
        self.sent: list[dict[str, Any]] = []
        self.pings = 0
        self.closed_codes: list[int] = []
        self.last_frame_at = time.monotonic()

    def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)

    def send_ping(self, payload: bytes = b"gc") -> None:
        self.pings += 1

    def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed_codes.append(int(code))

    def recv_event(self, timeout: float | None = None) -> Any:
        self.last_frame_at = time.monotonic()
        if self._events:
            item = self._events.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        self._stop_event.set()
        return None


class _HandshakeSocket:
    """Minimal socket double that completes a websocket upgrade."""

    def __init__(self) -> None:
        self.sent = bytearray()
        self._response = b""

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)
        blob = bytes(self.sent)
        if b"\r\n\r\n" in blob and not self._response:
            text = blob.decode("utf-8", errors="replace")
            key = ""
            for line in text.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
            accept = gateway_service.websocket_accept_value(key)
            self._response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode("utf-8")

    def recv(self, length: int) -> bytes:
        chunk = self._response[:length]
        self._response = self._response[length:]
        return chunk

    def settimeout(self, timeout: float | None) -> None:
        return None

    def close(self) -> None:
        return None

    def request_text(self) -> str:
        return bytes(self.sent).decode("utf-8", errors="replace")


class MattermostGatewayServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        gateway_service.CHANNEL_INFO_CACHE.clear()
        gateway_service.CHANNEL_INFO_FETCH_LOCKS.clear()
        gateway_service.STALE_RECLAIM_LOCKS.clear()
        gateway_service.INGRESS_PROCESS_LOCKS.clear()
        gateway_service.GC_API_HEALTH_CACHE["checked_at"] = 0.0
        gateway_service.GC_API_HEALTH_CACHE["reachable"] = True
        gateway_service.AMBIENT_ROOM_BINDINGS_CACHE["config_signature"] = None
        gateway_service.AMBIENT_ROOM_BINDINGS_CACHE["bindings"] = {}
        gateway_service.BOT_IDENTITY_CACHE["fetched_at"] = 0.0
        gateway_service.BOT_IDENTITY_CACHE["user_id"] = ""
        gateway_service.BOT_IDENTITY_CACHE["username"] = ""

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def _new_gateway_worker(self) -> gateway_service.GatewayWorker:
        runtime_state = gateway_service.GatewayRuntimeState()
        with mock.patch.object(gateway_service, "GATEWAY_WORKER_THREADS", 0):
            worker = gateway_service.GatewayWorker(runtime_state)
        self.addCleanup(worker.stop)
        return worker

    def _process(self, post: dict[str, Any]) -> dict[str, Any]:
        return gateway_service.process_inbound_message(post, BOT_USER_ID, BOT_USERNAME)

    # ------------------------------------------------------------------
    # Websocket envelope / protocol shape
    # ------------------------------------------------------------------

    def test_normalize_posted_event_decodes_json_encoded_post_string(self) -> None:
        post_id = mm_id("post100")
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": post_id,
                        "channel_id": ROOM_CHANNEL,
                        "root_id": "",
                        "message": "hello there",
                        "user_id": mm_id("user100"),
                    }
                ),
                "team_id": TEAM_ID,
                "channel_type": "o",
                "channel_name": "town-square",
                "channel_display_name": "Town Square",
                "sender_name": "@alice",
                "mentions": json.dumps([BOT_USER_ID]),
            },
            "broadcast": {"channel_id": ROOM_CHANNEL, "team_id": TEAM_ID},
            "seq": 7,
        }

        post = gateway_service.normalize_posted_event(event)

        self.assertEqual(post["id"], post_id)
        self.assertEqual(post["channel_id"], ROOM_CHANNEL)
        self.assertEqual(post["team_id"], TEAM_ID)
        self.assertEqual(post["channel_type"], "O")
        self.assertEqual(post["channel_name"], "town-square")
        self.assertEqual(post["channel_display_name"], "Town Square")
        self.assertEqual(post["sender_name"], "alice")
        self.assertEqual(post["from_username"], "alice")
        self.assertEqual(post["mentions"], [BOT_USER_ID])
        self.assertEqual(post["message"], "hello there")

    def test_normalize_posted_event_falls_back_to_broadcast_ids(self) -> None:
        post_id = mm_id("post101")
        event = {
            "event": "posted",
            "data": {"post": json.dumps({"id": post_id, "message": "hi"})},
            "broadcast": {"channel_id": ROOM_CHANNEL, "team_id": TEAM_ID},
        }

        post = gateway_service.normalize_posted_event(event)

        self.assertEqual(post["channel_id"], ROOM_CHANNEL)
        self.assertEqual(post["team_id"], TEAM_ID)

    def test_normalize_posted_event_returns_empty_for_unusable_payloads(self) -> None:
        self.assertEqual(gateway_service.normalize_posted_event({}), {})
        self.assertEqual(gateway_service.normalize_posted_event({"data": {"post": "not json"}}), {})
        self.assertEqual(gateway_service.normalize_posted_event({"data": {"post": "[]"}}), {})
        self.assertEqual(gateway_service.normalize_posted_event({"data": "nope"}), {})

    def test_parse_event_mentions_accepts_json_string_and_list(self) -> None:
        self.assertEqual(gateway_service.parse_event_mentions({"mentions": json.dumps([BOT_USER_ID])}), [BOT_USER_ID])
        self.assertEqual(gateway_service.parse_event_mentions({"mentions": [BOT_USER_ID, BOT_USER_ID]}), [BOT_USER_ID])
        self.assertEqual(gateway_service.parse_event_mentions({"mentions": "{bad"}), [])
        self.assertEqual(gateway_service.parse_event_mentions({}), [])

    def test_bot_mention_pattern_requires_username_boundaries(self) -> None:
        pattern = gateway_service.bot_mention_pattern(BOT_USERNAME)
        assert pattern is not None
        self.assertTrue(pattern.search(f"hey @{BOT_USERNAME} please look"))
        self.assertTrue(pattern.search(f"@{BOT_USERNAME}"))
        self.assertTrue(pattern.search(f"@{BOT_USERNAME}, hello"))
        self.assertIsNone(pattern.search(f"@{BOT_USERNAME}x"))
        self.assertIsNone(pattern.search(f"@{BOT_USERNAME}.deploy"))
        self.assertIsNone(pattern.search(f"mail@{BOT_USERNAME}"))
        self.assertIsNone(gateway_service.bot_mention_pattern("  "))

    def test_bot_was_mentioned_matches_literal_username(self) -> None:
        post = {"message": f"@{BOT_USERNAME} can you check", "mentions": []}
        self.assertTrue(gateway_service.bot_was_mentioned(post, BOT_USER_ID, BOT_USERNAME))

    def test_bot_was_mentioned_accepts_mentions_array_without_username_text(self) -> None:
        post = {"message": "can you check this", "mentions": [BOT_USER_ID]}
        self.assertTrue(gateway_service.bot_was_mentioned(post, BOT_USER_ID, BOT_USERNAME))

    def test_bot_was_mentioned_ignores_bare_broadcast_mentions(self) -> None:
        for reserved in ("@channel", "@all", "@here"):
            post = {"message": f"{reserved} standup in five", "mentions": [BOT_USER_ID]}
            self.assertFalse(
                gateway_service.bot_was_mentioned(post, BOT_USER_ID, BOT_USERNAME),
                msg=f"{reserved} alone must not wake the bot",
            )

    def test_bot_was_mentioned_wakes_when_broadcast_and_username_both_present(self) -> None:
        post = {"message": f"@channel and @{BOT_USERNAME} please look", "mentions": [BOT_USER_ID]}
        self.assertTrue(gateway_service.bot_was_mentioned(post, BOT_USER_ID, BOT_USERNAME))

    def test_bot_was_mentioned_ignores_unrelated_mentions(self) -> None:
        post = {"message": "hey team", "mentions": [mm_id("someoneelse")]}
        self.assertFalse(gateway_service.bot_was_mentioned(post, BOT_USER_ID, BOT_USERNAME))

    def test_strip_bot_mentions_removes_only_the_bot_username(self) -> None:
        stripped = gateway_service.strip_bot_mentions(f"@{BOT_USERNAME} @sky please check", BOT_USERNAME)
        self.assertEqual(stripped, "@sky please check")

    def test_extract_alias_mentions_skips_reserved_mentions(self) -> None:
        self.assertEqual(gateway_service.extract_alias_mentions("@sky @channel @all @here @lawrence"), ["sky", "lawrence"])

    def test_display_name_from_message_skips_none_strings(self) -> None:
        post = {"props": {"override_username": None}, "from_username": None, "sender_name": None}
        self.assertEqual(gateway_service.display_name_from_message(post), "mattermost-user")

    def test_display_name_from_message_prefers_override_username(self) -> None:
        post = {"props": {"override_username": "@webhook-bot"}, "from_username": "alice"}
        self.assertEqual(gateway_service.display_name_from_message(post), "webhook-bot")

    def test_message_root_post_id_uses_flat_root_threading(self) -> None:
        reply = {"id": mm_id("post300"), "root_id": ROOT_POST}
        root = {"id": ROOT_POST, "root_id": ""}
        self.assertEqual(gateway_service.message_root_post_id(reply), ROOT_POST)
        self.assertEqual(gateway_service.message_root_post_id(root), ROOT_POST)

    def test_conversation_fields_distinguish_dm_room_and_thread(self) -> None:
        dm_post = make_post(mm_id("post310"), channel_id=DM_CHANNEL)
        room_post = make_post(mm_id("post311"), channel_id=ROOM_CHANNEL, team_id=TEAM_ID)
        thread_post = make_post(mm_id("post312"), channel_id=ROOM_CHANNEL, team_id=TEAM_ID, root_id=ROOT_POST)

        self.assertEqual(gateway_service.conversation_fields(dm_post), (f"dm:{DM_CHANNEL}", DM_CHANNEL))
        self.assertEqual(gateway_service.conversation_fields(room_post), (f"team:{TEAM_ID} channel:{ROOM_CHANNEL}", ROOM_CHANNEL))
        self.assertEqual(
            gateway_service.conversation_fields(thread_post),
            (f"team:{TEAM_ID} channel:{ROOM_CHANNEL} thread:{ROOT_POST}", f"{ROOM_CHANNEL}/{ROOT_POST}"),
        )

    def test_referenced_post_id_reads_props_reply_target(self) -> None:
        target = mm_id("post320")
        self.assertEqual(gateway_service.referenced_post_id({"props": {"reply_to_post_id": target}}), target)
        self.assertEqual(gateway_service.referenced_post_id({"props": {"in_reply_to_id": target}}), target)
        self.assertEqual(gateway_service.referenced_post_id({"root_id": ROOT_POST}), "")
        self.assertEqual(gateway_service.referenced_post_id({}), "")

    def test_bound_room_claims_message_covers_threads_in_the_same_channel(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)
        config = common.load_config()

        self.assertTrue(gateway_service.bound_room_claims_message(config, ROOM_CHANNEL))
        self.assertFalse(gateway_service.bound_room_claims_message(config, OTHER_CHANNEL))

    # ------------------------------------------------------------------
    # Binding resolution and direct routing
    # ------------------------------------------------------------------

    def test_process_inbound_dm_routes_to_bound_session(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post101")
        post = make_post(post_id, channel_id=DM_CHANNEL, message="hello from mattermost")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "suspended"}}
        ), mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-1"},
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "sky")
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn("kind: mattermost_human_message", envelope)
        self.assertIn('untrusted_body_json: "hello from mattermost"', envelope)
        self.assertIn(
            f"reply_tool: gc mattermost reply-current --conversation-id {DM_CHANNEL} --root-id {post_id} --body-file <path>",
            envelope,
        )
        self.assertIn(f"conversation: dm:{DM_CHANNEL}", envelope)
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["status"], "delivered")

    def test_process_inbound_dm_routes_flat_when_thread_replies_disabled(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "dm",
            DM_CHANNEL,
            ["sky"],
            policy={"thread_replies": False},
        )
        post_id = mm_id("post101b")
        post = make_post(post_id, channel_id=DM_CHANNEL, message="hello from mattermost")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "suspended"}}
        ), mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-1"},
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        envelope = deliver_session_message.call_args.args[1]
        reply_tool_line = next(line for line in envelope.splitlines() if line.startswith("reply_tool:"))
        self.assertEqual(
            reply_tool_line,
            f"reply_tool: gc mattermost reply-current --conversation-id {DM_CHANNEL} --body-file <path> "
            "(this binding posts flat — do NOT pass --root-id yourself)",
        )
        self.assertIn("publish_root_post_id: \n", envelope)

    def test_process_inbound_room_message_targets_only_named_alias(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post_id = mm_id("post202")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @Sky please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "sky")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["delivery"], "targeted")
        self.assertEqual(receipt["mentioned_aliases"], ["sky"])

    def test_process_inbound_room_message_matches_session_names_case_insensitively(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["Sky"], TEAM_ID)
        post = make_post(
            mm_id("post207"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common, "session_index_by_name", return_value={"Sky": {"session_name": "Sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "Sky")

    def test_process_inbound_room_message_broadcasts_to_all_bound_selectors(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post = make_post(
            mm_id("post214"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} please investigate",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        self.assertEqual(deliver_session_message.call_count, 2)
        self.assertEqual(deliver_session_message.call_args_list[0].args[0], "sky")
        self.assertEqual(deliver_session_message.call_args_list[1].args[0], "lawrence")

    def test_process_inbound_room_message_rejects_unknown_alias(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post_id = mm_id("post303")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @ghost please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "rejected_targeting")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "unknown_alias:ghost")

    def test_resolve_targets_reports_alias_collisions_and_unknown_aliases(self) -> None:
        binding = {"id": f"room:{ROOM_CHANNEL}", "kind": "room", "session_names": ["Sky", "sky", "lawrence"]}

        self.assertEqual(gateway_service.resolve_targets(binding, ["sky"]), ([], "targeted", "ambiguous_alias:sky"))
        self.assertEqual(gateway_service.resolve_targets(binding, ["ghost"]), ([], "targeted", "unknown_alias:ghost"))
        self.assertEqual(gateway_service.resolve_targets(binding, ["Lawrence"]), (["lawrence"], "targeted", ""))
        self.assertEqual(
            gateway_service.resolve_targets(binding, []),
            (["Sky", "sky", "lawrence"], "broadcast", ""),
        )
        self.assertEqual(
            gateway_service.resolve_targets(binding, [], require_targeted_aliases=True),
            ([], "targeted", "target_required"),
        )

    def test_process_inbound_message_dedupes_existing_ingress(self) -> None:
        post_id = mm_id("post404")
        common.save_chat_ingress({"ingress_id": f"in-{post_id}", "status": "delivered"})
        post = make_post(post_id, channel_id=DM_CHANNEL, message="hello from mattermost")

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "duplicate")
        deliver_session_message.assert_not_called()

    def test_process_inbound_room_message_ignores_non_mentions(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post = make_post(
            mm_id("post505"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message="just chatting here",
        )

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored")
        self.assertEqual(outcome["reason"], "not_mentioned")
        deliver_session_message.assert_not_called()

    def test_process_inbound_room_message_ignores_bare_broadcast_mention(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)
        post = make_post(
            mm_id("post505b"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message="@channel standup time",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored")
        self.assertEqual(outcome["reason"], "not_mentioned")
        deliver_session_message.assert_not_called()

    def test_process_inbound_room_message_ignores_mentions_array_for_aliases(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post_id = mm_id("post606")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} please investigate",
            mentions=[BOT_USER_ID, mm_id("otheruser")],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        self.assertEqual(deliver_session_message.call_count, 2)
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["delivery"], "broadcast")
        self.assertEqual(receipt["mentioned_aliases"], [])

    def test_process_inbound_room_message_treats_reserved_mentions_as_broadcast(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post_id = mm_id("post607")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @channel please look at this",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        self.assertEqual(deliver_session_message.call_count, 2)
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["delivery"], "broadcast")
        self.assertEqual(receipt["mentioned_aliases"], [])

    def test_process_inbound_room_message_records_partial_failed_delivery(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky", "lawrence"], TEAM_ID)
        post_id = mm_id("post707")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} please investigate",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(
            common,
            "deliver_session_message",
            side_effect=[{"status": "accepted"}, common.GCAPIError("boom")],
        ):
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "partial_failed")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["status"], "partial_failed")
        self.assertEqual(receipt["targets"][0]["status"], "delivered")
        self.assertEqual(receipt["targets"][1]["status"], "failed")

    def test_process_inbound_unbound_room_message_records_rejected_unbound(self) -> None:
        post_id = mm_id("post708")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} anyone home?",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "rejected_unbound")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "binding_not_found")

    def test_process_inbound_ignores_bot_and_system_posts(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        bot_post = make_post(mm_id("post709"), channel_id=DM_CHANNEL, message="hi", user_id=BOT_USER_ID)
        system_post = make_post(mm_id("post710"), channel_id=DM_CHANNEL, message="hi")
        system_post["type"] = "system_join_channel"

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            self.assertEqual(self._process(bot_post)["reason"], "bot_message")
            self.assertEqual(self._process(system_post)["reason"], "bot_message")

        deliver_session_message.assert_not_called()

    def test_process_inbound_ignores_post_without_channel(self) -> None:
        post = make_post(mm_id("post711"), channel_id="", message="hi")

        outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored")
        self.assertEqual(outcome["reason"], "missing_channel")

    # ------------------------------------------------------------------
    # Ambient rooms
    # ------------------------------------------------------------------

    def test_process_inbound_ambient_room_message_routes_targeted_alias_without_bot_mention(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post_id = mm_id("post506")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message="@Sky please check the shard",
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "sky")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["delivery"], "targeted")
        self.assertEqual(receipt["mentioned_aliases"], ["sky"])

    def test_process_inbound_ambient_thread_message_derives_thread_from_root_id(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        common.save_bot_token("bot-token")
        post = make_post(
            mm_id("post506b"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            message="@sky please check the shard",
        )

        with mock.patch.object(common, "describe_channel") as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        describe_channel.assert_not_called()
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"conversation: team:{TEAM_ID} channel:{ROOM_CHANNEL} thread:{ROOT_POST}", envelope)
        self.assertIn(f"conversation_key: {ROOM_CHANNEL}/{ROOT_POST}", envelope)
        self.assertIn(f"publish_conversation_id: {ROOM_CHANNEL}", envelope)
        self.assertIn(f"publish_root_post_id: {ROOT_POST}", envelope)

    def test_process_inbound_bot_mentioned_thread_uses_binding_channel_metadata(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky"],
            TEAM_ID,
            channel_metadata={"channel_type": "O"},
        )
        common.save_bot_token("bot-token")
        post = make_post(
            mm_id("post506c"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(common, "describe_channel") as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        describe_channel.assert_not_called()
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"binding_id: room:{ROOM_CHANNEL}", envelope)
        self.assertIn(f"conversation: team:{TEAM_ID} channel:{ROOM_CHANNEL} thread:{ROOT_POST}", envelope)

    def test_process_inbound_bot_mentioned_thread_missing_metadata_falls_back_to_lookup(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)
        common.save_bot_token("bot-token")
        post = make_post(
            mm_id("post506d"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "describe_channel",
            return_value={"id": ROOM_CHANNEL, "type": "O", "team_id": TEAM_ID},
        ) as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        describe_channel.assert_called_once()
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"conversation: team:{TEAM_ID} channel:{ROOM_CHANNEL} thread:{ROOT_POST}", envelope)

    def test_process_inbound_room_message_marks_lookup_failure_as_retryable(self) -> None:
        common.save_bot_token("bot-token")
        post_id = mm_id("post213")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            message=f"@{BOT_USERNAME} can you take a look?",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common, "describe_channel", side_effect=common.MattermostAPIError("GET channel failed", status_code=500)
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "failed_lookup")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["status"], "failed_lookup")

    def test_process_inbound_ambient_room_message_ignores_untargeted_body(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post_id = mm_id("post507")
        post = make_post(post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="just chatting here")

        with mock.patch.object(common, "session_index_by_name") as session_index_by_name, mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored_untargeted")
        session_index_by_name.assert_not_called()
        deliver_session_message.assert_not_called()
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["status"], "ignored_untargeted")
        self.assertEqual(receipt["reason"], "ambient_target_required")

    def test_process_inbound_ambient_room_message_routes_untargeted_single_session_when_enabled(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["randy"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )
        post_id = mm_id("post507single")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="what changed since yesterday?"
        )

        with mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "randy")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["status"], "delivered")
        self.assertEqual(receipt["delivery"], "broadcast")

    def test_process_inbound_ambient_room_message_routes_unknown_alias_to_sticky_single_session(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["deacon__deacon"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )
        post_id = mm_id("post507sticky")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message="@deacon: can you check the dashboard deploy?",
        )

        with mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "deacon__deacon")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["status"], "delivered")
        self.assertEqual(receipt["delivery"], "broadcast")
        self.assertEqual(receipt["mentioned_aliases"], ["deacon"])

    def test_process_inbound_ambient_room_message_ignores_unknown_alias_with_receipt(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post_id = mm_id("post507a")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@ghost please check the shard"
        )

        with mock.patch.object(common, "session_index_by_name") as session_index_by_name, mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored_untargeted")
        session_index_by_name.assert_not_called()
        deliver_session_message.assert_not_called()
        receipt = common.load_chat_ingress(f"in-{post_id}")
        self.assertEqual(receipt["status"], "ignored_untargeted")
        self.assertEqual(receipt["reason"], "ambient_target_required")

    def test_process_inbound_ambient_room_message_dedupes_replayed_unknown_alias_after_binding_changes(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post = make_post(
            mm_id("post507aa"), channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@ghost please check"
        )

        with mock.patch.object(common, "session_index_by_name") as session_index_by_name, mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            first_outcome = self._process(post)

        self.assertEqual(first_outcome["status"], "ignored_untargeted")
        session_index_by_name.assert_not_called()
        deliver_session_message.assert_not_called()

        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence", "ghost"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )

        with mock.patch.object(common, "session_index_by_name") as session_index_by_name, mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            replay_outcome = self._process(post)

        self.assertEqual(replay_outcome["status"], "duplicate")
        session_index_by_name.assert_not_called()
        deliver_session_message.assert_not_called()

    def test_process_inbound_ambient_room_message_preserves_unknown_alias_rejection_when_mixed(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post_id = mm_id("post507b")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@sky @ghost please check the shard"
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "rejected_targeting")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "unknown_alias:ghost")

    def test_process_inbound_ambient_room_message_still_requires_target_when_bot_mentioned(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post_id = mm_id("post508")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored_untargeted")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "ambient_target_required")

    def test_process_inbound_bot_mentioned_ambient_room_routes_untargeted_single_session_when_enabled(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["randy"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )
        post_id = mm_id("post508single")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} what changed since yesterday?",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common, "session_index_by_name", return_value={"randy": {"session_name": "randy", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "randy")
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["status"], "delivered")

    def test_process_inbound_bot_mentioned_ambient_room_delivers_to_unmaterialized_named_selector(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["employees.corp--alex"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )
        post_id = mm_id("post508unmat")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} are you there?",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "employees.corp--alex")
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["status"], "delivered")

    def test_process_inbound_bot_mentioned_ambient_thread_still_requires_target(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        post_id = mm_id("post508b")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message=f"@{BOT_USERNAME} please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common,
            "session_index_by_name",
            return_value={
                "sky": {"session_name": "sky", "state": "active"},
                "lawrence": {"session_name": "lawrence", "state": "active"},
            },
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored_untargeted")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "ambient_target_required")

    def test_process_inbound_unmentioned_unbound_channel_does_not_probe_channel_info(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        common.save_bot_token("bot-token")
        post = make_post(
            mm_id("post509"), channel_id=OTHER_CHANNEL, team_id=TEAM_ID, message="@sky please check the shard"
        )

        with mock.patch.object(common, "describe_channel") as describe_channel, mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored")
        self.assertEqual(outcome["reason"], "not_mentioned")
        describe_channel.assert_not_called()
        deliver_session_message.assert_not_called()

    # ------------------------------------------------------------------
    # Channel metadata caching
    # ------------------------------------------------------------------

    def test_process_inbound_bound_room_message_does_not_fetch_channel_info_when_metadata_is_known(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky"],
            TEAM_ID,
            channel_metadata={"channel_type": "O"},
        )
        common.save_bot_token("bot-token")
        post = make_post(
            mm_id("post507bb"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(common, "describe_channel") as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        describe_channel.assert_not_called()
        deliver_session_message.assert_called_once()

    def test_process_inbound_legacy_main_room_binding_survives_lookup_failure(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)
        common.save_bot_token("bot-token")
        post = make_post(
            mm_id("post507c"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common, "describe_channel", side_effect=common.MattermostAPIError("GET failed", status_code=500)
        ), mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()

    def test_process_inbound_legacy_main_room_binding_caches_metadata_after_successful_lookup(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)
        common.save_bot_token("bot-token")
        first_post = make_post(
            mm_id("post507d"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard",
            mentions=[BOT_USER_ID],
        )
        second_post = make_post(
            mm_id("post507e"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message=f"@{BOT_USERNAME} @sky please check the shard again",
            mentions=[BOT_USER_ID],
        )

        with mock.patch.object(
            common, "describe_channel", return_value={"id": ROOM_CHANNEL, "type": "O", "team_id": TEAM_ID}
        ) as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            first_outcome = self._process(first_post)

        self.assertEqual(first_outcome["status"], "delivered")
        describe_channel.assert_called_once()
        deliver_session_message.assert_called_once()
        binding = common.resolve_chat_binding(common.load_config(), common.chat_binding_id("room", ROOM_CHANNEL))
        assert binding is not None
        self.assertNotIn("channel_type", binding)
        self.assertEqual(
            common.load_channel_metadata_cache(ROOM_CHANNEL),
            {"channel_type": "O", "channel_team_id": TEAM_ID},
        )

        gateway_service.CHANNEL_INFO_CACHE.clear()

        with mock.patch.object(common, "describe_channel") as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            second_outcome = self._process(second_post)

        self.assertEqual(second_outcome["status"], "delivered")
        describe_channel.assert_not_called()
        deliver_session_message.assert_called_once()

    def test_persist_binding_channel_metadata_writes_runtime_cache_without_rewriting_binding(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
        )
        stale_binding = common.resolve_chat_binding(common.load_config(), common.chat_binding_id("room", ROOM_CHANNEL))
        assert stale_binding is not None
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky", "lawrence"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "peer_fanout_enabled": True},
        )

        gateway_service.persist_binding_channel_metadata({**stale_binding, "channel_type": "O"})

        binding = common.resolve_chat_binding(common.load_config(), common.chat_binding_id("room", ROOM_CHANNEL))
        assert binding is not None
        self.assertEqual(binding["session_names"], ["sky", "lawrence"])
        self.assertNotIn("channel_type", binding)
        self.assertTrue(common.binding_peer_policy(binding)["peer_fanout_enabled"])
        self.assertEqual(common.load_channel_metadata_cache(ROOM_CHANNEL), {"channel_type": "O"})

    # ------------------------------------------------------------------
    # Room launch surfaces
    # ------------------------------------------------------------------

    def _save_room_launch(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "launch_id": f"room-launch:{ROOT_POST}",
            "launcher_id": f"launch-room:{ROOM_CHANNEL}",
            "team_id": TEAM_ID,
            "conversation_id": ROOM_CHANNEL,
            "root_post_id": ROOT_POST,
            "qualified_handle": "corp/sky",
            "session_alias": "mm-123-sky",
            "session_name": "mm-sky",
            "participants": {
                "corp/sky": {
                    "qualified_handle": "corp/sky",
                    "session_alias": "mm-123-sky",
                    "session_name": "mm-sky",
                    "session_id": "gc-sky",
                }
            },
            "state": "active",
        }
        payload.update(overrides)
        return common.save_room_launch(payload)

    def test_process_inbound_room_launch_routes_handle_without_bot_mention(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post208")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@@sky please help"
        )

        with mock.patch.object(common, "resolve_agent_handle", return_value=("corp/sky", "")), mock.patch.object(
            common,
            "ensure_room_launch_session",
            return_value={
                "launch_id": f"room-launch:{post_id}",
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "s-gc-123",
                "session_id": "gc-123",
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "s-gc-123")
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"binding_id: launch-room:{ROOM_CHANNEL}", envelope)
        self.assertIn(f"launch_id: room-launch:{post_id}", envelope)
        self.assertIn("launch_session_alias: mm-123-sky", envelope)
        self.assertIn("reply_tool: gc mattermost reply-current --body-file <path>", envelope)
        self.assertIn(
            "reply_turn_requirement: if you intend to answer, do not end the turn without a successful reply-current",
            envelope,
        )
        self.assertIn(
            "peer_targeting_rule: include @@rig/alias in the Mattermost reply if you want another launcher participant to receive it as peer input",
            envelope,
        )
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["launch_id"], f"room-launch:{post_id}")

    def test_process_inbound_room_launch_recovers_empty_team_content_via_rest(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post208b")
        user_id = mm_id("user208b")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            channel_type="O",
            message="",
            user_id=user_id,
            from_username="",
        )

        with mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={
                "id": post_id,
                "channel_id": ROOM_CHANNEL,
                "message": "@@corp/sky please help",
                "user_id": user_id,
            },
        ) as mattermost_api_request, mock.patch.object(
            common, "describe_user", return_value={"username": "alice"}
        ), mock.patch.object(common, "resolve_agent_handle", return_value=("corp/sky", "")), mock.patch.object(
            common,
            "ensure_room_launch_session",
            return_value={
                "launch_id": f"room-launch:{post_id}",
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "s-gc-123",
                "session_id": "gc-123",
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        mattermost_api_request.assert_called_once_with("GET", f"/posts/{post_id}")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "s-gc-123")
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn('untrusted_body_json: "@@corp/sky please help"', envelope)
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["body_preview"], "@@corp/sky please help")
        self.assertEqual(receipt["from_display"], "alice")
        self.assertEqual((receipt.get("message_debug") or {}).get("content_source"), "rest_fallback")

    def test_process_inbound_room_launch_marks_team_empty_content_unavailable(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post208c")
        post = make_post(post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="")

        with mock.patch.object(common, "mattermost_api_request", return_value=[]), mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored_empty")
        deliver_session_message.assert_not_called()
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["reason"], "message_content_unavailable")
        self.assertEqual((receipt.get("message_debug") or {}).get("content_source"), "gateway_empty_rest_unavailable")

    def test_process_inbound_room_launch_thread_routes_follow_up_without_bot_mention(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        self._save_room_launch(
            participants={
                "corp/sky": {
                    "qualified_handle": "corp/sky",
                    "session_alias": "mm-123-sky",
                    "session_name": "mm-123-sky",
                    "primer_version": common.ROOM_LAUNCH_PRIMER_VERSION,
                    "primed_at": "2026-03-22T00:00:00Z",
                }
            },
            session_name="mm-123-sky",
        )
        post_id = mm_id("post209")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message="follow up",
        )

        with mock.patch.object(
            common,
            "ensure_room_launch_session_for_handle",
            return_value=(
                common.load_room_launch(f"room-launch:{ROOT_POST}") or {},
                {
                    "qualified_handle": "corp/sky",
                    "session_alias": "mm-123-sky",
                    "session_name": "mm-123-sky",
                    "session_id": "gc-sky",
                },
            ),
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "mm-123-sky")
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"conversation: team:{TEAM_ID} channel:{ROOM_CHANNEL} thread:{ROOT_POST}", envelope)
        self.assertIn(f"publish_conversation_id: {ROOM_CHANNEL}", envelope)
        self.assertIn(f"publish_root_post_id: {ROOT_POST}", envelope)
        self.assertTrue(str(common.load_room_launch(f"room-launch:{ROOT_POST}").get("last_activity_at", "")).strip())

    def test_process_inbound_room_launch_rejects_ambiguous_handle(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post210")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@@sky please help"
        )

        with mock.patch.object(common, "resolve_agent_handle", return_value=("", "ambiguous_handle")), mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "rejected_targeting")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "ambiguous_handle")

    def test_process_inbound_room_launch_rejects_multiple_handles(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post210a")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@@corp/sky @@corp/alex help"
        )

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "rejected_targeting")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "multiple_handles_not_supported")

    def test_process_inbound_room_launch_ignores_untargeted_mention_only_post(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post210d")
        post = make_post(post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="please help")

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored_untargeted")
        deliver_session_message.assert_not_called()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "launch_handle_required")

    def test_process_inbound_room_launch_respond_all_uses_default_handle(self) -> None:
        common.set_room_launcher(
            common.load_config(),
            TEAM_ID,
            ROOM_CHANNEL,
            response_mode="respond_all",
            default_qualified_handle="corp/sky",
        )
        post_id = mm_id("post210b")
        post = make_post(post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="please help")

        with mock.patch.object(
            common,
            "ensure_room_launch_session",
            return_value={
                "launch_id": f"room-launch:{post_id}",
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "mm-123-sky",
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertIn("launch_qualified_handle: corp/sky", deliver_session_message.call_args.args[1])

    def test_process_inbound_room_launch_respond_all_honors_mixed_case_explicit_handle(self) -> None:
        common.set_room_launcher(
            common.load_config(),
            TEAM_ID,
            ROOM_CHANNEL,
            response_mode="respond_all",
            default_qualified_handle="corp/default",
        )
        post_id = mm_id("post210c")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@@Sky please help"
        )

        with mock.patch.object(common, "resolve_agent_handle", return_value=("corp/sky", "")), mock.patch.object(
            common,
            "ensure_room_launch_session",
            return_value={
                "launch_id": f"room-launch:{post_id}",
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "mm-123-sky",
            },
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn("launch_qualified_handle: corp/sky", envelope)
        self.assertNotIn("launch_qualified_handle: corp/default", envelope)

    def test_process_inbound_room_launch_thread_retargets_to_new_handle(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        self._save_room_launch()
        post_id = mm_id("post211")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message="@@alex please join",
        )

        with mock.patch.object(common, "resolve_agent_handle", return_value=("corp/alex", "")), mock.patch.object(
            common,
            "ensure_room_launch_session_for_handle",
            return_value=(
                {
                    **(common.load_room_launch(f"room-launch:{ROOT_POST}") or {}),
                    "participants": {
                        "corp/sky": {
                            "qualified_handle": "corp/sky",
                            "session_alias": "mm-123-sky",
                            "session_name": "mm-sky",
                            "session_id": "gc-sky",
                        },
                        "corp/alex": {
                            "qualified_handle": "corp/alex",
                            "session_alias": "mm-456-alex",
                            "session_name": "mm-alex",
                            "session_id": "gc-alex",
                        },
                    },
                },
                {
                    "qualified_handle": "corp/alex",
                    "session_alias": "mm-456-alex",
                    "session_name": "mm-alex",
                    "session_id": "gc-alex",
                },
            ),
        ), mock.patch.object(common, "set_room_launch_last_addressed"), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted"}
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "mm-alex")
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn("launch_qualified_handle: corp/alex", envelope)
        self.assertIn('thread_participants_json: [{"qualified_handle": "corp/alex"', envelope)
        self.assertIn("reply_success_signal: record.remote_message_id", envelope)
        self.assertIn(
            "peer_targeting_rule: include @@rig/alias in the Mattermost reply if you want another launcher participant to receive it as peer input",
            envelope,
        )
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["routing_mode"], "explicit_handle")
        self.assertEqual(receipt["qualified_handle"], "corp/alex")

    def test_process_inbound_room_launch_thread_reply_targets_matching_agent_publish(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        agent_post_id = mm_id("postagent1")
        self._save_room_launch(
            participants={
                "corp/sky": {
                    "qualified_handle": "corp/sky",
                    "session_alias": "mm-123-sky",
                    "session_name": "mm-sky",
                    "session_id": "gc-sky",
                },
                "corp/alex": {
                    "qualified_handle": "corp/alex",
                    "session_alias": "mm-456-alex",
                    "session_name": "mm-alex",
                    "session_id": "gc-alex",
                },
            },
            message_targets={agent_post_id: "corp/alex"},
        )
        post_id = mm_id("post212a")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message="what do you think?",
            props={"reply_to_post_id": agent_post_id},
        )

        with mock.patch.object(
            common,
            "ensure_room_launch_session_for_handle",
            return_value=(
                common.load_room_launch(f"room-launch:{ROOT_POST}") or {},
                {
                    "qualified_handle": "corp/alex",
                    "session_alias": "mm-456-alex",
                    "session_name": "mm-alex",
                    "session_id": "gc-alex",
                },
            ),
        ), mock.patch.object(common, "set_room_launch_last_addressed"), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted"}
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        self.assertEqual(deliver_session_message.call_args.args[0], "mm-alex")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["routing_mode"], "reply_to")
        self.assertIn(f"reply_to_mattermost_post_id: {agent_post_id}", deliver_session_message.call_args.args[1])

    def test_process_inbound_room_launch_thread_uses_last_addressed_fallback(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        self._save_room_launch(
            last_addressed_qualified_handle="corp/alex",
            participants={
                "corp/sky": {
                    "qualified_handle": "corp/sky",
                    "session_alias": "mm-123-sky",
                    "session_name": "mm-sky",
                    "session_id": "gc-sky",
                },
                "corp/alex": {
                    "qualified_handle": "corp/alex",
                    "session_alias": "mm-456-alex",
                    "session_name": "mm-alex",
                    "session_id": "gc-alex",
                },
            },
        )
        post_id = mm_id("post212b")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message="keep going",
        )

        with mock.patch.object(
            common,
            "ensure_room_launch_session_for_handle",
            return_value=(
                common.load_room_launch(f"room-launch:{ROOT_POST}") or {},
                {
                    "qualified_handle": "corp/alex",
                    "session_alias": "mm-456-alex",
                    "session_name": "mm-alex",
                    "session_id": "gc-alex",
                },
            ),
        ), mock.patch.object(common, "set_room_launch_last_addressed"), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted"}
        ) as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "delivered")
        self.assertEqual(deliver_session_message.call_args.args[0], "mm-alex")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["routing_mode"], "last_addressed")

    def test_process_inbound_room_launch_thread_ignores_reply_under_unknown_root(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, ROOM_CHANNEL)
        post_id = mm_id("post212c")
        post = make_post(
            post_id,
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=mm_id("unknownroot"),
            channel_type="O",
            message="anyone there?",
        )

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(post)

        self.assertEqual(outcome["status"], "ignored")
        self.assertEqual(outcome["reason"], "not_mentioned")
        deliver_session_message.assert_not_called()

    # ------------------------------------------------------------------
    # extmsg fabric interplay
    # ------------------------------------------------------------------

    def test_record_extmsg_inbound_skips_bound_room_mentions(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["randy"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )
        worker = self._new_gateway_worker()
        post = make_post(
            mm_id("post207a"), channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@randy what changed?"
        )

        with mock.patch.object(common, "resolve_at_mentions", return_value=["randy"]) as resolve_at_mentions, mock.patch.object(
            common, "resolve_mention_targets"
        ) as resolve_mention_targets, mock.patch.object(common, "launch_thread_for_mentions") as launch_thread_for_mentions:
            handled = worker._record_extmsg_inbound(post, BOT_USER_ID, BOT_USERNAME)

        self.assertFalse(handled)
        resolve_at_mentions.assert_not_called()
        resolve_mention_targets.assert_not_called()
        launch_thread_for_mentions.assert_not_called()

    def test_record_extmsg_inbound_skips_thread_when_channel_is_bound(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["randy"], TEAM_ID)
        worker = self._new_gateway_worker()
        post = make_post(
            mm_id("post207b"),
            channel_id=ROOM_CHANNEL,
            team_id=TEAM_ID,
            root_id=ROOT_POST,
            channel_type="O",
            message="@randy still there?",
        )

        with mock.patch.object(common, "deliver_to_extmsg") as deliver_to_extmsg, mock.patch.object(
            common, "normalize_to_extmsg_message"
        ) as normalize_to_extmsg_message:
            handled = worker._record_extmsg_inbound(post, BOT_USER_ID, BOT_USERNAME)

        self.assertFalse(handled)
        normalize_to_extmsg_message.assert_not_called()
        deliver_to_extmsg.assert_not_called()

    def test_record_extmsg_inbound_leaves_dm_thread_replies_to_the_dm_binding(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        worker = self._new_gateway_worker()
        post = make_post(
            mm_id("post207c"),
            channel_id=DM_CHANNEL,
            root_id=ROOT_POST,
            channel_type="D",
            message="following up in the thread",
        )

        with mock.patch.object(common, "deliver_to_extmsg") as deliver_to_extmsg, mock.patch.object(
            common, "normalize_to_extmsg_message"
        ) as normalize_to_extmsg_message, mock.patch.object(common, "resolve_nl_agent_mentions") as resolve_nl_agent_mentions:
            handled = worker._record_extmsg_inbound(post, BOT_USER_ID, BOT_USERNAME)

        self.assertFalse(handled)
        normalize_to_extmsg_message.assert_not_called()
        deliver_to_extmsg.assert_not_called()
        resolve_nl_agent_mentions.assert_not_called()

    def test_handle_gateway_message_routes_dm_thread_reply_to_bound_session(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        worker = self._new_gateway_worker()
        post_id = mm_id("post207d")
        post = make_post(
            post_id, channel_id=DM_CHANNEL, root_id=ROOT_POST, channel_type="D", message="following up in the thread"
        )

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            worker.handle_gateway_message(post, BOT_USER_ID, BOT_USERNAME)

        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "sky")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["binding_id"], f"dm:{DM_CHANNEL}")
        self.assertEqual(receipt["status"], "delivered")
        self.assertIn(f"root_id: {ROOT_POST}", deliver_session_message.call_args.args[1])

    def test_agent_at_mentions_drops_the_bots_own_username(self) -> None:
        mentions = gateway_service.GatewayWorker._agent_at_mentions(
            f"@{BOT_USERNAME} please ask @randy and @sky", BOT_USERNAME
        )

        self.assertEqual(mentions, ["randy", "sky"])

    def test_handle_gateway_message_prefers_bound_room_over_extmsg_thread_launch(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["randy"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )
        worker = self._new_gateway_worker()
        post_id = mm_id("post207aa")
        post = make_post(
            post_id, channel_id=ROOM_CHANNEL, team_id=TEAM_ID, channel_type="O", message="@randy what changed?"
        )

        with mock.patch.object(common, "launch_thread_for_mentions") as launch_thread_for_mentions, mock.patch.object(
            common, "session_index_by_name", return_value={"randy": {"session_name": "randy", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}) as deliver_session_message:
            worker.handle_gateway_message(post, BOT_USER_ID, BOT_USERNAME)

        launch_thread_for_mentions.assert_not_called()
        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "randy")
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["binding_id"], f"room:{ROOM_CHANNEL}")
        self.assertEqual(receipt["status"], "delivered")

    # ------------------------------------------------------------------
    # Ingress receipt lifecycle
    # ------------------------------------------------------------------

    def _stale_receipt(self, ingress_id: str, status: str) -> None:
        common.atomic_write_json(
            common.chat_ingress_path(ingress_id),
            {
                "ingress_id": ingress_id,
                "status": status,
                "created_at": "2000-01-01T00:00:00Z",
                "updated_at": "2000-01-01T00:00:00Z",
            },
        )

    def _dm_post(self, post_id: str) -> dict[str, Any]:
        return make_post(post_id, channel_id=DM_CHANNEL, message="hello from mattermost")

    def test_process_inbound_message_reclaims_stale_processing_receipt(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post909")
        self._stale_receipt(f"in-{post_id}", "processing")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-9"}
        ) as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()

    def test_process_inbound_message_records_unreadable_claim_conflict(self) -> None:
        post_id = mm_id("post910")
        path = common.chat_ingress_path(f"in-{post_id}")
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text("", encoding="utf-8")

        with mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "failed_claim_conflict")
        deliver_session_message.assert_not_called()
        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["status"], "failed_claim_conflict")
        self.assertEqual(receipt["reason"], "ingress_claim_unreadable")

    def test_failed_claim_conflict_receipt_retries_after_backoff(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post915")
        self._stale_receipt(f"in-{post_id}", "failed_claim_conflict")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-15"}
        ) as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "retry_after_failed_claim_conflict")

    def test_rejected_shutting_down_receipt_retries_immediately(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post916")
        self._stale_receipt(f"in-{post_id}", "rejected_shutting_down")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-16"}
        ) as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "retry_after_shutdown")

    def test_failed_receipt_retries_after_backoff(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post913")
        self._stale_receipt(f"in-{post_id}", "failed")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-13"}
        ) as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()

    def test_failed_lookup_receipt_retries_after_backoff(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post914")
        self._stale_receipt(f"in-{post_id}", "failed_lookup")

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-14"}
        ) as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "delivered")
        deliver_session_message.assert_called_once()
        self.assertEqual(common.load_chat_ingress(f"in-{post_id}")["reason"], "retry_after_failed_lookup")

    def test_stale_reclaim_lock_allows_only_one_delivery(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post911")
        self._stale_receipt(f"in-{post_id}", "processing")
        post = self._dm_post(post_id)
        barrier = threading.Barrier(2)
        release = threading.Event()
        started = threading.Event()
        outcomes: list[str] = []

        def fake_deliver(*args: object, **kwargs: object) -> dict[str, object]:
            started.set()
            release.wait(timeout=1)
            return {"status": "accepted", "id": "gc-11"}

        def worker() -> None:
            barrier.wait()
            outcome = gateway_service.process_inbound_message(post, BOT_USER_ID, BOT_USERNAME)
            outcomes.append(str(outcome.get("status", "")))

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", side_effect=fake_deliver) as deliver_session_message:
            thread_a = threading.Thread(target=worker)
            thread_b = threading.Thread(target=worker)
            thread_a.start()
            thread_b.start()
            self.assertTrue(started.wait(timeout=1))
            release.set()
            thread_a.join()
            thread_b.join()

        self.assertEqual(deliver_session_message.call_count, 1)
        self.assertEqual(sorted(outcomes), ["delivered", "duplicate"])

    def test_stale_reclaim_defers_when_original_processor_lock_is_held(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post_id = mm_id("post912")
        self._stale_receipt(f"in-{post_id}", "processing")
        process_lock = gateway_service.ingress_process_lock(f"in-{post_id}")
        process_lock.acquire()
        self.addCleanup(lambda: process_lock.locked() and process_lock.release())

        with mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-12"}
        ) as deliver_session_message:
            outcome = self._process(self._dm_post(post_id))

        self.assertEqual(outcome["status"], "duplicate")
        deliver_session_message.assert_not_called()

    # ------------------------------------------------------------------
    # Ambient binding cache
    # ------------------------------------------------------------------

    def test_cached_ambient_room_binding_reuses_cached_config_between_messages(self) -> None:
        common.set_chat_binding(
            common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID, policy={"ambient_read_enabled": True}
        )

        with mock.patch.object(common, "load_config", wraps=common.load_config) as load_config:
            first = gateway_service.cached_ambient_room_binding(ROOM_CHANNEL)
            second = gateway_service.cached_ambient_room_binding(ROOM_CHANNEL)

        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(load_config.call_count, 1)

    def test_cached_ambient_room_binding_serializes_cache_refill(self) -> None:
        common.set_chat_binding(
            common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID, policy={"ambient_read_enabled": True}
        )

        release = threading.Event()
        started = threading.Event()
        load_count = 0
        real_load_config = common.load_config

        def blocking_load_config() -> dict[str, object]:
            nonlocal load_count
            load_count += 1
            started.set()
            release.wait(timeout=2)
            return real_load_config()

        def worker() -> None:
            gateway_service.cached_ambient_room_binding(ROOM_CHANNEL)

        with mock.patch.object(common, "load_config", side_effect=blocking_load_config):
            thread_a = threading.Thread(target=worker)
            thread_b = threading.Thread(target=worker)
            thread_a.start()
            thread_b.start()
            started.wait(timeout=2)
            time.sleep(0.05)
            release.set()
            thread_a.join()
            thread_b.join()

        self.assertEqual(load_count, 1)

    def test_cached_ambient_room_binding_refreshes_on_signature_change(self) -> None:
        binding_id = f"room:{ROOM_CHANNEL}"
        config_one = {
            "chat": {
                "bindings": {
                    binding_id: {
                        "id": binding_id,
                        "kind": "room",
                        "conversation_id": ROOM_CHANNEL,
                        "team_id": TEAM_ID,
                        "session_names": ["sky"],
                        "policy": {"ambient_read_enabled": True},
                    }
                }
            }
        }
        config_two = {
            "chat": {
                "bindings": {
                    binding_id: {
                        "id": binding_id,
                        "kind": "room",
                        "conversation_id": ROOM_CHANNEL,
                        "team_id": TEAM_ID,
                        "session_names": ["lawrence"],
                        "policy": {"ambient_read_enabled": True},
                    }
                }
            }
        }

        stat_one = mock.Mock(st_mtime_ns=100, st_size=1000, st_ino=1)
        stat_two = mock.Mock(st_mtime_ns=100, st_size=1000, st_ino=2)

        with mock.patch.object(gateway_service.os, "stat", side_effect=[stat_one, stat_one, stat_two, stat_two]), mock.patch.object(
            common,
            "load_config",
            side_effect=[common.normalize_config(config_one), common.normalize_config(config_two)],
        ) as load_config:
            first = gateway_service.cached_ambient_room_binding(ROOM_CHANNEL)
            second = gateway_service.cached_ambient_room_binding(ROOM_CHANNEL)

        assert first is not None
        assert second is not None
        self.assertEqual(first["session_names"], ["sky"])
        self.assertEqual(second["session_names"], ["lawrence"])
        self.assertEqual(load_config.call_count, 2)

    def test_cached_ambient_room_binding_skips_lookup_for_persisted_channel_metadata(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            ROOM_CHANNEL,
            ["sky"],
            TEAM_ID,
            policy={"ambient_read_enabled": True},
            channel_metadata={"channel_type": "O"},
        )

        with mock.patch.object(common, "describe_channel") as describe_channel:
            binding = gateway_service.cached_ambient_room_binding(ROOM_CHANNEL)

        assert binding is not None
        self.assertEqual(binding["channel_type"], "O")
        describe_channel.assert_not_called()

    def test_cached_ambient_room_binding_ignores_invalid_config(self) -> None:
        common.ensure_layout()
        pathlib.Path(common.config_path()).write_text("{not valid json", encoding="utf-8")

        self.assertIsNone(gateway_service.cached_ambient_room_binding(ROOM_CHANNEL))

    def test_cached_ambient_room_binding_ignores_non_ambient_bindings(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)

        self.assertIsNone(gateway_service.cached_ambient_room_binding(ROOM_CHANNEL))

    # ------------------------------------------------------------------
    # Channel info cache primitives
    # ------------------------------------------------------------------

    def test_process_inbound_messages_cache_channel_lookup(self) -> None:
        common.set_chat_binding(common.load_config(), "room", ROOM_CHANNEL, ["sky"], TEAM_ID)
        common.save_bot_token("bot-token")
        base = {
            "channel_id": ROOM_CHANNEL,
            "team_id": TEAM_ID,
            "message": f"@{BOT_USERNAME} please check",
            "mentions": [BOT_USER_ID],
        }

        with mock.patch.object(
            common, "describe_channel", return_value={"id": ROOM_CHANNEL, "type": "O", "team_id": TEAM_ID}
        ) as describe_channel, mock.patch.object(
            common, "session_index_by_name", return_value={"sky": {"session_name": "sky", "state": "active"}}
        ), mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted"}):
            outcome_1 = self._process(make_post(mm_id("post801"), **base))
            outcome_2 = self._process(make_post(mm_id("post802"), **base))

        self.assertEqual(outcome_1["status"], "delivered")
        self.assertEqual(outcome_2["status"], "delivered")
        describe_channel.assert_called_once()

    def test_load_channel_info_serializes_cache_fill(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        calls: list[str] = []
        results: list[dict[str, object]] = []

        def fake_describe(channel_id: str, *, bot_token: str = "") -> dict[str, object]:
            calls.append(channel_id)
            entered.set()
            release.wait(timeout=1)
            return {"id": ROOM_CHANNEL, "type": "O"}

        def worker() -> None:
            results.append(gateway_service.load_channel_info(ROOM_CHANNEL, "bot-token"))

        with mock.patch.object(common, "describe_channel", side_effect=fake_describe):
            thread_a = threading.Thread(target=worker)
            thread_b = threading.Thread(target=worker)
            thread_a.start()
            thread_b.start()
            self.assertTrue(entered.wait(timeout=1))
            release.set()
            thread_a.join()
            thread_b.join()

        self.assertEqual(calls, [ROOM_CHANNEL])
        self.assertEqual(
            results,
            [
                {"id": ROOM_CHANNEL, "type": "O", "channel_type": "O"},
                {"id": ROOM_CHANNEL, "type": "O", "channel_type": "O"},
            ],
        )

    def test_load_channel_info_normalizes_channel_type(self) -> None:
        with mock.patch.object(common, "describe_channel", return_value={"id": DM_CHANNEL, "type": "d"}):
            info = gateway_service.load_channel_info(DM_CHANNEL, "bot-token")

        self.assertEqual(info, {"id": DM_CHANNEL, "type": "D", "channel_type": "D"})

    def test_normalize_channel_info_ignores_unknown_types(self) -> None:
        self.assertEqual(
            gateway_service.normalize_channel_info({"id": ROOM_CHANNEL, "type": "Z"}), {"id": ROOM_CHANNEL, "type": "Z"}
        )
        self.assertEqual(gateway_service.normalize_channel_info(None), {})

    def test_channel_info_fetch_lock_is_scoped_per_channel(self) -> None:
        lock_a = gateway_service.channel_info_fetch_lock(ROOM_CHANNEL)
        lock_b = gateway_service.channel_info_fetch_lock(OTHER_CHANNEL)

        self.assertIs(lock_a, gateway_service.channel_info_fetch_lock(ROOM_CHANNEL))
        self.assertIsNot(lock_a, lock_b)

    def test_resolve_binding_treats_direct_channel_type_as_dm(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", DM_CHANNEL, ["sky"])
        post = make_post(mm_id("post803"), channel_id=DM_CHANNEL, channel_type="D", message="hi")

        binding, _channel_info = gateway_service.resolve_binding(common.load_config(), post)

        assert binding is not None
        self.assertEqual(binding["id"], f"dm:{DM_CHANNEL}")

    def test_resolve_binding_returns_none_for_missing_channel_lookup(self) -> None:
        common.save_bot_token("bot-token")
        post = make_post(mm_id("post804"), channel_id=OTHER_CHANNEL, team_id=TEAM_ID, message="hi")

        with mock.patch.object(
            common, "describe_channel", side_effect=common.MattermostAPIError("gone", status_code=404)
        ):
            binding, channel_info = gateway_service.resolve_binding(common.load_config(), post)

        self.assertIsNone(binding)
        self.assertEqual(channel_info, {})

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def test_worker_stop_drains_queued_messages_before_exit(self) -> None:
        runtime_state = gateway_service.GatewayRuntimeState()
        worker = gateway_service.GatewayWorker(runtime_state)
        self.addCleanup(lambda: worker.stop() if not worker.stop_event.is_set() else None)

        handled: list[str] = []
        with mock.patch.object(
            worker,
            "handle_gateway_message",
            side_effect=lambda post, bot_user_id, bot_username: handled.append(str(post.get("id", ""))),
        ):
            worker.dispatch_gateway_message(
                make_post(mm_id("post1001"), channel_id=DM_CHANNEL, message="hi"), BOT_USER_ID, BOT_USERNAME
            )
            worker.stop()

        self.assertEqual(handled, [mm_id("post1001")])
        self.assertTrue(worker.stop_event.is_set())
        self.assertTrue(all(not thread.is_alive() for thread in worker.worker_threads))

    def test_dispatch_gateway_message_persists_shutting_down_receipt(self) -> None:
        runtime_state = gateway_service.GatewayRuntimeState()
        worker = gateway_service.GatewayWorker(runtime_state)
        self.addCleanup(worker.stop)
        worker.request_stop()
        post_id = mm_id("post1002")

        worker.dispatch_gateway_message(
            make_post(post_id, channel_id=DM_CHANNEL, message="hi"), BOT_USER_ID, BOT_USERNAME
        )

        receipt = common.load_chat_ingress(f"in-{post_id}")
        assert receipt is not None
        self.assertEqual(receipt["status"], "rejected_shutting_down")
        self.assertEqual(receipt["reason"], "service_shutting_down")

    def test_worker_stop_returns_when_worker_pool_is_idle(self) -> None:
        runtime_state = gateway_service.GatewayRuntimeState()
        worker = gateway_service.GatewayWorker(runtime_state)

        stop_thread = threading.Thread(target=worker.stop)
        stop_thread.start()
        stop_thread.join(timeout=5)

        self.assertFalse(stop_thread.is_alive())
        self.assertTrue(worker.stop_event.is_set())
        self.assertTrue(all(not thread.is_alive() for thread in worker.worker_threads))

    def test_utc_age_seconds_uses_utc_epoch_conversion(self) -> None:
        if not hasattr(time, "tzset"):
            self.skipTest("tzset not available on this platform")
        previous_tz = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Etc/GMT+8"
            time.tzset()
            stamp = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(time.time() - gateway_service.STALE_PROCESSING_RECEIPT_SECONDS - 5),
            )
            age = gateway_service.utc_age_seconds(stamp)
        finally:
            if previous_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous_tz
            time.tzset()

        self.assertGreaterEqual(age, gateway_service.STALE_PROCESSING_RECEIPT_SECONDS)
        self.assertLess(age, gateway_service.STALE_PROCESSING_RECEIPT_SECONDS + 30)

    def test_probe_gc_api_health_caches_recent_result(self) -> None:
        runtime_state = gateway_service.GatewayRuntimeState()

        with mock.patch.object(common, "gc_api_request", return_value={"items": []}) as gc_api_request:
            self.assertTrue(gateway_service.probe_gc_api_health(runtime_state))
            self.assertTrue(gateway_service.probe_gc_api_health(runtime_state))

        gc_api_request.assert_called_once()
        self.assertEqual(
            gc_api_request.call_args.kwargs["timeout"],
            gateway_service.GC_API_HEALTH_PROBE_TIMEOUT_SECONDS,
        )

    def test_gateway_health_status_code_requires_gc_api_when_ready(self) -> None:
        self.assertEqual(
            gateway_service.gateway_health_status_code({"state": "ready"}, gc_api_reachable=False),
            gateway_service.HTTPStatus.SERVICE_UNAVAILABLE,
        )
        self.assertEqual(
            gateway_service.gateway_health_status_code({"state": "ready"}, gc_api_reachable=True),
            gateway_service.HTTPStatus.NO_CONTENT,
        )

    def test_gateway_health_status_code_honors_reconnect_grace_window(self) -> None:
        state = {"state": "reconnecting", "last_ready_epoch": int(time.time())}

        self.assertEqual(
            gateway_service.gateway_health_status_code(state, gc_api_reachable=True),
            gateway_service.HTTPStatus.NO_CONTENT,
        )

    def test_gateway_health_status_code_honors_resume_grace_window(self) -> None:
        state = {"state": "reconnecting", "last_ready_epoch": 1, "last_resumed_epoch": int(time.time())}

        self.assertEqual(
            gateway_service.gateway_health_status_code(state, gc_api_reachable=True),
            gateway_service.HTTPStatus.NO_CONTENT,
        )

    def test_gateway_health_status_code_fails_stale_reconnect(self) -> None:
        state = {"state": "reconnecting", "last_ready_epoch": 1, "last_resumed_epoch": 1}

        self.assertEqual(
            gateway_service.gateway_health_status_code(state, gc_api_reachable=True),
            gateway_service.HTTPStatus.SERVICE_UNAVAILABLE,
        )

    # ------------------------------------------------------------------
    # Websocket transport
    # ------------------------------------------------------------------

    def test_gateway_websocket_recv_event_reassembles_fragmented_text_frames(self) -> None:
        ws = object.__new__(gateway_service.GatewayWebSocket)
        frames = iter(
            [
                (False, 0x1, b'{"event":"posted",'),
                (True, 0x0, b'"seq":3}'),
            ]
        )
        ws.read_frame = lambda timeout=None: next(frames)  # type: ignore[attr-defined]
        ws.send_frame = mock.Mock()

        event = gateway_service.GatewayWebSocket.recv_event(ws, timeout=1.0)

        self.assertEqual(event, {"event": "posted", "seq": 3})

    def test_gateway_websocket_recv_event_answers_ping_with_pong(self) -> None:
        ws = object.__new__(gateway_service.GatewayWebSocket)
        frames = iter(
            [
                (True, 0x9, b"keepalive"),
                (True, 0x1, b'{"event":"hello"}'),
            ]
        )
        ws.read_frame = lambda timeout=None: next(frames)  # type: ignore[attr-defined]
        ws.send_frame = mock.Mock()

        event = gateway_service.GatewayWebSocket.recv_event(ws, timeout=1.0)

        self.assertEqual(event, {"event": "hello"})
        ws.send_frame.assert_called_once_with(0xA, b"keepalive")

    def test_gateway_websocket_read_frame_rejects_oversized_payloads(self) -> None:
        ws = object.__new__(gateway_service.GatewayWebSocket)
        parts = iter(
            [
                bytes([0x81, 0x7F]),
                struct.pack("!Q", gateway_service.MAX_FRAME_BYTES + 1),
            ]
        )
        ws.read_exact = lambda length, timeout=None: next(parts)  # type: ignore[attr-defined]

        with self.assertRaises(gateway_service.WebSocketClosed):
            gateway_service.GatewayWebSocket.read_frame(ws)

    def test_validate_websocket_handshake_rejects_bad_accept_header(self) -> None:
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        header_blob = "\r\n".join(
            [
                "HTTP/1.1 101 Switching Protocols",
                "Upgrade: websocket",
                "Connection: Upgrade",
                "Sec-WebSocket-Accept: bad-value",
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "Sec-WebSocket-Accept"):
            gateway_service.validate_websocket_handshake(header_blob, key)

    def test_validate_websocket_handshake_accepts_valid_upgrade(self) -> None:
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        header_blob = "\r\n".join(
            [
                "HTTP/1.1 101 Switching Protocols",
                "Upgrade: websocket",
                "Connection: keep-alive, Upgrade",
                f"Sec-WebSocket-Accept: {gateway_service.websocket_accept_value(key)}",
            ]
        )

        gateway_service.validate_websocket_handshake(header_blob, key)

    def test_gateway_websocket_handshake_sends_bearer_authorization_header(self) -> None:
        fake_socket = _HandshakeSocket()

        with mock.patch.object(gateway_service.socket, "create_connection", return_value=fake_socket):
            ws = gateway_service.GatewayWebSocket(
                "ws://mattermost.example/api/v4/websocket",
                headers={"Authorization": "Bearer bot-token"},
            )

        request = fake_socket.request_text()
        self.assertIn("GET /api/v4/websocket HTTP/1.1", request)
        self.assertIn("Upgrade: websocket", request)
        self.assertIn("Authorization: Bearer bot-token", request)
        self.assertIs(ws.sock, fake_socket)

    # ------------------------------------------------------------------
    # Connect URL, authentication and event dispatch
    # ------------------------------------------------------------------

    def test_gateway_connect_url_without_resume_keeps_base_url(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)

        with mock.patch.object(common, "mattermost_websocket_url", return_value="wss://mm.example/api/v4/websocket"):
            url = gateway_service.GatewayWorker.gateway_connect_url(worker)

        self.assertEqual(url, "wss://mm.example/api/v4/websocket")

    def test_gateway_connect_url_adds_reliable_reconnect_params(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)

        with mock.patch.object(common, "mattermost_websocket_url", return_value="wss://mm.example/api/v4/websocket"):
            url = gateway_service.GatewayWorker.gateway_connect_url(worker, "conn-1", 7, 4000)

        self.assertIn("connection_id=conn-1", url)
        self.assertIn("sequence_number=7", url)
        self.assertIn("disconnect_err_code=4000", url)

    def test_gateway_connect_url_clamps_negative_sequence(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)

        with mock.patch.object(common, "mattermost_websocket_url", return_value="wss://mm.example/api/v4/websocket"):
            url = gateway_service.GatewayWorker.gateway_connect_url(worker, "conn-1", -5)

        self.assertIn("sequence_number=0", url)

    def test_gateway_connect_url_requires_configured_websocket_url(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)

        with mock.patch.object(common, "mattermost_websocket_url", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "websocket URL is missing"):
                gateway_service.GatewayWorker.gateway_connect_url(worker)

    def test_authenticate_sends_authentication_challenge_frame(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)
        ws = _ScriptedWebSocket([], threading.Event())

        gateway_service.GatewayWorker.authenticate(worker, ws, "bot-token", 1)

        self.assertEqual(
            ws.sent,
            [{"seq": 1, "action": gateway_service.AUTHENTICATION_CHALLENGE_ACTION, "data": {"token": "bot-token"}}],
        )

    def test_current_bot_identity_prefers_last_known_after_resume(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)

        with mock.patch.object(gateway_service, "load_bot_identity", return_value=("", "")):
            identity = gateway_service.GatewayWorker.current_bot_identity(
                worker, {"app": {"bot_user_id": "config-bot"}}, (BOT_USER_ID, BOT_USERNAME)
            )

        self.assertEqual(identity, (BOT_USER_ID, BOT_USERNAME))

    def test_current_bot_identity_falls_back_to_config_bot_user_id(self) -> None:
        worker = object.__new__(gateway_service.GatewayWorker)

        with mock.patch.object(gateway_service, "load_bot_identity", return_value=("", "")):
            identity = gateway_service.GatewayWorker.current_bot_identity(worker, {"app": {"bot_user_id": "config-bot"}})

        self.assertEqual(identity, ("config-bot", ""))

    def test_load_bot_identity_reads_users_me_and_caches(self) -> None:
        with mock.patch.object(
            common, "mattermost_api_request", return_value={"id": BOT_USER_ID, "username": BOT_USERNAME}
        ) as mattermost_api_request:
            first = gateway_service.load_bot_identity()
            second = gateway_service.load_bot_identity()

        self.assertEqual(first, (BOT_USER_ID, BOT_USERNAME))
        self.assertEqual(second, (BOT_USER_ID, BOT_USERNAME))
        mattermost_api_request.assert_called_once_with("GET", "/users/me")

    def test_load_bot_identity_falls_back_to_config_when_api_fails(self) -> None:
        with mock.patch.object(
            common, "mattermost_api_request", side_effect=common.MattermostAPIError("boom", status_code=500)
        ):
            identity = gateway_service.load_bot_identity({"app": {"bot_user_id": BOT_USER_ID}})

        self.assertEqual(identity, (BOT_USER_ID, ""))

    def _drive_run_forever(
        self, worker: gateway_service.GatewayWorker, scripts: list[list[Any]]
    ) -> tuple[list[_ScriptedWebSocket], list[dict[str, Any]]]:
        remaining = list(scripts)
        created: list[_ScriptedWebSocket] = []
        patches: list[dict[str, Any]] = []
        real_patch = worker.runtime_state.patch

        def recording_patch(**values: Any) -> None:
            patches.append(dict(values))
            real_patch(**values)

        worker.runtime_state.patch = recording_patch  # type: ignore[method-assign]
        self.addCleanup(lambda: setattr(worker.runtime_state, "patch", real_patch))

        def factory(url: str, headers: dict[str, str] | None = None) -> _ScriptedWebSocket:
            events = remaining.pop(0) if remaining else []
            ws = _ScriptedWebSocket(events, worker.stop_event, url, headers)
            created.append(ws)
            return ws

        with mock.patch.object(gateway_service, "GatewayWebSocket", side_effect=factory), mock.patch.object(
            gateway_service, "RECONNECT_BASE_DELAY_SECONDS", 0.01
        ), mock.patch.object(
            gateway_service, "load_bot_identity", return_value=(BOT_USER_ID, BOT_USERNAME)
        ), mock.patch.object(common, "load_bot_token", return_value="bot-token"), mock.patch.object(
            common, "mattermost_site_url", return_value="https://mm.example"
        ), mock.patch.object(
            common, "mattermost_websocket_url", return_value="wss://mm.example/api/v4/websocket"
        ):
            worker.run_forever()
        return created, patches

    def test_run_forever_marks_ready_on_hello_event(self) -> None:
        worker = self._new_gateway_worker()

        created, _patches = self._drive_run_forever(
            worker,
            [[{"event": "hello", "data": {"connection_id": "conn-1", "server_version": "9.5.0"}, "seq": 0}]],
        )

        state = worker.runtime_state.snapshot()
        self.assertTrue(state["connected"])
        self.assertEqual(state["state"], "ready")
        self.assertEqual(state["connection_id"], "conn-1")
        self.assertEqual(state["bot_user_id"], BOT_USER_ID)
        self.assertEqual(state["bot_username"], BOT_USERNAME)
        self.assertEqual(state["server_version"], "9.5.0")
        self.assertFalse(state["resumed_connection"])
        self.assertEqual(
            created[0].sent,
            [{"seq": 1, "action": gateway_service.AUTHENTICATION_CHALLENGE_ACTION, "data": {"token": "bot-token"}}],
        )
        self.assertEqual(created[0].headers.get("Authorization"), "Bearer bot-token")

    def test_run_forever_marks_ready_on_authentication_challenge_reply(self) -> None:
        worker = self._new_gateway_worker()

        self._drive_run_forever(worker, [[{"status": "OK", "seq_reply": 1, "data": {}}]])

        state = worker.runtime_state.snapshot()
        self.assertTrue(state["connected"])
        self.assertEqual(state["state"], "ready")

    def test_run_forever_raises_when_authentication_is_rejected(self) -> None:
        worker = self._new_gateway_worker()

        _created, patches = self._drive_run_forever(
            worker, [[{"status": "FAIL", "seq_reply": 1, "error": {"id": "api.unauthorized"}}]]
        )

        errors = [str(item.get("last_error", "")) for item in patches]
        self.assertTrue(any("rejected authentication" in error for error in errors), msg=errors)
        self.assertTrue(any(str(item.get("state", "")) == "reconnecting" for item in patches))

    def test_run_forever_dispatches_posted_events(self) -> None:
        worker = self._new_gateway_worker()
        post_id = mm_id("post1100")
        posted = {
            "event": "posted",
            "data": {
                "post": json.dumps({"id": post_id, "channel_id": ROOM_CHANNEL, "message": "hello"}),
                "team_id": TEAM_ID,
                "channel_type": "O",
                "sender_name": "@alice",
            },
            "broadcast": {"channel_id": ROOM_CHANNEL},
            "seq": 1,
        }

        with mock.patch.object(worker, "dispatch_gateway_message") as dispatch_gateway_message:
            self._drive_run_forever(
                worker,
                [[{"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 0}, posted]],
            )

        dispatch_gateway_message.assert_called_once()
        dispatched_post = dispatch_gateway_message.call_args.args[0]
        self.assertEqual(dispatched_post["id"], post_id)
        self.assertEqual(dispatched_post["channel_id"], ROOM_CHANNEL)
        self.assertEqual(dispatched_post["team_id"], TEAM_ID)
        self.assertEqual(dispatch_gateway_message.call_args.args[1], BOT_USER_ID)
        self.assertEqual(dispatch_gateway_message.call_args.args[2], BOT_USERNAME)

    def test_run_forever_ignores_non_posted_events(self) -> None:
        worker = self._new_gateway_worker()

        with mock.patch.object(worker, "dispatch_gateway_message") as dispatch_gateway_message:
            self._drive_run_forever(
                worker,
                [
                    [
                        {"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 0},
                        {"event": "reaction_added", "data": {"reaction": "{}"}, "seq": 1},
                        {"event": "typing", "data": {}, "seq": 2},
                    ]
                ],
            )

        dispatch_gateway_message.assert_not_called()
        self.assertEqual(worker.runtime_state.snapshot()["last_sequence"], 2)

    def test_run_forever_drops_socket_on_sequence_gap(self) -> None:
        worker = self._new_gateway_worker()

        created, patches = self._drive_run_forever(
            worker,
            [
                [
                    {"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 0},
                    {"event": "posted", "data": {}, "seq": 9},
                ],
                [],
            ],
        )

        self.assertIn(gateway_service.CLIENT_SEQUENCE_MISMATCH_CLOSE_CODE, created[0].closed_codes)
        errors = [str(item.get("last_error", "")) for item in patches]
        self.assertTrue(any("sequence mismatch" in error for error in errors), msg=errors)
        self.assertTrue(any(str(item.get("state", "")) == "reconnecting" for item in patches))
        self.assertIn("disconnect_err_code=4001", created[1].url)

    def test_run_forever_marks_resumed_connection_when_server_replays(self) -> None:
        worker = self._new_gateway_worker()

        created, _patches = self._drive_run_forever(
            worker,
            [
                [
                    {"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 0},
                    {"event": "posted", "data": {}, "seq": 9},
                ],
                [{"event": "hello", "data": {"connection_id": "conn-2"}, "seq": 0}],
            ],
        )

        self.assertEqual(len(created), 2)
        state = worker.runtime_state.snapshot()
        self.assertEqual(state["connection_id"], "conn-2")
        self.assertFalse(state["resumed_connection"])

    def test_run_forever_resumes_with_connection_id_and_sequence_cursor(self) -> None:
        worker = self._new_gateway_worker()

        created, _patches = self._drive_run_forever(
            worker,
            [
                [
                    {"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 0},
                    {"event": "typing", "data": {}, "seq": 1},
                    gateway_service.WebSocketClosed("socket closed"),
                ],
                [{"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 2}],
            ],
        )

        self.assertEqual(len(created), 2)
        self.assertIn("connection_id=conn-1", created[1].url)
        self.assertIn("sequence_number=2", created[1].url)
        state = worker.runtime_state.snapshot()
        self.assertTrue(state["resumed_connection"])
        self.assertTrue(str(state.get("last_resumed_at", "")).strip())

    def test_run_forever_clears_sequence_cursor_when_server_cannot_replay(self) -> None:
        worker = self._new_gateway_worker()

        created, _patches = self._drive_run_forever(
            worker,
            [
                [
                    {"event": "hello", "data": {"connection_id": "conn-1"}, "seq": 0},
                    {"event": "typing", "data": {}, "seq": 1},
                    gateway_service.WebSocketClosed("socket closed"),
                ],
                [
                    {"event": "hello", "data": {"connection_id": "conn-9"}, "seq": 0},
                    {"event": "typing", "data": {}, "seq": 1},
                ],
            ],
        )

        # The server restarting at seq 0 under a new connection_id is a resync,
        # not a gap: it must not force a second 4001 teardown.
        self.assertEqual(len(created), 2)
        self.assertEqual(created[1].closed_codes, [1000])
        self.assertIn("connection_id=conn-1", created[1].url)
        state = worker.runtime_state.snapshot()
        self.assertFalse(state["resumed_connection"])
        self.assertEqual(state["connection_id"], "conn-9")
        self.assertEqual(state["last_sequence"], 1)

    def test_run_forever_waits_for_config_when_token_is_missing(self) -> None:
        worker = self._new_gateway_worker()

        def stop_after_first_wait(timeout: float | None = None) -> bool:
            worker.stop_event.set()
            return True

        with mock.patch.object(common, "load_bot_token", return_value=""), mock.patch.object(
            common, "mattermost_site_url", return_value=""
        ), mock.patch.object(worker.stop_event, "wait", side_effect=stop_after_first_wait):
            worker.run_forever()

        state = worker.runtime_state.snapshot()
        self.assertEqual(state["state"], "waiting_for_config")
        self.assertFalse(state["connected"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import discord_chat_bind as bind_script
import discord_chat_publish as publish_script
import discord_chat_reply_current as reply_current_script
import discord_chat_retry_peer_fanout as retry_peer_fanout_script
import discord_intake_common as common


class DiscordChatScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def test_publish_uses_binding_target_and_saves_record(self) -> None:
        common.set_chat_binding(common.load_config(), "room", "22", ["sky"], guild_id="1")

        with mock.patch.object(common, "post_channel_message", return_value={"id": "msg-1"}) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(["--binding", "room:22", "--trigger", "orig-9", "--body", "hello humans"])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with("22", "hello humans", reply_to_message_id="orig-9")
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["binding_id"], "room:22")
        self.assertEqual(recent[0]["remote_message_id"], "msg-1")

    def test_publish_allows_conversation_override_for_thread_replies(self) -> None:
        common.set_chat_binding(common.load_config(), "room", "22", ["sky"], guild_id="1")

        with mock.patch.object(common, "discord_api_request", return_value={"id": "222", "parent_id": "22"}), mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-2"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    [
                        "--binding",
                        "room:22",
                        "--conversation-id",
                        "222",
                        "--trigger",
                        "orig-10",
                        "--body",
                        "thread reply",
                    ]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with("222", "thread reply", reply_to_message_id="orig-10")
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(recent[0]["binding_conversation_id"], "22")
        self.assertEqual(recent[0]["conversation_id"], "222")

    def test_publish_rejects_cross_channel_override(self) -> None:
        common.set_chat_binding(common.load_config(), "room", "22", ["sky"], guild_id="1")

        with mock.patch.object(common, "discord_api_request", return_value={"id": "999", "parent_id": "77"}):
            with self.assertRaises(SystemExit) as exc:
                publish_script.main(["--binding", "room:22", "--conversation-id", "999", "--body", "nope"])

        self.assertEqual(str(exc.exception), "--conversation-id must be the bound room or a thread within it")

    def test_publish_rejects_missing_remote_message_id(self) -> None:
        common.set_chat_binding(common.load_config(), "room", "22", ["sky"], guild_id="1")

        with mock.patch.object(common, "post_channel_message", return_value={}):
            with self.assertRaises(SystemExit) as exc:
                publish_script.main(["--binding", "room:22", "--trigger", "orig-9", "--body", "hello humans"])

        self.assertEqual(str(exc.exception), "discord publish returned no message id")

    def test_publish_returns_exit_code_two_for_partial_peer_fanout(self) -> None:
        common.set_chat_binding(common.load_config(), "room", "22", ["corp--sky"], guild_id="1")

        with mock.patch.object(
            common,
            "publish_binding_message",
            return_value={
                "binding": {"id": "room:22"},
                "record": {
                    "remote_message_id": "msg-1",
                    "peer_delivery": {
                        "phase": "peer_fanout_partial_failure",
                        "status": "partial_failure",
                    },
                },
                "response": {"id": "msg-1"},
            },
        ):
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    [
                        "--binding",
                        "room:22",
                        "--body",
                        "hello humans",
                    ]
                )

        self.assertEqual(code, 2)

    def test_publish_with_source_context_and_session_can_peer_fanout(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["corp--sky", "corp--priya"],
            guild_id="1",
            policy={"peer_fanout_enabled": True},
        )

        with mock.patch.object(common, "post_channel_message", return_value={"id": "msg-1"}), mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-priya"},
        ) as deliver_session_message, mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"id": "gc-sky", "session_name": "corp--sky", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
                {"id": "gc-priya", "session_name": "corp--priya", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
            ],
        ):
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    [
                        "--binding",
                        "room:22",
                        "--source-event-kind",
                        "discord_human_message",
                        "--source-ingress-receipt-id",
                        "in-1",
                        "--source-session",
                        "corp--sky",
                        "--body",
                        "@corp--priya hello",
                    ]
                )

        self.assertEqual(code, 0)
        deliver_session_message.assert_called_once()

    def test_plain_publish_without_source_context_stays_successful_in_peer_room(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["corp--sky", "corp--priya"],
            guild_id="1",
            policy={"peer_fanout_enabled": True},
        )
        os.environ.pop("GC_SESSION_NAME", None)
        os.environ.pop("GC_SESSION_ID", None)

        with mock.patch.object(common, "post_channel_message", return_value={"id": "msg-1"}), mock.patch.object(
            common,
            "deliver_session_message",
        ) as deliver_session_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = publish_script.main(["--binding", "room:22", "--body", "hello humans"])

        self.assertEqual(code, 0)
        payload = common.json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["peer_delivery"]["status"], "skipped_missing_root_context")
        deliver_session_message.assert_not_called()

    def test_reply_current_uses_latest_discord_context(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", "22", ["sky"])
        os.environ["GC_SESSION_NAME"] = "sky"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_discord_reply_context",
            return_value={
                "publish_binding_id": "dm:22",
                "publish_conversation_id": "22",
                "publish_trigger_id": "orig-22",
                "publish_reply_to_discord_message_id": "orig-22",
            },
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "msg-22"}) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with("22", "safe reply", reply_to_message_id="orig-22")
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(recent[0]["binding_id"], "dm:22")
        self.assertEqual(recent[0]["remote_message_id"], "msg-22")

    def test_reply_current_passes_source_context_and_surfaces_partial_peer_failure(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["corp--sky", "corp--priya"],
            guild_id="1",
            policy={"peer_fanout_enabled": True},
        )
        os.environ["GC_SESSION_NAME"] = "corp--sky"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("@corp--priya safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_discord_reply_context",
            return_value={
                "kind": "discord_peer_publication",
                "publish_binding_id": "room:22",
                "publish_conversation_id": "22",
                "publish_trigger_id": "orig-22",
                "publish_reply_to_discord_message_id": "orig-22",
                "root_ingress_receipt_id": "in-1",
            },
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "msg-22"}), mock.patch.object(
            common,
            "deliver_session_message",
            side_effect=common.GCAPIError("boom"),
        ), mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"session_name": "corp--sky", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
                {"session_name": "corp--priya", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
            ],
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 2)
        payload = common.json.loads(stdout.getvalue())
        self.assertEqual(payload["reply_context"]["source_event_kind"], "discord_peer_publication")
        self.assertEqual(payload["reply_context"]["root_ingress_receipt_id"], "in-1")
        self.assertEqual(payload["record"]["source_event_kind"], "discord_peer_publication")

    def test_reply_current_session_override_sets_source_identity(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["corp--sky", "corp--priya"],
            guild_id="1",
            policy={"peer_fanout_enabled": True},
        )
        os.environ["GC_SESSION_NAME"] = "corp--else"
        os.environ["GC_SESSION_ID"] = "gc-else"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("@corp--priya safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_discord_reply_context",
            return_value={
                "kind": "discord_peer_publication",
                "publish_binding_id": "room:22",
                "publish_conversation_id": "22",
                "publish_trigger_id": "orig-22",
                "publish_reply_to_discord_message_id": "orig-22",
                "root_ingress_receipt_id": "in-1",
            },
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "msg-22"}), mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-priya"},
        ), mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"id": "gc-sky", "session_name": "corp--sky", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
                {"id": "gc-priya", "session_name": "corp--priya", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
                {"id": "gc-else", "session_name": "corp--else", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
            ],
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--session", "corp--sky", "--body-file", str(body_file)])

        self.assertEqual(code, 0)
        payload = common.json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["source_session_name"], "corp--sky")
        self.assertEqual(payload["record"]["source_session_id"], "gc-sky")
        self.assertEqual(payload["reply_context"]["source_session_name"], "corp--sky")

    def test_reply_current_reply_context_falls_back_to_current_session_env(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", "22", ["sky"])
        os.environ["GC_SESSION_NAME"] = "sky"
        os.environ["GC_SESSION_ID"] = "gc-sky"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_discord_reply_context",
            return_value={
                "kind": "discord_human_message",
                "ingress_receipt_id": "in-22",
                "publish_binding_id": "dm:22",
                "publish_conversation_id": "22",
                "publish_trigger_id": "orig-22",
                "publish_reply_to_discord_message_id": "orig-22",
            },
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "msg-22"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 0)
        payload = common.json.loads(stdout.getvalue())
        self.assertEqual(payload["reply_context"]["source_session_name"], "sky")
        self.assertEqual(payload["reply_context"]["source_session_id"], "gc-sky")

    def test_bind_script_creates_room_binding(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(["--kind", "room", "--guild-id", "1", "22", "sky", "lawrence"])

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), "room:22")
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["session_names"], ["sky", "lawrence"])

    def test_bind_script_persists_peer_fanout_policy(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(
                [
                    "--kind",
                    "room",
                    "--guild-id",
                    "1",
                    "--enable-peer-fanout",
                    "--allow-untargeted-peer-fanout",
                    "--max-peer-triggered-publishes-per-root",
                    "2",
                    "--max-total-peer-deliveries-per-root",
                    "9",
                    "--max-peer-triggered-publishes-per-session-per-minute",
                    "7",
                    "22",
                    "corp--sky",
                    "corp--priya",
                ]
            )

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), "room:22")
        assert binding is not None
        self.assertTrue(binding["policy"]["peer_fanout_enabled"])
        self.assertTrue(binding["policy"]["allow_untargeted_peer_fanout"])
        self.assertEqual(binding["policy"]["max_peer_triggered_publishes_per_root"], 2)
        self.assertEqual(binding["policy"]["max_total_peer_deliveries_per_root"], 9)
        self.assertEqual(binding["policy"]["max_peer_triggered_publishes_per_session_per_minute"], 7)

    def test_bind_script_rejects_invalid_dm_fanout_cleanly(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            bind_script.main(["--kind", "dm", "55", "sky", "lawrence"])

        self.assertEqual(str(exc.exception), "DM bindings require exactly one session name")

    def test_retry_peer_fanout_script_retries_saved_publish(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["corp--sky", "corp--priya"],
            guild_id="1",
            policy={"peer_fanout_enabled": True},
        )
        common.save_chat_publish(
            {
                "publish_id": "discord-publish-1",
                "binding_id": "room:22",
                "binding_kind": "room",
                "binding_conversation_id": "22",
                "conversation_id": "22",
                "guild_id": "1",
                "source_session_name": "corp--sky",
                "source_session_id": "gc-1",
                "source_event_kind": "discord_human_message",
                "root_ingress_receipt_id": "in-1",
                "body": "@corp--priya hello",
                "remote_message_id": "msg-1",
                "peer_delivery": {
                    "phase": "peer_fanout_partial_failure",
                    "status": "partial_failure",
                    "delivery": "targeted",
                    "mentioned_session_names": ["corp--priya"],
                    "frozen_targets": ["corp--priya"],
                    "targets": [
                        {
                            "session_name": "corp--priya",
                            "status": "failed_retryable",
                            "attempt_count": 1,
                            "idempotency_key": "peer_publish:discord-publish-1:binding:room:22:target:corp--priya",
                            "attempts": [],
                        }
                    ],
                    "budget_snapshot": {},
                },
            }
        )

        with mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-1"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = retry_peer_fanout_script.main(["discord-publish-1"])

        self.assertEqual(code, 0)
        payload = common.json.loads(stdout.getvalue())
        self.assertEqual(payload["peer_delivery"]["status"], "delivered")


if __name__ == "__main__":
    unittest.main()

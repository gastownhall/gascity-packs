from __future__ import annotations

import io
import json
import pathlib
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from unittest import mock

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import mattermost_chat_bind as bind_script
import mattermost_chat_publish as publish_script
import mattermost_chat_reply_current as reply_current_script
import mattermost_chat_retry_peer_fanout as retry_peer_fanout_script
import mattermost_room_launch as room_launch_script
import mattermost_intake_common as common


CHANNEL = "9h5j7k1m3n5p7r9t1v3x5z7b9c"
OTHER_CHANNEL = "1a2b3c4d5e6f7g8h9i0j1k2l3m"
TEAM = "7k3m9x2c5n8b1v4z6q0r2s4t6w"
ROOT_POST = "2a4b6c8d0e2f4g6h8i0j2k4m6n"


def _post(post_id: str, channel_id: str, root_id: str = "") -> dict[str, str]:
    """Shape of a Mattermost GET /posts/<id> response."""
    return {"id": post_id, "channel_id": channel_id, "root_id": root_id}


class MattermostChatScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        # The publish path resolves the acting session from the environment;
        # keep every test explicit about which session (if any) is acting.
        for key in ("GC_SESSION_ID", "GC_SESSION_NAME", "GC_ALIAS"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    # ------------------------------------------------------------------
    # pack wiring
    # ------------------------------------------------------------------

    def test_pack_commands_reference_existing_files(self) -> None:
        pack_dir = pathlib.Path(__file__).resolve().parents[1]
        manifest = tomllib.loads((pack_dir / "pack.toml").read_text(encoding="utf-8"))
        schema = int(manifest.get("pack", {}).get("schema", 1))

        if schema >= 2:
            command_dirs = sorted(path for path in (pack_dir / "commands").iterdir() if path.is_dir())
            self.assertTrue(command_dirs, "expected pack v2 command directories")
            for command_dir in command_dirs:
                command_manifest = tomllib.loads((command_dir / "command.toml").read_text(encoding="utf-8"))
                run_path = (command_dir / str(command_manifest.get("run", "")).strip()).resolve()
                help_path = command_dir / "help.md"
                self.assertTrue(run_path.is_file(), f"missing command script for {command_dir.name}: {run_path}")
                self.assertTrue(help_path.is_file(), f"missing help text for {command_dir.name}: {help_path}")
            return

        for command in manifest.get("commands", []):
            script_path = pack_dir / str(command.get("script", "")).strip()
            help_path = pack_dir / str(command.get("long_description", "")).strip()
            self.assertTrue(script_path.is_file(), f"missing command script for {command.get('name')}: {script_path}")
            self.assertTrue(help_path.is_file(), f"missing help text for {command.get('name')}: {help_path}")

    # ------------------------------------------------------------------
    # publish
    # ------------------------------------------------------------------

    def test_publish_uses_binding_target_and_saves_record(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with mock.patch.object(
            common, "mattermost_api_request", return_value=_post("orig-9", CHANNEL)
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "msg-1"}) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    ["--binding", f"room:{CHANNEL}", "--trigger", "orig-9", "--body", "hello humans"]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "hello humans", root_id="orig-9", file_ids=None)
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["binding_id"], f"room:{CHANNEL}")
        self.assertEqual(recent[0]["remote_message_id"], "msg-1")
        self.assertEqual(recent[0]["conversation_id"], CHANNEL)

    def test_publish_walks_reply_target_up_to_its_thread_root(self) -> None:
        """Mattermost rejects a root_id that points at a reply."""
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with mock.patch.object(
            common, "mattermost_api_request", return_value=_post("reply-9", CHANNEL, root_id=ROOT_POST)
        ) as api_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-2"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    ["--binding", f"room:{CHANNEL}", "--reply-to", "reply-9", "--body", "thread reply"]
                )

        self.assertEqual(code, 0)
        api_request.assert_called_once_with("GET", "/posts/reply-9", bot_token=None)
        post_channel_message.assert_called_once_with(CHANNEL, "thread reply", root_id=ROOT_POST, file_ids=None)
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(recent[0]["root_post_id"], ROOT_POST)

    def test_publish_allows_conversation_override_matching_the_bound_channel(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with mock.patch.object(common, "post_channel_message", return_value={"id": "msg-3"}) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    ["--binding", f"room:{CHANNEL}", "--conversation-id", CHANNEL, "--body", "same channel"]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "same channel", root_id="", file_ids=None)

    def test_publish_rejects_cross_channel_override(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with self.assertRaises(SystemExit) as exc:
            publish_script.main(
                ["--binding", f"room:{CHANNEL}", "--conversation-id", OTHER_CHANNEL, "--body", "nope"]
            )

        self.assertEqual(str(exc.exception), "--conversation-id must match the bound channel")

    def test_publish_rejects_conversation_override_on_a_dm_binding(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", CHANNEL, ["sky"])

        with self.assertRaises(SystemExit) as exc:
            publish_script.main(["--binding", f"dm:{CHANNEL}", "--conversation-id", OTHER_CHANNEL, "--body", "nope"])

        self.assertEqual(str(exc.exception), "--conversation-id cannot override a DM binding")

    def test_publish_rejects_unknown_binding(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            publish_script.main(["--binding", f"room:{CHANNEL}", "--body", "nope"])

        self.assertEqual(str(exc.exception), f"binding not found: room:{CHANNEL}")

    def test_publish_rejects_missing_remote_message_id(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with mock.patch.object(common, "post_channel_message", return_value={}):
            with self.assertRaises(SystemExit) as exc:
                publish_script.main(["--binding", f"room:{CHANNEL}", "--body", "hello humans"])

        self.assertEqual(str(exc.exception), "mattermost publish returned no post id")

    def test_publish_requires_a_body(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with self.assertRaises(SystemExit) as exc:
            publish_script.main(["--binding", f"room:{CHANNEL}"])

        self.assertEqual(str(exc.exception), "either --body or --body-file is required")

    def test_publish_returns_exit_code_two_for_partial_peer_fanout(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["corp--sky"], team_id=TEAM)

        with mock.patch.object(
            common,
            "publish_binding_message",
            return_value={
                "binding": {"id": f"room:{CHANNEL}"},
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
                code = publish_script.main(["--binding", f"room:{CHANNEL}", "--body", "hello humans"])

        self.assertEqual(code, 2)

    def test_publish_with_source_context_and_session_saves_source_metadata(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL,
            ["corp--sky", "corp--priya"],
            team_id=TEAM,
            policy={"peer_fanout_enabled": True},
        )

        with mock.patch.object(common, "post_channel_message", return_value={"id": "msg-1"}), mock.patch.object(
            common,
            "resolve_session_identity",
            return_value={"session_name": "corp--sky", "session_id": "gc-sky"},
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = publish_script.main(
                    [
                        "--binding",
                        f"room:{CHANNEL}",
                        "--source-event-kind",
                        common.HUMAN_MESSAGE_EVENT_KIND,
                        "--source-ingress-receipt-id",
                        "in-1",
                        "--source-session",
                        "corp--sky",
                        "--body",
                        "@corp--priya hello",
                    ]
                )

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["source_session_name"], "corp--sky")
        self.assertEqual(payload["record"]["source_session_id"], "gc-sky")
        self.assertEqual(payload["record"]["source_event_kind"], common.HUMAN_MESSAGE_EVENT_KIND)
        self.assertEqual(payload["record"]["root_ingress_receipt_id"], "in-1")
        # Peer notification moved to the extmsg outbound orchestrator; the pack
        # must not fan out on its own any more.
        deliver_session_message.assert_not_called()

    def test_publish_reports_unresolvable_source_session(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with mock.patch.object(
            common, "resolve_session_identity", side_effect=common.GCAPIError("session not found: ghost")
        ):
            with self.assertRaises(SystemExit) as exc:
                publish_script.main(
                    ["--binding", f"room:{CHANNEL}", "--source-session", "ghost", "--body", "hello"]
                )

        self.assertEqual(str(exc.exception), "session not found: ghost")

    def test_plain_publish_without_source_context_stays_successful_in_peer_room(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL,
            ["corp--sky", "corp--priya"],
            team_id=TEAM,
            policy={"peer_fanout_enabled": True},
        )

        with mock.patch.object(common, "post_channel_message", return_value={"id": "msg-1"}), mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = publish_script.main(["--binding", f"room:{CHANNEL}", "--body", "hello humans"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertNotIn("peer_delivery", payload["record"])
        deliver_session_message.assert_not_called()

    # ------------------------------------------------------------------
    # thread-scoped (bind-room --root-id) bindings, end to end
    # ------------------------------------------------------------------

    def test_bind_room_root_id_creates_thread_scoped_binding(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(
                ["--kind", "room", "--team-id", TEAM, "--root-id", ROOT_POST, CHANNEL, "sky"]
            )

        self.assertEqual(code, 0)
        binding_id = f"room:{CHANNEL}/{ROOT_POST}"
        binding = common.resolve_chat_binding(common.load_config(), binding_id)
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["conversation_id"], f"{CHANNEL}/{ROOT_POST}")
        self.assertEqual(binding["channel_id"], CHANNEL)
        self.assertEqual(binding["root_id"], ROOT_POST)
        self.assertEqual(json.loads(stdout.getvalue())["id"], binding_id)
        # The whole-channel binding id must stay distinct and unbound.
        self.assertIsNone(common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL}"))

    def test_thread_scoped_binding_publishes_to_real_channel_with_pinned_root(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                bind_script.main(["--kind", "room", "--team-id", TEAM, "--root-id", ROOT_POST, CHANNEL, "sky"]),
                0,
            )

        with mock.patch.object(common, "mattermost_api_request") as api_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-thread"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = publish_script.main(
                    ["--binding", f"room:{CHANNEL}/{ROOT_POST}", "--body", "into the bound thread"]
                )

        self.assertEqual(code, 0)
        # The composite "channel/root" key is the binding identity, never an API
        # channel id — the post has to go to the real channel with the pinned root.
        post_channel_message.assert_called_once_with(
            CHANNEL, "into the bound thread", root_id=ROOT_POST, file_ids=None
        )
        api_request.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["conversation_id"], CHANNEL)
        self.assertEqual(payload["record"]["root_post_id"], ROOT_POST)
        self.assertEqual(payload["record"]["binding_conversation_id"], f"{CHANNEL}/{ROOT_POST}")

    def test_thread_scoped_binding_ignores_a_foreign_reply_target(self) -> None:
        with redirect_stdout(io.StringIO()):
            bind_script.main(["--kind", "room", "--team-id", TEAM, "--root-id", ROOT_POST, CHANNEL, "sky"])

        with mock.patch.object(common, "mattermost_api_request") as api_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-thread"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    [
                        "--binding",
                        f"room:{CHANNEL}/{ROOT_POST}",
                        "--reply-to",
                        "some-other-post",
                        "--trigger",
                        "another-post",
                        "--body",
                        "stays pinned",
                    ]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "stays pinned", root_id=ROOT_POST, file_ids=None)
        api_request.assert_not_called()

    def test_thread_scoped_binding_accepts_the_bare_channel_id_override(self) -> None:
        with redirect_stdout(io.StringIO()):
            bind_script.main(["--kind", "room", "--team-id", TEAM, "--root-id", ROOT_POST, CHANNEL, "sky"])

        with mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-thread"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    [
                        "--binding",
                        f"room:{CHANNEL}/{ROOT_POST}",
                        "--conversation-id",
                        CHANNEL,
                        "--body",
                        "explicit channel",
                    ]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "explicit channel", root_id=ROOT_POST, file_ids=None)

    def test_whole_channel_binding_resolves_root_id_dynamically(self) -> None:
        with redirect_stdout(io.StringIO()):
            bind_script.main(["--kind", "room", "--team-id", TEAM, CHANNEL, "sky"])

        with mock.patch.object(
            common, "mattermost_api_request", return_value=_post("reply-77", CHANNEL, root_id="root-77")
        ) as api_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-dyn"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(
                    ["--binding", f"room:{CHANNEL}", "--root-id", "reply-77", "--body", "dynamic"]
                )

        self.assertEqual(code, 0)
        api_request.assert_called_once_with("GET", "/posts/reply-77", bot_token=None)
        post_channel_message.assert_called_once_with(CHANNEL, "dynamic", root_id="root-77", file_ids=None)

    def test_whole_channel_binding_posts_at_channel_level_without_a_reply_target(self) -> None:
        with redirect_stdout(io.StringIO()):
            bind_script.main(["--kind", "room", "--team-id", TEAM, CHANNEL, "sky"])

        with mock.patch.object(common, "mattermost_api_request") as api_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-flat"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = publish_script.main(["--binding", f"room:{CHANNEL}", "--body", "channel level"])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "channel level", root_id="", file_ids=None)
        api_request.assert_not_called()

    # ------------------------------------------------------------------
    # reply-current
    # ------------------------------------------------------------------

    def test_reply_current_uses_latest_mattermost_context(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", CHANNEL, ["sky"])
        os.environ["GC_SESSION_NAME"] = "sky"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            return_value={
                "publish_binding_id": f"dm:{CHANNEL}",
                "publish_conversation_id": CHANNEL,
                "publish_trigger_id": "orig-22",
                "publish_root_post_id": "orig-22",
            },
        ), mock.patch.object(
            common, "mattermost_api_request", return_value=_post("orig-22", CHANNEL)
        ), mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-22"}
        ) as post_channel_message:
            with redirect_stdout(io.StringIO()):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "safe reply", root_id="orig-22", file_ids=None)
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(recent[0]["binding_id"], f"dm:{CHANNEL}")
        self.assertEqual(recent[0]["remote_message_id"], "msg-22")

    def test_reply_current_replies_into_a_thread_scoped_binding(self) -> None:
        with redirect_stdout(io.StringIO()):
            bind_script.main(["--kind", "room", "--team-id", TEAM, "--root-id", ROOT_POST, CHANNEL, "sky"])
        os.environ["GC_SESSION_NAME"] = "sky"

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            return_value={
                "publish_binding_id": f"room:{CHANNEL}/{ROOT_POST}",
                "publish_conversation_id": CHANNEL,
                "publish_trigger_id": "human-post-1",
                "publish_root_post_id": ROOT_POST,
            },
        ), mock.patch.object(common, "mattermost_api_request") as api_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-33"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--body", "threaded reply"])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "threaded reply", root_id=ROOT_POST, file_ids=None)
        api_request.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["reply_context"]["publish_root_post_id"], ROOT_POST)

    def test_reply_current_passes_source_context_through_publish(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL,
            ["corp--sky", "corp--priya"],
            team_id=TEAM,
            policy={"peer_fanout_enabled": True},
        )
        os.environ["GC_SESSION_NAME"] = "corp--sky"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("@corp--priya safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            return_value={
                "kind": common.PEER_PUBLICATION_EVENT_KIND,
                "publish_binding_id": f"room:{CHANNEL}",
                "publish_conversation_id": CHANNEL,
                "publish_trigger_id": "orig-22",
                "publish_root_post_id": "orig-22",
                "root_ingress_receipt_id": "in-1",
            },
        ), mock.patch.object(
            common, "mattermost_api_request", return_value=_post("orig-22", CHANNEL)
        ), mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-22"}
        ), mock.patch.object(
            common, "resolve_session_identity", side_effect=common.GCAPIError("offline")
        ), mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["reply_context"]["source_event_kind"], common.PEER_PUBLICATION_EVENT_KIND)
        self.assertEqual(payload["reply_context"]["root_ingress_receipt_id"], "in-1")
        self.assertEqual(payload["record"]["source_event_kind"], common.PEER_PUBLICATION_EVENT_KIND)
        self.assertNotIn("peer_delivery", payload["record"])
        deliver_session_message.assert_not_called()

    def test_reply_current_session_override_sets_source_identity(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL,
            ["corp--sky", "corp--priya"],
            team_id=TEAM,
            policy={"peer_fanout_enabled": True},
        )
        os.environ["GC_SESSION_NAME"] = "corp--else"
        os.environ["GC_SESSION_ID"] = "gc-else"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("@corp--priya safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            return_value={
                "kind": common.PEER_PUBLICATION_EVENT_KIND,
                "publish_binding_id": f"room:{CHANNEL}",
                "publish_conversation_id": CHANNEL,
                "publish_trigger_id": "orig-22",
                "publish_root_post_id": "orig-22",
                "root_ingress_receipt_id": "in-1",
            },
        ), mock.patch.object(
            common, "mattermost_api_request", return_value=_post("orig-22", CHANNEL)
        ), mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-22"}
        ), mock.patch.object(
            common,
            "resolve_session_identity",
            return_value={"session_name": "corp--sky", "session_id": "gc-sky"},
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--session", "corp--sky", "--body-file", str(body_file)])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["source_session_name"], "corp--sky")
        self.assertEqual(payload["record"]["source_session_id"], "gc-sky")
        self.assertEqual(payload["reply_context"]["source_session_name"], "corp--sky")

    def test_reply_current_reply_context_falls_back_to_current_session_env(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", CHANNEL, ["sky"])
        os.environ["GC_SESSION_NAME"] = "sky"
        os.environ["GC_SESSION_ID"] = "gc-sky"
        body_file = pathlib.Path(self.tempdir.name) / "reply.txt"
        body_file.write_text("safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            return_value={
                "kind": common.HUMAN_MESSAGE_EVENT_KIND,
                "ingress_receipt_id": "in-22",
                "publish_binding_id": f"dm:{CHANNEL}",
                "publish_conversation_id": CHANNEL,
                "publish_trigger_id": "orig-22",
                "publish_root_post_id": "orig-22",
            },
        ), mock.patch.object(
            common, "mattermost_api_request", return_value=_post("orig-22", CHANNEL)
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "msg-22"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["reply_context"]["source_session_name"], "sky")
        self.assertEqual(payload["reply_context"]["source_session_id"], "gc-sky")

    def test_reply_current_without_binding_posts_directly(self) -> None:
        os.environ["GC_SESSION_NAME"] = "sky"

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            side_effect=common.GCAPIError("no recent mattermost event"),
        ), mock.patch.object(
            common, "mattermost_api_request", return_value=_post("reply-5", CHANNEL, root_id="root-5")
        ), mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-direct"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(
                    ["--conversation-id", CHANNEL, "--reply-to", "reply-5", "--body", "direct"]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "direct", root_id="root-5")
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["conversation_id"], CHANNEL)
        self.assertEqual(payload["record"]["root_post_id"], "root-5")

    def test_reply_current_without_context_or_conversation_id_fails(self) -> None:
        os.environ["GC_SESSION_NAME"] = "sky"

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            side_effect=common.GCAPIError("no recent mattermost event with publish metadata found for sky"),
        ):
            with self.assertRaises(SystemExit) as exc:
                reply_current_script.main(["--body", "orphan"])

        self.assertEqual(str(exc.exception), "no recent mattermost event with publish metadata found for sky")

    def test_reply_current_requires_a_body(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            reply_current_script.main([])

        self.assertEqual(str(exc.exception), "either --body or --body-file is required")

    # ------------------------------------------------------------------
    # room launch routing
    # ------------------------------------------------------------------

    def test_reply_current_uses_launch_route(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM, CHANNEL)
        common.save_room_launch(
            {
                "launch_id": "room-launch:orig-22",
                "launcher_id": f"launch-room:{CHANNEL}",
                "team_id": TEAM,
                "conversation_id": CHANNEL,
                "root_post_id": "orig-22",
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )
        os.environ["GC_SESSION_NAME"] = "mm-runtime"
        body_file = pathlib.Path(self.tempdir.name) / "reply-launch.txt"
        body_file.write_text("safe reply", encoding="utf-8")

        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            return_value={
                "kind": common.HUMAN_MESSAGE_EVENT_KIND,
                "ingress_receipt_id": "in-22",
                "publish_binding_id": f"launch-room:{CHANNEL}",
                "publish_conversation_id": CHANNEL,
                "publish_trigger_id": "orig-22",
                "publish_launch_id": "room-launch:orig-22",
            },
        ), mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-22"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = reply_current_script.main(["--body-file", str(body_file)])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "safe reply", root_id="orig-22", file_ids=None)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["conversation_id"], CHANNEL)
        self.assertEqual(payload["record"]["root_post_id"], "orig-22")
        self.assertEqual(payload["record"]["launch_id"], "room-launch:orig-22")
        # First use promotes the launch record to active.
        self.assertEqual(str(common.load_room_launch("room-launch:orig-22").get("state", "")), "active")

    def test_publish_launch_route_hydrates_launch_id_from_source_ingress(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM, CHANNEL)
        common.save_room_launch(
            {
                "launch_id": "room-launch:orig-29",
                "launcher_id": f"launch-room:{CHANNEL}",
                "team_id": TEAM,
                "conversation_id": CHANNEL,
                "root_post_id": "orig-29",
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )
        common.save_chat_ingress({"ingress_id": "in-29", "launch_id": "room-launch:orig-29", "status": "delivered"})

        with mock.patch.object(
            common, "post_channel_message", return_value={"id": "msg-29"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = publish_script.main(
                    [
                        "--binding",
                        f"launch-room:{CHANNEL}",
                        "--source-event-kind",
                        common.HUMAN_MESSAGE_EVENT_KIND,
                        "--source-ingress-receipt-id",
                        "in-29",
                        "--body",
                        "hello launcher",
                    ]
                )

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "hello launcher", root_id="orig-29", file_ids=None)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["record"]["launch_id"], "room-launch:orig-29")
        self.assertEqual(payload["record"]["conversation_id"], CHANNEL)
        self.assertEqual(payload["record"]["root_post_id"], "orig-29")

    def test_publish_launch_route_requires_source_ingress_receipt(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM, CHANNEL)

        with self.assertRaises(SystemExit) as exc:
            publish_script.main(["--binding", f"launch-room:{CHANNEL}", "--body", "hello launcher"])

        self.assertEqual(str(exc.exception), "launch-room publish requires --source-ingress-receipt-id")

    def test_publish_launch_route_rejects_unknown_source_ingress_receipt(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM, CHANNEL)

        with self.assertRaises(SystemExit) as exc:
            publish_script.main(
                [
                    "--binding",
                    f"launch-room:{CHANNEL}",
                    "--source-ingress-receipt-id",
                    "in-missing",
                    "--body",
                    "hello launcher",
                ]
            )

        self.assertEqual(str(exc.exception), "source ingress receipt not found: in-missing")

    # ------------------------------------------------------------------
    # bind
    # ------------------------------------------------------------------

    def test_bind_script_creates_room_binding(self) -> None:
        stdout = io.StringIO()
        with mock.patch.object(
            common, "describe_room_channel_metadata"
        ) as describe_room_channel_metadata, redirect_stdout(stdout):
            code = bind_script.main(["--kind", "room", "--team-id", TEAM, CHANNEL, "sky", "lawrence"])

        self.assertEqual(code, 0)
        describe_room_channel_metadata.assert_not_called()
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL}")
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["session_names"], ["sky", "lawrence"])
        self.assertEqual(binding["team_id"], TEAM)
        self.assertEqual(binding["channel_id"], CHANNEL)
        self.assertEqual(binding["root_id"], "")

    def test_bind_script_creates_dm_binding_from_a_plain_channel_id(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(["--kind", "dm", CHANNEL, "sky"])

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), f"dm:{CHANNEL}")
        assert binding is not None
        self.assertEqual(binding["conversation_id"], CHANNEL)
        self.assertEqual(binding["channel_id"], CHANNEL)
        self.assertEqual(binding["session_names"], ["sky"])

    def test_bind_script_persists_peer_fanout_policy(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(
                [
                    "--kind",
                    "room",
                    "--team-id",
                    TEAM,
                    "--enable-ambient-read",
                    "--enable-peer-fanout",
                    "--allow-untargeted-peer-fanout",
                    "--max-peer-triggered-publishes-per-root",
                    "2",
                    "--max-total-peer-deliveries-per-root",
                    "9",
                    "--max-peer-triggered-publishes-per-session-per-minute",
                    "7",
                    CHANNEL,
                    "corp--sky",
                    "corp--priya",
                ]
            )

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL}")
        assert binding is not None
        self.assertTrue(binding["policy"]["ambient_read_enabled"])
        self.assertTrue(binding["policy"]["peer_fanout_enabled"])
        self.assertTrue(binding["policy"]["allow_untargeted_peer_fanout"])
        self.assertEqual(binding["policy"]["max_peer_triggered_publishes_per_root"], 2)
        self.assertEqual(binding["policy"]["max_total_peer_deliveries_per_root"], 9)
        self.assertEqual(binding["policy"]["max_peer_triggered_publishes_per_session_per_minute"], 7)

    def test_bind_script_persists_untargeted_ambient_delivery_policy(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(
                [
                    "--kind",
                    "room",
                    "--team-id",
                    TEAM,
                    "--enable-ambient-read",
                    "--allow-untargeted-ambient-delivery",
                    CHANNEL,
                    "randy",
                ]
            )

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL}")
        assert binding is not None
        self.assertTrue(binding["policy"]["ambient_read_enabled"])
        self.assertTrue(binding["policy"]["allow_untargeted_ambient_delivery"])

    def test_bind_script_disable_ambient_read_updates_existing_room_binding(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL,
            ["sky", "lawrence"],
            team_id=TEAM,
            policy={"ambient_read_enabled": True},
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(
                ["--kind", "room", "--team-id", TEAM, "--disable-ambient-read", CHANNEL, "sky", "lawrence"]
            )

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL}")
        assert binding is not None
        self.assertFalse(binding["policy"]["ambient_read_enabled"])

    def test_bind_script_rejects_conflicting_ambient_read_flags(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            bind_script.main(
                ["--kind", "room", "--enable-ambient-read", "--disable-ambient-read", CHANNEL, "sky"]
            )

        self.assertEqual(str(exc.exception), "choose only one of --enable-ambient-read or --disable-ambient-read")

    def test_bind_script_rejects_conflicting_untargeted_ambient_delivery_flags(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            bind_script.main(
                [
                    "--kind",
                    "room",
                    "--allow-untargeted-ambient-delivery",
                    "--disallow-untargeted-ambient-delivery",
                    CHANNEL,
                    "randy",
                ]
            )

        self.assertEqual(
            str(exc.exception),
            "choose only one of --allow-untargeted-ambient-delivery or --disallow-untargeted-ambient-delivery",
        )

    def test_bind_script_rejects_room_policy_flags_on_a_dm(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            bind_script.main(["--kind", "dm", "--enable-ambient-read", CHANNEL, "sky"])

        self.assertEqual(str(exc.exception), "room policy flags require --kind room")

    def test_bind_script_rejects_root_id_on_a_dm(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            bind_script.main(["--kind", "dm", "--root-id", ROOT_POST, CHANNEL, "sky"])

        self.assertEqual(str(exc.exception), "--root-id requires --kind room")

    def test_bind_script_rejects_invalid_dm_fanout_cleanly(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            bind_script.main(["--kind", "dm", CHANNEL, "sky", "lawrence"])

        self.assertEqual(str(exc.exception), "DM bindings require exactly one session name")

    def test_bind_script_rejects_a_room_that_already_has_room_launch(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM, CHANNEL)

        with self.assertRaises(SystemExit) as exc:
            bind_script.main(["--kind", "room", "--team-id", TEAM, CHANNEL, "sky"])

        self.assertEqual(str(exc.exception), "room launch is already enabled for that conversation")

    # ------------------------------------------------------------------
    # enable-room-launch
    # ------------------------------------------------------------------

    def test_enable_room_launch_script_creates_launcher(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = room_launch_script.main(["--team-id", TEAM, CHANNEL])

        self.assertEqual(code, 0)
        launcher = common.resolve_room_launcher(common.load_config(), CHANNEL)
        self.assertIsNotNone(launcher)
        assert launcher is not None
        self.assertEqual(launcher["response_mode"], "mention_only")
        self.assertEqual(launcher["team_id"], TEAM)
        self.assertTrue(launcher["policy"]["peer_fanout_enabled"])
        self.assertTrue(launcher["policy"]["allow_untargeted_peer_fanout"])

    def test_enable_room_launch_script_can_disable_peer_fanout(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = room_launch_script.main(
                ["--team-id", TEAM, "--disable-peer-fanout", "--disallow-untargeted-peer-fanout", CHANNEL]
            )

        self.assertEqual(code, 0)
        launcher = common.resolve_room_launcher(common.load_config(), CHANNEL)
        self.assertIsNotNone(launcher)
        assert launcher is not None
        self.assertFalse(launcher["policy"]["peer_fanout_enabled"])
        self.assertFalse(launcher["policy"]["allow_untargeted_peer_fanout"])

    def test_enable_room_launch_preserves_legacy_launcher_without_policy_flags(self) -> None:
        common.save_config(
            common.normalize_config(
                {
                    "chat": {
                        "launchers": {
                            f"launch-room:{CHANNEL}": {
                                "id": f"launch-room:{CHANNEL}",
                                "kind": "room",
                                "team_id": TEAM,
                                "conversation_id": CHANNEL,
                                "response_mode": "mention_only",
                            }
                        }
                    }
                }
            )
        )

        with redirect_stdout(io.StringIO()):
            code = room_launch_script.main(["--team-id", TEAM, CHANNEL])

        self.assertEqual(code, 0)
        launcher = common.resolve_room_launcher(common.load_config(), CHANNEL)
        self.assertIsNotNone(launcher)
        assert launcher is not None
        self.assertNotIn("policy", launcher)

    def test_enable_room_launch_rejects_a_directly_bound_room(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL, ["sky"], team_id=TEAM)

        with self.assertRaises(SystemExit) as exc:
            room_launch_script.main(["--team-id", TEAM, CHANNEL])

        self.assertEqual(str(exc.exception), "room launch cannot be enabled on a directly bound room")

    def test_enable_room_launch_respond_all_requires_default_handle(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            room_launch_script.main(["--team-id", TEAM, "--response-mode", "respond_all", CHANNEL])

        self.assertEqual(str(exc.exception), "respond_all room launchers require --default-handle")

    # ------------------------------------------------------------------
    # retry-peer-fanout
    # ------------------------------------------------------------------

    def _partial_failure_publish(self, publish_id: str, binding_id: str) -> dict[str, object]:
        return {
            "publish_id": publish_id,
            "binding_id": binding_id,
            "binding_kind": "room",
            "binding_conversation_id": CHANNEL,
            "conversation_id": CHANNEL,
            "team_id": TEAM,
            "source_session_name": "corp--sky",
            "source_session_id": "gc-1",
            "source_event_kind": common.HUMAN_MESSAGE_EVENT_KIND,
            "root_ingress_receipt_id": "in-1",
            "body": "@corp--priya hello",
            "remote_message_id": "msg-1",
            "root_post_id": "orig-1",
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
                        "idempotency_key": f"peer_publish:{publish_id}:binding:{binding_id}:target:corp--priya",
                        "attempts": [],
                    }
                ],
                "budget_snapshot": {},
            },
        }

    def test_retry_peer_fanout_script_retries_saved_publish(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL,
            ["corp--sky", "corp--priya"],
            team_id=TEAM,
            policy={"peer_fanout_enabled": True},
        )
        common.save_chat_publish(self._partial_failure_publish("mattermost-publish-1", f"room:{CHANNEL}"))

        with mock.patch.object(
            common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-1"}
        ) as deliver_session_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = retry_peer_fanout_script.main(["mattermost-publish-1"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["peer_delivery"]["status"], "delivered")
        deliver_session_message.assert_called_once()
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"channel_id: {CHANNEL}", envelope)
        self.assertIn(f"team_id: {TEAM}", envelope)

    def test_retry_peer_fanout_script_accepts_launch_room_binding(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM, CHANNEL)
        common.save_chat_publish(
            self._partial_failure_publish("mattermost-publish-launch", f"launch-room:{CHANNEL}")
        )

        with mock.patch.object(common, "deliver_session_message", return_value={"status": "accepted", "id": "gc-1"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = retry_peer_fanout_script.main(["mattermost-publish-launch"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["peer_delivery"]["status"], "delivered")

    def test_retry_peer_fanout_script_reports_unknown_publish(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            retry_peer_fanout_script.main(["mattermost-publish-missing"])

        self.assertEqual(str(exc.exception), "publish not found: mattermost-publish-missing")


if __name__ == "__main__":
    unittest.main()

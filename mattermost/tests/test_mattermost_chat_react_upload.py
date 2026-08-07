from __future__ import annotations

import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import mattermost_chat_react as react_script
import mattermost_chat_upload as upload_script
import mattermost_intake_common as common


CHANNEL = "9h5j7k1m3n5p7r9t1v3x5z7b9c"
POST = "5s7t9u1v3w5x7y9z1a3b5c7d9e"
ROOT_POST = "2a4b6c8d0e2f4g6h8i0j2k4m6n"
TEAM = "7k3m9x2c5n8b1v4z6q0r2s4t6w"
BOT_USER = "3c5e7g9i1k3m5o7q9s1u3w5y7a"


def _reply_context(**overrides: str) -> dict[str, str]:
    """The shape find_latest_mattermost_reply_context() returns."""
    context = {
        "kind": common.HUMAN_MESSAGE_EVENT_KIND,
        "binding_id": f"room:{CHANNEL}",
        "ingress_receipt_id": "in-1",
        "mattermost_post_id": POST,
        "publish_binding_id": f"room:{CHANNEL}",
        "publish_conversation_id": CHANNEL,
        "publish_trigger_id": POST,
        "publish_root_post_id": ROOT_POST,
        "team_id": TEAM,
    }
    context.update(overrides)
    return context


class MattermostScriptTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        for key in ("GC_SESSION_ID", "GC_SESSION_NAME", "GC_ALIAS"):
            os.environ.pop(key, None)
        os.environ["GC_SESSION_NAME"] = "sky"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def _tempfile(self, name: str, content: bytes = b"hello bytes") -> pathlib.Path:
        path = pathlib.Path(self.tempdir.name) / name
        path.write_bytes(content)
        return path


# ----------------------------------------------------------------------
# gc mattermost react
# ----------------------------------------------------------------------


class MattermostChatReactTests(MattermostScriptTestCase):
    def test_explicit_target_adds_reaction(self) -> None:
        with mock.patch.object(common, "resolve_bot_user_id", return_value=BOT_USER), mock.patch.object(
            common, "add_message_reaction", return_value={"user_id": BOT_USER, "post_id": POST, "emoji_name": "eyes"}
        ) as add_message_reaction, mock.patch.object(
            common, "find_latest_mattermost_reply_context"
        ) as find_context:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = react_script.main(["--conversation-id", CHANNEL, "--message-id", POST])

        self.assertEqual(code, 0)
        find_context.assert_not_called()
        add_message_reaction.assert_called_once_with(POST, "eyes", user_id=BOT_USER)
        receipt = json.loads(stdout.getvalue())
        self.assertTrue(receipt["delivered"])
        self.assertEqual(receipt["mode"], "explicit")
        self.assertEqual(receipt["emoji"], "eyes")
        self.assertEqual(receipt["conversation_id"], CHANNEL)
        self.assertEqual(receipt["post_id"], POST)
        self.assertEqual(receipt["user_id"], BOT_USER)
        self.assertEqual(receipt["binding_id"], "")
        self.assertEqual(receipt["failure_kind"], "")
        self.assertEqual(receipt["error"], "")

    def test_current_mode_uses_latest_inbound_post(self) -> None:
        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ) as find_context, mock.patch.object(
            common, "resolve_bot_user_id", return_value=BOT_USER
        ), mock.patch.object(common, "add_message_reaction", return_value={"emoji_name": "eyes"}) as add_reaction:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = react_script.main([])

        self.assertEqual(code, 0)
        find_context.assert_called_once_with("", tail=react_script.DEFAULT_TRANSCRIPT_TAIL)
        add_reaction.assert_called_once_with(POST, "eyes", user_id=BOT_USER)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["mode"], "current")
        self.assertEqual(receipt["conversation_id"], CHANNEL)
        self.assertEqual(receipt["binding_id"], f"room:{CHANNEL}")
        self.assertEqual(receipt["session_selector"], "sky")

    def test_current_mode_honours_session_override(self) -> None:
        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ) as find_context, mock.patch.object(
            common, "resolve_bot_user_id", return_value=BOT_USER
        ), mock.patch.object(common, "add_message_reaction", return_value={}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = react_script.main(["--session", "corp--priya"])

        self.assertEqual(code, 0)
        find_context.assert_called_once_with("corp--priya", tail=react_script.DEFAULT_TRANSCRIPT_TAIL)
        self.assertEqual(json.loads(stdout.getvalue())["session_selector"], "corp--priya")

    def test_current_mode_falls_back_to_publish_trigger_id(self) -> None:
        context = _reply_context()
        context.pop("mattermost_post_id")
        context["publish_trigger_id"] = "fallback-post"

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=context
        ), mock.patch.object(common, "resolve_bot_user_id", return_value=BOT_USER), mock.patch.object(
            common, "add_message_reaction", return_value={}
        ) as add_reaction:
            with redirect_stdout(io.StringIO()):
                code = react_script.main([])

        self.assertEqual(code, 0)
        add_reaction.assert_called_once_with("fallback-post", "eyes", user_id=BOT_USER)

    def test_current_flag_is_the_explicit_default_mode(self) -> None:
        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(common, "resolve_bot_user_id", return_value=BOT_USER), mock.patch.object(
            common, "add_message_reaction", return_value={}
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = react_script.main(["--current"])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["mode"], "current")

    # -- emoji normalization ------------------------------------------------

    def test_emoji_colons_are_stripped(self) -> None:
        for raw, expected in ((":thumbsup:", "thumbsup"), ("  white_check_mark  ", "white_check_mark"), (": eyes :", "eyes")):
            with self.subTest(raw=raw):
                with mock.patch.object(common, "resolve_bot_user_id", return_value=BOT_USER), mock.patch.object(
                    common, "add_message_reaction", return_value={}
                ) as add_reaction:
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        code = react_script.main(
                            ["--conversation-id", CHANNEL, "--message-id", POST, "--emoji", raw]
                        )

                self.assertEqual(code, 0)
                add_reaction.assert_called_once_with(POST, expected, user_id=BOT_USER)
                self.assertEqual(json.loads(stdout.getvalue())["emoji"], expected)

    def test_default_emoji_is_eyes(self) -> None:
        self.assertEqual(react_script.DEFAULT_EMOJI, "eyes")

    def test_blank_emoji_is_rejected(self) -> None:
        for raw in ("", "   ", "::", ":  :"):
            with self.subTest(raw=raw):
                with self.assertRaises(SystemExit) as exc:
                    react_script.main(["--conversation-id", CHANNEL, "--message-id", POST, "--emoji", raw])
                self.assertEqual(str(exc.exception), "--emoji must be a non-empty emoji name such as eyes")

    # -- argument validation ------------------------------------------------

    def test_conversation_id_without_message_id_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            react_script.main(["--conversation-id", CHANNEL])

        self.assertEqual(str(exc.exception), "--conversation-id and --message-id must be passed together")

    def test_message_id_without_conversation_id_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            react_script.main(["--message-id", POST])

        self.assertEqual(str(exc.exception), "--conversation-id and --message-id must be passed together")

    def test_current_cannot_be_combined_with_explicit_target(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            react_script.main(["--current", "--conversation-id", CHANNEL, "--message-id", POST])

        self.assertEqual(str(exc.exception), "--current cannot be combined with --conversation-id/--message-id")

    def test_missing_transcript_context_suggests_explicit_flags(self) -> None:
        with mock.patch.object(
            common,
            "find_latest_mattermost_reply_context",
            side_effect=common.GCAPIError("no recent mattermost event with publish metadata found for sky"),
        ):
            with self.assertRaises(SystemExit) as exc:
                react_script.main([])

        self.assertEqual(
            str(exc.exception),
            "no recent mattermost event with publish metadata found for sky; "
            "pass --conversation-id <channel_id> --message-id <post_id> to react to a specific post",
        )

    def test_context_without_a_post_id_is_rejected(self) -> None:
        context = _reply_context()
        context.pop("mattermost_post_id")
        context["publish_trigger_id"] = ""

        with mock.patch.object(common, "find_latest_mattermost_reply_context", return_value=context):
            with self.assertRaises(SystemExit) as exc:
                react_script.main([])

        self.assertEqual(
            str(exc.exception),
            "latest mattermost event has no post id; pass --conversation-id and --message-id explicitly",
        )

    # -- REST failure modes -------------------------------------------------

    def test_reaction_failures_map_to_failure_kinds(self) -> None:
        cases = (
            (404, "not_found"),
            (401, "auth"),
            (403, "auth"),
            (429, "rate_limited"),
            (400, "invalid_request"),
            (500, "error"),
            (None, "error"),
        )
        for status, expected in cases:
            with self.subTest(status=status):
                error = common.MattermostAPIError("boom", status_code=status)
                with mock.patch.object(common, "resolve_bot_user_id", return_value=BOT_USER), mock.patch.object(
                    common, "add_message_reaction", side_effect=error
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        code = react_script.main(["--conversation-id", CHANNEL, "--message-id", POST])

                self.assertEqual(code, 1)
                receipt = json.loads(stdout.getvalue())
                self.assertFalse(receipt["delivered"])
                self.assertEqual(receipt["failure_kind"], expected)
                self.assertEqual(receipt["error"], "boom")
                self.assertNotIn("reaction", receipt)

    def test_unresolvable_bot_user_id_returns_a_failure_receipt(self) -> None:
        with mock.patch.object(common, "resolve_bot_user_id", return_value=""), mock.patch.object(
            common, "add_message_reaction"
        ) as add_reaction:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = react_script.main(["--conversation-id", CHANNEL, "--message-id", POST])

        self.assertEqual(code, 1)
        add_reaction.assert_not_called()
        receipt = json.loads(stdout.getvalue())
        self.assertFalse(receipt["delivered"])
        self.assertEqual(receipt["failure_kind"], "error")
        self.assertEqual(receipt["error"], "could not resolve the bot user id from GET /users/me")

    def test_unconfigured_site_url_returns_a_failure_receipt(self) -> None:
        # resolve_bot_user_id() reaches the HTTP layer, which raises before any
        # request is made when site_url is unset.
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = react_script.main(["--conversation-id", CHANNEL, "--message-id", POST])

        self.assertEqual(code, 1)
        receipt = json.loads(stdout.getvalue())
        self.assertFalse(receipt["delivered"])
        self.assertEqual(receipt["failure_kind"], "error")
        self.assertEqual(receipt["error"], "Mattermost site_url is not configured")


# ----------------------------------------------------------------------
# gc mattermost upload
# ----------------------------------------------------------------------


class MattermostChatUploadTests(MattermostScriptTestCase):
    def _bind_room(self, *, root_id: str = "") -> dict[str, object]:
        conversation_id = common.mattermost_conversation_key(CHANNEL, root_id)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["sky"], team_id=TEAM)
        binding = common.resolve_chat_binding(
            common.load_config(), common.chat_binding_id("room", conversation_id)
        )
        assert binding is not None
        return binding

    # -- argument validation ------------------------------------------------

    def test_root_id_and_thread_current_are_mutually_exclusive(self) -> None:
        path = self._tempfile("plot.png")
        with self.assertRaises(SystemExit) as exc:
            upload_script.main(["--file", str(path), "--root-id", ROOT_POST, "--thread-current"])

        self.assertEqual(str(exc.exception), "--root-id and --thread-current are mutually exclusive")

    def test_file_is_required(self) -> None:
        with self.assertRaises(SystemExit) as exc, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            upload_script.main([])

        # argparse exits with status 2 for a missing required flag.
        self.assertEqual(exc.exception.code, 2)

    def test_via_only_accepts_gc_or_adapter(self) -> None:
        path = self._tempfile("plot.png")
        with self.assertRaises(SystemExit) as exc, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            upload_script.main(["--file", str(path), "--via", "smoke-signal"])

        self.assertEqual(exc.exception.code, 2)

    def test_missing_file_is_rejected(self) -> None:
        missing = str(pathlib.Path(self.tempdir.name) / "nope.png")
        with self.assertRaises(SystemExit) as exc:
            upload_script.main(["--file", missing])

        self.assertEqual(str(exc.exception), f"file not found: {missing}")

    def test_directory_is_rejected(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            upload_script.main(["--file", self.tempdir.name])

        self.assertEqual(str(exc.exception), f"not a regular file: {self.tempdir.name}")

    def test_missing_transcript_context_suggests_binding(self) -> None:
        path = self._tempfile("plot.png")
        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", side_effect=common.GCAPIError("no recent event")
        ):
            with self.assertRaises(SystemExit) as exc:
                upload_script.main(["--file", str(path)])

        self.assertEqual(
            str(exc.exception),
            "no recent event; bind this session with `gc mattermost bind-room` or `gc mattermost bind-dm` first",
        )

    def test_context_without_binding_id_is_rejected(self) -> None:
        path = self._tempfile("plot.png")
        context = _reply_context(publish_binding_id="")
        with mock.patch.object(common, "find_latest_mattermost_reply_context", return_value=context):
            with self.assertRaises(SystemExit) as exc:
                upload_script.main(["--file", str(path)])

        self.assertEqual(str(exc.exception), "latest mattermost event has no publish_binding_id")

    def test_unknown_binding_is_rejected(self) -> None:
        path = self._tempfile("plot.png")
        with mock.patch.object(common, "find_latest_mattermost_reply_context", return_value=_reply_context()):
            with self.assertRaises(SystemExit) as exc:
                upload_script.main(["--file", str(path)])

        self.assertEqual(str(exc.exception), f"binding not found: room:{CHANNEL}")

    # -- happy paths --------------------------------------------------------

    def test_plain_upload_posts_at_channel_level(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png", b"\x89PNG payload")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(common, "mattermost_api_request") as api_request, mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-1"}]}
        ) as upload_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "post-1"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path), "--initial-comment", "latest run"])

        self.assertEqual(code, 0)
        upload_request.assert_called_once_with(
            "/files", [("channel_id", CHANNEL)], [("files", "plot.png", b"\x89PNG payload")]
        )
        post_channel_message.assert_called_once_with(CHANNEL, "latest run", root_id="", file_ids=["file-1"])
        # A plain upload drops the inbound threading hints, so no thread-root walk.
        api_request.assert_not_called()

        receipt = json.loads(stdout.getvalue())
        self.assertTrue(receipt["delivered"])
        self.assertEqual(receipt["via"], "gc")
        self.assertEqual(receipt["file_id"], "file-1")
        self.assertEqual(receipt["file_ids"], ["file-1"])
        self.assertEqual(receipt["filename"], "plot.png")
        self.assertEqual(receipt["size_bytes"], len(b"\x89PNG payload"))
        self.assertEqual(receipt["conversation_id"], CHANNEL)
        self.assertEqual(receipt["root_id"], "")
        self.assertEqual(receipt["post_id"], "post-1")
        self.assertEqual(receipt["binding_id"], f"room:{CHANNEL}")
        self.assertEqual(receipt["failure_kind"], "")
        self.assertEqual(receipt["record"]["remote_message_id"], "post-1")

        # --via gc records the upload as a publish.
        recent = common.list_recent_chat_publishes(limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["remote_message_id"], "post-1")

    def test_thread_current_attaches_under_the_inbound_thread_root(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": ROOT_POST, "channel_id": CHANNEL, "root_id": ""},
        ) as api_request, mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-2"}]}
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "post-2"}) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path), "--thread-current"])

        self.assertEqual(code, 0)
        api_request.assert_called_with("GET", f"/posts/{ROOT_POST}", bot_token=None)
        post_channel_message.assert_called_once_with(CHANNEL, "", root_id=ROOT_POST, file_ids=["file-2"])
        self.assertEqual(json.loads(stdout.getvalue())["root_id"], ROOT_POST)

    def test_explicit_root_id_attaches_under_that_thread(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": "reply-42", "channel_id": CHANNEL, "root_id": "root-42"},
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-3"}]}
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "post-3"}) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path), "--root-id", "reply-42"])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "", root_id="root-42", file_ids=["file-3"])
        self.assertEqual(json.loads(stdout.getvalue())["root_id"], "root-42")

    def test_thread_scoped_binding_pins_the_bound_root(self) -> None:
        self._bind_room(root_id=ROOT_POST)
        path = self._tempfile("plot.png")
        context = _reply_context(publish_binding_id=f"room:{CHANNEL}/{ROOT_POST}")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=context
        ), mock.patch.object(common, "mattermost_api_request") as api_request, mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-4"}]}
        ) as upload_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "post-4"}
        ) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path)])

        self.assertEqual(code, 0)
        # The composite "channel/root" binding key must never reach the REST API.
        upload_request.assert_called_once_with(
            "/files", [("channel_id", CHANNEL)], [("files", "plot.png", b"hello bytes")]
        )
        post_channel_message.assert_called_once_with(CHANNEL, "", root_id=ROOT_POST, file_ids=["file-4"])
        api_request.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue())["conversation_id"], CHANNEL)

    def test_filename_override_and_basename_default(self) -> None:
        self._bind_room()
        path = self._tempfile("digest.csv", b"a,b\n")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-5"}]}
        ) as upload_request, mock.patch.object(common, "post_channel_message", return_value={"id": "post-5"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path), "--filename", "overnight-digest.csv"])

        self.assertEqual(code, 0)
        upload_request.assert_called_once_with(
            "/files", [("channel_id", CHANNEL)], [("files", "overnight-digest.csv", b"a,b\n")]
        )
        self.assertEqual(json.loads(stdout.getvalue())["filename"], "overnight-digest.csv")

    def test_via_adapter_bypasses_the_publish_record(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-6"}]}
        ), mock.patch.object(
            common, "post_channel_message", return_value={"id": "post-6"}
        ) as post_channel_message, mock.patch.object(
            common, "publish_binding_message"
        ) as publish_binding_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path), "--via", "adapter", "--initial-comment", "diag"])

        self.assertEqual(code, 0)
        publish_binding_message.assert_not_called()
        post_channel_message.assert_called_once_with(CHANNEL, "diag", root_id="", file_ids=["file-6"])
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["via"], "adapter")
        self.assertEqual(receipt["post_id"], "post-6")
        self.assertNotIn("record", receipt)
        self.assertEqual(common.list_recent_chat_publishes(limit=5), [])

    def test_multiple_file_infos_are_all_attached(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common,
            "mattermost_upload_request",
            return_value={"file_infos": [{"id": "file-a"}, {"id": ""}, {"id": "file-b"}, "junk"]},
        ), mock.patch.object(common, "post_channel_message", return_value={"id": "post-7"}) as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path)])

        self.assertEqual(code, 0)
        post_channel_message.assert_called_once_with(CHANNEL, "", root_id="", file_ids=["file-a", "file-b"])
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["file_ids"], ["file-a", "file-b"])
        self.assertEqual(receipt["file_id"], "file-a")

    def test_peer_delivery_attention_propagates_exit_code_two(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-8"}]}
        ), mock.patch.object(
            common,
            "publish_binding_message",
            return_value={
                "record": {
                    "remote_message_id": "post-8",
                    "peer_delivery": {"phase": "peer_fanout_partial_failure", "status": "partial_failure"},
                },
                "response": {"id": "post-8"},
            },
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path)])

        self.assertEqual(code, 2)
        self.assertTrue(json.loads(stdout.getvalue())["delivered"])

    # -- REST failure modes -------------------------------------------------

    def test_upload_without_a_file_id_returns_a_failure_receipt(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": []}
        ), mock.patch.object(common, "post_channel_message") as post_channel_message:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path)])

        self.assertEqual(code, 1)
        post_channel_message.assert_not_called()
        receipt = json.loads(stdout.getvalue())
        self.assertFalse(receipt["delivered"])
        self.assertEqual(receipt["failure_kind"], "error")
        self.assertEqual(receipt["error"], "mattermost upload returned no file id")

    def test_upload_failures_map_to_failure_kinds(self) -> None:
        cases = (
            (404, "not_found"),
            (401, "auth"),
            (403, "auth"),
            (429, "rate_limited"),
            (413, "too_large"),
            (400, "invalid_request"),
            (500, "error"),
            (None, "error"),
        )
        for status, expected in cases:
            with self.subTest(status=status):
                self.setUp()
                self._bind_room()
                path = self._tempfile("plot.png")
                error = common.MattermostAPIError("boom", status_code=status)
                with mock.patch.object(
                    common, "find_latest_mattermost_reply_context", return_value=_reply_context()
                ), mock.patch.object(common, "mattermost_upload_request", side_effect=error):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        code = upload_script.main(["--file", str(path)])

                self.assertEqual(code, 1)
                receipt = json.loads(stdout.getvalue())
                self.assertFalse(receipt["delivered"])
                self.assertEqual(receipt["failure_kind"], expected)
                self.assertEqual(receipt["error"], "boom")

    def test_post_creation_failure_still_reports_the_uploaded_file_id(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-9"}]}
        ), mock.patch.object(
            common, "post_channel_message", side_effect=common.MattermostAPIError("forbidden", status_code=403)
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path)])

        self.assertEqual(code, 1)
        receipt = json.loads(stdout.getvalue())
        self.assertFalse(receipt["delivered"])
        self.assertEqual(receipt["file_id"], "file-9")
        self.assertEqual(receipt["failure_kind"], "auth")

    # -- idempotency --------------------------------------------------------

    def test_idempotency_key_replays_the_saved_receipt(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-10"}]}
        ) as upload_request, mock.patch.object(common, "post_channel_message", return_value={"id": "post-10"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                first = upload_script.main(["--file", str(path), "--idempotency-key", "up-1"])

            self.assertEqual(first, 0)
            self.assertEqual(upload_request.call_count, 1)
            self.assertNotIn("idempotent_replay", json.loads(stdout.getvalue()))

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                second = upload_script.main(["--file", str(path), "--idempotency-key", "up-1"])

        self.assertEqual(second, 0)
        # The replay must not re-upload the bytes or create a second post.
        self.assertEqual(upload_request.call_count, 1)
        replay = json.loads(stdout.getvalue())
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["post_id"], "post-10")
        self.assertEqual(len(common.list_recent_chat_publishes(limit=5)), 1)

    def test_failed_uploads_are_not_cached(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", side_effect=common.MattermostAPIError("boom", status_code=500)
        ):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(upload_script.main(["--file", str(path), "--idempotency-key", "up-2"]), 1)

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-11"}]}
        ) as upload_request, mock.patch.object(common, "post_channel_message", return_value={"id": "post-11"}):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = upload_script.main(["--file", str(path), "--idempotency-key", "up-2"])

        self.assertEqual(code, 0)
        upload_request.assert_called_once()
        self.assertNotIn("idempotent_replay", json.loads(stdout.getvalue()))

    def test_replay_preserves_the_original_exit_code(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")
        partial = {
            "record": {
                "remote_message_id": "post-12",
                "peer_delivery": {"phase": "peer_fanout_partial_failure", "status": "partial_failure"},
            },
            "response": {"id": "post-12"},
        }

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-12"}]}
        ), mock.patch.object(common, "publish_binding_message", return_value=partial):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(upload_script.main(["--file", str(path), "--idempotency-key", "up-3"]), 2)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            replay_code = upload_script.main(["--file", str(path), "--idempotency-key", "up-3"])

        # A replay of a partially-delivered upload must not read as a clean success.
        self.assertEqual(replay_code, 2)
        self.assertTrue(json.loads(stdout.getvalue())["idempotent_replay"])

    def test_uploads_without_a_key_are_never_cached(self) -> None:
        self._bind_room()
        path = self._tempfile("plot.png")

        with mock.patch.object(
            common, "find_latest_mattermost_reply_context", return_value=_reply_context()
        ), mock.patch.object(
            common, "mattermost_upload_request", return_value={"file_infos": [{"id": "file-13"}]}
        ) as upload_request, mock.patch.object(common, "post_channel_message", return_value={"id": "post-13"}):
            for _ in range(2):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(upload_script.main(["--file", str(path)]), 0)

        self.assertEqual(upload_request.call_count, 2)
        self.assertFalse(os.path.isdir(upload_script._idempotency_dir()))


if __name__ == "__main__":
    unittest.main()

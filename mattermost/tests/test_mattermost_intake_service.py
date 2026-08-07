from __future__ import annotations

import base64
import errno
import json
import pathlib
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
from unittest import mock

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import mattermost_intake_common as common
import mattermost_intake_service as service

# Mattermost ids are 26-character lowercase alphanumerics; `validate_mattermost_id`
# rejects anything else, so the fixtures below have to be shaped like real ids.
TEAM_ID = "team0000000000000000000000"
OTHER_TEAM_ID = "team1111111111111111111111"
CHANNEL_ID = "chan0000000000000000000000"
OTHER_CHANNEL_ID = "chan1111111111111111111111"
ROOT_ID = "root0000000000000000000000"
USER_ID = "user0000000000000000000000"
BOT_USER_ID = "bot00000000000000000000000"
COMMAND_TOKEN = "tok00000000000000000000000"
SITE_URL = "https://mattermost.example.com"


def unix_http_request(
    socket_path: str,
    method: str,
    path: str,
    *,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    request_headers = {
        "Host": "localhost",
        "Connection": "close",
        "Content-Length": str(len(body)),
    }
    if headers:
        request_headers.update(headers)
    request_lines = [f"{method} {path} HTTP/1.1", *[f"{key}: {value}" for key, value in request_headers.items()], "", ""]
    payload = "\r\n".join(request_lines).encode("utf-8") + body
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(payload)
        try:
            client.shutdown(socket.SHUT_WR)
        except OSError as exc:
            # Routes that answer without draining the request body (404, 401)
            # can close first; macOS then reports ENOTCONN on shutdown.
            if exc.errno not in {errno.ENOTCONN, errno.EPIPE}:
                raise
        chunks: list[bytes] = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    raw = b"".join(chunks)
    head, _, response_body = raw.partition(b"\r\n\r\n")
    status_line = head.splitlines()[0].decode("utf-8")
    return int(status_line.split()[1]), response_body


class MattermostIntakeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        for key in (
            "GC_SERVICE_NAME",
            "GC_SERVICE_STATE_ROOT",
            "GC_SERVICE_SECRETS_DIR",
            "GC_SERVICE_PUBLIC_URL",
            "GC_SERVICE_SOCKET",
            "GC_MATTERMOST_URL",
            "GC_MATTERMOST_API_BASE",
            "GC_BIN",
            "GC_CITY_PATH",
        ):
            os.environ.pop(key, None)
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        service.LAST_REQUEST_PRUNE_AT = 0.0
        service.LAST_REQUEST_RECOVERY_AT = 0.0
        service.PROCESSING_REQUESTS.clear()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)
        service.LAST_REQUEST_PRUNE_AT = 0.0
        service.LAST_REQUEST_RECOVERY_AT = 0.0
        service.PROCESSING_REQUESTS.clear()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def write_rig_route(self, rig: str) -> None:
        beads_dir = pathlib.Path(self.tempdir.name, ".beads")
        beads_dir.mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.tempdir.name, rig).mkdir(parents=True, exist_ok=True)
        pathlib.Path(beads_dir, "routes.jsonl").write_text(f'{{"path":"{rig}"}}\n', encoding="utf-8")

    def import_app(self, **overrides: object) -> dict[str, object]:
        fields: dict[str, object] = {
            "site_url": SITE_URL,
            "team_id": TEAM_ID,
            "bot_user_id": BOT_USER_ID,
            "command_name": "gc",
        }
        fields.update(overrides)
        return common.import_app_config(common.load_config(), fields)

    def command_form(self, **overrides: str) -> dict[str, str]:
        form = {
            "token": COMMAND_TOKEN,
            "team_id": TEAM_ID,
            "team_domain": "acme",
            "channel_id": CHANNEL_ID,
            "channel_name": "town-square",
            "root_id": "",
            "user_id": USER_ID,
            "user_name": "alice",
            "command": "/gc",
            "text": "",
            "trigger_id": "trigger-1",
            "response_url": "https://mattermost.example.com/hooks/commands/response",
        }
        form.update(overrides)
        return form

    def command_invocation(self, **overrides: str) -> dict[str, str]:
        return service.normalize_command_invocation(self.command_form(**overrides))

    def channel_context(self, **overrides: object) -> dict[str, object]:
        context: dict[str, object] = {
            "team_id": TEAM_ID,
            "channel_id": CHANNEL_ID,
            "root_id": "",
            "mapping": {},
            "channel_info": {},
        }
        context.update(overrides)
        return context

    def start_interactions_server(self) -> str:
        socket_path = pathlib.Path(self.tempdir.name, "mm-intake.sock")
        os.environ["GC_SERVICE_NAME"] = common.INTERACTIONS_SERVICE_NAME
        server = service.ThreadingUnixHTTPServer(str(socket_path), service.IntakeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop() -> None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

        self.addCleanup(stop)
        deadline = time.time() + 1.0
        while not socket_path.exists():
            if time.time() >= deadline:
                break
            time.sleep(0.01)
        return str(socket_path)

    # ------------------------------------------------------------------
    # command / dialog parsing
    # ------------------------------------------------------------------

    def test_fix_command_behavior(self) -> None:
        behavior = service.command_behavior("fix")

        self.assertEqual(behavior["workflow_scope"], "conversation")

    def test_unknown_command_has_no_behavior(self) -> None:
        self.assertEqual(service.command_behavior("ship"), {})

    def test_normalize_command_invocation_reads_form_fields(self) -> None:
        invocation = service.normalize_command_invocation(self.command_form(text="  fix crash  "))

        self.assertEqual(invocation["surface"], "command")
        self.assertEqual(invocation["team_id"], TEAM_ID)
        self.assertEqual(invocation["channel_id"], CHANNEL_ID)
        self.assertEqual(invocation["user_id"], USER_ID)
        self.assertEqual(invocation["command"], "/gc")
        self.assertEqual(invocation["text"], "fix crash")
        self.assertEqual(invocation["trigger_id"], "trigger-1")

    def test_parse_command_text_reads_prompt(self) -> None:
        config = self.import_app()
        invocation = self.command_invocation(text="fix crash on startup when x is unset")

        parsed = service.parse_command_text(config, invocation, common.command_name(config))

        self.assertEqual(parsed["command"], "fix")
        self.assertIn("crash on startup", parsed["prompt"])
        self.assertEqual(parsed["rig"], "")

    def test_parse_command_text_ignores_foreign_trigger(self) -> None:
        config = self.import_app()
        invocation = self.command_invocation(command="/other", text="fix crash on startup")

        self.assertEqual(service.parse_command_text(config, invocation, common.command_name(config)), {})

    def test_parse_command_text_extracts_bare_rig_token(self) -> None:
        config = self.import_app()
        config = common.set_rig_mapping(config, TEAM_ID, "mission-control", "mission-control/polecat", common.FIX_FORMULA_DEFAULT)
        invocation = self.command_invocation(text="fix mission-control crash on startup")

        parsed = service.parse_command_text(config, invocation, common.command_name(config))

        self.assertEqual(parsed["command"], "fix")
        self.assertEqual(parsed["rig"], "mission-control")
        self.assertEqual(parsed["prompt"], "crash on startup")

    def test_parse_command_text_keeps_unmapped_leading_token_in_prompt(self) -> None:
        config = self.import_app()
        invocation = self.command_invocation(text="fix mission-control crash on startup")

        parsed = service.parse_command_text(config, invocation, common.command_name(config))

        self.assertEqual(parsed["rig"], "")
        self.assertEqual(parsed["prompt"], "mission-control crash on startup")

    def test_parse_command_text_extracts_rig_flag_forms(self) -> None:
        config = self.import_app()
        invocation = self.command_invocation(text="fix --rig=mission-control crash on startup")
        parsed = service.parse_command_text(config, invocation, common.command_name(config))
        self.assertEqual(parsed["rig"], "mission-control")
        self.assertEqual(parsed["prompt"], "crash on startup")

        invocation = self.command_invocation(text="fix --rig mission-control crash on startup")
        parsed = service.parse_command_text(config, invocation, common.command_name(config))
        self.assertEqual(parsed["rig"], "mission-control")
        self.assertEqual(parsed["prompt"], "crash on startup")

    def test_parse_command_text_preserves_newlines_in_prompt(self) -> None:
        # `prompt_to_summary_context` derives the summary from the prompt's first
        # line, so the parser must not flatten a multi-line slash-command text.
        config = self.import_app()
        invocation = self.command_invocation(text="fix crash on startup\nwhen x is unset\n\nrepro: unset X")

        parsed = service.parse_command_text(config, invocation, common.command_name(config))

        self.assertEqual(parsed["command"], "fix")
        self.assertEqual(parsed["prompt"], "crash on startup\nwhen x is unset\n\nrepro: unset X")
        summary, context_markdown = service.prompt_to_summary_context(parsed["prompt"])
        self.assertEqual(summary, "crash on startup")
        self.assertIn("repro: unset X", context_markdown)

    def test_parse_command_text_preserves_newlines_after_rig_token(self) -> None:
        config = self.import_app()
        config = common.set_rig_mapping(config, TEAM_ID, "mission-control", "mission-control/polecat", common.FIX_FORMULA_DEFAULT)
        invocation = self.command_invocation(text="fix mission-control crash on startup\nwhen x is unset")

        parsed = service.parse_command_text(config, invocation, common.command_name(config))

        self.assertEqual(parsed["rig"], "mission-control")
        self.assertEqual(parsed["prompt"], "crash on startup\nwhen x is unset")

    def test_parse_command_text_keeps_dangling_rig_flag_in_prompt(self) -> None:
        config = self.import_app()
        invocation = self.command_invocation(text="fix --rig")

        parsed = service.parse_command_text(config, invocation, common.command_name(config))

        self.assertEqual(parsed["rig"], "")
        self.assertEqual(parsed["prompt"], "--rig")

    def test_parse_command_text_returns_empty_prompt_for_bare_subcommand(self) -> None:
        config = self.import_app()

        parsed = service.parse_command_text(config, self.command_invocation(text="fix"), common.command_name(config))

        self.assertEqual(parsed["command"], "fix")
        self.assertEqual(parsed["prompt"], "")
        self.assertEqual(parsed["rig"], "")

    def test_extract_dialog_fields_reads_summary_and_context(self) -> None:
        payload = {
            "type": "dialog_submission",
            "callback_id": service.FIX_DIALOG_CALLBACK_ID,
            "state": "state-token",
            "user_id": USER_ID,
            "channel_id": CHANNEL_ID,
            "team_id": TEAM_ID,
            "submission": {"summary": "Crash on boot", "context": "unset env X"},
            "cancelled": False,
        }

        fields = service.extract_dialog_fields(payload)

        self.assertEqual(fields["summary"], "Crash on boot")
        self.assertEqual(fields["context"], "unset env X")

    def test_extract_dialog_fields_tolerates_missing_submission(self) -> None:
        self.assertEqual(service.extract_dialog_fields({"type": "dialog_submission"}), {})
        self.assertEqual(service.extract_dialog_fields({"submission": "nope"}), {})
        self.assertEqual(service.extract_dialog_fields({"submission": {"context": None}}), {"context": ""})

    def test_normalize_dialog_invocation_backfills_from_pending_record(self) -> None:
        payload = {
            "type": "dialog_submission",
            "state": "state-token",
            "user_id": USER_ID,
            "channel_id": CHANNEL_ID,
            "team_id": TEAM_ID,
            "submission": {"summary": "Crash"},
        }
        pending = {
            "nonce": "nonce-1",
            "team_id": TEAM_ID,
            "team_domain": "acme",
            "channel_id": CHANNEL_ID,
            "channel_name": "town-square",
            "root_id": ROOT_ID,
            "user_id": USER_ID,
            "user_name": "alice",
            "command_trigger": "/gc",
        }

        invocation = service.normalize_dialog_invocation(payload, pending)

        self.assertEqual(invocation["surface"], "dialog")
        self.assertEqual(invocation["team_id"], TEAM_ID)
        self.assertEqual(invocation["channel_id"], CHANNEL_ID)
        self.assertEqual(invocation["root_id"], ROOT_ID)
        self.assertEqual(invocation["team_domain"], "acme")
        self.assertEqual(invocation["channel_name"], "town-square")
        self.assertEqual(invocation["user_name"], "alice")
        self.assertEqual(invocation["command"], "/gc")

    def test_build_message_response_uses_mattermost_response_type(self) -> None:
        self.assertEqual(
            service.build_message_response("hello", ephemeral=True),
            {"response_type": "ephemeral", "text": "hello"},
        )
        self.assertEqual(
            service.build_message_response("hello", ephemeral=False),
            {"response_type": "in_channel", "text": "hello"},
        )

    def test_build_dialog_error_response_targets_field_when_given(self) -> None:
        self.assertEqual(
            service.build_dialog_error_response("summary_required", "summary"),
            {"errors": {"summary": service.human_reason("summary_required")}},
        )
        self.assertEqual(
            service.build_dialog_error_response("dialog_expired"),
            {"error": service.human_reason("dialog_expired")},
        )
        self.assertEqual(service.build_dialog_ok_response(), {})

    def test_build_fix_dialog_declares_summary_and_context_elements(self) -> None:
        dialog = service.build_fix_dialog("state-token")

        self.assertEqual(dialog["callback_id"], service.FIX_DIALOG_CALLBACK_ID)
        self.assertEqual(dialog["state"], "state-token")
        names = [element["name"] for element in dialog["elements"]]
        self.assertEqual(names, ["summary", "context"])
        self.assertLessEqual(max(len(element["display_name"]) for element in dialog["elements"]), 24)

    # ------------------------------------------------------------------
    # bead payload construction
    # ------------------------------------------------------------------

    def test_build_fix_bead_notes_includes_mattermost_context(self) -> None:
        request = {
            "team_id": TEAM_ID,
            "channel_id": CHANNEL_ID,
            "root_id": ROOT_ID,
            "conversation_id": f"{CHANNEL_ID}/{ROOT_ID}",
            "permalink": f"{SITE_URL}/acme/channels/town-square",
            "request_id": "mm-1-fix",
            "invoking_user_display_name": "alice",
            "invoking_user_id": USER_ID,
            "summary": "Crash on startup",
            "context_markdown": "repro: unset X",
        }

        notes = service.build_fix_bead_notes(request)

        self.assertIn("## Mattermost Source", notes)
        self.assertIn("Crash on startup", notes)
        self.assertIn("repro: unset X", notes)
        self.assertIn(f"{SITE_URL}/acme/channels/town-square", notes)
        self.assertIn(ROOT_ID, notes)

    def test_build_fix_bead_title_is_bounded(self) -> None:
        title = service.build_fix_bead_title({"summary": "x" * 400})

        self.assertTrue(title.startswith("Fix Mattermost request: "))
        self.assertLessEqual(len(title), 180)

    def test_build_fix_vars_encodes_prompt_sensitive_fields(self) -> None:
        request = {
            "request_id": "mm-1-fix",
            "team_id": TEAM_ID,
            "channel_id": CHANNEL_ID,
            "root_id": ROOT_ID,
            "conversation_id": f"{CHANNEL_ID}/{ROOT_ID}",
            "permalink": f"{SITE_URL}/acme/channels/town-square",
            "invoking_user_display_name": "alice `review this`",
            "summary": "Crash on startup",
            "context_markdown": "unset env X",
        }

        variables = service.build_fix_vars(request, "bd-1")

        self.assertNotIn("mattermost_requester", variables)
        self.assertNotIn("mattermost_permalink", variables)
        self.assertNotIn("mattermost_summary", variables)
        self.assertNotIn("mattermost_context", variables)
        self.assertEqual(variables["issue"], "bd-1")
        self.assertEqual(variables["mattermost_team_id"], TEAM_ID)
        self.assertEqual(variables["mattermost_root_id"], ROOT_ID)
        self.assertEqual(
            base64.b64decode(variables["mattermost_requester_b64"]).decode("utf-8"),
            "alice `review this`",
        )
        self.assertEqual(
            base64.b64decode(variables["mattermost_permalink_b64"]).decode("utf-8"),
            f"{SITE_URL}/acme/channels/town-square",
        )
        self.assertEqual(
            base64.b64decode(variables["mattermost_summary_b64"]).decode("utf-8"),
            "Crash on startup",
        )
        self.assertEqual(
            base64.b64decode(variables["mattermost_context_b64"]).decode("utf-8"),
            "unset env X",
        )

    def test_build_request_uses_mattermost_field_names(self) -> None:
        self.import_app()
        invocation = self.command_invocation(root_id=ROOT_ID)
        mapping = {"target": "product/polecat", "commands": {"fix": {"formula": common.FIX_FORMULA_DEFAULT}}}

        request = service.build_request(
            invocation,
            "Crash on startup",
            "unset env X",
            self.channel_context(root_id=ROOT_ID),
            "interaction-1",
            mapping,
        )

        self.assertEqual(request["team_id"], TEAM_ID)
        self.assertEqual(request["channel_id"], CHANNEL_ID)
        self.assertEqual(request["root_id"], ROOT_ID)
        self.assertEqual(request["conversation_id"], f"{CHANNEL_ID}/{ROOT_ID}")
        self.assertEqual(
            request["workflow_key"],
            f"mm:team:{TEAM_ID}:conversation:{CHANNEL_ID}/{ROOT_ID}:fix",
        )
        self.assertEqual(request["request_id"], common.build_request_id("interaction-1", "fix"))
        self.assertEqual(request["status"], "received")
        self.assertEqual(request["command"], "fix")
        self.assertEqual(request["dispatch_target"], "product/polecat")
        self.assertEqual(request["dispatch_formula"], common.FIX_FORMULA_DEFAULT)
        self.assertEqual(request["invoking_user_id"], USER_ID)
        self.assertEqual(request["invoking_user_display_name"], "alice")
        self.assertEqual(request["permalink"], f"{SITE_URL}/acme/channels/town-square")
        # Discord's guild/thread/jump_url names must not leak into the record.
        for legacy in ("guild_id", "thread_id", "jump_url"):
            self.assertNotIn(legacy, request)

    def test_build_request_without_thread_root_uses_bare_channel_conversation(self) -> None:
        self.import_app()
        invocation = self.command_invocation()

        request = service.build_request(
            invocation,
            "Crash",
            "",
            self.channel_context(),
            "interaction-2",
            {"target": "product/polecat"},
        )

        self.assertEqual(request["root_id"], "")
        self.assertEqual(request["conversation_id"], CHANNEL_ID)
        self.assertEqual(request["workflow_key"], f"mm:team:{TEAM_ID}:conversation:{CHANNEL_ID}:fix")

    # ------------------------------------------------------------------
    # reservation / dedupe
    # ------------------------------------------------------------------

    def test_reserve_request_deduplicates_conversation_workflow(self) -> None:
        behavior = service.command_behavior("fix")
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        first = {
            "request_id": "mm-1-fix",
            "workflow_key": workflow_key,
            "command": "fix",
            "team_id": TEAM_ID,
            "conversation_id": CHANNEL_ID,
        }
        second = {
            "request_id": "mm-2-fix",
            "workflow_key": workflow_key,
            "command": "fix",
            "team_id": TEAM_ID,
            "conversation_id": CHANNEL_ID,
        }

        self.assertIsNone(service.reserve_request(first, behavior, "interaction-1"))
        duplicate = service.reserve_request(second, behavior, "interaction-2")

        self.assertIsNotNone(duplicate)
        assert duplicate is not None
        self.assertEqual(duplicate["request_id"], "mm-1-fix")

    def test_reserve_request_rejects_distinct_rig_workflows_in_same_conversation(self) -> None:
        behavior = service.command_behavior("fix")
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        first = {
            "request_id": "mm-rig-1",
            "workflow_key": workflow_key,
            "command": "fix",
            "team_id": TEAM_ID,
            "conversation_id": CHANNEL_ID,
            "rig_name": "mission-control",
        }
        second = {
            "request_id": "mm-rig-2",
            "workflow_key": workflow_key,
            "command": "fix",
            "team_id": TEAM_ID,
            "conversation_id": CHANNEL_ID,
            "rig_name": "product",
        }

        self.assertIsNone(service.reserve_request(first, behavior, "interaction-rig-1"))
        duplicate = service.reserve_request(second, behavior, "interaction-rig-2")
        self.assertIsNotNone(duplicate)
        assert duplicate is not None
        self.assertEqual(duplicate["request_id"], "mm-rig-1")

    def test_reserve_request_replays_existing_interaction_receipt(self) -> None:
        behavior = service.command_behavior("fix")
        request = {
            "request_id": "mm-replay-1",
            "workflow_key": common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix"),
            "command": "fix",
            "team_id": TEAM_ID,
            "conversation_id": CHANNEL_ID,
        }

        self.assertIsNone(service.reserve_request(dict(request), behavior, "interaction-replay"))
        replayed = service.reserve_request(dict(request), behavior, "interaction-replay")

        self.assertIsNotNone(replayed)
        assert replayed is not None
        self.assertEqual(replayed["request_id"], "mm-replay-1")

    # ------------------------------------------------------------------
    # accept_fix_request
    # ------------------------------------------------------------------

    def test_accept_fix_request_saves_and_enqueues_new_request(self) -> None:
        self.import_app()
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        common.save_bot_token("bot-token")
        invocation = self.command_invocation()

        with mock.patch.object(service, "enqueue_request") as enqueue_request:
            outcome, receipt = service.accept_fix_request(invocation, "Crash on startup", "unset env X", "interaction-1")

        self.assertEqual(outcome["kind"], "accepted")
        self.assertIn("Accepted /gc fix", outcome["content"])
        self.assertEqual(receipt["response_kind"], "accepted")
        self.assertEqual(
            service.command_response_for_outcome(outcome),
            {"response_type": "in_channel", "text": outcome["content"]},
        )
        request = common.list_recent_requests(limit=1)[0]
        self.assertEqual(request["summary"], "Crash on startup")
        self.assertEqual(request["context_markdown"], "unset env X")
        self.assertEqual(request["dispatch_target"], "product/polecat")
        self.assertEqual(request["conversation_id"], CHANNEL_ID)
        enqueue_request.assert_called_once()

    def test_accept_fix_request_rejects_when_bot_token_missing(self) -> None:
        self.import_app()
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        invocation = self.command_invocation()

        outcome, receipt = service.accept_fix_request(invocation, "Crash on startup", "unset env X", "interaction-1")

        self.assertEqual(outcome["kind"], "message")
        self.assertEqual(outcome["reason"], "mattermost_app_not_configured")
        self.assertIn("not fully configured", outcome["content"])
        self.assertEqual(receipt["response_kind"], "message")
        self.assertEqual(
            service.command_response_for_outcome(outcome),
            {"response_type": "ephemeral", "text": outcome["content"]},
        )
        self.assertEqual(common.list_recent_requests(limit=20), [])

    def test_accept_fix_request_requires_team_scope(self) -> None:
        self.import_app()
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(team_id="")

        outcome, receipt = service.accept_fix_request(invocation, "Crash", "", "interaction-dm")

        self.assertEqual(outcome["reason"], "team_required")
        self.assertEqual(receipt["response_kind"], "message")

    def test_accept_fix_request_rejects_unmapped_channel(self) -> None:
        self.import_app()
        common.save_bot_token("bot-token")
        invocation = self.command_invocation()

        with mock.patch.object(common, "load_channel_context", return_value=self.channel_context()):
            outcome, _receipt = service.accept_fix_request(invocation, "Crash", "", "interaction-unmapped")

        self.assertEqual(outcome["reason"], "channel_mapping_missing")

    def test_accept_fix_request_requires_summary(self) -> None:
        self.import_app()
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        common.save_bot_token("bot-token")
        invocation = self.command_invocation()

        outcome, _receipt = service.accept_fix_request(invocation, "", "", "interaction-empty")

        self.assertEqual(outcome["reason"], "summary_required")
        self.assertEqual(outcome["field"], "summary")
        self.assertEqual(
            service.dialog_response_for_outcome(outcome, invocation),
            {"errors": {"summary": service.human_reason("summary_required")}},
        )

    def test_accept_fix_request_derives_summary_from_context_only_submission(self) -> None:
        self.import_app()
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        common.save_bot_token("bot-token")
        invocation = self.command_invocation()

        with mock.patch.object(service, "enqueue_request"):
            outcome, _receipt = service.accept_fix_request(
                invocation, "", "crash on startup\nwhen x is unset", "interaction-derived"
            )

        self.assertEqual(outcome["kind"], "accepted")
        request = common.list_recent_requests(limit=1)[0]
        self.assertEqual(request["summary"], "crash on startup")
        self.assertIn("when x is unset", request["context_markdown"])

    def test_accept_fix_request_rejects_disallowed_channel_by_policy(self) -> None:
        self.import_app(channel_allowlist=[OTHER_CHANNEL_ID])
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        common.save_bot_token("bot-token")
        invocation = self.command_invocation()

        outcome, _receipt = service.accept_fix_request(invocation, "Crash", "", "interaction-policy")

        self.assertEqual(outcome["reason"], "channel_not_allowed")

    def test_accept_fix_request_routes_via_rig_mapping(self) -> None:
        self.import_app()
        common.set_rig_mapping(
            common.load_config(), TEAM_ID, "mission-control", "mission-control/polecat", common.FIX_FORMULA_DEFAULT
        )
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(channel_id=OTHER_CHANNEL_ID)

        with mock.patch.object(service, "enqueue_request") as enqueue_request:
            outcome, _receipt = service.accept_fix_request(
                invocation, "Crash on startup", "unset env X", "interaction-2", rig_name="mission-control"
            )

        self.assertEqual(outcome["kind"], "accepted")
        self.assertIn("Accepted /gc fix", outcome["content"])
        request = common.list_recent_requests(limit=1)[0]
        self.assertEqual(request["dispatch_target"], "mission-control/polecat")
        self.assertEqual(request["rig_name"], "mission-control")
        self.assertEqual(request["workflow_key"], f"mm:team:{TEAM_ID}:conversation:{OTHER_CHANNEL_ID}:fix")
        enqueue_request.assert_called_once()

    def test_accept_fix_request_rig_routing_skips_channel_lookup_outside_threads(self) -> None:
        self.import_app()
        common.set_rig_mapping(
            common.load_config(), TEAM_ID, "mission-control", "mission-control/polecat", common.FIX_FORMULA_DEFAULT
        )
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(channel_id=OTHER_CHANNEL_ID)

        with mock.patch.object(service, "enqueue_request"), mock.patch.object(
            common, "load_channel_context"
        ) as load_channel_context:
            outcome, _receipt = service.accept_fix_request(
                invocation, "Crash", "", "interaction-no-lookup", rig_name="mission-control"
            )

        self.assertEqual(outcome["kind"], "accepted")
        load_channel_context.assert_not_called()

    def test_accept_fix_request_routes_threaded_rig_mapping_with_channel_context(self) -> None:
        self.import_app(channel_allowlist=[CHANNEL_ID])
        common.set_rig_mapping(
            common.load_config(), TEAM_ID, "mission-control", "mission-control/polecat", common.FIX_FORMULA_DEFAULT
        )
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(root_id=ROOT_ID)

        with mock.patch.object(service, "enqueue_request") as enqueue_request, mock.patch.object(
            common,
            "load_channel_context",
            return_value=self.channel_context(root_id=ROOT_ID),
        ):
            outcome, _receipt = service.accept_fix_request(
                invocation, "Crash on startup", "unset env X", "interaction-thread", rig_name="mission-control"
            )

        self.assertEqual(outcome["kind"], "accepted")
        request = common.list_recent_requests(limit=1)[0]
        self.assertEqual(request["channel_id"], CHANNEL_ID)
        self.assertEqual(request["root_id"], ROOT_ID)
        self.assertEqual(request["conversation_id"], f"{CHANNEL_ID}/{ROOT_ID}")
        self.assertEqual(request["dispatch_target"], "mission-control/polecat")
        enqueue_request.assert_called_once()

    def test_accept_fix_request_rejects_unknown_rig(self) -> None:
        self.import_app()
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(channel_id=OTHER_CHANNEL_ID)

        outcome, _receipt = service.accept_fix_request(
            invocation, "Crash", "", "interaction-3", rig_name="nonexistent"
        )

        self.assertEqual(outcome["reason"], "rig_mapping_missing")
        self.assertIn("no rig mapping", outcome["content"])

    def test_accept_fix_request_surfaces_channel_lookup_failure(self) -> None:
        self.import_app()
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(channel_id=OTHER_CHANNEL_ID)

        with mock.patch.object(
            common,
            "load_channel_context",
            return_value={"mapping": {}, "lookup_error": "GET failed"},
        ):
            outcome, receipt = service.accept_fix_request(invocation, "Crash", "", "interaction-lookup-1")

        self.assertEqual(outcome["reason"], "mattermost_lookup_failed")
        self.assertIn("lookup failed", outcome["content"].lower())
        self.assertEqual(receipt["response_kind"], "message")

    def test_accept_fix_request_rejects_rig_mapping_when_thread_lookup_fails(self) -> None:
        self.import_app()
        common.set_rig_mapping(
            common.load_config(), TEAM_ID, "mission-control", "mission-control/polecat", common.FIX_FORMULA_DEFAULT
        )
        common.save_bot_token("bot-token")
        invocation = self.command_invocation(root_id=ROOT_ID)

        with mock.patch.object(
            common,
            "load_channel_context",
            return_value={"mapping": {}, "lookup_error": "GET failed"},
        ):
            outcome, receipt = service.accept_fix_request(
                invocation, "Crash", "", "interaction-lookup-2", rig_name="mission-control"
            )

        self.assertEqual(outcome["reason"], "mattermost_lookup_failed")
        self.assertIn("lookup failed", outcome["content"].lower())
        self.assertEqual(receipt["response_kind"], "message")

    def test_accept_fix_request_returns_duplicate_outcome(self) -> None:
        self.import_app()
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        common.save_bot_token("bot-token")
        invocation = self.command_invocation()

        with mock.patch.object(service, "enqueue_request"):
            service.accept_fix_request(invocation, "Crash on startup", "", "interaction-dup-1")
            outcome, receipt = service.accept_fix_request(invocation, "Crash again", "", "interaction-dup-2")

        self.assertEqual(outcome["kind"], "duplicate")
        self.assertIn("already active", outcome["content"])
        self.assertEqual(receipt["response_kind"], "duplicate")
        self.assertEqual(
            service.command_response_for_outcome(outcome),
            {"response_type": "ephemeral", "text": outcome["content"]},
        )

    def test_dialog_response_for_outcome_posts_acceptance_into_conversation(self) -> None:
        invocation = self.command_invocation(root_id=ROOT_ID)
        outcome = {"kind": "accepted", "content": "Accepted /gc fix for this conversation.", "request": {}}

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-1"}) as post_channel_message:
            response = service.dialog_response_for_outcome(outcome, invocation)

        self.assertEqual(response, {})
        post_channel_message.assert_called_once()
        self.assertEqual(post_channel_message.call_args.args[0], CHANNEL_ID)
        self.assertEqual(post_channel_message.call_args.kwargs["root_id"], ROOT_ID)

    # ------------------------------------------------------------------
    # admin surface
    # ------------------------------------------------------------------

    def test_render_admin_home_includes_launcher_sections(self) -> None:
        self.import_app()
        common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        common.save_room_launch(
            {
                "launch_id": f"room-launch:{CHANNEL_ID}",
                "launcher_id": common.room_launch_surface_id(CHANNEL_ID),
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )

        html_body = service.render_admin_home()

        self.assertIn("Chat Launchers", html_body)
        self.assertIn("Recent Room Launches", html_body)
        self.assertIn("Command Sync Payload", html_body)
        self.assertIn("corp/sky", html_body)

    # ------------------------------------------------------------------
    # bead creation / dispatch
    # ------------------------------------------------------------------

    def test_create_fix_bead_parses_json_after_cli_noise(self) -> None:
        self.write_rig_route("product")
        request = {
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "team_id": TEAM_ID,
            "channel_id": CHANNEL_ID,
            "root_id": "",
            "conversation_id": CHANNEL_ID,
            "permalink": f"{SITE_URL}/acme/channels/town-square",
            "request_id": "mm-1-fix",
            "invoking_user_display_name": "alice",
            "invoking_user_id": USER_ID,
            "context_markdown": "unset env X",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            side_effect=[
                mock.Mock(returncode=0, stdout='warning: something\n{"id":"bd-1"}\n', stderr=""),
                mock.Mock(returncode=0, stdout="", stderr=""),
            ],
        ):
            outcome = service.create_fix_bead(request, "product/polecat")

        self.assertEqual(outcome["bead_id"], "bd-1")

    def test_create_fix_bead_stamps_mattermost_metadata(self) -> None:
        self.write_rig_route("product")
        request = {
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "team_id": TEAM_ID,
            "channel_id": CHANNEL_ID,
            "root_id": ROOT_ID,
            "conversation_id": f"{CHANNEL_ID}/{ROOT_ID}",
            "request_id": "mm-meta-fix",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            side_effect=[
                mock.Mock(returncode=0, stdout='{"id":"bd-9"}\n', stderr=""),
                mock.Mock(returncode=0, stdout="", stderr=""),
            ],
        ) as run_subprocess:
            outcome = service.create_fix_bead(request, "product/polecat")

        self.assertEqual(outcome["bead_id"], "bd-9")
        update_command = run_subprocess.call_args_list[1].args[0]
        self.assertIn("mattermost_request_id=mm-meta-fix", update_command)
        self.assertIn(f"mattermost_team_id={TEAM_ID}", update_command)
        self.assertIn(f"mattermost_channel_id={CHANNEL_ID}", update_command)
        self.assertIn(f"mattermost_root_id={ROOT_ID}", update_command)
        self.assertIn(f"mattermost_conversation_id={CHANNEL_ID}/{ROOT_ID}", update_command)

    def test_create_fix_bead_returns_dispatch_timeout_when_bd_create_hangs(self) -> None:
        self.write_rig_route("product")
        request = {
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            side_effect=service.DispatchSubprocessTimeout(
                ["gc", "--city", self.tempdir.name, "--rig", "product", "bd", "create"],
                service.DISPATCH_SUBPROCESS_TIMEOUT_SECONDS,
            ),
        ):
            outcome = service.create_fix_bead(request, "product/polecat")

        self.assertEqual(outcome["status"], "dispatch_failed")
        self.assertEqual(outcome["reason"], "dispatch_timeout")
        self.assertEqual(
            outcome["dispatch_command"],
            ["gc", "--city", self.tempdir.name, "--rig", "product", "bd", "create"],
        )

    def test_create_fix_bead_fails_closed_when_rig_workdir_is_missing(self) -> None:
        request = {
            "request_id": "mm-route-missing",
            "summary": "Crash on startup",
        }

        with mock.patch.object(service, "run_subprocess") as run_subprocess:
            outcome = service.create_fix_bead(request, "mission-control/polecat")

        self.assertEqual(outcome["status"], "dispatch_failed")
        self.assertEqual(outcome["reason"], "rig_workdir_missing")
        run_subprocess.assert_not_called()

    def test_create_fix_bead_rejects_non_rig_scoped_target(self) -> None:
        with mock.patch.object(service, "run_subprocess") as run_subprocess:
            outcome = service.create_fix_bead({"summary": "Crash"}, "polecat")

        self.assertEqual(outcome["reason"], "invalid_dispatch_target")
        run_subprocess.assert_not_called()

    def test_run_fix_dispatch_returns_bead_init_failure_without_slinging(self) -> None:
        self.write_rig_route("product")
        request = {
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }

        with mock.patch.object(
            service,
            "create_fix_bead",
            return_value={"status": "dispatch_failed", "reason": "bead_update_failed", "bead_id": "bd-1"},
        ), mock.patch.object(
            service,
            "run_subprocess",
            side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=0), mock.Mock(returncode=0)],
        ) as run_subprocess:
            outcome = service.run_fix_dispatch(request)

        self.assertEqual(outcome["status"], "dispatch_failed")
        self.assertEqual(outcome["bead_id"], "bd-1")
        self.assertTrue(outcome["bead_closed"])
        commands = [call.args[0] for call in run_subprocess.call_args_list]
        prefix = ["gc", "--city", self.tempdir.name, "--rig", "product", "bd"]
        self.assertEqual(
            commands[0],
            prefix + ["update", "bd-1", "--set-metadata", "close_reason=mattermost:bead_update_failed"],
        )
        self.assertEqual(commands[1], prefix + ["ready", "bd-1"])
        self.assertEqual(commands[2], prefix + ["close", "bd-1"])

    def test_run_fix_dispatch_ignores_unconfigured_command(self) -> None:
        outcome = service.run_fix_dispatch({"summary": "Crash"})

        self.assertEqual(outcome["status"], "ignored")
        self.assertEqual(outcome["reason"], "command_not_configured")

    def test_run_fix_dispatch_slings_with_encoded_vars(self) -> None:
        request = {
            "request_id": "mm-sling-1",
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
            "team_id": TEAM_ID,
            "channel_id": CHANNEL_ID,
            "root_id": ROOT_ID,
            "conversation_id": f"{CHANNEL_ID}/{ROOT_ID}",
        }

        with mock.patch.object(service, "create_fix_bead", return_value={"bead_id": "bd-5"}), mock.patch.object(
            service,
            "run_subprocess",
            return_value=mock.Mock(returncode=0, stdout="", stderr=""),
        ) as run_subprocess:
            outcome = service.run_fix_dispatch(request)

        self.assertEqual(outcome["status"], "dispatched")
        command = run_subprocess.call_args.args[0]
        self.assertEqual(command[:5], ["gc", "sling", "product/polecat", "bd-5", "--on"])
        self.assertEqual(command[5], common.FIX_FORMULA_DEFAULT)
        self.assertIn("issue=bd-5", command)
        self.assertIn(f"mattermost_root_id={ROOT_ID}", command)

    def test_run_fix_dispatch_returns_dispatch_timeout_when_gc_sling_hangs(self) -> None:
        request = {
            "request_id": "mm-timeout-1",
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }

        with mock.patch.object(service, "create_fix_bead", return_value={"bead_id": "bd-1"}), mock.patch.object(
            service,
            "run_subprocess",
            side_effect=service.DispatchSubprocessTimeout(["gc", "sling", "product/polecat", "bd-1"], 300),
        ), mock.patch.object(service, "dispatch_recovery_state", return_value="inactive"), mock.patch.object(
            service,
            "close_failed_bead",
            return_value=True,
        ) as close_failed_bead:
            outcome = service.run_fix_dispatch(request)

        self.assertEqual(outcome["status"], "dispatch_failed")
        self.assertEqual(outcome["reason"], "dispatch_timeout")
        self.assertTrue(outcome["bead_closed"])
        close_failed_bead.assert_called_once_with("bd-1", "dispatch_timeout", "product")

    def test_run_fix_dispatch_converges_timeout_to_dispatched_when_bead_is_active(self) -> None:
        request = {
            "request_id": "mm-timeout-2",
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }

        with mock.patch.object(service, "create_fix_bead", return_value={"bead_id": "bd-2"}), mock.patch.object(
            service,
            "run_subprocess",
            side_effect=service.DispatchSubprocessTimeout(["gc", "sling", "product/polecat", "bd-2"], 300),
        ), mock.patch.object(service, "dispatch_recovery_state", return_value="active"), mock.patch.object(
            service,
            "close_failed_bead",
        ) as close_failed_bead:
            outcome = service.run_fix_dispatch(request)

        self.assertEqual(outcome["status"], "dispatched")
        self.assertEqual(outcome["dispatch_recovery_reason"], "dispatch_timeout_but_bead_already_routed")
        close_failed_bead.assert_not_called()

    def test_run_fix_dispatch_leaves_timeout_in_dispatching_when_bead_state_is_unknown(self) -> None:
        request = {
            "request_id": "mm-timeout-3",
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }

        with mock.patch.object(service, "create_fix_bead", return_value={"bead_id": "bd-3"}), mock.patch.object(
            service,
            "run_subprocess",
            side_effect=service.DispatchSubprocessTimeout(["gc", "sling", "product/polecat", "bd-3"], 300),
        ), mock.patch.object(service, "dispatch_recovery_state", return_value="unknown"), mock.patch.object(
            service,
            "close_failed_bead",
        ) as close_failed_bead:
            outcome = service.run_fix_dispatch(request)

        self.assertEqual(outcome["status"], "dispatching")
        self.assertEqual(outcome["dispatch_recovery_reason"], "dispatch_timeout_state_unavailable")
        self.assertIn("dispatch_timeout_at", outcome)
        close_failed_bead.assert_not_called()

    # ------------------------------------------------------------------
    # process_request
    # ------------------------------------------------------------------

    def test_process_request_releases_workflow_link_after_dispatch_failure(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-3-fix",
            "workflow_key": workflow_key,
            "command": "fix",
            "summary": "Crash on startup",
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(
            service,
            "run_fix_dispatch",
            return_value={"status": "dispatch_failed", "reason": "dispatch_failed", "bead_id": "bd-1"},
        ):
            service.process_request(request["request_id"])

        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["status"], "dispatch_failed")
        self.assertIsNone(common.load_workflow_link(workflow_key))

    def test_process_request_posts_failure_followup_for_async_dispatch_failure(self) -> None:
        common.save_bot_token("bot-token")
        request = {
            "request_id": "mm-4-fix",
            "workflow_key": common.build_workflow_key(TEAM_ID, f"{CHANNEL_ID}/{ROOT_ID}", "fix"),
            "command": "fix",
            "summary": "Crash on startup",
            "channel_id": CHANNEL_ID,
            "root_id": ROOT_ID,
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }
        common.save_request(request)

        with mock.patch.object(
            service,
            "run_fix_dispatch",
            return_value={"status": "dispatch_failed", "reason": "dispatch_failed", "bead_id": "bd-1"},
        ), mock.patch.object(
            common,
            "post_channel_message",
            return_value={"id": "post-1"},
        ) as post_channel_message:
            service.process_request(request["request_id"])

        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["failure_message_id"], "post-1")
        post_channel_message.assert_called_once()
        self.assertEqual(post_channel_message.call_args.args[0], CHANNEL_ID)
        self.assertEqual(post_channel_message.call_args.kwargs["root_id"], ROOT_ID)
        self.assertIn("could not be started", post_channel_message.call_args.args[1])

    def test_process_request_releases_workflow_link_when_request_file_is_missing(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        common.save_workflow_link(workflow_key, "mm-missing")

        with mock.patch.object(common, "load_request", return_value=None):
            service.process_request("mm-missing")

        self.assertIsNone(common.load_workflow_link(workflow_key))

    def test_process_request_sanitizes_internal_error_followup(self) -> None:
        common.save_bot_token("bot-token")
        request = {
            "request_id": "mm-5-fix",
            "workflow_key": common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix"),
            "command": "fix",
            "summary": "Crash on startup",
            "channel_id": CHANNEL_ID,
            "dispatch_target": "product/polecat",
            "dispatch_formula": common.FIX_FORMULA_DEFAULT,
        }
        common.save_request(request)

        with mock.patch.object(service, "run_fix_dispatch", side_effect=RuntimeError("leak this path")), mock.patch.object(
            common,
            "post_channel_message",
            return_value={"id": "post-2"},
        ) as post_channel_message:
            service.process_request(request["request_id"])

        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["reason"], "internal_error")
        self.assertEqual(saved["error_message"], "leak this path")
        self.assertIn("internal error occurred", post_channel_message.call_args.args[1])
        self.assertNotIn("leak this path", post_channel_message.call_args.args[1])

    def test_process_request_ignores_unsupported_command(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "ship")
        request = {
            "request_id": "mm-6-ship",
            "workflow_key": workflow_key,
            "command": "ship",
            "status": "received",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        service.process_request(request["request_id"])

        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["status"], "ignored")
        self.assertEqual(saved["reason"], "command_not_supported")
        self.assertIsNone(common.load_workflow_link(workflow_key))

    # ------------------------------------------------------------------
    # rig routing helpers
    # ------------------------------------------------------------------

    def test_rig_from_target_requires_pool_scope(self) -> None:
        self.assertEqual(service.rig_from_target("product/polecat"), "product")
        self.assertEqual(service.rig_from_target("polecat"), "")

    def test_gc_bd_command_includes_city_and_rig_scope(self) -> None:
        self.assertEqual(
            service.gc_bd_command(self.tempdir.name, "show", "bd-1", "--json", rig="product"),
            ["gc", "--city", self.tempdir.name, "--rig", "product", "bd", "show", "bd-1", "--json"],
        )
        self.assertEqual(service.gc_bd_command(".", "ready", "bd-1"), ["gc", "bd", "ready", "bd-1"])

    def test_rig_workdir_resolves_routed_directory(self) -> None:
        self.write_rig_route("product")

        self.assertEqual(
            service.rig_workdir("product"),
            os.path.realpath(os.path.join(self.tempdir.name, "product")),
        )

    def test_rig_workdir_rejects_paths_outside_city_root(self) -> None:
        beads_dir = pathlib.Path(self.tempdir.name, ".beads")
        beads_dir.mkdir(parents=True, exist_ok=True)
        pathlib.Path(beads_dir, "routes.jsonl").write_text('{"path":"../../tmp"}\n', encoding="utf-8")

        self.assertEqual(service.rig_workdir("../../tmp"), "")

    def test_rig_workdir_rejects_symlink_target_outside_city_root(self) -> None:
        beads_dir = pathlib.Path(self.tempdir.name, ".beads")
        beads_dir.mkdir(parents=True, exist_ok=True)
        outside_dir = pathlib.Path(self.tempdir.name).parent / "mattermost-outside-rig"
        outside_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: outside_dir.exists() and outside_dir.rmdir())
        rig_link = pathlib.Path(self.tempdir.name, "product")
        rig_link.symlink_to(outside_dir, target_is_directory=True)
        pathlib.Path(beads_dir, "routes.jsonl").write_text('{"path":"product"}\n', encoding="utf-8")

        self.assertEqual(service.rig_workdir("product"), "")

    def test_extract_json_output_ignores_warning_braces_before_payload(self) -> None:
        payload = service.extract_json_output('warning: field {name} missing\n{"id":"bd-1"}\n')

        self.assertEqual(payload["id"], "bd-1")

    def test_extract_json_output_returns_empty_for_non_json(self) -> None:
        self.assertEqual(service.extract_json_output("no json here"), {})
        self.assertEqual(service.extract_json_output(""), {})

    # ------------------------------------------------------------------
    # recovery
    # ------------------------------------------------------------------

    def test_recover_incomplete_requests_marks_request_failed_and_releases_workflow(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-1",
            "workflow_key": workflow_key,
            "status": "received",
            "command": "fix",
            "dispatch_target": "mission-control/polecat",
            "channel_id": CHANNEL_ID,
            "conversation_id": CHANNEL_ID,
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "maybe_notify_dispatch_failure", side_effect=lambda payload: payload) as notify_failure:
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 1)
        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["status"], "internal_error")
        self.assertEqual(saved["reason"], "service_restarted_before_dispatch")
        self.assertIsNone(common.load_workflow_link(workflow_key))
        notify_failure.assert_called_once()

    def test_recover_incomplete_requests_closes_persisted_bead(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, OTHER_CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-2",
            "workflow_key": workflow_key,
            "status": "bead_created",
            "command": "fix",
            "bead_id": "bd-10",
            "dispatch_target": "mission-control/polecat",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "close_failed_bead", return_value=True) as close_failed_bead, mock.patch.object(
            service,
            "maybe_notify_dispatch_failure",
            side_effect=lambda payload: payload,
        ):
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 1)
        close_failed_bead.assert_called_once_with("bd-10", "service_restarted_before_dispatch", "mission-control")
        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertTrue(saved["bead_closed"])

    def test_recover_incomplete_requests_preserves_workflow_lock_when_cleanup_fails(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, OTHER_CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-3",
            "workflow_key": workflow_key,
            "status": "bead_created",
            "command": "fix",
            "bead_id": "bd-11",
            "dispatch_target": "mission-control/polecat",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "close_failed_bead", return_value=False), mock.patch.object(
            service,
            "maybe_notify_dispatch_failure",
            side_effect=lambda payload: payload,
        ):
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 1)
        self.assertIsNotNone(common.load_workflow_link(workflow_key))

    def test_recover_incomplete_requests_skips_recent_dispatching_request(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-4",
            "workflow_key": workflow_key,
            "status": "dispatching",
            "dispatch_started_at": common.utcnow(),
            "command": "fix",
            "bead_id": "bd-12",
            "dispatch_target": "mission-control/polecat",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "maybe_notify_dispatch_failure", side_effect=lambda payload: payload) as notify_failure:
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 0)
        self.assertIsNotNone(common.load_workflow_link(workflow_key))
        notify_failure.assert_not_called()

    def test_recover_incomplete_requests_reclaims_stale_dispatching_request(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-5",
            "workflow_key": workflow_key,
            "status": "dispatching",
            "dispatch_started_at": "2000-01-01T00:00:00Z",
            "command": "fix",
            "bead_id": "bd-13",
            "dispatch_target": "mission-control/polecat",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "dispatch_recovery_state", return_value="inactive"), mock.patch.object(
            service, "close_failed_bead", return_value=True
        ) as close_failed_bead, mock.patch.object(
            service,
            "maybe_notify_dispatch_failure",
            side_effect=lambda payload: payload,
        ):
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 1)
        close_failed_bead.assert_called_once_with("bd-13", "service_restarted_during_dispatch", "mission-control")
        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["reason"], "service_restarted_during_dispatch")

    def test_recover_incomplete_requests_marks_dispatched_when_bead_is_already_routed(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-6",
            "workflow_key": workflow_key,
            "status": "dispatching",
            "dispatch_started_at": "2000-01-01T00:00:00Z",
            "command": "fix",
            "bead_id": "bd-14",
            "dispatch_target": "mission-control/polecat",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "dispatch_recovery_state", return_value="active"), mock.patch.object(
            service, "close_failed_bead"
        ) as close_failed_bead, mock.patch.object(
            service,
            "maybe_notify_dispatch_failure",
            side_effect=lambda payload: payload,
        ) as notify_failure:
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 0)
        close_failed_bead.assert_not_called()
        notify_failure.assert_not_called()
        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["status"], "dispatched")
        self.assertEqual(saved["dispatch_recovery_reason"], "bead_already_routed")
        self.assertIsNotNone(common.load_workflow_link(workflow_key))

    def test_recover_incomplete_requests_defers_when_bead_state_is_unavailable(self) -> None:
        workflow_key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        request = {
            "request_id": "mm-recover-7",
            "workflow_key": workflow_key,
            "status": "dispatching",
            "dispatch_started_at": "2000-01-01T00:00:00Z",
            "command": "fix",
            "bead_id": "bd-15",
            "dispatch_target": "mission-control/polecat",
        }
        common.save_request(request)
        common.save_workflow_link(workflow_key, request["request_id"])

        with mock.patch.object(service, "dispatch_recovery_state", return_value="unknown"), mock.patch.object(
            service, "close_failed_bead"
        ) as close_failed_bead, mock.patch.object(
            service,
            "maybe_notify_dispatch_failure",
            side_effect=lambda payload: payload,
        ) as notify_failure:
            recovered = service.recover_incomplete_requests()

        self.assertEqual(recovered, 0)
        close_failed_bead.assert_not_called()
        notify_failure.assert_not_called()
        saved = common.load_request(request["request_id"])
        assert saved is not None
        self.assertEqual(saved["status"], "dispatching")
        self.assertEqual(saved["dispatch_recovery_reason"], "bead_state_unavailable")
        self.assertIsNotNone(common.load_workflow_link(workflow_key))

    # ------------------------------------------------------------------
    # dispatch_recovery_state
    # ------------------------------------------------------------------

    def test_dispatch_recovery_state_treats_assigned_bead_as_active(self) -> None:
        self.write_rig_route("mission-control")
        request = {
            "bead_id": "bd-21",
            "dispatch_target": "mission-control/polecat",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            return_value=mock.Mock(
                returncode=0,
                stdout='{"id":"bd-21","status":"open","assignee":"mission-control/polecat","metadata":{"workflow_id":"gc-2"}}\n',
                stderr="",
            ),
        ):
            state = service.dispatch_recovery_state(request)

        self.assertEqual(state, "active")

    def test_dispatch_recovery_state_treats_open_unassigned_bead_as_inactive(self) -> None:
        self.write_rig_route("mission-control")
        request = {
            "bead_id": "bd-22",
            "dispatch_target": "mission-control/polecat",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            return_value=mock.Mock(
                returncode=0,
                stdout='{"id":"bd-22","status":"open","assignee":"","metadata":{}}\n',
                stderr="",
            ),
        ):
            state = service.dispatch_recovery_state(request)

        self.assertEqual(state, "inactive")

    def test_dispatch_recovery_state_treats_closed_failed_bead_as_inactive(self) -> None:
        self.write_rig_route("mission-control")
        request = {
            "bead_id": "bd-23",
            "dispatch_target": "mission-control/polecat",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            return_value=mock.Mock(
                returncode=0,
                stdout='{"id":"bd-23","status":"closed","metadata":{"close_reason":"mattermost:dispatch_failed"}}\n',
                stderr="",
            ),
        ):
            state = service.dispatch_recovery_state(request)

        self.assertEqual(state, "inactive")

    def test_dispatch_recovery_state_treats_closed_bead_without_failure_reason_as_active(self) -> None:
        self.write_rig_route("mission-control")
        request = {
            "bead_id": "bd-24",
            "dispatch_target": "mission-control/polecat",
        }

        with mock.patch.object(
            service,
            "run_subprocess",
            return_value=mock.Mock(
                returncode=0,
                stdout='{"id":"bd-24","status":"closed","metadata":{}}\n',
                stderr="",
            ),
        ):
            state = service.dispatch_recovery_state(request)

        self.assertEqual(state, "active")

    def test_dispatch_recovery_state_is_unknown_when_bead_cannot_be_read(self) -> None:
        self.write_rig_route("mission-control")
        request = {
            "bead_id": "bd-25",
            "dispatch_target": "mission-control/polecat",
        }

        with mock.patch.object(service, "run_subprocess", return_value=mock.Mock(returncode=1, stdout="", stderr="boom")):
            self.assertEqual(service.dispatch_recovery_state(request), "unknown")

    def test_dispatch_recovery_state_is_inactive_without_bead_id(self) -> None:
        self.assertEqual(service.dispatch_recovery_state({}), "inactive")

    # ------------------------------------------------------------------
    # rate limiting / service scoping
    # ------------------------------------------------------------------

    def test_maybe_prune_request_state_rate_limits_repeated_calls(self) -> None:
        with mock.patch.object(common, "prune_requests") as prune_requests, mock.patch.object(
            common, "prune_receipts"
        ) as prune_receipts, mock.patch.object(common, "prune_pending_modals") as prune_pending_modals, mock.patch(
            "mattermost_intake_service.time.monotonic",
            side_effect=[100.0, 100.5, 161.0],
        ):
            self.assertTrue(service.maybe_prune_request_state())
            self.assertFalse(service.maybe_prune_request_state())
            self.assertTrue(service.maybe_prune_request_state())

        self.assertEqual(prune_requests.call_count, 2)
        self.assertEqual(prune_receipts.call_count, 2)
        self.assertEqual(prune_pending_modals.call_count, 2)

    def test_maybe_recover_request_state_rate_limits_repeated_calls(self) -> None:
        os.environ["GC_SERVICE_NAME"] = common.INTERACTIONS_SERVICE_NAME

        with mock.patch.object(service, "recover_incomplete_requests", return_value=0) as recover_incomplete_requests, mock.patch(
            "mattermost_intake_service.time.monotonic",
            side_effect=[200.0, 200.5, 261.0],
        ):
            self.assertTrue(service.maybe_recover_request_state())
            self.assertFalse(service.maybe_recover_request_state())
            self.assertTrue(service.maybe_recover_request_state())

        self.assertEqual(recover_incomplete_requests.call_count, 2)

    def test_maybe_recover_request_state_skips_non_interactions_service(self) -> None:
        os.environ["GC_SERVICE_NAME"] = common.ADMIN_SERVICE_NAME

        with mock.patch.object(service, "recover_incomplete_requests") as recover_incomplete_requests:
            self.assertFalse(service.maybe_recover_request_state())

        recover_incomplete_requests.assert_not_called()

    def test_should_run_request_recovery_only_for_interactions_service(self) -> None:
        with mock.patch.object(common, "current_service_name", return_value=common.ADMIN_SERVICE_NAME):
            self.assertFalse(service.should_run_request_recovery())
        with mock.patch.object(common, "current_service_name", return_value=common.INTERACTIONS_SERVICE_NAME):
            self.assertTrue(service.should_run_request_recovery())

    def test_utc_age_seconds_handles_missing_and_malformed_values(self) -> None:
        self.assertEqual(service.utc_age_seconds(""), float("inf"))
        self.assertEqual(service.utc_age_seconds("not-a-timestamp"), float("inf"))
        self.assertLess(service.utc_age_seconds(common.utcnow()), 60)

    # ------------------------------------------------------------------
    # receipts / replay
    # ------------------------------------------------------------------

    def test_command_interaction_id_is_stable_per_trigger(self) -> None:
        first = service.command_interaction_id({"trigger_id": "trigger-1"})
        second = service.command_interaction_id({"trigger_id": "trigger-1"})

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("mm-command:"))
        self.assertNotEqual(service.command_interaction_id({}), service.command_interaction_id({}))

    def test_dialog_interaction_id_requires_a_nonce(self) -> None:
        self.assertEqual(service.dialog_interaction_id(""), "")
        self.assertEqual(service.dialog_interaction_id("nonce-1"), "mm-dialog:nonce-1")

    def test_finalize_dialog_origin_receipt_replaces_stale_dialog_replay(self) -> None:
        common.save_interaction_receipt("slash-1", {"response_kind": "dialog", "dialog_nonce": "nonce-1"})
        receipt = {"response_kind": "accepted", "request_id": "mm-1", "response": {}}

        service.finalize_dialog_origin_receipt("slash-1", receipt)

        saved = common.load_interaction_receipt("slash-1")
        assert saved is not None
        self.assertEqual(saved["response_kind"], "accepted")
        # The dialog-submission body must not be replayed to a slash command.
        self.assertNotIn("response", saved)
        replayed = service.replay_response_from_receipt(saved, surface="command")
        self.assertEqual(replayed["response_type"], "in_channel")
        self.assertIn("Accepted /gc fix", replayed["text"])
        self.assertIn("mm-1", replayed["text"])

    def test_persist_interaction_receipt_makes_dialog_submit_replay_safe(self) -> None:
        response = service.build_dialog_ok_response()
        receipt = {"response_kind": "accepted", "request_id": "mm-2", "response": response}

        service.persist_interaction_receipt("mm-dialog:nonce-2", receipt)

        saved = common.load_interaction_receipt("mm-dialog:nonce-2")
        assert saved is not None
        self.assertEqual(saved["response_kind"], "accepted")
        self.assertEqual(service.replay_response_from_receipt(saved, surface="dialog"), response)

    def test_persist_interaction_receipt_saves_prompt_path_response(self) -> None:
        response = service.build_message_response("team only", ephemeral=True)
        receipt = service.receipt_payload(response, response_kind="message")

        service.persist_interaction_receipt("interaction-1", receipt)

        saved = common.load_interaction_receipt("interaction-1")
        assert saved is not None
        self.assertEqual(saved["response_kind"], "message")
        self.assertEqual(service.replay_response_from_receipt(saved), response)

    def test_replay_response_from_receipt_rebuilds_duplicate_notice(self) -> None:
        receipt = {"response_kind": "duplicate", "request_id": "mm-dup"}

        replayed = service.replay_response_from_receipt(receipt, surface="command")

        self.assertEqual(replayed["response_type"], "ephemeral")
        self.assertIn("already active", replayed["text"])

    def test_replay_response_from_receipt_returns_empty_body_for_dialog_surface(self) -> None:
        receipt = {"response_kind": "dialog", "dialog_nonce": "nonce-3"}

        self.assertEqual(service.replay_response_from_receipt(receipt, surface="command"), {})
        self.assertEqual(service.replay_response_from_receipt(receipt, surface="dialog"), {})

    # ------------------------------------------------------------------
    # HTTP surface
    # ------------------------------------------------------------------

    def test_slash_command_handler_rejects_invalid_command_token(self) -> None:
        self.import_app()
        common.save_command_token(COMMAND_TOKEN)
        socket_path = self.start_interactions_server()
        body = urllib.parse.urlencode(self.command_form(token="wrong-token", text="fix crash")).encode("utf-8")

        status, response_body = unix_http_request(
            socket_path,
            "POST",
            common.COMMAND_ROUTE_PATH,
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(status, 401)
        self.assertEqual(json.loads(response_body.decode("utf-8"))["error"], "invalid_command_token")

    def test_slash_command_handler_requires_configured_command_token(self) -> None:
        self.import_app()
        socket_path = self.start_interactions_server()
        body = urllib.parse.urlencode(self.command_form(text="fix crash")).encode("utf-8")

        status, _response_body = unix_http_request(
            socket_path,
            "POST",
            common.COMMAND_ROUTE_PATH,
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(status, 503)

    def test_slash_command_handler_answers_form_encoded_callback_over_http(self) -> None:
        self.import_app()
        common.save_command_token(COMMAND_TOKEN)
        socket_path = self.start_interactions_server()
        body = urllib.parse.urlencode(self.command_form(text="")).encode("utf-8")

        status, response_body = unix_http_request(
            socket_path,
            "POST",
            common.COMMAND_ROUTE_PATH,
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(status, 200)
        payload = json.loads(response_body.decode("utf-8"))
        self.assertEqual(payload["response_type"], "ephemeral")
        self.assertEqual(payload["text"], service.human_reason("command_not_supported"))

    def test_slash_command_handler_replays_receipt_for_repeated_trigger(self) -> None:
        self.import_app()
        common.save_command_token(COMMAND_TOKEN)
        socket_path = self.start_interactions_server()
        body = urllib.parse.urlencode(self.command_form(text="")).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        first_status, first_body = unix_http_request(socket_path, "POST", common.COMMAND_ROUTE_PATH, body=body, headers=headers)
        second_status, second_body = unix_http_request(socket_path, "POST", common.COMMAND_ROUTE_PATH, body=body, headers=headers)

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(json.loads(first_body.decode("utf-8")), json.loads(second_body.decode("utf-8")))

    def test_dialog_handler_rejects_unsigned_route_token(self) -> None:
        self.import_app()
        socket_path = self.start_interactions_server()
        body = json.dumps({"type": "dialog_submission", "state": "nope"}).encode("utf-8")

        status, response_body = unix_http_request(
            socket_path,
            "POST",
            f"{common.DIALOG_ROUTE_PATH}/not-a-real-token",
            body=body,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status, 401)
        self.assertEqual(json.loads(response_body.decode("utf-8"))["error"], "invalid_dialog_route_token")

    def test_dialog_handler_rejects_expired_dialog_state(self) -> None:
        self.import_app()
        socket_path = self.start_interactions_server()
        route_token = common.dialog_route_token()
        body = json.dumps(
            {
                "type": "dialog_submission",
                "callback_id": service.FIX_DIALOG_CALLBACK_ID,
                "state": "stale-state",
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "submission": {"summary": "Crash"},
            }
        ).encode("utf-8")

        status, response_body = unix_http_request(
            socket_path,
            "POST",
            f"{common.DIALOG_ROUTE_PATH}/{route_token}",
            body=body,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(response_body.decode("utf-8")),
            {"error": service.human_reason("dialog_expired")},
        )

    def test_dialog_handler_accepts_submission_and_dispatches_request(self) -> None:
        self.import_app()
        common.set_channel_mapping(common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", common.FIX_FORMULA_DEFAULT)
        common.save_bot_token("bot-token")
        socket_path = self.start_interactions_server()
        route_token = common.dialog_route_token()
        nonce = "nonce-accept-1"
        common.save_pending_modal(
            {
                "nonce": nonce,
                "team_id": TEAM_ID,
                "team_domain": "acme",
                "channel_id": CHANNEL_ID,
                "channel_name": "town-square",
                "root_id": "",
                "user_id": USER_ID,
                "user_name": "alice",
                "interaction_id": "mm-command:trigger-1",
                "command": "fix",
                "command_trigger": "/gc",
                "rig_name": "",
            }
        )
        body = json.dumps(
            {
                "type": "dialog_submission",
                "callback_id": service.FIX_DIALOG_CALLBACK_ID,
                "state": common.mint_dialog_state(nonce),
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "submission": {"summary": "Crash on startup", "context": "unset env X"},
                "cancelled": False,
            }
        ).encode("utf-8")

        with mock.patch.object(service, "enqueue_request") as enqueue_request, mock.patch.object(
            common, "post_channel_message", return_value={"id": "post-9"}
        ) as post_channel_message:
            status, response_body = unix_http_request(
                socket_path,
                "POST",
                f"{common.DIALOG_ROUTE_PATH}/{route_token}",
                body=body,
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(response_body.decode("utf-8")), {})
        enqueue_request.assert_called_once()
        post_channel_message.assert_called_once()
        request = common.list_recent_requests(limit=1)[0]
        self.assertEqual(request["summary"], "Crash on startup")
        self.assertEqual(request["dispatch_target"], "product/polecat")
        # The originating slash-command receipt is rewritten so a replay is safe.
        origin = common.load_interaction_receipt("mm-command:trigger-1")
        assert origin is not None
        self.assertEqual(origin["response_kind"], "accepted")

    def test_dialog_handler_accepts_cancellation_without_dispatching(self) -> None:
        self.import_app()
        socket_path = self.start_interactions_server()
        route_token = common.dialog_route_token()
        nonce = "nonce-cancel-1"
        common.save_pending_modal(
            {
                "nonce": nonce,
                "team_id": TEAM_ID,
                "channel_id": CHANNEL_ID,
                "user_id": USER_ID,
                "interaction_id": "mm-command:trigger-cancel",
                "command": "fix",
            }
        )
        body = json.dumps(
            {
                "type": "dialog_submission",
                "state": common.mint_dialog_state(nonce),
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "submission": {},
                "cancelled": True,
            }
        ).encode("utf-8")

        with mock.patch.object(service, "enqueue_request") as enqueue_request:
            status, response_body = unix_http_request(
                socket_path,
                "POST",
                f"{common.DIALOG_ROUTE_PATH}/{route_token}",
                body=body,
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(response_body.decode("utf-8")), {})
        enqueue_request.assert_not_called()
        self.assertEqual(common.list_recent_requests(limit=20), [])

    def test_dialog_handler_rejects_mismatched_channel_context(self) -> None:
        self.import_app()
        socket_path = self.start_interactions_server()
        route_token = common.dialog_route_token()
        nonce = "nonce-mismatch-1"
        common.save_pending_modal(
            {
                "nonce": nonce,
                "team_id": TEAM_ID,
                "channel_id": CHANNEL_ID,
                "user_id": USER_ID,
                "interaction_id": "mm-command:trigger-mismatch",
                "command": "fix",
            }
        )
        body = json.dumps(
            {
                "type": "dialog_submission",
                "state": common.mint_dialog_state(nonce),
                "user_id": USER_ID,
                "channel_id": OTHER_CHANNEL_ID,
                "team_id": TEAM_ID,
                "submission": {"summary": "Crash"},
            }
        ).encode("utf-8")

        status, response_body = unix_http_request(
            socket_path,
            "POST",
            f"{common.DIALOG_ROUTE_PATH}/{route_token}",
            body=body,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(response_body.decode("utf-8")),
            {"error": service.human_reason("bad_dialog_context")},
        )

    def test_message_action_route_reports_unsupported_action(self) -> None:
        self.import_app()
        socket_path = self.start_interactions_server()
        route_token = common.dialog_route_token()

        status, response_body = unix_http_request(
            socket_path,
            "POST",
            f"{common.ACTION_ROUTE_PATH}/{route_token}",
            body=json.dumps({"user_id": USER_ID}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status, 200)
        self.assertIn("Unsupported", json.loads(response_body.decode("utf-8"))["ephemeral_text"])

    def test_interactions_healthz_and_root(self) -> None:
        socket_path = self.start_interactions_server()

        status, _body = unix_http_request(socket_path, "GET", "/healthz")
        self.assertEqual(status, 204)

        status, body = unix_http_request(socket_path, "GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["service"], common.INTERACTIONS_SERVICE_NAME)

    def test_unknown_interactions_route_is_not_found(self) -> None:
        socket_path = self.start_interactions_server()

        status, body = unix_http_request(
            socket_path,
            "POST",
            "/mattermost/nope",
            body=b"{}",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body.decode("utf-8"))["error"], "not_found")


if __name__ == "__main__":
    unittest.main()

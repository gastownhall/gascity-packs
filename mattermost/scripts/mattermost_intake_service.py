#!/usr/bin/env python3

from __future__ import annotations

import base64
import calendar
import html
import json
import os
import pathlib
import secrets
import socketserver
import subprocess
import threading
import time
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

import mattermost_intake_common as common

PROCESSING_LOCK = threading.Lock()
ACCEPTANCE_LOCK = threading.Lock()
DIALOG_SUBMIT_LOCK = threading.Lock()
REQUEST_PRUNE_LOCK = threading.Lock()
REQUEST_RECOVERY_LOCK = threading.Lock()
PROCESSING_REQUESTS: set[str] = set()
MAX_REQUEST_BYTES = 64 * 1024
DISPATCHING_RECOVERY_GRACE_SECONDS = 10 * 60
REQUEST_PRUNE_INTERVAL_SECONDS = 60
REQUEST_RECOVERY_INTERVAL_SECONDS = 60
DISPATCH_SUBPROCESS_TIMEOUT_SECONDS = 5 * 60
LAST_REQUEST_PRUNE_AT = 0.0
LAST_REQUEST_RECOVERY_AT = 0.0

FIX_DIALOG_CALLBACK_ID = "gc_fix"
FIX_DIALOG_TITLE = "GC Fix Request"
# Mattermost caps dialog element display names at 24 characters and textarea
# defaults/placeholders at 3000; see model/integration_action.go.
FIX_SUMMARY_MIN_LENGTH = 4
FIX_SUMMARY_MAX_LENGTH = 120
FIX_CONTEXT_MAX_LENGTH = 3000


class ThreadingUnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class DispatchSubprocessTimeout(RuntimeError):
    def __init__(self, command: list[str], timeout_seconds: float) -> None:
        self.command = list(command)
        self.timeout_seconds = timeout_seconds
        super().__init__(f"command timed out after {timeout_seconds:g}s: {' '.join(self.command)}")


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str) -> None:
    payload = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def interaction_response(handler: BaseHTTPRequestHandler, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def command_behavior(command: str) -> dict[str, Any]:
    if command != "fix":
        return {}
    return {"workflow_scope": "conversation"}


def trim_output(value: str, limit: int = 1200) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def human_reason(code: str) -> str:
    mapping = {
        "command_not_supported": "this Mattermost slice only supports /gc fix",
        "channel_mapping_missing": "no channel mapping exists for this conversation",
        "rig_mapping_missing": "no rig mapping exists for that rig in this team",
        "command_not_configured": "this channel does not configure that /gc command",
        "team_required": "Mattermost /gc fix is only accepted inside a team channel",
        "team_not_allowed": "this team is not allowed to dispatch /gc fix",
        "channel_not_allowed": "this channel is not allowed to dispatch /gc fix",
        "channel_membership_required": "you must be a member of this channel to dispatch /gc fix",
        "channel_role_not_allowed": "you do not have a Mattermost channel role that is allowed to dispatch /gc fix",
        "mattermost_app_not_configured": "the Mattermost app is not fully configured in this workspace",
        "bead_create_failed": "the workflow bead could not be created",
        "bead_update_failed": "the workflow bead could not be initialized",
        "gc_not_available": "the gc CLI is not available in this runtime",
        "dispatch_timeout": "workflow dispatch timed out before it could finish",
        "invalid_dispatch_target": "the configured target is not a rig-scoped sling target",
        "rig_workdir_missing": "the rig is not routed to a local workspace directory",
        "mattermost_lookup_failed": "Mattermost metadata lookup failed; retry in a moment",
        "dialog_open_failed": "the /gc fix dialog could not be opened; retry in a moment",
        "dialog_expired": "that dialog submission has expired; run /gc fix again",
        "bad_dialog_context": "that dialog submission does not match the original slash command",
        "summary_required": "a short summary is required before the workflow can start",
        "internal_error": "an internal error occurred while starting the workflow",
        "service_restarted_before_dispatch": "the Mattermost worker restarted before the workflow could be started",
        "service_restarted_during_dispatch": "the Mattermost worker restarted during workflow dispatch",
    }
    return mapping.get(code, code or "unknown_error")


def utc_age_seconds(value: str) -> float:
    normalized = str(value).strip()
    if not normalized:
        return float("inf")
    try:
        parsed = time.strptime(normalized, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return float("inf")
    return max(time.time() - calendar.timegm(parsed), 0.0)


def should_run_request_recovery() -> bool:
    service_name = str(common.current_service_name() or "").strip()
    return service_name in {"", common.INTERACTIONS_SERVICE_NAME}


def maybe_prune_request_state() -> bool:
    global LAST_REQUEST_PRUNE_AT
    now = time.monotonic()
    with REQUEST_PRUNE_LOCK:
        if LAST_REQUEST_PRUNE_AT and (now - LAST_REQUEST_PRUNE_AT) < REQUEST_PRUNE_INTERVAL_SECONDS:
            return False
        LAST_REQUEST_PRUNE_AT = now
    common.prune_requests()
    common.prune_receipts()
    common.prune_pending_modals()
    return True


def maybe_recover_request_state() -> bool:
    global LAST_REQUEST_RECOVERY_AT
    if not should_run_request_recovery():
        return False
    now = time.monotonic()
    with REQUEST_RECOVERY_LOCK:
        if LAST_REQUEST_RECOVERY_AT and (now - LAST_REQUEST_RECOVERY_AT) < REQUEST_RECOVERY_INTERVAL_SECONDS:
            return False
        LAST_REQUEST_RECOVERY_AT = now
    recover_incomplete_requests()
    return True


def request_summary(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request.get("request_id"),
        "workflow_key": request.get("workflow_key", ""),
        "status": request.get("status"),
        "command": request.get("command"),
        "team_id": request.get("team_id"),
        "conversation_id": request.get("conversation_id"),
        "bead_id": request.get("bead_id", ""),
        "dispatch_target": request.get("dispatch_target", ""),
        "dispatch_formula": request.get("dispatch_formula", ""),
        "reason": request.get("reason", ""),
    }


def build_message_response(content: str, ephemeral: bool) -> dict[str, Any]:
    # Mattermost slash-command responses are CommandResponse objects; the
    # `response_type` field decides whether the post is user-only or public.
    return {
        "response_type": "ephemeral" if ephemeral else "in_channel",
        "text": content,
    }


def build_dialog_ok_response() -> dict[str, Any]:
    # An empty SubmitDialogResponse closes the dialog without an error banner.
    return {}


def build_dialog_error_response(reason: str, field: str = "") -> dict[str, Any]:
    message = human_reason(reason)
    if field:
        return {"errors": {field: message}}
    return {"error": message}


def build_fix_dialog(state: str) -> dict[str, Any]:
    return {
        "callback_id": FIX_DIALOG_CALLBACK_ID,
        "title": FIX_DIALOG_TITLE,
        "introduction_text": "Describe the bug you want a GC worker session to fix.",
        "submit_label": "Start workflow",
        "notify_on_cancel": False,
        "state": state,
        "elements": [
            {
                "display_name": "Short summary",
                "name": "summary",
                "type": "text",
                "subtype": "text",
                "min_length": FIX_SUMMARY_MIN_LENGTH,
                "max_length": FIX_SUMMARY_MAX_LENGTH,
                "optional": False,
                "placeholder": "What is broken?",
            },
            {
                "display_name": "Additional context",
                "name": "context",
                "type": "textarea",
                "max_length": FIX_CONTEXT_MAX_LENGTH,
                "optional": True,
                "placeholder": "Reproduction steps, links, logs, anything else useful.",
            },
        ],
    }


def open_fix_dialog(trigger_id: str, state: str) -> None:
    """Open the /gc fix dialog. `trigger_id` is short lived, so call this first."""
    url = common.dialog_callback_url()
    if not url:
        raise common.MattermostAPIError("interactions service URL is not published yet")
    common.mattermost_api_request(
        "POST",
        "/actions/dialogs/open",
        payload={
            "trigger_id": str(trigger_id).strip(),
            "url": url,
            "dialog": build_fix_dialog(state),
        },
    )


def build_acceptance_response(request: dict[str, Any]) -> dict[str, Any]:
    return build_message_response(build_acceptance_message(request), ephemeral=False)


def build_acceptance_message(request: dict[str, Any]) -> str:
    summary = str(request.get("summary", "")).strip()
    return "\n".join(
        part
        for part in (
            "Accepted /gc fix for this conversation.",
            f"Request: `{request.get('request_id', '')}`" if request.get("request_id") else "",
            f"Summary: {summary}" if summary else "",
        )
        if part
    )


def build_duplicate_message(existing: dict[str, Any]) -> str:
    content = "\n".join(
        part
        for part in (
            "A /gc fix workflow is already active for this conversation.",
            f"Request: `{existing.get('request_id', '')}`" if existing.get("request_id") else "",
            f"Status: `{existing.get('status', '')}`" if existing.get("status") else "",
            f"Bead: `{existing.get('bead_id', '')}`" if existing.get("bead_id") else "",
        )
        if part
    )
    return content or "A workflow is already active for this conversation."


def build_duplicate_response(existing: dict[str, Any]) -> dict[str, Any]:
    return build_message_response(build_duplicate_message(existing), ephemeral=True)


def receipt_payload(response: dict[str, Any], response_kind: str = "", request_id: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "response": response,
    }
    if response_kind:
        payload["response_kind"] = response_kind
    if request_id:
        payload["request_id"] = request_id
    return payload


def prompt_to_summary_context(prompt: str) -> tuple[str, str]:
    prompt = prompt.strip()
    if not prompt:
        return "", ""
    lines = [line.strip() for line in prompt.splitlines()]
    summary = next((line for line in lines if line), "")[:FIX_SUMMARY_MAX_LENGTH]
    return summary, prompt


def normalize_command_invocation(form: dict[str, str]) -> dict[str, str]:
    """Normalize a Mattermost slash-command callback into a stable shape.

    Mattermost POSTs `application/x-www-form-urlencoded` with token, team_id,
    team_domain, channel_id, channel_name, root_id, user_id, user_name,
    command, text, trigger_id and response_url.
    """
    return {
        "surface": "command",
        "team_id": str(form.get("team_id", "")).strip(),
        "team_domain": str(form.get("team_domain", "")).strip(),
        "channel_id": str(form.get("channel_id", "")).strip(),
        "channel_name": str(form.get("channel_name", "")).strip(),
        "root_id": str(form.get("root_id", "")).strip(),
        "user_id": str(form.get("user_id", "")).strip(),
        "user_name": str(form.get("user_name", "")).strip(),
        "command": str(form.get("command", "")).strip(),
        "text": str(form.get("text", "")).strip(),
        "trigger_id": str(form.get("trigger_id", "")).strip(),
        "response_url": str(form.get("response_url", "")).strip(),
    }


def normalize_dialog_invocation(payload: dict[str, Any], pending: dict[str, Any]) -> dict[str, str]:
    """Normalize a `dialog_submission` payload, back-filled from the pending record.

    Dialog submissions only carry type, callback_id, state, user_id, channel_id,
    team_id, submission, file_ids and cancelled — the channel/team display names
    and the thread root come from the slash command that opened the dialog.
    """
    return {
        "surface": "dialog",
        "team_id": str(payload.get("team_id", "")).strip() or str(pending.get("team_id", "")).strip(),
        "team_domain": str(pending.get("team_domain", "")).strip(),
        "channel_id": str(payload.get("channel_id", "")).strip() or str(pending.get("channel_id", "")).strip(),
        "channel_name": str(pending.get("channel_name", "")).strip(),
        "root_id": str(pending.get("root_id", "")).strip(),
        "user_id": str(payload.get("user_id", "")).strip() or str(pending.get("user_id", "")).strip(),
        "user_name": str(pending.get("user_name", "")).strip(),
        "command": str(pending.get("command_trigger", "")).strip(),
        "text": "",
        "trigger_id": "",
        "response_url": "",
    }


def _strip_rig_flag(token: str) -> str:
    for prefix in ("--rig=", "-rig=", "rig=", "rig:"):
        if token.startswith(prefix):
            return token[len(prefix) :].strip()
    return ""


def _split_leading_token(text: str) -> tuple[str, str]:
    """Peel one whitespace-delimited token off the front, keeping the tail verbatim.

    The tail has to survive intact: `prompt_to_summary_context` derives the bead
    summary from the prompt's first line, so collapsing newlines here would make
    every multi-line `/gc fix` prompt a single 120-character summary.
    """
    stripped = text.lstrip()
    index = 0
    while index < len(stripped) and not stripped[index].isspace():
        index += 1
    return stripped[:index], stripped[index:]


def parse_command_text(
    config: dict[str, Any],
    invocation: dict[str, str],
    command_name_value: str,
) -> dict[str, str]:
    """Parse `/gc fix [rig] [prompt]` out of the slash-command `text` field.

    Mattermost slash commands carry a single freeform `text` string rather than
    Discord's typed option tree, so the subcommand and optional rig are parsed
    positionally. A leading bare token only counts as a rig when it resolves to
    a configured rig mapping; otherwise it stays part of the prompt.
    """
    trigger = str(invocation.get("command", "")).strip().lstrip("/")
    if trigger and trigger != str(command_name_value).strip().lstrip("/"):
        return {}
    command_token, remainder = _split_leading_token(str(invocation.get("text", "")))
    if not command_token:
        return {"command": "", "prompt": "", "rig": ""}
    command = command_token.lower()
    rig = ""
    next_token, after_next = _split_leading_token(remainder)
    if next_token:
        flag_value = _strip_rig_flag(next_token)
        if flag_value:
            rig = flag_value
            remainder = after_next
        elif next_token in {"--rig", "-rig"}:
            rig_token, after_rig = _split_leading_token(after_next)
            if rig_token:
                rig = rig_token
                remainder = after_rig
        elif common.resolve_rig_mapping(config, str(invocation.get("team_id", "")).strip(), next_token):
            rig = next_token
            remainder = after_next
    return {
        "command": command,
        "prompt": remainder.strip(),
        "rig": rig,
    }


def extract_dialog_fields(payload: dict[str, Any]) -> dict[str, str]:
    submission = payload.get("submission") or {}
    if not isinstance(submission, dict):
        return {}
    fields: dict[str, str] = {}
    for key, value in submission.items():
        name = str(key).strip()
        if not name:
            continue
        fields[name] = "" if value is None else str(value)
    return fields


def display_name(invocation: dict[str, str]) -> str:
    return str(invocation.get("user_name", "")).strip()


def channel_roles(config: dict[str, Any], channel_id: str, user_id: str) -> list[str]:
    """Fetch the invoking user's channel roles, but only when policy needs them."""
    policy = common.normalize_config(config).get("policy", {})
    if not policy.get("channel_role_allowlist"):
        return []
    if not channel_id or not user_id:
        return []
    try:
        return common.channel_member_roles(channel_id, user_id)
    except common.MattermostAPIError:
        return []


def run_subprocess(command: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=DISPATCH_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DispatchSubprocessTimeout(command, DISPATCH_SUBPROCESS_TIMEOUT_SECONDS) from exc


def rig_from_target(target: str) -> str:
    if "/" not in target:
        return ""
    rig, _, _ = target.partition("/")
    return rig.strip()


def gc_bd_command(city_root: str, *args: str, rig: str = "") -> list[str]:
    command = [os.environ.get("GC_BIN", "gc")]
    if city_root not in {"", "."}:
        command.extend(["--city", city_root])
    if rig:
        command.extend(["--rig", rig])
    command.append("bd")
    command.extend(args)
    return command


def rig_workdir(rig: str) -> str:
    """Resolve a rig's working directory from .beads/routes.jsonl."""
    root = common.city_root() or "."
    root_abs = os.path.realpath(root)
    routes_path = os.path.join(root, ".beads", "routes.jsonl")
    try:
        with open(routes_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                path = str(entry.get("path", ""))
                if path == rig:
                    if os.path.isabs(path):
                        candidate = os.path.abspath(path)
                    else:
                        candidate = os.path.abspath(os.path.normpath(os.path.join(root_abs, path)))
                    resolved = os.path.realpath(candidate)
                    if resolved == root_abs or resolved.startswith(root_abs + os.sep):
                        if os.path.isdir(resolved):
                            return resolved
    except (OSError, json.JSONDecodeError):
        pass
    return ""


def extract_json_output(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
    for left, right in (("{", "}"), ("[", "]")):
        start = raw.find(left)
        end = raw.rfind(right)
        if start == -1 or end == -1 or end < start:
            continue
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
    return {}


def load_bead_snapshot(bead_id: str, rig: str = "") -> dict[str, Any]:
    normalized_bead_id = str(bead_id).strip()
    if not normalized_bead_id:
        return {}
    city_root = common.city_root() or "."
    bd_cwd = rig_workdir(rig) or city_root
    try:
        result = run_subprocess(
            gc_bd_command(city_root, "show", normalized_bead_id, "--json", rig=rig),
            bd_cwd,
        )
    except (DispatchSubprocessTimeout, FileNotFoundError):
        return {}
    if result.returncode != 0:
        return {}
    return extract_json_output(result.stdout)


def dispatch_recovery_state(payload: dict[str, Any]) -> str:
    bead_id = str(payload.get("bead_id", "")).strip()
    if not bead_id:
        return "inactive"
    bead = load_bead_snapshot(bead_id, rig_from_target(str(payload.get("dispatch_target", ""))))
    if not bead:
        return "unknown"
    status = str(bead.get("status", "")).strip().lower()
    assignee = str(bead.get("assignee", "")).strip()
    parent_id = str(bead.get("parent_id", "") or bead.get("parent", "") or bead.get("parentID", "")).strip()
    metadata = bead.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    workflow_id = str(metadata.get("workflow_id", "")).strip()
    close_reason = str(metadata.get("close_reason", "")).strip()

    if status == "closed":
        if close_reason.startswith("mattermost:"):
            return "inactive"
        return "active"
    if assignee or parent_id or workflow_id:
        return "active"
    if status in {"", "open"}:
        return "inactive"
    return "unknown"


def build_fix_bead_title(request: dict[str, Any]) -> str:
    summary = str(request.get("summary", "")).strip() or "Mattermost fix request"
    return f"Fix Mattermost request: {summary}"[:180]


def build_fix_bead_notes(request: dict[str, Any]) -> str:
    lines = [
        "## Mattermost Source",
        "",
        f"- Team: {request.get('team_id', '')}",
        f"- Channel: {request.get('channel_id', '')}",
        f"- Thread Root: {request.get('root_id', '') or '(none)'}",
        f"- Conversation: {request.get('conversation_id', '')}",
        f"- Permalink: {request.get('permalink', '')}",
        f"- Request ID: {request.get('request_id', '')}",
        f"- Requested By: {request.get('invoking_user_display_name', '')} ({request.get('invoking_user_id', '')})",
        "",
        "## Summary",
        "",
        str(request.get("summary", "")).strip() or "(none)",
        "",
        "## Additional Context",
        "",
        str(request.get("context_markdown", "")).strip() or "(none)",
    ]
    return "\n".join(lines)


def base64_var(value: Any) -> str:
    return base64.b64encode(str(value or "").encode("utf-8")).decode("ascii")


def create_fix_bead(request: dict[str, Any], target: str) -> dict[str, Any]:
    rig = rig_from_target(target)
    if not rig:
        return {"status": "dispatch_failed", "reason": "invalid_dispatch_target"}
    city_root = common.city_root() or "."
    bd_cwd = rig_workdir(rig)
    if not bd_cwd:
        return {"status": "dispatch_failed", "reason": "rig_workdir_missing"}
    create_command = gc_bd_command(
        city_root,
        "create",
        "--json",
        build_fix_bead_title(request),
        "-t",
        "task",
        rig=rig,
    )
    try:
        create_result = run_subprocess(create_command, bd_cwd)
    except FileNotFoundError:
        return {"status": "dispatch_failed", "reason": "bead_create_failed", "dispatch_stderr": "gc not available"}
    except DispatchSubprocessTimeout as exc:
        return {
            "status": "dispatch_failed",
            "reason": "dispatch_timeout",
            "dispatch_command": exc.command,
            "dispatch_timeout_seconds": exc.timeout_seconds,
        }
    if create_result.returncode != 0:
        return {
            "status": "dispatch_failed",
            "reason": "bead_create_failed",
            "dispatch_stdout": trim_output(create_result.stdout),
            "dispatch_stderr": trim_output(create_result.stderr),
        }
    created = extract_json_output(create_result.stdout)
    bead_id = str(created.get("id", "")).strip()
    if not bead_id:
        return {
            "status": "dispatch_failed",
            "reason": "bead_create_failed",
            "dispatch_stdout": trim_output(create_result.stdout),
            "dispatch_stderr": trim_output(create_result.stderr),
        }
    request["bead_id"] = bead_id
    request["status"] = "bead_created"
    common.save_request(request)

    update_command = gc_bd_command(city_root, "update", bead_id, "--notes", build_fix_bead_notes(request), rig=rig)
    metadata = {
        "mattermost_request_id": str(request.get("request_id", "")),
        "mattermost_team_id": str(request.get("team_id", "")),
        "mattermost_channel_id": str(request.get("channel_id", "")),
        "mattermost_root_id": str(request.get("root_id", "")),
        "mattermost_conversation_id": str(request.get("conversation_id", "")),
        "mattermost_summary": str(request.get("summary", "")),
    }
    for key, value in metadata.items():
        if value:
            update_command.extend(["--set-metadata", f"{key}={value}"])
    try:
        update_result = run_subprocess(update_command, bd_cwd)
    except FileNotFoundError:
        return {
            "status": "dispatch_failed",
            "reason": "bead_update_failed",
            "bead_id": bead_id,
            "dispatch_stderr": "gc not available",
        }
    except DispatchSubprocessTimeout as exc:
        return {
            "status": "dispatch_failed",
            "reason": "dispatch_timeout",
            "bead_id": bead_id,
            "dispatch_command": exc.command,
            "dispatch_timeout_seconds": exc.timeout_seconds,
        }
    if update_result.returncode != 0:
        return {
            "status": "dispatch_failed",
            "reason": "bead_update_failed",
            "bead_id": bead_id,
            "dispatch_stdout": trim_output(update_result.stdout),
            "dispatch_stderr": trim_output(update_result.stderr),
        }
    return {"bead_id": bead_id}


def build_fix_vars(request: dict[str, Any], bead_id: str) -> dict[str, str]:
    return {
        "issue": bead_id,
        "mattermost_request_id": str(request.get("request_id", "")),
        "mattermost_team_id": str(request.get("team_id", "")),
        "mattermost_channel_id": str(request.get("channel_id", "")),
        "mattermost_root_id": str(request.get("root_id", "")),
        "mattermost_conversation_id": str(request.get("conversation_id", "")),
        "mattermost_permalink_b64": base64_var(request.get("permalink", "")),
        "mattermost_requester_b64": base64_var(request.get("invoking_user_display_name", "")),
        "mattermost_summary_b64": base64_var(request.get("summary", "")),
        "mattermost_context_b64": base64_var(request.get("context_markdown", "")),
    }


def close_failed_bead(bead_id: str, reason: str, rig: str = "") -> bool:
    bead_id = bead_id.strip()
    if not bead_id:
        return True
    city_root = common.city_root() or "."
    if rig:
        bd_cwd = rig_workdir(rig)
        if not bd_cwd:
            return False
    else:
        bd_cwd = city_root
    try:
        # Prefer closing a failed bead even if we could not persist the close_reason metadata.
        run_subprocess(
            gc_bd_command(
                city_root,
                "update",
                bead_id,
                "--set-metadata",
                f"close_reason=mattermost:{reason or 'dispatch_failed'}",
                rig=rig,
            ),
            bd_cwd,
        )
        run_subprocess(gc_bd_command(city_root, "ready", bead_id, rig=rig), bd_cwd)
        result = run_subprocess(gc_bd_command(city_root, "close", bead_id, rig=rig), bd_cwd)
    except (DispatchSubprocessTimeout, FileNotFoundError):
        return False
    return result.returncode == 0


def run_fix_dispatch(request: dict[str, Any]) -> dict[str, Any]:
    formula = str(request.get("dispatch_formula", "")).strip()
    target = str(request.get("dispatch_target", "")).strip()
    if not formula or not target:
        return {"status": "ignored", "reason": "command_not_configured"}
    try:
        target = common.validate_fix_dispatch_target(target, formula)
    except ValueError:
        return {"status": "dispatch_failed", "reason": "invalid_dispatch_target"}

    rig = rig_from_target(target)
    bead_outcome = create_fix_bead(request, target)
    if bead_outcome.get("status") == "dispatch_failed":
        cleanup_ok = close_failed_bead(str(bead_outcome.get("bead_id", "")), str(bead_outcome.get("reason", "")), rig)
        if cleanup_ok:
            bead_outcome["bead_closed"] = True
        else:
            bead_outcome["cleanup_failed"] = True
        return bead_outcome
    if "bead_id" not in bead_outcome:
        return bead_outcome
    bead_id = str(bead_outcome["bead_id"])
    request["bead_id"] = bead_id

    gc_bin = os.environ.get("GC_BIN", "gc")
    command = [gc_bin, "sling", target, bead_id, "--on", formula]
    for key, value in build_fix_vars(request, bead_id).items():
        if value:
            command.extend(["--var", f"{key}={value}"])
    request["status"] = "dispatching"
    request["dispatch_started_at"] = common.utcnow()
    common.save_request(request)
    try:
        result = run_subprocess(command, common.city_root() or ".")
    except FileNotFoundError:
        cleanup_ok = close_failed_bead(bead_id, "gc_not_available", rig)
        outcome = {"status": "dispatch_failed", "reason": "gc_not_available", "bead_id": bead_id}
        if cleanup_ok:
            outcome["bead_closed"] = True
        else:
            outcome["cleanup_failed"] = True
        return outcome
    except DispatchSubprocessTimeout as exc:
        recovery_state = dispatch_recovery_state(
            {
                "bead_id": bead_id,
                "dispatch_target": target,
            }
        )
        outcome: dict[str, Any] = {
            "bead_id": bead_id,
            "dispatch_command": exc.command,
            "dispatch_timeout_seconds": exc.timeout_seconds,
        }
        if recovery_state == "active":
            outcome["status"] = "dispatched"
            outcome["dispatch_completed_at"] = common.utcnow()
            outcome["dispatch_recovery_reason"] = "dispatch_timeout_but_bead_already_routed"
        elif recovery_state == "unknown":
            outcome["status"] = "dispatching"
            outcome["dispatch_recovery_reason"] = "dispatch_timeout_state_unavailable"
            outcome["dispatch_timeout_at"] = common.utcnow()
        else:
            cleanup_ok = close_failed_bead(bead_id, "dispatch_timeout", rig)
            outcome["status"] = "dispatch_failed"
            outcome["reason"] = "dispatch_timeout"
            if cleanup_ok:
                outcome["bead_closed"] = True
            else:
                outcome["cleanup_failed"] = True
        request.update(outcome)
        common.save_request(request)
        return outcome
    outcome = {
        "bead_id": bead_id,
        "dispatch_target": target,
        "dispatch_formula": formula,
        "dispatch_command": command,
        "dispatch_exit_code": result.returncode,
        "dispatch_stdout": trim_output(result.stdout),
        "dispatch_stderr": trim_output(result.stderr),
    }
    if result.returncode == 0:
        outcome["status"] = "dispatched"
        outcome["dispatch_completed_at"] = common.utcnow()
    else:
        outcome["status"] = "dispatch_failed"
        outcome["reason"] = "dispatch_failed"
        if close_failed_bead(bead_id, "dispatch_failed", rig):
            outcome["bead_closed"] = True
        else:
            outcome["cleanup_failed"] = True
    request.update(outcome)
    common.save_request(request)
    return outcome


def process_request(request_id: str) -> None:
    request: dict[str, Any] | None = None
    workflow_key_hint = ""
    try:
        request = common.load_request(request_id)
        if not request:
            return
        workflow_key_hint = str(request.get("workflow_key", ""))
        if str(request.get("status", "")).strip() == "received":
            request["status"] = "processing"
            common.save_request(request)
        behavior = command_behavior(str(request.get("command", "")))
        if not behavior:
            request["status"] = "ignored"
            request["reason"] = "command_not_supported"
        else:
            outcome = run_fix_dispatch(request)
            request.update(outcome)
            if request.get("status") in {"dispatch_failed", "internal_error"}:
                maybe_notify_dispatch_failure(request)
        common.save_request(request)
    except Exception as exc:  # noqa: BLE001
        payload = request or common.load_request(request_id) or {"request_id": request_id}
        bead_id = str(payload.get("bead_id", ""))
        rig = rig_from_target(str(payload.get("dispatch_target", "")))
        if bead_id and not payload.get("bead_closed"):
            if close_failed_bead(bead_id, "internal_error", rig):
                payload["bead_closed"] = True
            else:
                payload["cleanup_failed"] = True
        payload["status"] = "internal_error"
        payload["reason"] = "internal_error"
        payload["error_message"] = str(exc)
        payload["traceback"] = traceback.format_exc(limit=20)
        maybe_notify_dispatch_failure(payload)
        common.save_request(payload)
        request = payload
    finally:
        if request:
            workflow_key = str(request.get("workflow_key", "")) or workflow_key_hint
            if (
                workflow_key
                and request.get("status") in {"ignored", "dispatch_failed", "internal_error"}
                and not request.get("cleanup_failed")
            ):
                with ACCEPTANCE_LOCK:
                    common.remove_workflow_link_if_request(workflow_key, request_id)
        elif request_id:
            with ACCEPTANCE_LOCK:
                common.remove_workflow_links_for_request(request_id)
        with PROCESSING_LOCK:
            PROCESSING_REQUESTS.discard(request_id)


def enqueue_request(request_id: str) -> None:
    with PROCESSING_LOCK:
        if request_id in PROCESSING_REQUESTS:
            return
        PROCESSING_REQUESTS.add(request_id)
    thread = threading.Thread(target=process_request, args=(request_id,), daemon=True)
    thread.start()


def recover_incomplete_requests() -> int:
    recovered = 0
    for path in pathlib.Path(common.requests_dir()).glob("*.json"):
        payload = common.read_json(str(path), allow_invalid=True)
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status", "")).strip()
        recovery_reason = "service_restarted_before_dispatch"
        if status in {"received", "processing", "bead_created"}:
            pass
        elif status == "dispatching":
            if utc_age_seconds(str(payload.get("dispatch_started_at", "")).strip()) < DISPATCHING_RECOVERY_GRACE_SECONDS:
                continue
            recovery_state = dispatch_recovery_state(payload)
            if recovery_state == "active":
                payload["status"] = "dispatched"
                payload["dispatch_recovered_at"] = common.utcnow()
                payload["dispatch_recovery_reason"] = "bead_already_routed"
                common.save_request(payload)
                continue
            if recovery_state == "unknown":
                payload["dispatch_recovery_deferred_at"] = common.utcnow()
                payload["dispatch_recovery_reason"] = "bead_state_unavailable"
                common.save_request(payload)
                continue
            recovery_reason = "service_restarted_during_dispatch"
        else:
            continue
        bead_id = str(payload.get("bead_id", "")).strip()
        rig = rig_from_target(str(payload.get("dispatch_target", "")))
        if bead_id and not payload.get("bead_closed"):
            if close_failed_bead(bead_id, recovery_reason, rig):
                payload["bead_closed"] = True
            else:
                payload["cleanup_failed"] = True
        payload["status"] = "internal_error"
        payload["reason"] = recovery_reason
        payload["recovered_at"] = common.utcnow()
        maybe_notify_dispatch_failure(payload)
        common.save_request(payload)
        workflow_key = str(payload.get("workflow_key", "")).strip()
        request_id = str(payload.get("request_id", "")).strip()
        if workflow_key and request_id and not payload.get("cleanup_failed"):
            common.remove_workflow_link_if_request(workflow_key, request_id)
        recovered += 1
    return recovered


def reserve_request(request: dict[str, Any], behavior: dict[str, Any], interaction_id: str) -> dict[str, Any] | None:
    with ACCEPTANCE_LOCK:
        existing_receipt = common.load_interaction_receipt(interaction_id)
        if existing_receipt:
            request_id = str(existing_receipt.get("request_id", "")).strip()
            if request_id:
                return common.load_request(request_id) or {"request_id": request_id}
            return {"request_id": "", "status": "duplicate"}
        existing = common.load_request(request["request_id"])
        if existing:
            common.save_interaction_receipt(
                interaction_id,
                {"request_id": str(existing.get("request_id", "")), "response_kind": "duplicate"},
            )
            return existing
        workflow_key = str(request.get("workflow_key", ""))
        if behavior.get("workflow_scope") == "conversation" and workflow_key:
            workflow_link = common.load_workflow_link(workflow_key)
            if workflow_link:
                existing_request_id = str(workflow_link.get("request_id", ""))
                existing_request = common.load_request(existing_request_id) or {
                    "request_id": existing_request_id,
                    "workflow_key": workflow_key,
                    "status": "duplicate",
                    "command": request.get("command", ""),
                    "team_id": request.get("team_id", ""),
                    "conversation_id": request.get("conversation_id", ""),
                }
                common.save_interaction_receipt(
                    interaction_id,
                    {"request_id": existing_request_id, "response_kind": "duplicate"},
                )
                return existing_request
        common.save_request(request)
        if behavior.get("workflow_scope") == "conversation" and workflow_key:
            common.save_workflow_link(workflow_key, request["request_id"])
        common.save_interaction_receipt(
            interaction_id,
            {"request_id": request["request_id"], "response_kind": "accepted"},
        )
    return None


def render_admin_home() -> str:
    snapshot = common.build_status_snapshot(limit=20)
    config = snapshot["config"]
    app_cfg = config.get("app", {})
    command_name_value = str(app_cfg.get("command_name", common.COMMAND_NAME_DEFAULT))
    team_id = str(app_cfg.get("team_id", ""))
    payload_preview = json.dumps(
        common.build_command_payload(command_name_value, team_id, common.command_callback_url()),
        indent=2,
        sort_keys=True,
    )
    command_url = common.command_callback_url() or "(publish mattermost-interactions first)"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mattermost Admin</title>
  <style>
    body {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: 2rem; line-height: 1.45; }}
    pre {{ background: #f5f5f5; padding: 1rem; overflow-x: auto; }}
    code {{ background: #f5f5f5; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Mattermost</h1>
  <p>Interactions URL: <code>{html.escape(str(snapshot.get('interactions_url') or '(not published yet)'))}</code></p>
  <p>Admin URL: <code>{html.escape(str(snapshot.get('admin_url') or '(not published yet)'))}</code></p>
  <h2>Setup</h2>
  <p>Import the Mattermost site URL, bot token, and slash-command verification token with <code>gc mattermost import-app ...</code>.</p>
  <p>Then point the Mattermost slash command Request URL at <code>{html.escape(command_url)}</code>.</p>
  <p>The interactive-dialog callback URL carries a secret path token and is registered automatically when the dialog is opened; it is not shown here.</p>
  <h2>Command Sync Payload</h2>
  <pre>{html.escape(payload_preview)}</pre>
  <h2>Config</h2>
  <pre>{html.escape(json.dumps(config, indent=2, sort_keys=True))}</pre>
  <h2>Recent Requests</h2>
  <pre>{html.escape(json.dumps(snapshot.get('recent_requests', []), indent=2, sort_keys=True))}</pre>
  <h2>Chat Bindings</h2>
  <pre>{html.escape(json.dumps(snapshot.get('chat_bindings', []), indent=2, sort_keys=True))}</pre>
  <h2>Chat Launchers</h2>
  <pre>{html.escape(json.dumps(snapshot.get('chat_launchers', []), indent=2, sort_keys=True))}</pre>
  <h2>Gateway Status</h2>
  <pre>{html.escape(json.dumps(snapshot.get('gateway_status', {}), indent=2, sort_keys=True))}</pre>
  <h2>Recent Chat Ingress</h2>
  <pre>{html.escape(json.dumps(snapshot.get('recent_chat_ingress', []), indent=2, sort_keys=True))}</pre>
  <h2>Recent Chat Publishes</h2>
  <pre>{html.escape(json.dumps(snapshot.get('recent_chat_publishes', []), indent=2, sort_keys=True))}</pre>
  <h2>Recent Room Launches</h2>
  <pre>{html.escape(json.dumps(snapshot.get('recent_room_launches', []), indent=2, sort_keys=True))}</pre>
</body>
</html>
"""


def build_request(
    invocation: dict[str, str],
    summary: str,
    context_markdown: str,
    channel_context: dict[str, Any],
    interaction_id: str,
    mapping: dict[str, Any] | None = None,
    rig_name: str = "",
) -> dict[str, Any]:
    team_id = str(channel_context.get("team_id", "")).strip() or str(invocation.get("team_id", "")).strip()
    channel_id = str(channel_context.get("channel_id", "")).strip() or str(invocation.get("channel_id", "")).strip()
    root_id = str(channel_context.get("root_id", "")).strip() or str(invocation.get("root_id", "")).strip()
    conversation_id = common.mattermost_conversation_key(channel_id, root_id)
    resolved_mapping: dict[str, Any] = mapping if mapping is not None else (channel_context.get("mapping") or {})
    request_id = common.build_request_id(interaction_id, "fix")
    workflow_key = common.build_workflow_key(team_id, conversation_id, "fix")
    return {
        "request_id": request_id,
        "workflow_key": workflow_key,
        "status": "received",
        "command": "fix",
        "created_at": common.utcnow(),
        "updated_at": common.utcnow(),
        "interaction_id": interaction_id,
        "team_id": team_id,
        "team_domain": str(invocation.get("team_domain", "")).strip(),
        "channel_id": channel_id,
        "channel_name": str(invocation.get("channel_name", "")).strip(),
        "root_id": root_id,
        "conversation_id": conversation_id,
        "invoking_user_id": str(invocation.get("user_id", "")).strip(),
        "invoking_user_display_name": display_name(invocation),
        "summary": summary.strip(),
        "context_markdown": context_markdown.strip(),
        "permalink": common.mattermost_channel_url(
            str(invocation.get("team_domain", "")).strip(),
            str(invocation.get("channel_name", "")).strip(),
        ),
        "rig_name": rig_name,
        "dispatch_target": str(resolved_mapping.get("target", "")),
        "dispatch_formula": str((((resolved_mapping.get("commands") or {}).get("fix") or {}).get("formula", common.FIX_FORMULA_DEFAULT))),
    }


def replay_response_from_receipt(receipt: dict[str, Any], surface: str = "command") -> dict[str, Any]:
    stored_response = receipt.get("response")
    if isinstance(stored_response, dict):
        return stored_response
    response_kind = str(receipt.get("response_kind", "")).strip()
    if surface == "dialog":
        return build_dialog_ok_response()
    if response_kind == "dialog":
        # The slash command already opened a dialog for this invocation.
        return {}
    request_id = str(receipt.get("request_id", "")).strip()
    request = common.load_request(request_id) if request_id else {}
    if response_kind == "accepted":
        return build_acceptance_response(request or {"request_id": request_id})
    return build_duplicate_response(request or {"request_id": request_id, "status": "duplicate"})


def build_dispatch_failure_message(request: dict[str, Any]) -> str:
    request_id = str(request.get("request_id", "")).strip()
    bead_id = str(request.get("bead_id", "")).strip()
    status = str(request.get("status", "")).strip()
    reason = str(request.get("reason", "")).strip()
    lines = [
        "Mattermost `/gc fix` could not be started.",
        f"Request: `{request_id}`" if request_id else "",
        f"Status: `{status}`" if status else "",
        f"Reason: {human_reason(reason)}" if reason else "",
        f"Bead: `{bead_id}`" if bead_id else "",
    ]
    return "\n".join(line for line in lines if line)


def maybe_notify_dispatch_failure(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("failure_notified_at"):
        return request
    target_channel = str(request.get("channel_id", "")).strip()
    if not target_channel:
        return request
    try:
        response = common.post_channel_message(
            target_channel,
            build_dispatch_failure_message(request),
            root_id=str(request.get("root_id", "")).strip(),
        )
    except common.MattermostAPIError as exc:
        request["failure_notification_error"] = str(exc)
        return request
    request["failure_notified_at"] = common.utcnow()
    message_id = str((response or {}).get("id", "")).strip() if isinstance(response, dict) else ""
    if message_id:
        request["failure_message_id"] = message_id
    return request


def post_conversation_message(invocation: dict[str, str], content: str) -> str:
    """Post back into the conversation.

    A `dialog_submission` response body cannot carry post content, so dialog
    acceptances and duplicate notices are delivered with the bot token instead.
    """
    channel_id = str(invocation.get("channel_id", "")).strip()
    if not channel_id or not content:
        return ""
    try:
        response = common.post_channel_message(channel_id, content, root_id=str(invocation.get("root_id", "")).strip())
    except common.MattermostAPIError:
        return ""
    if isinstance(response, dict):
        return str(response.get("id", "")).strip()
    return ""


def finalize_dialog_origin_receipt(
    origin_interaction_id: str,
    receipt: dict[str, Any],
) -> None:
    """Rewrite the slash-command receipt once its dialog has been submitted.

    The stored body is deliberately dropped: a replayed slash command must be
    answered with a CommandResponse, not with the dialog-submission response.
    """
    origin_interaction_id = origin_interaction_id.strip()
    if not origin_interaction_id:
        return
    payload = {
        "response_kind": str(receipt.get("response_kind", "")) or "accepted",
    }
    request_id = str(receipt.get("request_id", "")).strip()
    if request_id:
        payload["request_id"] = request_id
    common.replace_interaction_receipt(origin_interaction_id, payload)


def persist_interaction_receipt(
    interaction_id: str,
    receipt: dict[str, Any],
) -> None:
    interaction_id = interaction_id.strip()
    if not interaction_id:
        return
    payload = dict(receipt)
    common.save_interaction_receipt(interaction_id, payload)


def accept_fix_request(
    invocation: dict[str, str],
    summary: str,
    context_markdown: str,
    interaction_id: str,
    rig_name: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and reserve a /gc fix request.

    Returns (outcome, receipt) where outcome is a surface-neutral record:
      {"kind": "message"|"accepted"|"duplicate", "content": str, "request": {...}}
    """
    config = common.load_config()
    team_id = str(invocation.get("team_id", "")).strip()
    if not team_id:
        return refusal_outcome("team_required")
    if not common.load_bot_token():
        return refusal_outcome("mattermost_app_not_configured")

    # Resolve dispatch target: rig mapping takes priority, channel mapping as fallback.
    mapping: dict[str, Any] | None = None
    channel_id = str(invocation.get("channel_id", "")).strip()
    root_id = str(invocation.get("root_id", "")).strip()
    if rig_name and not root_id:
        channel_context: dict[str, Any] = {
            "team_id": team_id,
            "channel_id": channel_id,
            "root_id": "",
            "mapping": {},
            "channel_info": {},
        }
    else:
        channel_context = common.load_channel_context(config, team_id, channel_id, root_id)
    if channel_context.get("lookup_error") and (not rig_name or root_id):
        return refusal_outcome("mattermost_lookup_failed")
    effective_team_id = str(channel_context.get("team_id", "")).strip() or team_id
    if rig_name:
        mapping = common.resolve_rig_mapping(config, effective_team_id, rig_name)
        if not mapping:
            return refusal_outcome("rig_mapping_missing")
    else:
        mapping = channel_context.get("mapping") or {}
        if not mapping:
            return refusal_outcome("channel_mapping_missing")

    reason = common.policy_reason(
        config,
        effective_team_id,
        str(channel_context.get("channel_id", "")).strip() or channel_id,
        channel_roles(config, channel_id, str(invocation.get("user_id", "")).strip()),
    )
    if reason:
        return refusal_outcome(reason)
    summary = summary.strip()
    context_markdown = context_markdown.strip()
    if not summary and context_markdown:
        summary, context_markdown = prompt_to_summary_context(context_markdown)
    if not summary:
        return refusal_outcome("summary_required", field="summary")
    request = build_request(
        invocation,
        summary,
        context_markdown,
        channel_context,
        interaction_id,
        mapping,
        rig_name=rig_name,
    )
    behavior = command_behavior("fix")
    if not behavior:
        return refusal_outcome("command_not_supported")
    existing = reserve_request(request, behavior, interaction_id)
    if existing:
        outcome = {
            "kind": "duplicate",
            "content": build_duplicate_message(existing),
            "request": existing,
        }
        return outcome, receipt_payload(
            {},
            response_kind="duplicate",
            request_id=str(existing.get("request_id", "")).strip(),
        )
    enqueue_request(request["request_id"])
    outcome = {
        "kind": "accepted",
        "content": build_acceptance_message(request),
        "request": request,
    }
    return outcome, receipt_payload({}, response_kind="accepted", request_id=request["request_id"])


def refusal_outcome(reason: str, field: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    outcome = {
        "kind": "message",
        "reason": reason,
        "field": field,
        "content": human_reason(reason),
        "request": {},
    }
    return outcome, receipt_payload({}, response_kind="message")


def command_response_for_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    kind = str(outcome.get("kind", "message"))
    content = str(outcome.get("content", ""))
    if kind == "accepted":
        return build_message_response(content, ephemeral=False)
    return build_message_response(content, ephemeral=True)


def dialog_response_for_outcome(outcome: dict[str, Any], invocation: dict[str, str]) -> dict[str, Any]:
    kind = str(outcome.get("kind", "message"))
    if kind == "message":
        return build_dialog_error_response(str(outcome.get("reason", "")), str(outcome.get("field", "")))
    post_conversation_message(invocation, str(outcome.get("content", "")))
    return build_dialog_ok_response()


class IntakeHandler(BaseHTTPRequestHandler):
    server_version = "MattermostIntake/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{common.current_service_name() or 'mattermost'}] {fmt % args}")

    def _parsed(self) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(self.path)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length) if length > 0 else b"{}"
        if not data:
            return {}
        parsed = json.loads(data.decode("utf-8"))
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("request body must be a JSON object")

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_REQUEST_BYTES:
            return None
        return self.rfile.read(length) if length > 0 else b""

    def do_GET(self) -> None:  # noqa: N802
        parsed = self._parsed()
        service_name = common.current_service_name()
        if parsed.path == "/healthz":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if service_name == common.ADMIN_SERVICE_NAME:
            self._do_admin_get(parsed)
            return
        self._do_interactions_get(parsed)

    def do_POST(self) -> None:  # noqa: N802
        parsed = self._parsed()
        service_name = common.current_service_name()
        if service_name == common.ADMIN_SERVICE_NAME:
            self._do_admin_post(parsed)
            return
        self._do_interactions_post(parsed)

    def _do_admin_get(self, parsed: urllib.parse.ParseResult) -> None:
        if parsed.path == "/":
            text_response(self, HTTPStatus.OK, render_admin_home(), "text/html; charset=utf-8")
            return
        if parsed.path == "/v0/mattermost/status":
            json_response(self, HTTPStatus.OK, common.build_status_snapshot(limit=20))
            return
        if parsed.path == "/v0/mattermost/requests":
            json_response(self, HTTPStatus.OK, {"requests": common.list_recent_requests(limit=50)})
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _do_admin_post(self, parsed: urllib.parse.ParseResult) -> None:
        try:
            body = self._read_json_body()
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if parsed.path == "/v0/mattermost/app/import":
            try:
                config = common.import_app_config(common.load_config(), body)
            except ValueError as exc:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            json_response(self, HTTPStatus.OK, {"config": common.redact_config(config)})
            return
        if parsed.path == "/v0/mattermost/bot-token/import":
            token = str(body.get("bot_token", "")).strip()
            if not token:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "bot_token is required"})
                return
            common.save_bot_token(token)
            json_response(self, HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/v0/mattermost/command-token/import":
            # Mattermost authenticates inbound slash commands with the shared
            # verification token issued when the command is created.
            token = str(body.get("command_token", body.get("verification_token", ""))).strip()
            if not token:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "command_token is required"})
                return
            try:
                common.validate_command_token(token)
            except ValueError as exc:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            common.save_command_token(token)
            json_response(self, HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/v0/mattermost/commands/sync":
            team_ids = body.get("team_ids")
            if not isinstance(team_ids, list):
                team_id = str(body.get("team_id", "")).strip()
                team_ids = [team_id] if team_id else []
            if not team_ids:
                json_response(self, HTTPStatus.BAD_REQUEST, {"error": "team_id or team_ids is required"})
                return
            config = common.load_config()
            results: dict[str, Any] = {}
            had_errors = False
            for team_id in team_ids:
                try:
                    results[str(team_id)] = {
                        "status": "ok",
                        "command": common.sync_team_commands(config, str(team_id)),
                    }
                except common.MattermostAPIError as exc:
                    had_errors = True
                    results[str(team_id)] = {
                        "status": "error",
                        "error": str(exc),
                    }
            json_response(self, HTTPStatus.BAD_GATEWAY if had_errors else HTTPStatus.OK, {"teams": results})
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _do_interactions_get(self, parsed: urllib.parse.ParseResult) -> None:
        if parsed.path == "/":
            json_response(
                self,
                HTTPStatus.OK,
                {
                    "service": common.current_service_name(),
                    "status": "ok",
                    "interactions_url": common.interactions_url(),
                },
            )
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _do_interactions_post(self, parsed: urllib.parse.ParseResult) -> None:
        path = parsed.path.rstrip("/") or "/"
        if path == common.COMMAND_ROUTE_PATH:
            self._handle_slash_command()
            return
        if path.startswith(common.DIALOG_ROUTE_PATH + "/"):
            self._handle_dialog_submission(path[len(common.DIALOG_ROUTE_PATH) + 1 :])
            return
        if path.startswith(common.ACTION_ROUTE_PATH + "/"):
            self._handle_message_action(path[len(common.ACTION_ROUTE_PATH) + 1 :])
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _handle_slash_command(self) -> None:
        body = self._read_body()
        if body is None:
            json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return
        content_type = str(self.headers.get("Content-Type", "")).split(";")[0].strip().lower()
        try:
            if content_type == "application/json":
                decoded = json.loads(body.decode("utf-8") or "{}")
                if not isinstance(decoded, dict):
                    raise ValueError("request body must be an object")
                form = {str(key): "" if value is None else str(value) for key, value in decoded.items()}
            else:
                parsed_form = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
                form = {key: (values[0] if values else "") for key, values in parsed_form.items()}
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": f"invalid slash command payload: {exc}"})
            return

        if not common.load_command_token():
            json_response(self, HTTPStatus.SERVICE_UNAVAILABLE, {"error": "mattermost command token is not configured"})
            return
        if not common.verify_command_token(str(form.get("token", ""))):
            json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "invalid_command_token"})
            return

        maybe_prune_request_state()
        maybe_recover_request_state()

        config = common.load_config()
        invocation = normalize_command_invocation(form)
        interaction_id = command_interaction_id(invocation)

        existing_receipt = common.load_interaction_receipt(interaction_id) if interaction_id else None
        if existing_receipt:
            interaction_response(self, replay_response_from_receipt(existing_receipt, surface="command"))
            return

        if not invocation["team_id"]:
            response = build_message_response(human_reason("team_required"), ephemeral=True)
            persist_interaction_receipt(interaction_id, receipt_payload(response, response_kind="message"))
            interaction_response(self, response)
            return

        parsed_command = parse_command_text(config, invocation, common.command_name(config))
        command = str(parsed_command.get("command", "")).strip()
        if command != "fix":
            response = build_message_response(human_reason("command_not_supported"), ephemeral=True)
            persist_interaction_receipt(interaction_id, receipt_payload(response, response_kind="message"))
            interaction_response(self, response)
            return

        rig_name = str(parsed_command.get("rig", "")).strip()
        prompt = str(parsed_command.get("prompt", "")).strip()
        if prompt:
            summary, context_markdown = prompt_to_summary_context(prompt)
            outcome, receipt = accept_fix_request(invocation, summary, context_markdown, interaction_id, rig_name=rig_name)
            response = command_response_for_outcome(outcome)
            receipt = dict(receipt)
            receipt["response"] = response
            persist_interaction_receipt(interaction_id, receipt)
            interaction_response(self, response)
            return

        # No inline prompt: open the interactive dialog. The trigger_id is
        # short lived (Mattermost expires it after OutgoingIntegrationRequestsTimeout
        # seconds), so the dialog is opened before any other work.
        trigger_id = invocation["trigger_id"]
        if not trigger_id:
            response = build_message_response(human_reason("dialog_open_failed"), ephemeral=True)
            persist_interaction_receipt(interaction_id, receipt_payload(response, response_kind="message"))
            interaction_response(self, response)
            return
        nonce = secrets.token_hex(12)
        common.save_pending_modal(
            {
                "nonce": nonce,
                "team_id": invocation["team_id"],
                "team_domain": invocation["team_domain"],
                "channel_id": invocation["channel_id"],
                "channel_name": invocation["channel_name"],
                "root_id": invocation["root_id"],
                "user_id": invocation["user_id"],
                "user_name": invocation["user_name"],
                "interaction_id": interaction_id,
                "command": "fix",
                "command_trigger": invocation["command"],
                "rig_name": rig_name,
            }
        )
        try:
            open_fix_dialog(trigger_id, common.mint_dialog_state(nonce))
        except (common.MattermostAPIError, ValueError) as exc:
            common.remove_pending_modal(nonce)
            self.log_message("dialog open failed: %s", exc)
            response = build_message_response(human_reason("dialog_open_failed"), ephemeral=True)
            persist_interaction_receipt(interaction_id, receipt_payload(response, response_kind="message"))
            interaction_response(self, response)
            return
        common.save_interaction_receipt(
            interaction_id,
            {"response_kind": "dialog", "dialog_nonce": nonce, "command_name": common.command_name(config)},
        )
        # Mattermost renders the dialog itself; an empty response keeps the
        # channel clean while the operator fills it in.
        interaction_response(self, {})

    def _handle_dialog_submission(self, route_token: str) -> None:
        if not common.verify_dialog_route_token(route_token):
            json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "invalid_dialog_route_token"})
            return
        body = self._read_body()
        if body is None:
            json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON payload: {exc}"})
            return
        if not isinstance(payload, dict):
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "request body must be an object"})
            return

        maybe_prune_request_state()
        maybe_recover_request_state()

        if str(payload.get("type", "")).strip() not in {"", "dialog_submission"}:
            interaction_response(self, build_dialog_error_response("command_not_supported"))
            return

        state = str(payload.get("state", "")).strip()
        nonce = common.verify_dialog_state(state)
        interaction_id = dialog_interaction_id(nonce)

        with DIALOG_SUBMIT_LOCK:
            existing_receipt = common.load_interaction_receipt(interaction_id) if interaction_id else None
            if existing_receipt:
                interaction_response(self, replay_response_from_receipt(existing_receipt, surface="dialog"))
                return
            # `consume_pending_modal` re-verifies the HMAC state and is single use.
            pending = common.consume_pending_modal(state) if state else None
            if not nonce or not pending:
                interaction_response(self, build_dialog_error_response("dialog_expired"))
                return
            if bool(payload.get("cancelled")):
                interaction_response(self, build_dialog_ok_response())
                return
            invocation = normalize_dialog_invocation(payload, pending)
            if str(pending.get("team_id", "")) and str(payload.get("team_id", "")).strip():
                if str(pending.get("team_id", "")) != str(payload.get("team_id", "")).strip():
                    interaction_response(self, build_dialog_error_response("bad_dialog_context"))
                    return
            if str(pending.get("channel_id", "")) != str(payload.get("channel_id", "")).strip():
                interaction_response(self, build_dialog_error_response("bad_dialog_context"))
                return
            expected_user = str(pending.get("user_id", "")).strip()
            actual_user = str(payload.get("user_id", "")).strip()
            if expected_user and expected_user != actual_user:
                interaction_response(self, build_dialog_error_response("bad_dialog_context"))
                return
            fields = extract_dialog_fields(payload)
            summary = str(fields.get("summary", "")).strip()
            context_markdown = str(fields.get("context", "")).strip()
            rig_name = str(pending.get("rig_name", "")).strip()
            outcome, receipt = accept_fix_request(invocation, summary, context_markdown, interaction_id, rig_name=rig_name)
            response = dialog_response_for_outcome(outcome, invocation)
            receipt = dict(receipt)
            receipt["response"] = response
            persist_interaction_receipt(interaction_id, receipt)
            if outcome.get("kind") != "message":
                finalize_dialog_origin_receipt(str(pending.get("interaction_id", "")), receipt)
        interaction_response(self, response)

    def _handle_message_action(self, route_token: str) -> None:
        if not common.verify_dialog_route_token(route_token):
            json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "invalid_dialog_route_token"})
            return
        if self._read_body() is None:
            json_response(self, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request_too_large"})
            return
        interaction_response(self, {"ephemeral_text": "Unsupported Mattermost interactive action."})


def command_interaction_id(invocation: dict[str, str]) -> str:
    """Stable idempotency key for one slash-command invocation.

    Mattermost slash commands carry no interaction id, but `trigger_id` is
    minted per invocation, so it stands in for Discord's `interaction.id`.
    """
    trigger_id = str(invocation.get("trigger_id", "")).strip()
    if trigger_id:
        return common.safe_storage_id(f"mm-command:{trigger_id}", "command")
    return common.safe_storage_id(f"mm-command:{secrets.token_hex(16)}", "command")


def dialog_interaction_id(nonce: str) -> str:
    normalized = str(nonce).strip()
    if not normalized:
        return ""
    return common.safe_storage_id(f"mm-dialog:{normalized}", "dialog")


def main() -> int:
    common.ensure_layout()
    if should_run_request_recovery():
        recover_incomplete_requests()
    socket_path = os.environ.get("GC_SERVICE_SOCKET")
    try:
        common.prepare_service_socket(socket_path or "")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    with ThreadingUnixHTTPServer(socket_path, IntakeHandler) as server:
        print(f"[{common.current_service_name() or 'mattermost'}] listening on {socket_path}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
from typing import Any

import mattermost_intake_common as common

DEFAULT_TRANSCRIPT_TAIL = 40
VIA_GC = "gc"
VIA_ADAPTER = "adapter"


def _failure_kind(exc: common.MattermostAPIError) -> str:
    status = getattr(exc, "status_code", None)
    if status == 404:
        return "not_found"
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limited"
    if status == 413:
        return "too_large"
    if status == 400:
        return "invalid_request"
    return "error"


def _idempotency_dir() -> str:
    return os.path.join(common.data_dir(), "upload-idempotency")


def _idempotency_path(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return os.path.join(_idempotency_dir(), f"upload-{digest}.json")


def _load_idempotent_receipt(key: str) -> tuple[dict[str, Any], int]:
    """Return the cached (receipt, exit_code) for an idempotency key."""
    if not key:
        return {}, 0
    cached = common.read_json(_idempotency_path(key), default=None, allow_invalid=True)
    if isinstance(cached, dict) and cached.get("receipt"):
        receipt = cached.get("receipt")
        if not isinstance(receipt, dict):
            return {}, 0
        try:
            exit_code = int(cached.get("exit_code", 0))
        except (TypeError, ValueError):
            exit_code = 0
        return receipt, exit_code
    return {}, 0


def _save_idempotent_receipt(key: str, receipt: dict[str, Any], exit_code: int) -> None:
    if not key:
        return
    os.makedirs(_idempotency_dir(), exist_ok=True)
    common.atomic_write_json(
        _idempotency_path(key),
        {
            "idempotency_key": key,
            "saved_at": common.utcnow(),
            "exit_code": int(exit_code),
            "receipt": receipt,
        },
    )


def _read_file(path: str) -> bytes:
    candidate = pathlib.Path(path).expanduser()
    if not candidate.exists():
        raise SystemExit(f"file not found: {path}")
    if not candidate.is_file():
        raise SystemExit(f"not a regular file: {path}")
    try:
        return candidate.read_bytes()
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc


def _resolve_binding(session_selector: str) -> tuple[dict[str, Any], dict[str, str]]:
    try:
        context = common.find_latest_mattermost_reply_context(session_selector, tail=DEFAULT_TRANSCRIPT_TAIL)
    except common.GCAPIError as exc:
        raise SystemExit(f"{exc}; bind this session with `gc mattermost bind-room` or `gc mattermost bind-dm` first") from exc
    binding_id = str(context.get("publish_binding_id", "")).strip()
    if not binding_id:
        raise SystemExit("latest mattermost event has no publish_binding_id")
    binding = common.resolve_publish_route(common.load_config(), binding_id)
    if not binding:
        raise SystemExit(f"binding not found: {binding_id}")
    return binding, context


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Upload a local file into a session bound Mattermost channel")
    parser.add_argument("--file", required=True, help="Local file to upload")
    parser.add_argument("--session", default="", help="Session id whose binding to upload into")
    parser.add_argument("--filename", default="", help="Override the uploaded filename (defaults to basename of --file)")
    parser.add_argument("--initial-comment", default="", help="Post message text sent alongside the attachment")
    parser.add_argument("--root-id", default="", help="Thread root post id to attach under")
    parser.add_argument(
        "--thread-current",
        action="store_true",
        help="Attach under the thread of the latest inbound for this session",
    )
    parser.add_argument("--idempotency-key", default="", help="Caller supplied idempotency key for retries")
    parser.add_argument(
        "--via",
        default=VIA_GC,
        choices=(VIA_GC, VIA_ADAPTER),
        help="Routing path: gc records the upload and fans out to peers; adapter bypasses gc for diagnostics",
    )
    args = parser.parse_args(argv)

    root_id = str(args.root_id).strip()
    if root_id and args.thread_current:
        raise SystemExit("--root-id and --thread-current are mutually exclusive")

    content = _read_file(args.file)
    filename = str(args.filename).strip() or os.path.basename(str(args.file).rstrip("/")) or "upload.bin"
    message = str(args.initial_comment)
    idempotency_key = str(args.idempotency_key).strip()
    session_selector = str(args.session).strip() or common.current_session_selector()

    cached_receipt, cached_exit_code = _load_idempotent_receipt(idempotency_key)
    if cached_receipt:
        replay = dict(cached_receipt)
        replay["idempotent_replay"] = True
        print(json.dumps(replay, indent=2, sort_keys=True))
        # Replaying a partially-delivered upload must not read as a clean success.
        return cached_exit_code if replay.get("delivered") else 1

    binding, context = _resolve_binding(str(args.session).strip())

    source_context: dict[str, str] = dict(context)
    trigger_id = ""
    if args.thread_current:
        trigger_id = str(context.get("publish_trigger_id", "")).strip()
    else:
        # A plain upload posts at channel level; drop the inbound threading hints
        # but keep launch/attribution metadata so room launches still route.
        source_context.pop("publish_root_post_id", None)
        source_context.pop("publish_trigger_id", None)

    try:
        conversation_id, root_post_id, _launch = common.resolve_publish_destination(
            binding,
            trigger_id=trigger_id,
            reply_to_message_id=root_id,
            source_context=source_context,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    except common.MattermostAPIError as exc:
        raise SystemExit(str(exc)) from exc
    if not conversation_id:
        raise SystemExit("binding is missing a destination conversation_id")

    source_identity: dict[str, str] = {}
    if str(args.session).strip():
        try:
            source_identity = common.resolve_session_identity(str(args.session).strip())
        except common.GCAPIError as exc:
            raise SystemExit(str(exc)) from exc

    receipt: dict[str, Any] = {
        "delivered": False,
        "via": str(args.via),
        "file_id": "",
        "file_ids": [],
        "filename": filename,
        "size_bytes": len(content),
        "conversation_id": conversation_id,
        "root_id": root_post_id,
        "post_id": "",
        "binding_id": str(binding.get("id", "")).strip(),
        "session_selector": session_selector,
        "idempotency_key": idempotency_key,
        "failure_kind": "",
        "error": "",
    }

    try:
        uploaded = common.mattermost_upload_request(
            "/files",
            [("channel_id", conversation_id)],
            [("files", filename, content)],
        )
        file_infos = (uploaded or {}).get("file_infos")
        file_ids = [
            str(item.get("id", "")).strip()
            for item in (file_infos if isinstance(file_infos, list) else [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        ]
        if not file_ids:
            raise common.MattermostAPIError("mattermost upload returned no file id")
        receipt["file_ids"] = file_ids
        receipt["file_id"] = file_ids[0]

        if str(args.via) == VIA_ADAPTER:
            response = common.post_channel_message(
                conversation_id,
                message,
                root_id=root_post_id,
                file_ids=file_ids,
            )
            payload: dict[str, Any] = {"response": response}
            exit_code = 0
        else:
            payload = common.publish_binding_message(
                binding,
                message,
                trigger_id=trigger_id,
                reply_to_message_id=root_id,
                source_context=source_context or None,
                source_session_name=str(source_identity.get("session_name", "")).strip(),
                source_session_id=str(source_identity.get("session_id", "")).strip(),
                file_ids=file_ids,
            )
            response = payload.get("response") or {}
            receipt["record"] = payload.get("record", {})
            exit_code = common.peer_delivery_exit_code(payload.get("record", {}))
    except (ValueError, common.MattermostAPIError) as exc:
        if isinstance(exc, common.MattermostAPIError):
            receipt["failure_kind"] = _failure_kind(exc)
        else:
            receipt["failure_kind"] = "invalid_request"
        receipt["error"] = str(exc)
        # Failures are not cached: a retry with the same key must try again.
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 1

    receipt["delivered"] = True
    receipt["post_id"] = str((response or {}).get("id", "")).strip()
    receipt["response"] = response
    _save_idempotent_receipt(idempotency_key, receipt, exit_code)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

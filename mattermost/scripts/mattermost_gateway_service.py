#!/usr/bin/env python3

from __future__ import annotations

import base64
import calendar
import hashlib
import json
import os
import queue
import random
import re
import signal
import socket
import socketserver
import ssl
import struct
import threading
import time
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

import mattermost_intake_common as common

ALIAS_PATTERN = re.compile(r"(?<![A-Za-z0-9_@])@([a-z0-9][a-z0-9_-]*)", re.IGNORECASE)
RESERVED_MENTION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_@.\-])@(" + "|".join(sorted(re.escape(item) for item in common.MATTERMOST_RESERVED_MENTIONS)) + r")(?![A-Za-z0-9_.\-])",
    re.IGNORECASE,
)
MAX_STATUS_PREVIEW = 160
GATEWAY_WORKER_THREADS = 8
GATEWAY_MAX_PENDING_MESSAGES = 128
RECONNECT_BASE_DELAY_SECONDS = 5
RECONNECT_MAX_DELAY_SECONDS = 60
PRUNE_INTERVAL_SECONDS = 60
HEALTH_RECONNECT_GRACE_SECONDS = 90
GC_API_HEALTH_TTL_SECONDS = 30
GC_API_HEALTH_PROBE_TIMEOUT_SECONDS = 3.0
CHANNEL_INFO_TTL_SECONDS = 5 * 60
BOT_IDENTITY_TTL_SECONDS = 10 * 60
MAX_FRAME_BYTES = 16 * 1024 * 1024
STALE_PROCESSING_RECEIPT_SECONDS = 2 * 60
FAILED_RECEIPT_RETRY_SECONDS = 60
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
# Mattermost pings connected clients on a 60s cadence and treats 65s of silence
# as a dead connection (model.PingTimeoutBufferSeconds == 5). Mirror that here
# and drive our own ping so a half-open socket is detected in bounded time.
WEBSOCKET_PING_INTERVAL_SECONDS = 30.0
WEBSOCKET_SILENCE_TIMEOUT_SECONDS = 65.0
WEBSOCKET_AUTH_TIMEOUT_SECONDS = 20.0
AUTHENTICATION_CHALLENGE_ACTION = "authentication_challenge"
# Close codes the Mattermost reference webapp client reports back to the server
# via ?disconnect_err_code= on the next connect (webapp/platform/client).
CLIENT_PING_TIMEOUT_CLOSE_CODE = 4000
CLIENT_SEQUENCE_MISMATCH_CLOSE_CODE = 4001


class WebSocketClosed(RuntimeError):
    pass


class GatewayFrameTimeout(RuntimeError):
    pass


class ThreadingUnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


CHANNEL_INFO_CACHE_LOCK = threading.Lock()
CHANNEL_INFO_FETCH_LOCKS_LOCK = threading.Lock()
CHANNEL_INFO_FETCH_LOCKS: dict[str, threading.Lock] = {}
CHANNEL_INFO_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
AMBIENT_ROOM_BINDINGS_CACHE_LOCK = threading.Lock()
AMBIENT_ROOM_BINDINGS_FETCH_LOCK = threading.Lock()
AMBIENT_ROOM_BINDINGS_CACHE: dict[str, Any] = {"config_signature": None, "bindings": {}}
STALE_RECLAIM_LOCKS_LOCK = threading.Lock()
STALE_RECLAIM_LOCKS: dict[str, threading.Lock] = {}
INGRESS_PROCESS_LOCKS_LOCK = threading.Lock()
INGRESS_PROCESS_LOCKS: dict[str, threading.Lock] = {}
GC_API_HEALTH_LOCK = threading.Lock()
GC_API_HEALTH_CACHE = {"checked_at": 0.0, "reachable": True}
BOT_IDENTITY_LOCK = threading.Lock()
BOT_IDENTITY_CACHE: dict[str, Any] = {"fetched_at": 0.0, "user_id": "", "username": ""}
WORKER_QUEUE_SENTINEL: tuple[dict[str, Any], str, str] | None = None


def participant_delivery_selector(participant: dict[str, Any]) -> str:
    for key in ("session_name", "session_id", "session_alias"):
        value = str((participant or {}).get(key, "")).strip()
        if value:
            return value
    return ""


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


def summarize_body(value: str, limit: int = MAX_STATUS_PREVIEW) -> str:
    normalized = " ".join(str(value).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def parse_event_mentions(event_data: dict[str, Any]) -> list[str]:
    # Mattermost sends data.mentions as a JSON-encoded array of user ids.
    raw = (event_data or {}).get("mentions")
    if isinstance(raw, list):
        items: Any = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        return []
    if not isinstance(items, list):
        return []
    seen: set[str] = set()
    mentions: list[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            mentions.append(value)
    return mentions


def normalize_posted_event(event: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Mattermost `posted` websocket event into one routable post dict.

    Mattermost splits the information Discord packs into a single MESSAGE_CREATE
    payload across `data.post` (a JSON-encoded string), sibling `data` keys, and
    `broadcast`. Everything downstream expects one dict, so merge them here.
    """
    raw_data = (event or {}).get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    raw_broadcast = (event or {}).get("broadcast")
    broadcast: dict[str, Any] = raw_broadcast if isinstance(raw_broadcast, dict) else {}
    post = common.parse_websocket_post(data)
    if not isinstance(post, dict) or not post:
        return {}
    normalized = dict(post)
    normalized["channel_id"] = str(post.get("channel_id", "") or broadcast.get("channel_id", "")).strip()
    normalized["root_id"] = str(post.get("root_id", "")).strip()
    normalized["team_id"] = str(data.get("team_id", "") or broadcast.get("team_id", "")).strip()
    normalized["channel_type"] = str(data.get("channel_type", "")).strip().upper()
    normalized["channel_name"] = str(data.get("channel_name", "")).strip()
    normalized["channel_display_name"] = str(data.get("channel_display_name", "")).strip()
    sender_name = str(data.get("sender_name", "")).strip().lstrip("@")
    normalized["sender_name"] = sender_name
    normalized["from_username"] = sender_name
    normalized["mentions"] = parse_event_mentions(data)
    return normalized


def display_name_from_message(post: dict[str, Any]) -> str:
    raw_props = post.get("props")
    props: dict[str, Any] = raw_props if isinstance(raw_props, dict) else {}
    candidates: list[str] = []
    for raw in (
        props.get("override_username"),
        post.get("from_username"),
        post.get("sender_name"),
    ):
        if raw is None:
            continue
        value = str(raw).strip().lstrip("@")
        if value:
            candidates.append(value)
    for value in candidates:
        normalized = " ".join(value.replace("\r", " ").replace("\n", " ").split())
        if normalized:
            return normalized
    return "mattermost-user"


def raw_message_content(post: dict[str, Any]) -> str:
    value = post.get("message", "")
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def bot_mention_pattern(bot_username: str) -> re.Pattern[str] | None:
    normalized = str(bot_username).strip().lstrip("@")
    if not normalized:
        return None
    # Mattermost mentions are literal `@username` text, not `<@id>` markup, so
    # detection needs the bot's username and username-safe boundaries.
    return re.compile(
        rf"(?<![A-Za-z0-9_@.\-])@{re.escape(normalized)}(?![A-Za-z0-9_.\-])",
        re.IGNORECASE,
    )


def bot_was_mentioned(post: dict[str, Any], bot_user_id: str, bot_username: str = "") -> bool:
    content = raw_message_content(post)
    pattern = bot_mention_pattern(bot_username)
    if pattern is not None and pattern.search(content):
        return True
    normalized_bot_user_id = str(bot_user_id).strip()
    mentions = post.get("mentions")
    if not normalized_bot_user_id or not isinstance(mentions, list):
        return False
    if not any(str(item).strip() == normalized_bot_user_id for item in mentions):
        return False
    # Mattermost's `mentions` key only ever carries the receiving user's own id
    # (app/web_broadcast_hooks.go), and it is populated for @all / @channel /
    # @here just as it is for a direct @username. Discord's mention array
    # excludes @everyone, so keep that behaviour: a broadcast mention alone is
    # not an address to this bot.
    if RESERVED_MENTION_PATTERN.search(content):
        return False
    return True


def websocket_accept_value(key: str) -> str:
    digest = hashlib.sha1((str(key) + WEBSOCKET_GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def validate_websocket_handshake(header_blob: str, key: str) -> None:
    lines = header_blob.splitlines()
    status_line = lines[0] if lines else ""
    if "101" not in status_line:
        raise RuntimeError(f"websocket handshake failed: {status_line}")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    if headers.get("upgrade", "").lower() != "websocket":
        raise RuntimeError("websocket handshake missing Upgrade: websocket")
    connection_tokens = {token.strip().lower() for token in headers.get("connection", "").split(",") if token.strip()}
    if "upgrade" not in connection_tokens:
        raise RuntimeError("websocket handshake missing Connection: Upgrade")
    accept_value = headers.get("sec-websocket-accept", "")
    if accept_value != websocket_accept_value(key):
        raise RuntimeError("websocket handshake returned an unexpected Sec-WebSocket-Accept")


def strip_bot_mentions(content: str, bot_username: str) -> str:
    pattern = bot_mention_pattern(bot_username)
    if pattern is None:
        return " ".join(str(content).split())
    stripped = pattern.sub(" ", str(content))
    return " ".join(stripped.split())


def extract_alias_mentions(content: str) -> list[str]:
    seen: set[str] = set()
    aliases: list[str] = []
    for match in ALIAS_PATTERN.finditer(content):
        alias = str(match.group(1) or "").strip().lower()
        if alias and alias not in seen and alias not in common.MATTERMOST_RESERVED_MENTIONS:
            seen.add(alias)
            aliases.append(alias)
    return aliases


def referenced_post_id(post: dict[str, Any]) -> str:
    """Best-effort analogue of Discord's `message_reference.message_id`.

    Mattermost has no per-post reply reference: replying inside a thread only
    sets `root_id`, which is already the thread identity. Integrations that do
    carry a finer-grained reply target put it in `props`, so honour that and
    otherwise report "no explicit reply target".
    """
    props = post.get("props")
    if not isinstance(props, dict):
        return ""
    for key in ("reply_to_post_id", "in_reply_to_id"):
        value = str(props.get(key, "")).strip()
        if value:
            return value
    return ""


def casefold_lookup(values: list[str]) -> tuple[dict[str, str], set[str]]:
    lookup: dict[str, str] = {}
    collisions: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        existing = lookup.get(key)
        if existing and existing != normalized:
            collisions.add(key)
            continue
        lookup[key] = normalized
    return lookup, collisions


def message_ingress_id(post: dict[str, Any]) -> str:
    post_id = str(post.get("id", "")).strip()
    if post_id:
        return f"in-{post_id}"
    return f"in-{int(time.time() * 1000)}"


def message_root_post_id(post: dict[str, Any]) -> str:
    return common.post_thread_root_id(post)


def conversation_fields(post: dict[str, Any]) -> tuple[str, str]:
    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    root_id = str(post.get("root_id", "")).strip()
    conversation_key = common.mattermost_conversation_key(channel_id, root_id)
    if not team_id:
        return f"dm:{channel_id}", conversation_key
    if root_id:
        return f"team:{team_id} channel:{channel_id} thread:{root_id}", conversation_key
    return f"team:{team_id} channel:{channel_id}", conversation_key


def ingress_preview(post: dict[str, Any], bot_username: str) -> str:
    return summarize_body(strip_bot_mentions(raw_message_content(post), bot_username))


def fetch_post_via_rest(post_id: str) -> dict[str, Any]:
    normalized_post_id = str(post_id).strip()
    if not normalized_post_id:
        return {}
    try:
        payload = common.mattermost_api_request("GET", f"/posts/{urllib.parse.quote(normalized_post_id)}")
    except common.MattermostAPIError:
        return {}
    if isinstance(payload, dict) and str(payload.get("id", "")).strip() == normalized_post_id:
        return payload
    return {}


def recover_message_for_routing(post: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    recovered = dict(post)
    gateway_content = raw_message_content(post)
    debug = {
        "gateway_content_length": len(gateway_content),
        "rest_content_length": 0,
        "content_source": "gateway",
        "rest_fetch_attempted": False,
        "rest_fetch_succeeded": False,
    }
    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    post_id = str(post.get("id", "")).strip()
    needs_rest = bool(team_id and channel_id and post_id and not gateway_content.strip())
    if not needs_rest:
        return recovered, debug
    debug["rest_fetch_attempted"] = True
    fetched = fetch_post_via_rest(post_id)
    if not isinstance(fetched, dict) or not fetched:
        debug["content_source"] = "gateway_empty_rest_unavailable"
        return recovered, debug
    fetched_content = raw_message_content(fetched)
    debug["rest_content_length"] = len(fetched_content)
    debug["rest_fetch_succeeded"] = True
    if fetched_content:
        recovered["message"] = fetched_content
        debug["content_source"] = "rest_fallback"
    else:
        debug["content_source"] = "gateway_empty_rest_empty"
    for key in ("root_id", "props", "file_ids", "metadata"):
        current = recovered.get(key)
        if current in (None, "", [], {}):
            fetched_value = fetched.get(key)
            if fetched_value not in (None, "", [], {}):
                recovered[key] = fetched_value
    if display_name_from_message(recovered) == "mattermost-user":
        fetched_user_id = str(fetched.get("user_id", "")).strip()
        if fetched_user_id and not str(recovered.get("user_id", "")).strip():
            recovered["user_id"] = fetched_user_id
        author_username = lookup_username(str(recovered.get("user_id", "")).strip())
        if author_username:
            recovered["from_username"] = author_username
            recovered["sender_name"] = author_username
    return recovered, debug


def lookup_username(user_id: str) -> str:
    normalized_user_id = str(user_id).strip()
    if not normalized_user_id:
        return ""
    try:
        payload = common.describe_user(normalized_user_id)
    except common.MattermostAPIError:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("username", "")).strip()


def empty_body_reason(post: dict[str, Any], message_debug: dict[str, Any] | None = None) -> str:
    raw_content = raw_message_content(post)
    if raw_content.strip():
        return "empty_after_bot_mention_strip"
    if str(post.get("team_id", "")).strip():
        debug = message_debug or {}
        source = str(debug.get("content_source", "")).strip()
        if source in {"gateway_empty_rest_unavailable", "gateway_empty_rest_empty", "gateway"}:
            return "message_content_unavailable"
    return "empty_message_content"


def utc_age_seconds(value: str) -> float:
    normalized = str(value).strip()
    if not normalized:
        return float("inf")
    try:
        parsed = time.strptime(normalized, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return float("inf")
    return max(time.time() - calendar.timegm(parsed), 0.0)


def normalize_channel_info(info: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(info, dict):
        return {}
    normalized = dict(info)
    channel_type = str(normalized.get("channel_type", normalized.get("type", ""))).strip().upper()
    if channel_type in common.MATTERMOST_CHANNEL_TYPES:
        normalized["type"] = channel_type
        normalized["channel_type"] = channel_type
    return normalized


def binding_channel_info(binding: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(binding, dict):
        return {}
    return common.normalize_binding_channel_metadata(binding)


def persist_binding_channel_metadata(binding: dict[str, Any]) -> None:
    if str(binding.get("kind", "")).strip() != "room":
        return
    channel_metadata = common.normalize_binding_channel_metadata(binding)
    if not channel_metadata:
        return
    conversation_id = str(binding.get("conversation_id", "")).strip()
    if not conversation_id:
        return
    try:
        common.save_channel_metadata_cache(conversation_id, channel_metadata)
    except (ValueError, OSError, json.JSONDecodeError):
        return


def load_channel_info(channel_id: str, bot_token: str) -> dict[str, Any]:
    now = time.monotonic()
    with CHANNEL_INFO_CACHE_LOCK:
        cached = CHANNEL_INFO_CACHE.get(channel_id)
        if cached and cached[0] > now:
            return dict(cached[1])
    # Serialize cache fills so a burst of uncached channel lookups does not fan
    # out into concurrent Mattermost API reads for the same class of metadata.
    with channel_info_fetch_lock(channel_id):
        now = time.monotonic()
        with CHANNEL_INFO_CACHE_LOCK:
            cached = CHANNEL_INFO_CACHE.get(channel_id)
            if cached and cached[0] > now:
                return dict(cached[1])
        info = common.describe_channel(channel_id, bot_token=bot_token)
        if isinstance(info, dict) and info:
            info = normalize_channel_info(info)
            with CHANNEL_INFO_CACHE_LOCK:
                CHANNEL_INFO_CACHE[channel_id] = (now + CHANNEL_INFO_TTL_SECONDS, dict(info))
            return dict(info)
    return {}


def load_bot_identity(config: dict[str, Any] | None = None, *, force: bool = False) -> tuple[str, str]:
    """Resolve (bot_user_id, bot_username) from GET /users/me, cached.

    Mattermost mention text carries usernames rather than ids, so the gateway
    needs both halves of the bot identity to detect and strip self-mentions.
    """
    now = time.monotonic()
    with BOT_IDENTITY_LOCK:
        fetched_at = float(BOT_IDENTITY_CACHE.get("fetched_at", 0.0) or 0.0)
        cached_user_id = str(BOT_IDENTITY_CACHE.get("user_id", "")).strip()
        cached_username = str(BOT_IDENTITY_CACHE.get("username", "")).strip()
        if not force and cached_user_id and fetched_at and (now - fetched_at) < BOT_IDENTITY_TTL_SECONDS:
            return cached_user_id, cached_username
    user_id = ""
    username = ""
    try:
        payload = common.mattermost_api_request("GET", "/users/me")
    except common.MattermostAPIError:
        payload = {}
    if isinstance(payload, dict):
        user_id = str(payload.get("id", "")).strip()
        username = str(payload.get("username", "")).strip()
    if not user_id:
        cfg = config if isinstance(config, dict) else {}
        user_id = str((cfg.get("app") or {}).get("bot_user_id", "")).strip()
    if not user_id and not username:
        with BOT_IDENTITY_LOCK:
            return (
                str(BOT_IDENTITY_CACHE.get("user_id", "")).strip(),
                str(BOT_IDENTITY_CACHE.get("username", "")).strip(),
            )
    with BOT_IDENTITY_LOCK:
        BOT_IDENTITY_CACHE["fetched_at"] = now
        if user_id:
            BOT_IDENTITY_CACHE["user_id"] = user_id
        if username:
            BOT_IDENTITY_CACHE["username"] = username
        return (
            str(BOT_IDENTITY_CACHE.get("user_id", "")).strip(),
            str(BOT_IDENTITY_CACHE.get("username", "")).strip(),
        )


def stale_reclaim_lock(ingress_id: str) -> threading.Lock:
    with STALE_RECLAIM_LOCKS_LOCK:
        lock = STALE_RECLAIM_LOCKS.get(ingress_id)
        if lock is None:
            lock = threading.Lock()
            STALE_RECLAIM_LOCKS[ingress_id] = lock
        return lock


def channel_info_fetch_lock(channel_id: str) -> threading.Lock:
    with CHANNEL_INFO_FETCH_LOCKS_LOCK:
        lock = CHANNEL_INFO_FETCH_LOCKS.get(channel_id)
        if lock is None:
            lock = threading.Lock()
            CHANNEL_INFO_FETCH_LOCKS[channel_id] = lock
        return lock


def ingress_process_lock(ingress_id: str) -> threading.Lock:
    with INGRESS_PROCESS_LOCKS_LOCK:
        lock = INGRESS_PROCESS_LOCKS.get(ingress_id)
        if lock is None:
            lock = threading.Lock()
            INGRESS_PROCESS_LOCKS[ingress_id] = lock
        return lock


def prune_channel_info_cache() -> None:
    now = time.monotonic()
    with CHANNEL_INFO_CACHE_LOCK:
        expired = [key for key, (expires_at, _) in CHANNEL_INFO_CACHE.items() if expires_at <= now]
        for key in expired:
            del CHANNEL_INFO_CACHE[key]


def prune_channel_info_fetch_locks() -> None:
    with CHANNEL_INFO_CACHE_LOCK:
        cached_keys = set(CHANNEL_INFO_CACHE.keys())
    with CHANNEL_INFO_FETCH_LOCKS_LOCK:
        expired = [key for key, lock in CHANNEL_INFO_FETCH_LOCKS.items() if not lock.locked() and key not in cached_keys]
        for key in expired:
            del CHANNEL_INFO_FETCH_LOCKS[key]


def prune_stale_reclaim_locks() -> None:
    with STALE_RECLAIM_LOCKS_LOCK:
        expired = [key for key, lock in STALE_RECLAIM_LOCKS.items() if not lock.locked() and common.load_chat_ingress(key) is None]
        for key in expired:
            del STALE_RECLAIM_LOCKS[key]


def prune_ingress_process_locks() -> None:
    with INGRESS_PROCESS_LOCKS_LOCK:
        expired = [key for key, lock in INGRESS_PROCESS_LOCKS.items() if not lock.locked() and common.load_chat_ingress(key) is None]
        for key in expired:
            del INGRESS_PROCESS_LOCKS[key]


def probe_gc_api_health(runtime_state: "GatewayRuntimeState") -> bool:
    now = time.monotonic()
    with GC_API_HEALTH_LOCK:
        checked_at = float(GC_API_HEALTH_CACHE.get("checked_at", 0.0) or 0.0)
        if checked_at and (now - checked_at) < GC_API_HEALTH_TTL_SECONDS:
            return bool(GC_API_HEALTH_CACHE.get("reachable", True))
    try:
        common.gc_api_request(
            "GET",
            "/v0/sessions?limit=1&state=all",
            timeout=GC_API_HEALTH_PROBE_TIMEOUT_SECONDS,
        )
    except common.GCAPIError as exc:
        with GC_API_HEALTH_LOCK:
            GC_API_HEALTH_CACHE["checked_at"] = now
            GC_API_HEALTH_CACHE["reachable"] = False
        runtime_state.patch(last_gc_api_error=str(exc), last_gc_api_error_at=common.utcnow())
        return False
    with GC_API_HEALTH_LOCK:
        GC_API_HEALTH_CACHE["checked_at"] = now
        GC_API_HEALTH_CACHE["reachable"] = True
    runtime_state.patch(last_gc_api_error="", last_gc_api_ok_at=common.utcnow())
    return True


def resolve_binding(config: dict[str, Any], post: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Resolve the chat binding that owns this post.

    Mattermost threads live inside their parent channel (they are just posts
    sharing a root_id), so unlike Discord there is no parent channel to walk up
    to: the channel id in the event is always the binding key.
    """
    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    channel_type = str(post.get("channel_type", "")).strip().upper()
    channel_info: dict[str, Any] = {}
    if not channel_type:
        bot_token = common.load_bot_token()
        if bot_token:
            try:
                channel_info = load_channel_info(channel_id, bot_token)
            except common.MattermostAPIError as exc:
                if int(getattr(exc, "status_code", 0) or 0) == 404:
                    return None, {}
                raise
            channel_type = str(channel_info.get("type", channel_info.get("channel_type", ""))).strip().upper()
            if not team_id:
                team_id = str(channel_info.get("team_id", "")).strip()
    is_direct = channel_type in common.DIRECT_CHANNEL_TYPES or (not channel_type and not team_id)
    binding_id = common.chat_binding_id("dm" if is_direct else "room", channel_id)
    binding = common.resolve_chat_binding(config, binding_id)
    if is_direct:
        return binding, channel_info
    if not binding:
        return None, channel_info
    binding = dict(binding)
    if binding_allows_ambient_read(binding):
        cached_binding = cached_ambient_room_binding(channel_id)
        if cached_binding:
            binding = cached_binding
    channel_metadata = binding_channel_info(binding)
    if channel_metadata.get("channel_type"):
        return binding, channel_metadata
    cached_channel_metadata = common.load_channel_metadata_cache(channel_id)
    if cached_channel_metadata:
        binding.update(cached_channel_metadata)
        channel_metadata = binding_channel_info(binding)
        if channel_metadata.get("channel_type"):
            return binding, channel_metadata
    bot_token = common.load_bot_token()
    if not bot_token:
        return binding, channel_metadata
    try:
        looked_up_channel_info = load_channel_info(channel_id, bot_token)
    except common.MattermostAPIError:
        return binding, channel_metadata
    binding.update(common.normalize_binding_channel_metadata(looked_up_channel_info))
    persist_binding_channel_metadata(binding)
    return binding, binding_channel_info(binding)


def resolve_targets(
    binding: dict[str, Any],
    mentioned_aliases: list[str],
    *,
    require_targeted_aliases: bool = False,
) -> tuple[list[str], str, str]:
    # Bound room selectors are authoritative. Delivery materializes named
    # sessions on first reference via the core /v0/session/{selector}/messages API.
    participants = [str(item).strip() for item in binding.get("session_names", []) if str(item).strip()]
    participant_lookup, participant_collisions = casefold_lookup(participants)
    if mentioned_aliases:
        for alias in mentioned_aliases:
            key = alias.casefold()
            if key in participant_collisions:
                return [], "targeted", f"ambiguous_alias:{alias}"
            participant_name = participant_lookup.get(key)
            if not participant_name:
                return [], "targeted", f"unknown_alias:{alias}"
        targets: list[str] = []
        for alias in mentioned_aliases:
            participant_name = participant_lookup.get(alias.casefold())
            if not participant_name:
                return [], "targeted", f"unknown_alias:{alias}"
            targets.append(participant_name)
        return targets, "targeted", ""

    if require_targeted_aliases:
        return [], "targeted", "target_required"

    return participants, "broadcast", ""


def binding_allows_ambient_read(binding: dict[str, Any] | None) -> bool:
    if not isinstance(binding, dict):
        return False
    if str(binding.get("kind", "")).strip() != "room":
        return False
    return bool(common.binding_peer_policy(binding).get("ambient_read_enabled"))


def binding_allows_untargeted_ambient_delivery(binding: dict[str, Any] | None) -> bool:
    if not binding_allows_ambient_read(binding):
        return False
    if not isinstance(binding, dict):
        return False
    participants = [str(item).strip() for item in binding.get("session_names", []) if str(item).strip()]
    if len(participants) != 1:
        return False
    return bool(common.binding_peer_policy(binding).get("allow_untargeted_ambient_delivery"))


def explicit_room_binding(config: dict[str, Any], channel_id: str) -> dict[str, Any] | None:
    return common.resolve_chat_binding(config, common.chat_binding_id("room", channel_id))


def bound_room_claims_message(config: dict[str, Any], channel_id: str) -> bool:
    # Mattermost threads share their channel with the room, so the channel
    # binding covers both the root posts and every threaded reply.
    return bool(explicit_room_binding(config, channel_id))


def ambient_bindings_config_signature() -> tuple[int, int, int] | None:
    try:
        stat_result = os.stat(common.config_path())
    except OSError:
        return None
    return (
        int(getattr(stat_result, "st_mtime_ns", 0)),
        int(getattr(stat_result, "st_size", 0)),
        int(getattr(stat_result, "st_ino", 0)),
    )


def cached_ambient_room_binding(channel_id: str) -> dict[str, Any] | None:
    config_signature = ambient_bindings_config_signature()
    with AMBIENT_ROOM_BINDINGS_CACHE_LOCK:
        if AMBIENT_ROOM_BINDINGS_CACHE.get("config_signature") == config_signature:
            bindings = AMBIENT_ROOM_BINDINGS_CACHE.get("bindings", {})
            if isinstance(bindings, dict):
                binding = bindings.get(channel_id)
                return dict(binding) if isinstance(binding, dict) else None

    with AMBIENT_ROOM_BINDINGS_FETCH_LOCK:
        config_signature = ambient_bindings_config_signature()
        with AMBIENT_ROOM_BINDINGS_CACHE_LOCK:
            if AMBIENT_ROOM_BINDINGS_CACHE.get("config_signature") == config_signature:
                bindings = AMBIENT_ROOM_BINDINGS_CACHE.get("bindings", {})
                if isinstance(bindings, dict):
                    binding = bindings.get(channel_id)
                    return dict(binding) if isinstance(binding, dict) else None

        bindings: dict[str, dict[str, Any]] = {}
        try:
            config = common.load_config()
        except (OSError, ValueError, json.JSONDecodeError):
            config = {}
        for binding in common.list_chat_bindings(config):
            if str(binding.get("kind", "")).strip() != "room":
                continue
            if not binding_allows_ambient_read(binding):
                continue
            conversation_id = str(binding.get("conversation_id", "")).strip()
            if conversation_id:
                bindings[conversation_id] = dict(binding)

        with AMBIENT_ROOM_BINDINGS_CACHE_LOCK:
            AMBIENT_ROOM_BINDINGS_CACHE["config_signature"] = config_signature
            AMBIENT_ROOM_BINDINGS_CACHE["bindings"] = bindings
    binding = bindings.get(channel_id)
    return dict(binding) if isinstance(binding, dict) else None


def build_human_envelope(
    *,
    binding: dict[str, Any],
    post: dict[str, Any],
    body: str,
    mentioned_aliases: list[str],
    delivery: str,
    ingress_id: str,
) -> str:
    conversation_value, conversation_key = conversation_fields(post)
    binding_id = str(binding.get("id", "")).strip()
    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    post_id = str(post.get("id", "")).strip()
    root_post_id = message_root_post_id(post)
    # A binding can opt out of threading (bind-room/bind-dm
    # --disable-thread-replies) to force flat, top-level replies instead of
    # threading under the message being answered.
    thread_replies = common.binding_peer_policy(binding).get("thread_replies", True)
    reply_root_arg = f" --root-id {root_post_id}" if (thread_replies and root_post_id) else ""
    reply_tool_line = f"reply_tool: gc mattermost reply-current --conversation-id {channel_id}{reply_root_arg} --body-file <path>"
    if not thread_replies:
        reply_tool_line += " (this binding posts flat — do NOT pass --root-id yourself)"
    publish_root_post_id = root_post_id if thread_replies else ""
    lines = [
        f"<{common.EVENT_TAG}>",
        "version: 1",
        f"kind: {common.HUMAN_MESSAGE_EVENT_KIND}",
        f"binding_id: {binding_id}",
        f"ingress_receipt_id: {ingress_id}",
        f"conversation: {conversation_value}",
        f"conversation_key: {conversation_key}",
        f"team_id: {team_id}",
        f"channel_id: {channel_id}",
        f"root_id: {root_post_id}",
        f"mattermost_post_id: {post_id}",
        f"from_display: {display_name_from_message(post)}",
        f"from_username: {str(post.get('from_username', '')).strip()}",
        f"from_user_id: {str(post.get('user_id', '')).strip()}",
        f"delivery: {delivery}",
        f"mentioned_aliases_json: {json.dumps(mentioned_aliases)}",
        f"untrusted_body_json: {json.dumps(body)}",
        f"publish_binding_id: {binding_id}",
        f"publish_conversation_id: {channel_id}",
        f"publish_trigger_id: {post_id}",
        f"publish_root_post_id: {publish_root_post_id}",
        "normal_output_visibility: internal_only",
        "reply_contract: explicit_publish_required",
        reply_tool_line,
        "reply_success_signal: record.remote_message_id",
        "reply_turn_requirement: if you intend to answer, do not end the turn without a successful reply-current",
        f"</{common.EVENT_TAG}>",
    ]
    return "\n".join(lines)


def build_room_launch_envelope(
    *,
    launcher: dict[str, Any],
    launch: dict[str, Any],
    post: dict[str, Any],
    body: str,
    mentioned_handles: list[str],
    ingress_id: str,
) -> str:
    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    post_id = str(post.get("id", "")).strip()
    root_post_id = message_root_post_id(post)
    lines = [
        f"<{common.EVENT_TAG}>",
        "version: 1",
        f"kind: {common.HUMAN_MESSAGE_EVENT_KIND}",
        f"binding_id: {str(launcher.get('id', '')).strip()}",
        f"ingress_receipt_id: {ingress_id}",
        f"conversation: team:{team_id} channel:{channel_id}",
        f"conversation_key: {common.mattermost_conversation_key(channel_id, root_post_id)}",
        f"team_id: {team_id}",
        f"channel_id: {channel_id}",
        f"root_id: {root_post_id}",
        f"mattermost_post_id: {post_id}",
        f"from_display: {display_name_from_message(post)}",
        f"from_username: {str(post.get('from_username', '')).strip()}",
        f"from_user_id: {str(post.get('user_id', '')).strip()}",
        "delivery: targeted",
        f"mentioned_handles_json: {json.dumps(mentioned_handles)}",
        f"launch_id: {str(launch.get('launch_id', '')).strip()}",
        "launch_surface_kind: room",
        f"launch_qualified_handle: {str(launch.get('qualified_handle', '')).strip()}",
        f"launch_session_alias: {str(launch.get('session_alias', '')).strip()}",
        f"launch_session_name: {str(launch.get('session_name', '')).strip()}",
        f"thread_participants_json: {json.dumps(common.room_launch_participant_summaries(launch))}",
        f"untrusted_body_json: {json.dumps(body)}",
        f"publish_binding_id: {str(launcher.get('id', '')).strip()}",
        f"publish_conversation_id: {channel_id}",
        f"publish_trigger_id: {post_id}",
        f"publish_root_post_id: {root_post_id}",
        f"publish_launch_id: {str(launch.get('launch_id', '')).strip()}",
        "normal_output_visibility: internal_only",
        "reply_contract: explicit_publish_required",
        "reply_tool: gc mattermost reply-current --body-file <path>",
        "reply_success_signal: record.remote_message_id",
        "reply_turn_requirement: if you intend to answer, do not end the turn without a successful reply-current",
        "peer_targeting_rule: include @@rig/alias in the Mattermost reply if you want another launcher participant to receive it as peer input",
        f"</{common.EVENT_TAG}>",
    ]
    return "\n".join(lines)


def build_room_launch_thread_envelope(
    *,
    launcher: dict[str, Any],
    launch: dict[str, Any],
    target_participant: dict[str, Any],
    post: dict[str, Any],
    body: str,
    mentioned_handles: list[str],
    ingress_id: str,
    routing_mode: str,
    reply_to_id: str,
) -> str:
    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    post_id = str(post.get("id", "")).strip()
    root_post_id = message_root_post_id(post)
    target_qualified_handle = str(target_participant.get("qualified_handle", "")).strip() or str(launch.get("qualified_handle", "")).strip()
    target_session_alias = str(target_participant.get("session_alias", "")).strip() or str(launch.get("session_alias", "")).strip()
    target_session_name = str(target_participant.get("session_name", "")).strip()
    lines = [
        f"<{common.EVENT_TAG}>",
        "version: 1",
        f"kind: {common.HUMAN_MESSAGE_EVENT_KIND}",
        f"binding_id: {str(launcher.get('id', '')).strip()}",
        f"ingress_receipt_id: {ingress_id}",
        f"conversation: team:{team_id} channel:{channel_id} thread:{root_post_id}",
        f"conversation_key: {common.mattermost_conversation_key(channel_id, root_post_id)}",
        f"team_id: {team_id}",
        f"channel_id: {channel_id}",
        f"root_id: {root_post_id}",
        f"mattermost_post_id: {post_id}",
        f"from_display: {display_name_from_message(post)}",
        f"from_username: {str(post.get('from_username', '')).strip()}",
        f"from_user_id: {str(post.get('user_id', '')).strip()}",
        "delivery: targeted",
        f"routing_mode: {routing_mode}",
        f"reply_to_mattermost_post_id: {reply_to_id}",
        f"mentioned_handles_json: {json.dumps(mentioned_handles)}",
        f"launch_id: {str(launch.get('launch_id', '')).strip()}",
        "launch_surface_kind: room",
        f"launch_root_qualified_handle: {str(launch.get('qualified_handle', '')).strip()}",
        f"launch_root_session_alias: {str(launch.get('session_alias', '')).strip()}",
        f"launch_qualified_handle: {target_qualified_handle}",
        f"launch_session_alias: {target_session_alias}",
        f"launch_session_name: {target_session_name}",
        f"thread_participants_json: {json.dumps(common.room_launch_participant_summaries(launch))}",
        f"untrusted_body_json: {json.dumps(body)}",
        f"publish_binding_id: {str(launcher.get('id', '')).strip()}",
        f"publish_conversation_id: {channel_id}",
        f"publish_trigger_id: {post_id}",
        f"publish_root_post_id: {root_post_id}",
        f"publish_launch_id: {str(launch.get('launch_id', '')).strip()}",
        "normal_output_visibility: internal_only",
        "reply_contract: explicit_publish_required",
        "reply_tool: gc mattermost reply-current --body-file <path>",
        "reply_success_signal: record.remote_message_id",
        "reply_turn_requirement: if you intend to answer, do not end the turn without a successful reply-current",
        "peer_targeting_rule: include @@rig/alias in the Mattermost reply if you want another launcher participant to receive it as peer input",
        f"</{common.EVENT_TAG}>",
    ]
    return "\n".join(lines)


def persist_ingress_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    return common.save_chat_ingress(payload)


def base_receipt_identity(post: dict[str, Any], bot_username: str) -> dict[str, Any]:
    return {
        "mattermost_post_id": str(post.get("id", "")).strip(),
        "team_id": str(post.get("team_id", "")).strip(),
        "conversation_id": str(post.get("channel_id", "")).strip(),
        "root_post_id": message_root_post_id(post),
        "from_user_id": str(post.get("user_id", "")).strip(),
        "from_display": display_name_from_message(post),
        "body_preview": ingress_preview(post, bot_username),
    }


def save_rejected_ingress_receipt(
    post: dict[str, Any],
    bot_username: str,
    *,
    status: str,
    reason: str,
    message_debug: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any]]:
    ingress_id = message_ingress_id(post)
    return common.save_chat_ingress_if_absent(
        {
            "ingress_id": ingress_id,
            **base_receipt_identity(post, bot_username),
            "binding_id": "",
            "status": status,
            "reason": reason,
            "message_debug": dict(message_debug or {}),
            "targets": [],
        }
    )


def reject_ingress_before_processing(
    post: dict[str, Any],
    bot_username: str,
    *,
    status: str,
    reason: str,
    message_debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ingress_id = message_ingress_id(post)
    claimed, receipt = save_rejected_ingress_receipt(
        post,
        bot_username,
        status=status,
        reason=reason,
        message_debug=message_debug,
    )
    if claimed:
        return {"status": status, "reason": reason, "ingress_id": ingress_id, "receipt": receipt}
    if str(receipt.get("status", "")).strip() == "claim_conflict_unreadable":
        receipt = persist_ingress_receipt(
            {
                **receipt,
                "ingress_id": ingress_id,
                **base_receipt_identity(post, bot_username),
                "binding_id": "",
                "status": "failed_claim_conflict",
                "reason": str(receipt.get("reason", "")).strip() or "ingress_claim_unreadable",
                "message_debug": dict(message_debug or {}),
                "targets": [],
            }
        )
        return {"status": "failed_claim_conflict", "ingress_id": ingress_id, "receipt": receipt}
    return {"status": "duplicate", "ingress_id": ingress_id, "receipt": receipt}


def process_room_launch_message(
    *,
    base_receipt: dict[str, Any],
    launcher: dict[str, Any],
    post: dict[str, Any],
    bot_username: str,
    ingress_id: str,
    message_debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = strip_bot_mentions(raw_message_content(post), bot_username)
    if not body:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "ignored_empty",
                "reason": empty_body_reason(post, message_debug),
                "message_debug": dict(message_debug or {}),
                "targets": [],
            }
        )
        return {"status": "ignored_empty", "ingress_id": ingress_id, "receipt": receipt}

    mentioned_handles = common.extract_agent_handles(body)
    response_mode = str(launcher.get("response_mode", "mention_only")).strip() or "mention_only"
    reply_to_id = referenced_post_id(post)
    if len(mentioned_handles) > 1:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "rejected_targeting",
                "reason": "multiple_handles_not_supported",
                "mentioned_handles": mentioned_handles,
                "targets": [],
            }
        )
        return {"status": "rejected_targeting", "ingress_id": ingress_id, "receipt": receipt}

    requested_handle = mentioned_handles[0] if mentioned_handles else ""
    used_default_handle = False
    if not requested_handle:
        if response_mode != "respond_all":
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(launcher.get("id", "")).strip(),
                    "status": "ignored_untargeted",
                    "reason": "launch_handle_required",
                    "targets": [],
                }
            )
            return {"status": "ignored_untargeted", "ingress_id": ingress_id, "receipt": receipt}
        if reply_to_id:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(launcher.get("id", "")).strip(),
                    "status": "ignored_untargeted",
                    "reason": "respond_all_root_reply_requires_handle",
                    "targets": [],
                }
            )
            return {"status": "ignored_untargeted", "ingress_id": ingress_id, "receipt": receipt}
        requested_handle = str(launcher.get("default_qualified_handle", "")).strip()
        if not requested_handle:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(launcher.get("id", "")).strip(),
                    "status": "ignored_untargeted",
                    "reason": "launch_handle_required",
                    "targets": [],
                }
            )
            return {"status": "ignored_untargeted", "ingress_id": ingress_id, "receipt": receipt}
        used_default_handle = True

    if used_default_handle:
        qualified_handle, resolve_error = requested_handle, ""
    else:
        try:
            qualified_handle, resolve_error = common.resolve_agent_handle(requested_handle)
        except common.GCAPIError as exc:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(launcher.get("id", "")).strip(),
                    "status": "failed_lookup",
                    "reason": str(exc),
                    "targets": [],
                }
            )
            return {"status": "failed_lookup", "ingress_id": ingress_id, "receipt": receipt}
    if resolve_error:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "rejected_targeting",
                "reason": resolve_error,
                "mentioned_handles": mentioned_handles,
                "targets": [],
            }
        )
        return {"status": "rejected_targeting", "ingress_id": ingress_id, "receipt": receipt}

    root_post_id = str(post.get("id", "")).strip()
    launch_id = common.room_launch_record_id(root_post_id)
    existing_launch = common.load_room_launch(launch_id) or {}
    launch = common.save_room_launch(
        {
            **existing_launch,
            "launch_id": launch_id,
            "state": str(existing_launch.get("state", "")).strip() or "pending_thread",
            "launcher_id": str(launcher.get("id", "")).strip(),
            "team_id": str(post.get("team_id", "")).strip(),
            "conversation_id": str(post.get("channel_id", "")).strip(),
            "root_post_id": root_post_id,
            "qualified_handle": qualified_handle,
            "session_alias": str(existing_launch.get("session_alias", "")).strip()
            or common.room_launch_session_alias(
                str(post.get("team_id", "")).strip(),
                str(post.get("channel_id", "")).strip(),
                root_post_id,
                qualified_handle,
            ),
            "from_user_id": str(post.get("user_id", "")).strip(),
            "from_display": display_name_from_message(post),
            "body_preview": ingress_preview(post, bot_username),
        }
    )
    try:
        launch = common.ensure_room_launch_session(launch)
    except (ValueError, common.GCAPIError) as exc:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "failed_lookup",
                "reason": str(exc),
                "mentioned_handles": mentioned_handles,
                "targets": [],
            }
        )
        return {"status": "failed_lookup", "ingress_id": ingress_id, "receipt": receipt}

    target_selector = participant_delivery_selector(launch)
    receipt = persist_ingress_receipt(
        {
            **base_receipt,
            "binding_id": str(launcher.get("id", "")).strip(),
            "status": "pending",
            "delivery": "targeted",
            "route_kind": "room_launch",
            "launch_id": launch_id,
            "mentioned_handles": mentioned_handles,
            "qualified_handle": qualified_handle,
            "targets": [{"session_name": target_selector, "status": "pending"}],
        }
    )
    envelope = build_room_launch_envelope(
        launcher=launcher,
        launch=launch,
        post=post,
        body=body,
        mentioned_handles=mentioned_handles,
        ingress_id=ingress_id,
    )
    try:
        response = common.deliver_session_message(
            target_selector,
            envelope,
            idempotency_key=f"ingress:{ingress_id}:target:{target_selector}",
        )
    except common.GCAPIError as exc:
        receipt["status"] = "failed"
        receipt["targets"] = [{"session_name": target_selector, "status": "failed", "error": str(exc)}]
        receipt = persist_ingress_receipt(receipt)
        return {"status": "failed", "ingress_id": ingress_id, "receipt": receipt}
    receipt["status"] = "delivered"
    receipt["targets"] = [{"session_name": target_selector, "status": "delivered", "response": response}]
    receipt = persist_ingress_receipt(receipt)
    return {"status": "delivered", "ingress_id": ingress_id, "receipt": receipt}


def process_room_launch_thread_message(
    *,
    base_receipt: dict[str, Any],
    launcher: dict[str, Any],
    launch: dict[str, Any],
    post: dict[str, Any],
    bot_username: str,
    ingress_id: str,
    message_debug: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refreshed_launch = common.touch_room_launch(str(launch.get("launch_id", "")).strip())
    if isinstance(refreshed_launch, dict):
        launch = refreshed_launch
    body = strip_bot_mentions(raw_message_content(post), bot_username)
    if not body:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "ignored_empty",
                "reason": empty_body_reason(post, message_debug),
                "message_debug": dict(message_debug or {}),
                "targets": [],
            }
        )
        return {"status": "ignored_empty", "ingress_id": ingress_id, "receipt": receipt}
    mentioned_handles = common.extract_agent_handles(body)
    reply_to_id = referenced_post_id(post)
    if len(mentioned_handles) > 1:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "rejected_targeting",
                "reason": "multiple_handles_not_supported",
                "mentioned_handles": mentioned_handles,
                "targets": [],
            }
        )
        return {"status": "rejected_targeting", "ingress_id": ingress_id, "receipt": receipt}
    target_handle = ""
    routing_mode = ""
    if mentioned_handles:
        try:
            qualified_handle, resolve_error = common.resolve_agent_handle(mentioned_handles[0])
        except common.GCAPIError as exc:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(launcher.get("id", "")).strip(),
                    "status": "failed_lookup",
                    "reason": str(exc),
                    "targets": [],
                }
            )
            return {"status": "failed_lookup", "ingress_id": ingress_id, "receipt": receipt}
        if resolve_error:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(launcher.get("id", "")).strip(),
                    "status": "rejected_targeting",
                    "reason": resolve_error,
                    "mentioned_handles": mentioned_handles,
                    "targets": [],
                }
            )
            return {"status": "rejected_targeting", "ingress_id": ingress_id, "receipt": receipt}
        target_handle = qualified_handle
        routing_mode = "explicit_handle"
    if not target_handle and reply_to_id:
        target_handle = common.room_launch_message_target_handle(launch, reply_to_id)
        if target_handle:
            routing_mode = "reply_to"
    if not target_handle:
        target_handle = str(launch.get("last_addressed_qualified_handle", "")).strip()
        if target_handle:
            routing_mode = "last_addressed"
    if not target_handle:
        target_handle = str(launch.get("qualified_handle", "")).strip()
        if target_handle:
            routing_mode = "launch_default"
    if not target_handle:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "failed_lookup",
                "reason": "missing_thread_target",
                "targets": [],
            }
        )
        return {"status": "failed_lookup", "ingress_id": ingress_id, "receipt": receipt}
    try:
        launch, target_participant = common.ensure_room_launch_session_for_handle(launch, target_handle)
    except (ValueError, common.GCAPIError) as exc:
        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(launcher.get("id", "")).strip(),
                "status": "failed_lookup",
                "reason": str(exc),
                "targets": [],
            }
        )
        return {"status": "failed_lookup", "ingress_id": ingress_id, "receipt": receipt}
    target_selector = participant_delivery_selector(target_participant)

    receipt = persist_ingress_receipt(
        {
            **base_receipt,
            "binding_id": str(launcher.get("id", "")).strip(),
            "status": "pending",
            "delivery": "targeted",
            "route_kind": "room_launch_thread",
            "launch_id": str(launch.get("launch_id", "")).strip(),
            "routing_mode": routing_mode,
            "mentioned_handles": mentioned_handles,
            "qualified_handle": target_handle,
            "targets": [{"session_name": target_selector, "status": "pending"}],
        }
    )
    envelope = build_room_launch_thread_envelope(
        launcher=launcher,
        launch=launch,
        target_participant=target_participant,
        post=post,
        body=body,
        mentioned_handles=mentioned_handles,
        ingress_id=ingress_id,
        routing_mode=routing_mode,
        reply_to_id=reply_to_id,
    )
    try:
        response = common.deliver_session_message(
            target_selector,
            envelope,
            idempotency_key=f"ingress:{ingress_id}:target:{target_selector}",
        )
    except common.GCAPIError as exc:
        receipt["status"] = "failed"
        receipt["targets"] = [{"session_name": target_selector, "status": "failed", "error": str(exc)}]
        receipt = persist_ingress_receipt(receipt)
        return {"status": "failed", "ingress_id": ingress_id, "receipt": receipt}
    updated_launch = common.set_room_launch_last_addressed(str(launch.get("launch_id", "")).strip(), target_handle)
    if isinstance(updated_launch, dict):
        launch = updated_launch
    receipt["status"] = "delivered"
    receipt["targets"] = [{"session_name": target_selector, "status": "delivered", "response": response}]
    receipt = persist_ingress_receipt(receipt)
    return {"status": "delivered", "ingress_id": ingress_id, "receipt": receipt}


def process_inbound_message(post: dict[str, Any], bot_user_id: str, bot_username: str) -> dict[str, Any]:
    ingress_id = message_ingress_id(post)
    if common.post_is_from_bot(post, bot_user_id) or common.post_is_system(post):
        return {"status": "ignored", "reason": "bot_message", "ingress_id": ingress_id}

    team_id = str(post.get("team_id", "")).strip()
    channel_id = str(post.get("channel_id", "")).strip()
    root_id = str(post.get("root_id", "")).strip()
    if not channel_id:
        return {"status": "ignored", "reason": "missing_channel", "ingress_id": ingress_id}

    post, message_debug = recover_message_for_routing(post)
    root_id = str(post.get("root_id", "")).strip()

    config = common.load_config()
    room_launchers_configured = bool(common.list_room_launchers(config)) if team_id else False
    mentioned_bot = bot_was_mentioned(post, bot_user_id, bot_username) if team_id else False
    preloaded_launcher: dict[str, Any] | None = None
    preloaded_launch: dict[str, Any] | None = None
    preloaded_binding: dict[str, Any] | None = None
    preloaded_body: str | None = None
    preloaded_aliases: list[str] | None = None
    if team_id:
        if room_launchers_configured:
            if root_id:
                # A Mattermost thread is identified by the root post id, so the
                # launch record id is derived from root_id rather than from a
                # separate thread channel id the way Discord does it.
                launch = common.load_room_launch(common.room_launch_record_id(root_id))
                if launch and str(launch.get("root_post_id", "")).strip() == root_id:
                    launcher_id = str(launch.get("launcher_id", "")).strip()
                    launcher_conversation_id = launcher_id.removeprefix("launch-room:")
                    preloaded_launcher = common.resolve_room_launcher(config, launcher_conversation_id)
                    if preloaded_launcher:
                        preloaded_launch = launch
            elif not root_id:
                preloaded_launcher = common.resolve_room_launcher(config, channel_id)
        if preloaded_launcher is None and not mentioned_bot:
            preloaded_binding = cached_ambient_room_binding(channel_id)
            if not preloaded_binding or not binding_allows_ambient_read(preloaded_binding):
                return {"status": "ignored", "reason": "not_mentioned", "ingress_id": ingress_id}
            preloaded_body = strip_bot_mentions(raw_message_content(post), bot_username)
            preloaded_aliases = extract_alias_mentions(preloaded_body)
            sticky_single_session_delivery = binding_allows_untargeted_ambient_delivery(preloaded_binding)
            if not preloaded_aliases and not sticky_single_session_delivery:
                return reject_ingress_before_processing(
                    post,
                    bot_username,
                    status="ignored_untargeted",
                    reason="ambient_target_required",
                    message_debug=message_debug,
                )
            participant_names = [str(item).strip() for item in preloaded_binding.get("session_names", []) if str(item).strip()]
            participant_lookup, participant_collisions = casefold_lookup(participant_names)
            has_valid_preloaded_alias = False
            for alias in preloaded_aliases:
                key = alias.casefold()
                if key in participant_collisions:
                    continue
                if participant_lookup.get(key):
                    has_valid_preloaded_alias = True
                    break
            if preloaded_aliases and not has_valid_preloaded_alias and not sticky_single_session_delivery:
                return reject_ingress_before_processing(
                    post,
                    bot_username,
                    status="ignored_untargeted",
                    reason="ambient_target_required",
                    message_debug=message_debug,
                )

    preview = ingress_preview(post, bot_username)
    identity = base_receipt_identity(post, bot_username)
    claimed, base_receipt = common.save_chat_ingress_if_absent(
        {
            "ingress_id": ingress_id,
            **identity,
            "binding_id": "",
            "message_debug": dict(message_debug or {}),
            "status": "processing",
            "targets": [],
        }
    )
    if not claimed:
        receipt_status = str(base_receipt.get("status", "")).strip()
        receipt_age = utc_age_seconds(str(base_receipt.get("updated_at", "")).strip())
        if receipt_status == "claim_conflict_unreadable":
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "ingress_id": ingress_id,
                    **identity,
                    "binding_id": "",
                    "message_debug": dict(message_debug or {}),
                    "status": "failed_claim_conflict",
                    "reason": str(base_receipt.get("reason", "")).strip() or "ingress_claim_unreadable",
                    "targets": [],
                }
            )
            return {"status": "failed_claim_conflict", "ingress_id": ingress_id, "receipt": receipt}
        if receipt_status in {"processing", "failed", "partial_failed", "failed_lookup", "failed_claim_conflict", "rejected_shutting_down"} and (
            (receipt_status == "processing" and receipt_age >= STALE_PROCESSING_RECEIPT_SECONDS)
            or (
                receipt_status in {"failed", "partial_failed", "failed_lookup", "failed_claim_conflict"}
                and receipt_age >= FAILED_RECEIPT_RETRY_SECONDS
            )
            or receipt_status == "rejected_shutting_down"
        ):
            reclaim_lock = stale_reclaim_lock(ingress_id)
            if not reclaim_lock.acquire(blocking=False):
                return {"status": "duplicate", "ingress_id": ingress_id, "receipt": base_receipt}
            try:
                latest_receipt = common.load_chat_ingress(ingress_id) or base_receipt
                latest_status = str(latest_receipt.get("status", "")).strip()
                latest_age = utc_age_seconds(str(latest_receipt.get("updated_at", "")).strip())
                if not (
                    (latest_status == "processing" and latest_age >= STALE_PROCESSING_RECEIPT_SECONDS)
                    or (
                        latest_status in {"failed", "partial_failed", "failed_lookup", "failed_claim_conflict"}
                        and latest_age >= FAILED_RECEIPT_RETRY_SECONDS
                    )
                    or latest_status == "rejected_shutting_down"
                ):
                    return {"status": "duplicate", "ingress_id": ingress_id, "receipt": latest_receipt}
                retry_reason = "stale_processing_reclaimed"
                if latest_status in {"failed", "partial_failed", "failed_lookup"}:
                    retry_reason = "retry_after_failed_delivery"
                if latest_status == "failed_lookup":
                    retry_reason = "retry_after_failed_lookup"
                if latest_status == "failed_claim_conflict":
                    retry_reason = "retry_after_failed_claim_conflict"
                if latest_status == "rejected_shutting_down":
                    retry_reason = "retry_after_shutdown"
                base_receipt = persist_ingress_receipt(
                    {
                        **latest_receipt,
                        "ingress_id": ingress_id,
                        **identity,
                        "binding_id": "",
                        "message_debug": dict(message_debug or {}),
                        "status": "processing",
                        "reason": retry_reason,
                        "targets": [],
                    }
                )
                claimed = True
            finally:
                reclaim_lock.release()
        else:
            return {"status": "duplicate", "ingress_id": ingress_id, "receipt": base_receipt}

    process_lock = ingress_process_lock(ingress_id)
    if not process_lock.acquire(blocking=False):
        return {"status": "duplicate", "ingress_id": ingress_id, "receipt": common.load_chat_ingress(ingress_id) or base_receipt}
    try:
        launcher = preloaded_launcher
        launch = preloaded_launch
        binding = preloaded_binding
        if launcher is None and binding is None:
            config = common.load_config()
            try:
                binding, _channel_info = resolve_binding(config, post)
            except common.MattermostAPIError as exc:
                receipt = persist_ingress_receipt(
                    {
                        **base_receipt,
                        "status": "failed_lookup",
                        "reason": str(exc),
                        "targets": [],
                    }
                )
                return {"status": "failed_lookup", "ingress_id": ingress_id, "receipt": receipt}
        base_receipt.update(
            {
                "ingress_id": ingress_id,
                **identity,
                "binding_id": str((launcher or binding or {}).get("id", "")).strip(),
                "body_preview": preview,
            }
        )
        if launcher and launch:
            return process_room_launch_thread_message(
                base_receipt=base_receipt,
                launcher=launcher,
                launch=launch,
                post=post,
                bot_username=bot_username,
                ingress_id=ingress_id,
                message_debug=message_debug,
            )
        if launcher:
            return process_room_launch_message(
                base_receipt=base_receipt,
                launcher=launcher,
                post=post,
                bot_username=bot_username,
                ingress_id=ingress_id,
                message_debug=message_debug,
            )
        if not binding:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "status": "rejected_unbound",
                    "reason": "binding_not_found",
                    "targets": [],
                }
            )
            return {"status": "rejected_unbound", "ingress_id": ingress_id, "receipt": receipt}

        body = preloaded_body if preloaded_body is not None else strip_bot_mentions(raw_message_content(post), bot_username)
        if not body:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(binding.get("id", "")).strip(),
                    "status": "ignored_empty",
                    "reason": empty_body_reason(post, message_debug),
                    "message_debug": dict(message_debug or {}),
                    "targets": [],
                }
            )
            return {"status": "ignored_empty", "ingress_id": ingress_id, "receipt": receipt}

        mentioned_aliases = preloaded_aliases if preloaded_aliases is not None else extract_alias_mentions(body)
        target_aliases = [] if binding_allows_untargeted_ambient_delivery(binding) else mentioned_aliases
        targets, delivery, resolve_error = resolve_targets(
            binding,
            target_aliases,
            require_targeted_aliases=bool(
                binding_allows_ambient_read(binding) and team_id and not binding_allows_untargeted_ambient_delivery(binding)
            ),
        )
        if resolve_error:
            if resolve_error == "target_required":
                receipt = persist_ingress_receipt(
                    {
                        **base_receipt,
                        "binding_id": str(binding.get("id", "")).strip(),
                        "status": "ignored_untargeted",
                        "reason": "ambient_target_required",
                        "mentioned_aliases": mentioned_aliases,
                        "targets": [],
                    }
                )
                return {"status": "ignored_untargeted", "ingress_id": ingress_id, "receipt": receipt}
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(binding.get("id", "")).strip(),
                    "status": "rejected_targeting",
                    "reason": resolve_error,
                    "mentioned_aliases": mentioned_aliases,
                    "targets": [],
                }
            )
            return {"status": "rejected_targeting", "ingress_id": ingress_id, "receipt": receipt}
        if not targets:
            receipt = persist_ingress_receipt(
                {
                    **base_receipt,
                    "binding_id": str(binding.get("id", "")).strip(),
                    "status": "skipped_no_targets",
                    "reason": "no_targets",
                    "mentioned_aliases": mentioned_aliases,
                    "targets": [],
                }
            )
            return {"status": "skipped_no_targets", "ingress_id": ingress_id, "receipt": receipt}

        receipt = persist_ingress_receipt(
            {
                **base_receipt,
                "binding_id": str(binding.get("id", "")).strip(),
                "status": "pending",
                "mentioned_aliases": mentioned_aliases,
                "delivery": delivery,
                "targets": [{"session_name": target, "status": "pending"} for target in targets],
            }
        )
        envelope = build_human_envelope(
            binding=binding,
            post=post,
            body=body,
            mentioned_aliases=mentioned_aliases,
            delivery=delivery,
            ingress_id=ingress_id,
        )
        updated_targets: list[dict[str, Any]] = []
        failures = 0
        for target in targets:
            idempotency_key = f"ingress:{ingress_id}:target:{target}"
            try:
                response = common.deliver_session_message(
                    target,
                    envelope,
                    idempotency_key=idempotency_key,
                    intent="follow_up",
                )
                updated_targets.append(
                    {
                        "session_name": target,
                        "status": "delivered",
                        "idempotency_key": idempotency_key,
                        "response": response,
                    }
                )
            except common.GCAPIError as exc:
                failures += 1
                updated_targets.append(
                    {
                        "session_name": target,
                        "status": "failed",
                        "idempotency_key": idempotency_key,
                        "error": str(exc),
                    }
                )
        receipt["targets"] = updated_targets
        receipt["status"] = "delivered" if failures == 0 else ("partial_failed" if failures < len(targets) else "failed")
        receipt["delivery"] = delivery
        receipt["mentioned_aliases"] = mentioned_aliases
        receipt = persist_ingress_receipt(receipt)
        return {"status": receipt["status"], "ingress_id": ingress_id, "receipt": receipt}
    finally:
        process_lock.release()


class GatewayRuntimeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_persist_monotonic = 0.0
        self._status: dict[str, Any] = {
            "service": common.GATEWAY_SERVICE_NAME,
            "connected": False,
            "state": "starting",
            "routed_messages": 0,
            "duplicate_messages": 0,
            "ignored_messages": 0,
            "failed_messages": 0,
            "dropped_messages": 0,
            "message_queue_size": 0,
        }
        self._persist_locked(force=True)

    def _persist_locked(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or (now - self._last_persist_monotonic) >= 1.0:
            common.save_gateway_status(self._status)
            self._last_persist_monotonic = now

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def patch(self, **values: Any) -> None:
        with self._lock:
            self._status.update(values)
            force = bool({"state", "connected", "last_error", "last_disconnect_at", "last_ready_at", "last_resumed_at"} & set(values))
            self._persist_locked(force=force)

    def bump(self, field: str, delta: int = 1, **values: Any) -> None:
        with self._lock:
            self._status[field] = int(self._status.get(field, 0) or 0) + delta
            self._status.update(values)
            force = bool({"state", "connected", "last_error", "last_disconnect_at", "last_ready_at", "last_resumed_at"} & set(values))
            self._persist_locked(force=force)


class GatewayWebSocket:
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self._recv_buffer = bytearray()
        self.last_frame_at = time.monotonic()
        self._closed = False
        self.sock = self._connect(url, headers or {})
        self._send_lock = threading.Lock()

    def _connect(self, url: str, extra_headers: dict[str, str]) -> socket.socket:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        if not host:
            raise RuntimeError(f"gateway URL missing hostname: {url}")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        raw_sock = socket.create_connection((host, port), timeout=20)
        if parsed.scheme == "wss":
            context = ssl.create_default_context()
            sock = context.wrap_socket(raw_sock, server_hostname=host)
        else:
            sock = raw_sock
        sock.settimeout(20)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        header_lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        for name, value in extra_headers.items():
            normalized_name = str(name).strip()
            normalized_value = " ".join(str(value).split())
            if normalized_name and normalized_value:
                header_lines.append(f"{normalized_name}: {normalized_value}")
        request = "\r\n".join(header_lines) + "\r\n\r\n"
        sock.sendall(request.encode("utf-8"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("websocket handshake closed early")
            response += chunk
        header_bytes, remainder = response.split(b"\r\n\r\n", 1)
        self._recv_buffer.extend(remainder)
        header_blob = header_bytes.decode("utf-8", errors="replace")
        validate_websocket_handshake(header_blob, key)
        self.last_frame_at = time.monotonic()
        return sock

    def close(self, code: int = 1000, reason: str = "") -> None:
        if self._closed:
            return
        self._closed = True
        try:
            payload = b""
            if int(code or 0):
                payload = struct.pack("!H", int(code)) + str(reason).encode("utf-8")[:123]
            self.send_frame(0x8, payload)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.sock.close()
        except OSError:
            return

    def read_exact(self, length: int, timeout: float | None = None) -> bytes:
        if timeout is not None:
            self.sock.settimeout(timeout)
        data = bytearray()
        if self._recv_buffer:
            take = min(length, len(self._recv_buffer))
            data.extend(self._recv_buffer[:take])
            del self._recv_buffer[:take]
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise WebSocketClosed("socket closed")
            data.extend(chunk)
        return bytes(data)

    def read_frame(self, timeout: float | None = None) -> tuple[bool, int, bytes]:
        try:
            head = self.read_exact(2, timeout=timeout)
        except TimeoutError as exc:
            raise GatewayFrameTimeout("timed out waiting for gateway frame header") from exc
        fin = bool(head[0] & 0x80)
        opcode = head[0] & 0x0F
        masked = (head[1] & 0x80) != 0
        length = head[1] & 0x7F
        try:
            if length == 126:
                length = struct.unpack("!H", self.read_exact(2, timeout=20.0))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.read_exact(8, timeout=20.0))[0]
            if length > MAX_FRAME_BYTES:
                raise WebSocketClosed(f"gateway frame too large: {length}")
            mask = self.read_exact(4, timeout=20.0) if masked else b""
            payload = self.read_exact(length, timeout=20.0) if length else b""
        except TimeoutError as exc:
            raise WebSocketClosed("timed out while reading gateway frame payload") from exc
        if masked and mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.last_frame_at = time.monotonic()
        return fin, opcode, payload

    def send_frame(self, opcode: int, payload: bytes) -> None:
        length = len(payload)
        first = 0x80 | (opcode & 0x0F)
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length < (1 << 16):
            header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
        else:
            header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
        mask = os.urandom(4)
        masked_payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        with self._send_lock:
            self.sock.sendall(header + mask + masked_payload)

    def send_json(self, payload: dict[str, Any]) -> None:
        self.send_frame(0x1, json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    def send_ping(self, payload: bytes = b"gc") -> None:
        self.send_frame(0x9, payload)

    def recv_event(self, timeout: float | None = None) -> dict[str, Any] | None:
        fragments: list[bytes] = []
        while True:
            fin, opcode, payload = self.read_frame(timeout=timeout if not fragments else 20.0)
            if opcode == 0x1:
                if fin:
                    return json.loads(payload.decode("utf-8"))
                fragments = [payload]
                continue
            if opcode == 0x0:
                if not fragments:
                    raise WebSocketClosed("unexpected continuation frame")
                fragments.append(payload)
                if sum(len(part) for part in fragments) > MAX_FRAME_BYTES:
                    raise WebSocketClosed("gateway message too large")
                if fin:
                    return json.loads(b"".join(fragments).decode("utf-8"))
                continue
            if opcode == 0x8:
                raise WebSocketClosed("gateway requested close")
            if opcode == 0x9:
                self.send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                return None
            raise WebSocketClosed(f"unsupported websocket opcode: {opcode}")


class GatewayWorker:
    def __init__(self, runtime_state: GatewayRuntimeState) -> None:
        self.runtime_state = runtime_state
        self.stop_event = threading.Event()
        self._stopped = False
        self._stop_lock = threading.Lock()
        self.message_queue: queue.Queue[tuple[dict[str, Any], str, str] | None] = queue.Queue(maxsize=GATEWAY_MAX_PENDING_MESSAGES)
        self.worker_threads: list[threading.Thread] = []
        self._current_ws_lock = threading.Lock()
        self._current_ws: GatewayWebSocket | None = None
        for index in range(GATEWAY_WORKER_THREADS):
            thread = threading.Thread(target=self.message_worker_loop, name=f"mattermost-gateway-worker-{index + 1}")
            thread.start()
            self.worker_threads.append(thread)

    def set_current_ws(self, ws: GatewayWebSocket | None) -> None:
        with self._current_ws_lock:
            self._current_ws = ws

    def close_current_ws(self) -> None:
        with self._current_ws_lock:
            ws = self._current_ws
        if ws is not None:
            ws.close()

    def request_stop(self) -> None:
        self.stop_event.set()
        self.close_current_ws()

    def stop(self) -> None:
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
        self.runtime_state.patch(state="stopping", connected=False)
        self.request_stop()
        for _ in self.worker_threads:
            self.message_queue.put(WORKER_QUEUE_SENTINEL)
        self.message_queue.join()
        for thread in self.worker_threads:
            thread.join()
        self.runtime_state.patch(state="stopped", connected=False, message_queue_size=self.message_queue.qsize())

    def current_bot_identity(
        self,
        config: dict[str, Any],
        last_known: tuple[str, str] = ("", ""),
    ) -> tuple[str, str]:
        bot_user_id, bot_username = load_bot_identity(config)
        if bot_user_id or bot_username:
            return bot_user_id, bot_username
        last_user_id, last_username = last_known
        if last_user_id or last_username:
            return str(last_user_id).strip(), str(last_username).strip()
        return str((config.get("app") or {}).get("bot_user_id", "")).strip(), ""

    def gateway_connect_url(
        self,
        connection_id: str = "",
        next_sequence: int | None = None,
        disconnect_err_code: int = 0,
    ) -> str:
        base_url = common.mattermost_websocket_url()
        if not base_url:
            raise RuntimeError("Mattermost websocket URL is missing")
        normalized_connection_id = str(connection_id).strip()
        parsed = urllib.parse.urlparse(base_url)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        # Mattermost's reliable-websocket reconnect: replay everything the
        # server buffered from `sequence_number` onward for this connection.
        if normalized_connection_id and next_sequence is not None:
            query["connection_id"] = normalized_connection_id
            query["sequence_number"] = str(max(int(next_sequence), 0))
        if int(disconnect_err_code or 0):
            query["disconnect_err_code"] = str(int(disconnect_err_code))
        if not query:
            return base_url
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))

    def authenticate(self, ws: GatewayWebSocket, token: str, request_seq: int) -> None:
        ws.send_json(
            {
                "seq": int(request_seq),
                "action": AUTHENTICATION_CHALLENGE_ACTION,
                "data": {"token": token},
            }
        )

    def message_worker_loop(self) -> None:
        while True:
            try:
                item = self.message_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if item is WORKER_QUEUE_SENTINEL:
                    return
                post, bot_user_id, bot_username = item
                self.handle_gateway_message(post, bot_user_id, bot_username)
            finally:
                self.message_queue.task_done()
                self.runtime_state.patch(message_queue_size=self.message_queue.qsize())

    def _record_extmsg_inbound(self, post: dict[str, Any], bot_user_id: str, bot_username: str) -> bool:
        """Normalize and post an inbound Mattermost post to the extmsg fabric.

        If the post @mentions agents in a room (not a thread), this also starts
        the thread and session setup — the room is a launchpad.

        Returns True if the post was fully handled by extmsg (caller should
        skip legacy routing). Returns False to fall through to legacy path.
        """
        try:
            if common.post_is_from_bot(post, bot_user_id) or common.post_is_system(post):
                return False
            team_id = str(post.get("team_id", "")).strip()
            config = common.load_config()
            if not bot_user_id:
                bot_user_id = str(config.get("app", {}).get("bot_user_id", "")).strip()
            if not bot_user_id:
                return False

            content = raw_message_content(post)
            channel_id = str(post.get("channel_id", "")).strip()
            # Mattermost threads live inside the channel, keyed by root_id, so
            # thread detection is a field read rather than a channel lookup.
            root_id = str(post.get("root_id", "")).strip()
            is_thread = bool(root_id)

            # Explicit room bindings take precedence over generic extmsg
            # mention/thread launching. This keeps sticky bound rooms, and
            # their inherited thread routing, from spawning new sessions.
            if team_id and channel_id and bound_room_claims_message(config, channel_id):
                return False

            # ROOM: @mentions required to launch a new thread.
            # NL mentions in the room are ignored (no accidental threads).
            if team_id and channel_id and not is_thread:
                at_mentions = self._agent_at_mentions(content, bot_username)
                if not at_mentions:
                    return False  # No @mentions in room — fall through to legacy.
                targets = common.resolve_mention_targets(at_mentions)
                if not targets:
                    return False
                group = common.launch_thread_for_mentions(post, targets, team_id, bot_user_id)
                if group:
                    root_conversation = group.get("root_conversation") if isinstance(group, dict) else None
                    thread_root_id = str((root_conversation or {}).get("thread_root_id", "")).strip()
                    if thread_root_id:
                        participants = [{"handle": t.get("mention", "")} for t in targets]
                        normalized = common.normalize_to_extmsg_message(
                            {**post, "root_id": thread_root_id},
                            team_id,
                            bot_user_id,
                            participants,
                        )
                        common.deliver_to_extmsg(normalized, bot_user_id)
                    return True
                return False

            # THREAD: all messages go to transcript. Handle @mentions and NL names.
            # Only team channels take this path. Mattermost DMs support threads
            # too (root_id is set), but a DM belongs to its `dm:` binding, so
            # swallowing DM thread replies here would strand them.
            if team_id and is_thread:
                # @mentions in thread = add new participants (strong signal).
                at_mentions = self._agent_at_mentions(content, bot_username)
                if at_mentions:
                    targets = common.resolve_mention_targets(at_mentions)
                    if targets:
                        print(f"[extmsg] thread @mentions: adding {[t.get('mention','') for t in targets]}", flush=True)
                        common.add_participants_to_thread(
                            root_id, channel_id, targets, team_id, bot_user_id, content,
                        )

                # NL mentions in thread = set explicit_target (attention signal).
                nl_mentions = common.resolve_nl_agent_mentions(content)

                normalized = common.normalize_to_extmsg_message(post, team_id, bot_user_id)
                # Set explicit_target from @mention or NL match.
                if at_mentions:
                    normalized["explicit_target"] = at_mentions[0]
                elif nl_mentions:
                    normalized["explicit_target"] = nl_mentions[0]

                common.deliver_to_extmsg(normalized, bot_user_id)
                return True

            return False
        except Exception:  # noqa: BLE001
            return False  # On error, fall through to legacy path.

    @staticmethod
    def _agent_at_mentions(content: str, bot_username: str) -> list[str]:
        # Mattermost mention text is literal `@username`, so the bot's own
        # mention shows up in the body and must not be treated as a target.
        normalized_bot_username = str(bot_username).strip().lstrip("@").casefold()
        return [
            mention
            for mention in common.resolve_at_mentions(content)
            if mention.strip().casefold() != normalized_bot_username
        ]

    def handle_gateway_message(self, post: dict[str, Any], bot_user_id: str, bot_username: str) -> None:
        try:
            # Try the new extmsg path first. If it handles the message
            # (e.g., creates a thread from @mentions), skip legacy routing.
            if self._record_extmsg_inbound(post, bot_user_id, bot_username):
                self.runtime_state.bump("routed_messages",
                    last_message_status="extmsg_routed",
                    last_message_preview=common.utcnow(),
                    last_event_at=common.utcnow())
                return
            outcome = process_inbound_message(post, bot_user_id, bot_username)
            status = str(outcome.get("status", "")).strip()
            preview = summarize_body(str((outcome.get("receipt") or {}).get("body_preview", "")))
            if status == "duplicate":
                self.runtime_state.bump("duplicate_messages", last_message_status=status, last_message_preview=preview, last_event_at=common.utcnow())
                return
            if status.startswith("ignored"):
                self.runtime_state.bump("ignored_messages", last_message_status=status, last_message_preview=preview, last_event_at=common.utcnow())
                return
            if status in {"delivered", "partial_failed"}:
                self.runtime_state.bump("routed_messages", last_message_status=status, last_message_preview=preview, last_event_at=common.utcnow())
                return
            self.runtime_state.bump("failed_messages", last_message_status=status or "failed", last_message_preview=preview, last_event_at=common.utcnow())
        except Exception as exc:  # noqa: BLE001
            preview = ingress_preview(post, bot_username)
            self.runtime_state.bump(
                "failed_messages",
                last_message_status="exception",
                last_message_preview=preview,
                last_error=str(exc),
                last_exception=traceback.format_exc(limit=20),
                last_event_at=common.utcnow(),
            )

    def dispatch_gateway_message(self, post: dict[str, Any], bot_user_id: str, bot_username: str) -> None:
        if self.stop_event.is_set():
            save_rejected_ingress_receipt(
                post,
                bot_username,
                status="rejected_shutting_down",
                reason="service_shutting_down",
            )
            self.runtime_state.bump(
                "dropped_messages",
                last_message_status="shutting_down",
                last_message_preview=ingress_preview(post, bot_username),
                last_event_at=common.utcnow(),
                message_queue_size=self.message_queue.qsize(),
            )
            return
        try:
            self.message_queue.put_nowait((post, bot_user_id, bot_username))
            self.runtime_state.patch(message_queue_size=self.message_queue.qsize())
        except queue.Full:
            ingress_id = message_ingress_id(post)
            save_rejected_ingress_receipt(
                post,
                bot_username,
                status="rejected_overloaded",
                reason="message_queue_full",
            )
            print(
                f"[{common.current_service_name() or 'mattermost-gateway'}] dropping ingress {ingress_id}: message queue full",
                flush=True,
            )
            self.runtime_state.bump(
                "dropped_messages",
                last_message_status="queue_full",
                last_message_preview=ingress_preview(post, bot_username),
                last_event_at=common.utcnow(),
                message_queue_size=self.message_queue.qsize(),
            )

    def prune_runtime_data(self) -> None:
        common.prune_requests()
        common.prune_receipts()
        common.prune_pending_modals()
        common.prune_chat_ingress()
        common.prune_chat_publishes()
        common.prune_room_launches()
        prune_channel_info_cache()
        prune_channel_info_fetch_locks()
        prune_stale_reclaim_locks()
        prune_ingress_process_locks()
        self.runtime_state.patch(last_prune_at=common.utcnow())

    def run_forever(self) -> None:
        backoff_seconds = RECONNECT_BASE_DELAY_SECONDS
        next_prune_at = 0.0
        # `next_server_sequence` is the seq the server is expected to send next,
        # mirroring the reference webapp client's `serverSequence`.
        next_server_sequence = 0
        connection_id = ""
        disconnect_err_code = 0
        last_known_identity: tuple[str, str] = ("", "")
        while not self.stop_event.is_set():
            try:
                now = time.monotonic()
                if now >= next_prune_at:
                    self.prune_runtime_data()
                    next_prune_at = now + PRUNE_INTERVAL_SECONDS
                config = common.load_config()
                bot_token = common.load_bot_token()
                site_url = common.mattermost_site_url()
                if not bot_token or not site_url:
                    self.runtime_state.patch(
                        connected=False,
                        state="waiting_for_config",
                        last_error="mattermost site_url or bot token is not configured",
                    )
                    if self.stop_event.wait(RECONNECT_BASE_DELAY_SECONDS):
                        break
                    continue

                can_resume = bool(connection_id)
                requested_connection_id = connection_id
                connection_url = self.gateway_connect_url(
                    connection_id if can_resume else "",
                    next_server_sequence if can_resume else None,
                    disconnect_err_code,
                )
                disconnect_err_code = 0
                # Mattermost accepts either an Authorization header on the
                # upgrade (what the reliable Go client does) or an
                # `authentication_challenge` action once connected. Send both
                # so the handshake works against every supported deployment,
                # and accept readiness from `hello` or the challenge's OK reply.
                ws = GatewayWebSocket(connection_url, headers={"Authorization": f"Bearer {bot_token}"})
                self.set_current_ws(ws)
                authenticated = False
                auth_request_seq = 1
                self.runtime_state.patch(connected=False, state="connecting", last_error="", resume_attempt=can_resume)

                try:
                    self.authenticate(ws, bot_token, auth_request_seq)
                    auth_deadline = time.monotonic() + WEBSOCKET_AUTH_TIMEOUT_SECONDS
                    next_ping_at = time.monotonic() + WEBSOCKET_PING_INTERVAL_SECONDS

                    while not self.stop_event.is_set():
                        now = time.monotonic()
                        timeout = max(0.1, min(next_ping_at, auth_deadline if not authenticated else next_ping_at) - now)
                        try:
                            event = ws.recv_event(timeout=timeout)
                        except GatewayFrameTimeout:
                            event = None
                        now = time.monotonic()
                        if not authenticated and now >= auth_deadline:
                            raise RuntimeError("mattermost gateway authentication timed out")
                        if now >= next_ping_at:
                            ws.send_ping()
                            next_ping_at = now + WEBSOCKET_PING_INTERVAL_SECONDS
                            self.runtime_state.patch(last_ping_at=common.utcnow())
                        if (now - ws.last_frame_at) > WEBSOCKET_SILENCE_TIMEOUT_SECONDS:
                            disconnect_err_code = CLIENT_PING_TIMEOUT_CLOSE_CODE
                            ws.close(CLIENT_PING_TIMEOUT_CLOSE_CODE)
                            raise RuntimeError("mattermost gateway websocket went silent")
                        if now >= next_prune_at:
                            self.prune_runtime_data()
                            next_prune_at = now + PRUNE_INTERVAL_SECONDS
                        if not isinstance(event, dict):
                            continue

                        event_type = str(event.get("event", "")).strip()
                        if "event" in event:
                            try:
                                observed_sequence = int(event.get("seq", 0) or 0)
                            except (TypeError, ValueError):
                                observed_sequence = next_server_sequence
                            # `hello` re-establishes the sequence baseline. A
                            # server that could not replay our buffered queue
                            # answers with a fresh connection_id and restarts
                            # seq at 0 — that is a resync, not a gap, so it must
                            # be accepted before the gap check below.
                            if event_type != "hello" and observed_sequence != next_server_sequence:
                                # A gap means the server's dead queue could not
                                # replay everything; the reference client drops
                                # the socket with 4001 and resyncs from scratch.
                                expected_sequence = next_server_sequence
                                connection_id = ""
                                next_server_sequence = 0
                                disconnect_err_code = CLIENT_SEQUENCE_MISMATCH_CLOSE_CODE
                                ws.close(CLIENT_SEQUENCE_MISMATCH_CLOSE_CODE)
                                raise RuntimeError(
                                    f"mattermost gateway sequence mismatch: expected {expected_sequence}, got {observed_sequence}"
                                )
                            next_server_sequence = observed_sequence + 1
                            self.runtime_state.patch(last_sequence=observed_sequence)

                        status = str(event.get("status", "")).strip()
                        if status and "event" not in event:
                            # WebSocketResponse: {"status", "seq_reply", "data", "error"}
                            try:
                                seq_reply = int(event.get("seq_reply", 0) or 0)
                            except (TypeError, ValueError):
                                seq_reply = 0
                            if seq_reply == auth_request_seq:
                                if status.upper() != "OK":
                                    raise RuntimeError(f"mattermost gateway rejected authentication: {event.get('error')!r}")
                                if not authenticated:
                                    authenticated = True
                                    backoff_seconds = RECONNECT_BASE_DELAY_SECONDS
                                    self.runtime_state.patch(
                                        connected=True,
                                        state="ready",
                                        last_ready_at=common.utcnow(),
                                        last_ready_epoch=int(time.time()),
                                        last_error="",
                                    )
                            continue

                        raw_data = event.get("data")
                        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
                        raw_broadcast = event.get("broadcast")
                        broadcast: dict[str, Any] = raw_broadcast if isinstance(raw_broadcast, dict) else {}
                        if event_type == "hello":
                            hello_connection_id = (
                                str(data.get("connection_id", "")).strip()
                                or str(broadcast.get("connection_id", "")).strip()
                            )
                            # A different connection_id than the one we asked to
                            # resume means the server could not replay; the
                            # sequence cursor was already rebased off this
                            # `hello` above, so only the status differs.
                            resumed = bool(
                                requested_connection_id
                                and hello_connection_id
                                and hello_connection_id == requested_connection_id
                            )
                            connection_id = hello_connection_id or connection_id
                            bot_user_id, bot_username = self.current_bot_identity(config, last_known_identity)
                            last_known_identity = (bot_user_id, bot_username)
                            authenticated = True
                            backoff_seconds = RECONNECT_BASE_DELAY_SECONDS
                            self.runtime_state.patch(
                                connected=True,
                                state="ready",
                                bot_user_id=bot_user_id,
                                bot_username=bot_username,
                                connection_id=connection_id,
                                resumed_connection=resumed,
                                server_version=str(data.get("server_version", "")).strip(),
                                last_ready_at=common.utcnow(),
                                last_ready_epoch=int(time.time()),
                                last_error="",
                            )
                            if resumed:
                                self.runtime_state.patch(
                                    last_resumed_at=common.utcnow(),
                                    last_resumed_epoch=int(time.time()),
                                )
                            continue
                        if event_type == "posted":
                            post = normalize_posted_event(event)
                            if not post:
                                continue
                            bot_user_id, bot_username = self.current_bot_identity(config, last_known_identity)
                            last_known_identity = (bot_user_id, bot_username)
                            self.dispatch_gateway_message(post, bot_user_id, bot_username)
                            continue
                finally:
                    self.set_current_ws(None)
                    ws.close()
            except Exception as exc:  # noqa: BLE001
                if self.stop_event.is_set():
                    break
                if isinstance(exc, common.MattermostAPIError) and int(getattr(exc, "status_code", 0) or 0) in {401, 403}:
                    # A rejected token invalidates any buffered server queue.
                    connection_id = ""
                    next_server_sequence = 0
                sleep_seconds = min(RECONNECT_MAX_DELAY_SECONDS, backoff_seconds * random.uniform(0.8, 1.2))
                self.runtime_state.patch(
                    connected=False,
                    state="reconnecting",
                    last_error=str(exc),
                    last_exception=traceback.format_exc(limit=20),
                    last_disconnect_at=common.utcnow(),
                    next_retry_delay_seconds=round(sleep_seconds, 2),
                )
                if self.stop_event.wait(sleep_seconds):
                    break
                backoff_seconds = min(RECONNECT_MAX_DELAY_SECONDS, max(RECONNECT_BASE_DELAY_SECONDS, backoff_seconds * 2))


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "MattermostGateway/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{common.current_service_name() or 'mattermost-gateway'}] {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            state = get_runtime_state().snapshot()
            gc_api_reachable = True
            if str(state.get("state", "")).strip() in {"ready", "reconnecting"}:
                gc_api_reachable = probe_gc_api_health(get_runtime_state())
            code = gateway_health_status_code(state, gc_api_reachable=gc_api_reachable)
            self.send_response(code)
            self.end_headers()
            return
        if parsed.path in {"", "/"}:
            text_response(self, HTTPStatus.OK, "mattermost gateway ready\n", "text/plain; charset=utf-8")
            return
        if parsed.path == "/v0/mattermost/gateway/status":
            json_response(self, HTTPStatus.OK, get_runtime_state().snapshot())
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})


RUNTIME_STATE: GatewayRuntimeState | None = None


def get_runtime_state() -> GatewayRuntimeState:
    global RUNTIME_STATE
    if RUNTIME_STATE is None:
        RUNTIME_STATE = GatewayRuntimeState()
    return RUNTIME_STATE


def gateway_health_status_code(state: dict[str, Any], gc_api_reachable: bool = True) -> HTTPStatus:
    status = str(state.get("state", "")).strip()
    if status in {"connecting", "waiting_for_config", "starting"}:
        return HTTPStatus.NO_CONTENT
    if status == "ready":
        return HTTPStatus.NO_CONTENT if gc_api_reachable else HTTPStatus.SERVICE_UNAVAILABLE
    if status == "reconnecting":
        last_ready_epoch = int(state.get("last_ready_epoch", 0) or 0)
        last_resumed_epoch = int(state.get("last_resumed_epoch", 0) or 0)
        fresh_epoch = max(last_ready_epoch, last_resumed_epoch)
        if fresh_epoch and (time.time() - fresh_epoch) <= HEALTH_RECONNECT_GRACE_SECONDS:
            return HTTPStatus.NO_CONTENT if gc_api_reachable else HTTPStatus.SERVICE_UNAVAILABLE
    return HTTPStatus.SERVICE_UNAVAILABLE


def main() -> int:
    common.ensure_layout()
    common.prune_chat_ingress()
    common.prune_chat_publishes()
    common.prune_room_launches()
    socket_path = os.environ.get("GC_SERVICE_SOCKET", "")
    try:
        common.prepare_service_socket(socket_path)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    runtime_state = get_runtime_state()
    worker = GatewayWorker(runtime_state)
    thread = threading.Thread(target=worker.run_forever, name="mattermost-gateway")
    thread.start()

    with ThreadingUnixHTTPServer(socket_path, GatewayHandler) as server:
        def handle_shutdown(signum: int, _frame: Any) -> None:
            runtime_state.patch(last_shutdown_signal=signum, last_shutdown_at=common.utcnow())
            worker.request_stop()
            threading.Thread(target=server.shutdown, daemon=True).start()

        previous_sigint = signal.signal(signal.SIGINT, handle_shutdown)
        previous_sigterm = signal.signal(signal.SIGTERM, handle_shutdown)
        print(f"[{common.current_service_name() or 'mattermost-gateway'}] listening on {socket_path}")
        try:
            server.serve_forever()
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
            worker.stop()
            thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

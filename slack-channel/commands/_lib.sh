#!/bin/sh
# Shared helpers for slack-channel verb wrappers. This file is SOURCED by
# the verb scripts, never run as a command (it has no command.toml, so gc
# does not expose it). slack-channel ships no operator CLI binary: each verb
# resolves the adapter endpoint through gc's /svc/slack-channel reverse
# proxy and relays a JSON request. The adapter holds SLACK_BOT_TOKEN and
# owns the on-disk registries, so secrets never enter the command env.

sc_die() {
  echo "gc slack-channel: $1" >&2
  exit "${2:-1}"
}

sc_require() {
  command -v jq >/dev/null 2>&1 || sc_die "jq is required on PATH" 1
  command -v curl >/dev/null 2>&1 || sc_die "curl is required on PATH" 1
}

sc_city() {
  [ -n "${GC_CITY_NAME:-}" ] || sc_die "GC_CITY_NAME is not set" 1
  printf '%s' "$GC_CITY_NAME"
}

# sc_adapter_base prints the adapter's base URL. SLACK_CHANNEL_ADAPTER_URL
# overrides for local testing; otherwise it is gc's reverse-proxy path.
sc_adapter_base() {
  if [ -n "${SLACK_CHANNEL_ADAPTER_URL:-}" ]; then
    printf '%s' "${SLACK_CHANNEL_ADAPTER_URL%/}"
    return
  fi
  _base="${GC_API_BASE_URL:-http://127.0.0.1:9443}"
  _base="${_base%/}"
  printf '%s/v0/city/%s/svc/slack-channel' "$_base" "$(sc_city)"
}

# sc_call METHOD ENDPOINT JSON_BODY — relay to the adapter, print its JSON
# payload on stdout, and exit non-zero on a non-2xx status (surfacing the
# adapter's {"ok":false,"error":...} body rather than swallowing it).
sc_call() {
  _method="$1"
  _endpoint="$2"
  _body="$3"
  _url="$(sc_adapter_base)/${_endpoint}"
  _resp=$(curl -sS -X "$_method" "$_url" \
    -H 'Content-Type: application/json' \
    -H 'X-GC-Request: gc-slack-channel' \
    -d "$_body" \
    -w '\n%{http_code}') || sc_die "request to adapter failed: $_resp" 1
  _code=$(printf '%s\n' "$_resp" | tail -n1)
  _payload=$(printf '%s\n' "$_resp" | sed '$d')
  printf '%s\n' "$_payload"
  case "$_code" in
    2*) return 0 ;;
    *) sc_die "adapter returned HTTP $_code" 1 ;;
  esac
}

# sc_session prints the explicit session id if non-empty, else the current
# session ($GC_SESSION_ID), failing when neither is available.
sc_session() {
  if [ -n "$1" ]; then
    printf '%s' "$1"
    return
  fi
  [ -n "${GC_SESSION_ID:-}" ] || sc_die "no --session given and GC_SESSION_ID is not set" 1
  printf '%s' "$GC_SESSION_ID"
}

# sc_help VERB — print the verb's help.md (relative to the verb script) and
# exit 0.
sc_help() {
  cat "$(dirname "$0")/$1/help.md"
  exit 0
}

# sc_load_body BODY BODY_FILE — resolve a message body from --body or
# --body-file (mutually exclusive, exactly one required).
sc_load_body() {
  if [ -n "$1" ] && [ -n "$2" ]; then
    sc_die "pass --body OR --body-file, not both" 2
  fi
  if [ -n "$1" ]; then
    printf '%s' "$1"
    return
  fi
  [ -n "$2" ] || sc_die "either --body or --body-file is required" 2
  cat "$2"
}

# sc_bind KIND ARGS... — shared implementation for bind-dm / bind-room.
# Positional args: <channel_id> <session_id> [session_id...].
sc_bind() {
  _kind="$1"
  shift
  [ $# -ge 2 ] || sc_die "usage: bind-${_kind} <channel_id> <session_id> [session_id...]" 2
  _channel="$1"
  shift
  _sessions=$(printf '%s\n' "$@" | jq -R . | jq -s .)
  _body=$(jq -n \
    --arg ch "$_channel" \
    --arg kind "$_kind" \
    --argjson sessions "$_sessions" \
    '{channel_id: $ch, kind: $kind, session_ids: $sessions}')
  sc_call POST bindings "$_body"
}

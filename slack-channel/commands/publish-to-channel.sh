#!/bin/sh
# gc slack-channel publish-to-channel — post to a channel by id, bypassing
# the binding lookup. The session id (if any) still drives the identity
# override.
set -eu
. "$(dirname "$0")/_lib.sh"

channel=""
session=""
thread_ts=""
body=""
body_file=""

while [ $# -gt 0 ]; do
  case "$1" in
    --channel)     channel="$2"; shift 2 ;;
    --channel=*)   channel="${1#*=}"; shift ;;
    --session)     session="$2"; shift 2 ;;
    --session=*)   session="${1#*=}"; shift ;;
    --thread-ts)   thread_ts="$2"; shift 2 ;;
    --thread-ts=*) thread_ts="${1#*=}"; shift ;;
    --body)        body="$2"; shift 2 ;;
    --body=*)      body="${1#*=}"; shift ;;
    --body-file)   body_file="$2"; shift 2 ;;
    --body-file=*) body_file="${1#*=}"; shift ;;
    -h|--help)     sc_help publish-to-channel ;;
    *) sc_die "unknown argument: $1" 2 ;;
  esac
done

[ -n "$channel" ] || sc_die "--channel is required" 2
sc_require
text=$(sc_load_body "$body" "$body_file")
# Default to the current session so its identity override applies, but do
# not require one — publish-to-channel works with no session attribution.
[ -n "$session" ] || session="${GC_SESSION_ID:-}"

req=$(jq -n \
  --arg channel "$channel" \
  --arg session "$session" \
  --arg body "$text" \
  --arg thread_ts "$thread_ts" \
  '{channel_id: $channel, body: $body}
   + (if $session == "" then {} else {session_id: $session} end)
   + (if $thread_ts == "" then {} else {thread_ts: $thread_ts} end)')
sc_call POST publish-to-channel "$req"

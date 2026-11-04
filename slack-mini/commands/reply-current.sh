#!/usr/bin/env bash
# gc slack-mini reply-current — answer the conversation gc just handed this session.
#
# When gc delivers an inbound mention it tells the session:
#   "To reply in Slack, write your response to a file and run:
#      gc slack reply-current --conversation-id <C…> --body-file <path>"
# (gastownhall/gascity#5166). slack-mini never shipped that verb, so a Tier 1 city
# could receive a mention and had no advertised way to answer it. This is that verb:
# it posts the body file to the conversation through post-message.sh, threaded under
# the mention when the adapter recorded its ts (see rememberInboundTS in main.go).
#
#   gc slack-mini reply-current --conversation-id C0123 --body-file reply.md [--thread-ts <ts>]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
conv=""; body_file=""; thread_ts=""; text=""
while [ $# -gt 0 ]; do
  case "$1" in
    --conversation-id) conv="$2"; shift 2 ;;
    --conversation-id=*) conv="${1#*=}"; shift ;;
    --body-file) body_file="$2"; shift 2 ;;
    --body-file=*) body_file="${1#*=}"; shift ;;
    --text) text="$2"; shift 2 ;;
    --thread-ts) thread_ts="$2"; shift 2 ;;
    --thread-ts=*) thread_ts="${1#*=}"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "gc slack-mini reply-current: unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$conv" ] || { echo "gc slack-mini reply-current: --conversation-id is required" >&2; exit 2; }
if [ -n "$body_file" ]; then
  [ -f "$body_file" ] || { echo "gc slack-mini reply-current: body file not found: $body_file" >&2; exit 2; }
  text="$(cat "$body_file")"
fi
[ -n "$text" ] || { echo "gc slack-mini reply-current: --body-file or --text is required" >&2; exit 2; }

# Thread under the mention: the adapter records the latest inbound thread ts per channel
# under its service run root. The city path comes from gc itself, so this works whether
# the pack is imported from a cache or checked into the city.
if [ -z "$thread_ts" ] && command -v gc >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
  city="$(gc rig list --json 2>/dev/null | jq -r '.city_path // empty' 2>/dev/null || true)"
  f="${city:+$city/.gc/services/slack-mini/run/last-inbound-$conv.ts}"
  [ -n "$f" ] && [ -f "$f" ] && thread_ts="$(tr -d '[:space:]' < "$f")"
fi
args=(--channel "$conv" --text "$text")
[ -n "$thread_ts" ] && args+=(--thread-ts "$thread_ts")
exec bash "$here/post-message.sh" "${args[@]}"

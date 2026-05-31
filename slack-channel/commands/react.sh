#!/bin/sh
# gc slack-channel react — add an emoji reaction to the latest inbound Slack
# message for this session, or to an explicit (channel, ts) pair.
set -eu
. "$(dirname "$0")/_lib.sh"

session=""
conversation_id=""
message_id=""
emoji="eyes"

while [ $# -gt 0 ]; do
  case "$1" in
    --session)           session="$2"; shift 2 ;;
    --session=*)         session="${1#*=}"; shift ;;
    --conversation-id)   conversation_id="$2"; shift 2 ;;
    --conversation-id=*) conversation_id="${1#*=}"; shift ;;
    --message-id)        message_id="$2"; shift 2 ;;
    --message-id=*)      message_id="${1#*=}"; shift ;;
    --emoji)             emoji="$2"; shift 2 ;;
    --emoji=*)           emoji="${1#*=}"; shift ;;
    -h|--help)           sc_help react ;;
    *) sc_die "unknown argument: $1" 2 ;;
  esac
done

sc_require

# Explicit mode names channel + ts directly; otherwise react on the
# session's latest inbound, so the session id must be resolvable.
if [ -n "$conversation_id" ] || [ -n "$message_id" ]; then
  req=$(jq -n \
    --arg conversation_id "$conversation_id" \
    --arg message_id "$message_id" \
    --arg emoji "$emoji" \
    '{conversation_id: $conversation_id, message_id: $message_id, emoji: $emoji}')
else
  sid=$(sc_session "$session")
  req=$(jq -n --arg session "$sid" --arg emoji "$emoji" '{session_id: $session, emoji: $emoji}')
fi
sc_call POST react "$req"

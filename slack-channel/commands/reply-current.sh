#!/bin/sh
# gc slack-channel reply-current — reply into the conversation of the latest
# inbound message delivered to this session.
set -eu
. "$(dirname "$0")/_lib.sh"

session=""
reply_to=""
thread_current="false"
body=""
body_file=""

while [ $# -gt 0 ]; do
  case "$1" in
    --session)        session="$2"; shift 2 ;;
    --session=*)      session="${1#*=}"; shift ;;
    --reply-to)       reply_to="$2"; shift 2 ;;
    --reply-to=*)     reply_to="${1#*=}"; shift ;;
    --thread-current) thread_current="true"; shift ;;
    --body)           body="$2"; shift 2 ;;
    --body=*)         body="${1#*=}"; shift ;;
    --body-file)      body_file="$2"; shift 2 ;;
    --body-file=*)    body_file="${1#*=}"; shift ;;
    -h|--help)        sc_help reply-current ;;
    *) sc_die "unknown argument: $1" 2 ;;
  esac
done

sc_require
text=$(sc_load_body "$body" "$body_file")
sid=$(sc_session "$session")

req=$(jq -n \
  --arg session "$sid" \
  --arg body "$text" \
  --arg reply_to "$reply_to" \
  --argjson thread_current "$thread_current" \
  '{session_id: $session, body: $body, thread_current: $thread_current}
   + (if $reply_to == "" then {} else {reply_to: $reply_to} end)')
sc_call POST reply-current "$req"

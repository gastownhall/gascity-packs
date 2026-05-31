#!/bin/sh
# gc slack-channel handle-alias — register (or remove) a handle → session
# alias for address-by-handle routing from any channel.
set -eu
. "$(dirname "$0")/_lib.sh"

handle=""
session=""
remove="false"

while [ $# -gt 0 ]; do
  case "$1" in
    --handle)    handle="$2"; shift 2 ;;
    --handle=*)  handle="${1#*=}"; shift ;;
    --session)   session="$2"; shift 2 ;;
    --session=*) session="${1#*=}"; shift ;;
    --remove)    remove="true"; shift ;;
    -h|--help)   sc_help handle-alias ;;
    *) sc_die "unknown argument: $1" 2 ;;
  esac
done

[ -n "$handle" ] || sc_die "--handle is required" 2
sc_require

if [ "$remove" = "true" ]; then
  req=$(jq -n --arg handle "$handle" '{handle: $handle}')
  sc_call DELETE handle-alias "$req"
  exit 0
fi

[ -n "$session" ] || sc_die "--session is required (or pass --remove)" 2
req=$(jq -n --arg handle "$handle" --arg session "$session" '{handle: $handle, session_id: $session}')
sc_call POST handle-alias "$req"

#!/bin/sh
# gc slack-channel bind-room — bind a Slack channel to one or more sessions.
#
# A message arriving in the bound channel is delivered to every listed
# session. Single-rig at Tier 2 (multi-rig routing is Tier 3).
set -eu
. "$(dirname "$0")/_lib.sh"

case "${1:-}" in
  -h|--help) sc_help bind-room ;;
esac

sc_require
sc_bind room "$@"

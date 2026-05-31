#!/bin/sh
# gc slack-channel bind-dm — bind a Slack DM to one or more gc sessions.
#
# A message arriving in the bound DM is delivered to every listed session.
set -eu
. "$(dirname "$0")/_lib.sh"

case "${1:-}" in
  -h|--help) sc_help bind-dm ;;
esac

sc_require
sc_bind dm "$@"

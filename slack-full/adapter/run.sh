#!/usr/bin/env bash
#
# run.sh — start the gc-slack-adapter in foreground.
#
# Reads secrets from a sourced env file. Default location:
#   ~/.config/gc-slack-adapter/env
# Override via GC_SLACK_ADAPTER_ENV.
#
# Required env keys (in the file):
#   SLACK_WORKSPACE_ID      # T... id, find via Slack admin or auth.test API
#   SLACK_BOT_TOKEN         # xoxb-...
#   SLACK_SIGNING_SECRET    # signing secret from Slack app's Basic Information
#   GC_CITY_NAME            # gc city the adapter posts to (matches
#                           # [workspace].name in city.toml). No default —
#                           # adapter exits at startup if unset.
#
# Optional env keys:
#   LISTEN_PUBLIC           # default :8765 (Funnel exposes this; /slack/events)
#   LISTEN_INTERNAL         # default 127.0.0.1:8766 (localhost-only; /publish)
#   INTERNAL_CALLBACK_URL   # default http://127.0.0.1:8766
#   GC_API_BASE_URL         # default http://127.0.0.1:9443
#   ADAPTER_PROVIDER        # default slack
#   REGISTER_ON_START       # default true; set false to skip self-registration

set -euo pipefail

env_file="${GC_SLACK_ADAPTER_ENV:-$HOME/.config/gc-slack-adapter/env}"
if [[ ! -f "$env_file" ]]; then
  cat <<EOF >&2
gc-slack-adapter: env file not found at $env_file
Create it with at minimum:

  SLACK_WORKSPACE_ID=T01234567
  SLACK_BOT_TOKEN=xoxb-...
  SLACK_SIGNING_SECRET=...

EOF
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$env_file"; set +a

bin_dir="$(cd "$(dirname "$0")" && pwd)"
exec "$bin_dir/gc-slack-adapter"

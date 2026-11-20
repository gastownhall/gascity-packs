#!/bin/sh
# gc teams-mini post-message — post plain text into a Teams conversation.
#
# Tier 1 has no operator CLI binary: this wrapper relays to the running
# teams-mini adapter through gc's /svc/teams-mini reverse proxy. The
# adapter holds the app credentials and calls the Bot Framework REST API,
# so no secret has to be present in the command environment.
#
# Usage:
#   gc teams-mini post-message --conversation "19:abc@thread.tacv2" --text "build is green"
#   gc teams-mini post-message --conversation "19:abc@thread.tacv2;messageid=1699" \
#       --reply-to 1700000000001 --text "follow-up in thread"
set -eu

conversation=""
text=""
reply_to=""
service_url=""

require_value() {
  # $1 = flag name, $2 = arg count remaining (including the flag itself)
  if [ "$2" -lt 2 ]; then
    echo "gc teams-mini post-message: $1 requires a value" >&2
    exit 2
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --conversation)  require_value "$1" "$#"; conversation="$2"; shift 2 ;;
    --text)          require_value "$1" "$#"; text="$2"; shift 2 ;;
    --reply-to)      require_value "$1" "$#"; reply_to="$2"; shift 2 ;;
    --service-url)   require_value "$1" "$#"; service_url="$2"; shift 2 ;;
    --conversation=*) conversation="${1#*=}"; shift ;;
    --text=*)         text="${1#*=}"; shift ;;
    --reply-to=*)     reply_to="${1#*=}"; shift ;;
    --service-url=*)  service_url="${1#*=}"; shift ;;
    -h|--help)
      cat "$(dirname "$0")/post-message/help.md"
      exit 0
      ;;
    *)
      echo "gc teams-mini post-message: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$conversation" ]; then
  echo "gc teams-mini post-message: --conversation is required" >&2
  exit 2
fi
if [ -z "$text" ]; then
  echo "gc teams-mini post-message: --text is required" >&2
  exit 2
fi

api_base="${GC_API_BASE_URL:-http://127.0.0.1:9443}"
api_base="${api_base%/}"
city="${GC_CITY_NAME:-}"
if [ -z "$city" ]; then
  echo "gc teams-mini post-message: GC_CITY_NAME is not set" >&2
  exit 1
fi

# Resolve the adapter endpoint: gc proxies /svc/teams-mini/* to the
# adapter's UDS. TEAMS_MINI_ADAPTER_URL overrides for local testing.
url="${TEAMS_MINI_ADAPTER_URL:-${api_base}/v0/city/${city}/svc/teams-mini/post-message}"

# Build the request body with jq so every field is correctly JSON-escaped
# (text may contain quotes, newlines, etc.; conversation ids contain ';'
# and '@').
body=$(jq -n \
  --arg conversation "$conversation" \
  --arg text "$text" \
  --arg reply_to "$reply_to" \
  --arg service_url "$service_url" \
  '{conversation: $conversation, text: $text}
   + (if $reply_to == "" then {} else {reply_to: $reply_to} end)
   + (if $service_url == "" then {} else {service_url: $service_url} end)')

# Capture status and body separately so the adapter's JSON error payload
# ({"ok":false,"error":...}) reaches the operator instead of being swallowed
# by `curl -f`. -w writes the HTTP status on its own trailing line.
response=$(curl -sS -X POST "$url" \
  -H 'Content-Type: application/json' \
  -H 'X-GC-Request: gc-teams-mini' \
  -d "$body" \
  -w '\n%{http_code}') || {
  echo "gc teams-mini post-message: request to adapter failed" >&2
  echo "$response" >&2
  exit 1
}

http_code=$(printf '%s\n' "$response" | tail -n1)
payload=$(printf '%s\n' "$response" | sed '$d')

printf '%s\n' "$payload"
case "$http_code" in
  2*) exit 0 ;;
  *)
    echo "gc teams-mini post-message: adapter returned HTTP $http_code" >&2
    exit 1
    ;;
esac

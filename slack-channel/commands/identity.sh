#!/bin/sh
# gc slack-channel identity — register (or remove) a per-session Slack
# identity override: the username + avatar a session posts under.
set -eu
. "$(dirname "$0")/_lib.sh"

session=""
display_name=""
avatar_url=""
avatar_emoji=""
remove="false"

while [ $# -gt 0 ]; do
  case "$1" in
    --session)        session="$2"; shift 2 ;;
    --session=*)      session="${1#*=}"; shift ;;
    --as)             display_name="$2"; shift 2 ;;
    --as=*)           display_name="${1#*=}"; shift ;;
    --avatar-url)     avatar_url="$2"; shift 2 ;;
    --avatar-url=*)   avatar_url="${1#*=}"; shift ;;
    --avatar-emoji)   avatar_emoji="$2"; shift 2 ;;
    --avatar-emoji=*) avatar_emoji="${1#*=}"; shift ;;
    --remove)         remove="true"; shift ;;
    -h|--help)        sc_help identity ;;
    *) sc_die "unknown argument: $1" 2 ;;
  esac
done

sc_require
sid=$(sc_session "$session")

if [ "$remove" = "true" ]; then
  req=$(jq -n --arg session "$sid" '{session_id: $session}')
  sc_call DELETE identity "$req"
  exit 0
fi

if [ -n "$avatar_url" ] && [ -n "$avatar_emoji" ]; then
  sc_die "pass --avatar-url OR --avatar-emoji, not both" 2
fi
if [ -z "$display_name" ] && [ -z "$avatar_url" ] && [ -z "$avatar_emoji" ]; then
  sc_die "supply at least one of --as, --avatar-url, --avatar-emoji" 2
fi

req=$(jq -n \
  --arg session "$sid" \
  --arg username "$display_name" \
  --arg icon_url "$avatar_url" \
  --arg icon_emoji "$avatar_emoji" \
  '{session_id: $session}
   + (if $username   == "" then {} else {username: $username}     end)
   + (if $icon_url   == "" then {} else {icon_url: $icon_url}     end)
   + (if $icon_emoji == "" then {} else {icon_emoji: $icon_emoji} end)')
sc_call POST identity "$req"

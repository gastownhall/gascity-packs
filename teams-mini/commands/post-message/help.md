Post plain text into a Microsoft Teams conversation as the bot.

This is the only outbound verb in teams-mini. It relays to the running
teams-mini adapter through gc's /svc/teams-mini reverse proxy; the adapter
calls the Bot Framework conversations API. Use it to answer an inbound
mention in its thread, or to push a notification into a chat or channel the
bot has been added to.

Flags:
  --conversation  Teams conversation id — required. For a channel thread
                  this looks like "19:…@thread.tacv2;messageid=…"; for a
                  personal chat like "a:1…". It is surfaced to your session
                  as the inbound conversation id.
  --text          Message text (Teams markdown) — required.
  --reply-to      Reply to an existing activity. Pass the inbound message's
                  id (surfaced as the conversation's reply-to id).
  --service-url   Bot Framework service URL for the conversation. Only
                  needed for a conversation the adapter has not seen since
                  it started and when TEAMS_SERVICE_URL is unset.

Examples:
  gc teams-mini post-message --conversation "19:abc@thread.tacv2" \
    --text "build is green"

  gc teams-mini post-message --conversation "19:abc@thread.tacv2;messageid=1699" \
    --reply-to 1700000000001 --text "done — see PR #42"

On success, prints {"ok":true,"id":...,"conversation":...}. The returned id
is the new activity's id.

Requires: GC_CITY_NAME and GC_API_BASE_URL in the environment (gc sets
these for command wrappers), plus `jq` and `curl` on PATH. The teams-mini
service must be running (gc supervises it as a proxy_process).

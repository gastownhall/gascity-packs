Reply to the latest Slack inbound event seen by the current session.

The session's recent transcript is scanned for the most recent
`extmsg.inbound` system-reminder. The reply is published through the
local Slack adapter's /publish endpoint to the same conversation.

Examples:
  gc slack reply-current --body "ack"
  gc slack reply-current --body-file /tmp/reply.txt
  gc slack reply-current --conversation-id D0B0TTS550F --body "explicit channel"

If the session has no inbound history, --conversation-id is required.

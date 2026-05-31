Bind a Slack DM channel to exactly one named session.

Examples:
  gc slack bind-dm D0B0TTS550F oversight-rig.cos

This calls the gc extmsg API (POST /v0/city/<name>/extmsg/bind) and
also stores the binding under .gc/services/slack/data/config.json so
`gc slack reply-current` and future publish flows can resolve the
target conversation without re-querying gc.

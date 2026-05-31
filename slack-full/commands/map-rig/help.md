Bind a Slack rig to a set of channels for slash-command default routing.

Persists a (workspace_id, rig_name) → set-of-channel-ids record at
<cityPath>/.gc/slack/rig_mappings.json. The slack-pack adapter reads
this file at startup and uses it as the fall-through resolver when no
per-channel 'map-channel' binding exists for an inbound channel.

Examples:
  gc slack map-rig oversight-rig --workspace-id T1 --channel C1 --channel C2
  gc slack map-rig oversight-rig --workspace-id T1 --channel-pattern 'oversight-*'
  gc slack map-rig oversight-rig --workspace-id T1 \\
    --sling-target oversight-rig/polecat --fix-formula mol-slack-fix-issue
  gc slack map-rig oversight-rig --workspace-id T1 --remove

Channels can be supplied as repeated --channel flags, comma-separated
values, or glob patterns via --channel-pattern. --remove drops the
entire record; --remove-channels drops just the listed ids.

Routes to: gc-slack-cli map-rig

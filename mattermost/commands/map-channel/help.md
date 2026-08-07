Map a Mattermost channel to a workflow dispatch target.

Example:
  gc mattermost map-channel 7k3m9x2c5n8b1v4z6q0r2s4t6w 9h5j7k1m3n5p7r9t1v3x5z7b9c product/polecat \
    --fix-formula mol-mattermost-fix-issue

Arguments:
  <team_id>     Mattermost team id
  <channel_id>  Mattermost channel id
  <target>      rig/pool sling target
                `mol-mattermost-fix-issue` requires a `rig/polecat` target

Flags:
  --fix-formula <name>  formula to use for `/gc fix`, default: mol-mattermost-fix-issue

Thread replies inherit the mapping from their channel, because a Mattermost
thread is just a set of posts sharing a root post id inside that same channel.

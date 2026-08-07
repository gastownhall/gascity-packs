Map a Mattermost team rig name to a workflow dispatch target.

Example:
  gc mattermost map-rig 7k3m9x2c5n8b1v4z6q0r2s4t6w mission-control mission-control/polecat \
    --fix-formula mol-mattermost-fix-issue

Arguments:
  <team_id>     Mattermost team id
  <rig_name>    Rig name as used in /gc fix <rig>
  <target>      rig/pool sling target
                `mol-mattermost-fix-issue` requires a `rig/polecat` target

Flags:
  --fix-formula <name>  formula to use for `/gc fix`, default: mol-mattermost-fix-issue

Users type `/gc fix mission-control "summary"` in any channel. The rig
parameter routes the request to the configured target regardless of which
channel the command is invoked from.

Release a stuck workflow lock for a Mattermost conversation.

This is an operator recovery command. It does not touch the bead; it only
clears the intake-side workflow lock so `/gc fix` can be accepted again for the
same channel or thread.

Example:
  gc mattermost release-workflow 7k3m9x2c5n8b1v4z6q0r2s4t6w 9h5j7k1m3n5p7r9t1v3x5z7b9c
  gc mattermost release-workflow --request-id mm-interaction-fix

Arguments:
  <team_id>          Mattermost team id
  <conversation_id>  Channel id, or channel id plus thread root post id, used
                     for the workflow key

Flags:
  --request-id <id> Release the workflow key recorded on an existing request
  --command <name>  slash command to unlock, default: fix

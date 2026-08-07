Reply to the latest Mattermost event seen by the current session.

This is the safest agent-facing Mattermost reply path. It resolves the latest
`<mattermost-event>` from the current session transcript, reuses its
`publish_binding_id`, `publish_conversation_id`, and reply threading metadata,
then publishes the provided body back to Mattermost.

For launcher-backed root-channel turns, the first successful `reply-current`
starts the thread by replying to the launching post, and later replies reuse
that root post id. The agent does not need to create or target a thread
manually; Mattermost threads are just posts sharing a root post id in the same
channel.

Examples:
  gc mattermost reply-current --body-file ./reply.txt
  gc mattermost reply-current --session corp--sky --body-file ./reply.txt

Prefer `--body-file` for agent replies. It avoids fragile shell quoting and
makes multi-line responses safe.

If you use `--session`, the override is treated as the source session identity
for peer-fanout attribution as well as transcript lookup.

In peer-fanout-enabled rooms, replying to a `mattermost_peer_publication` with
an exact `@session_name` mention can route that publication to another bound
session. Untargeted peer-triggered replies stay human-visible only.

If the command exits with status `2`, the Mattermost reply was posted but peer
fanout was only partially delivered. Inspect `record.peer_delivery` and ask an
operator to run `gc mattermost retry-peer-fanout <publish-id>` if repair is
needed.

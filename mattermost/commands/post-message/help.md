Post a Mattermost message using the workspace bot token.

Examples:
  gc mattermost post-message --request-id mm-123-fix --body "Started work"
  gc mattermost post-message --channel-id 9h5j7k1m3n5p7r9t1v3x5z7b9c --body-file ./message.txt
  gc mattermost post-message --channel-id 9h5j7k1m3n5p7r9t1v3x5z7b9c --root-id 2a4b6c8d0e2f4g6h8i0j2k4m6n --body "Update"

Flags:
  --request-id <id>     load the target channel from a saved intake request
  --channel-id <id>     channel id if no request id is provided
  --root-id <id>        optional thread root post id to reply under
  --body <text>         inline message body
  --body-file <path>    read the message body from a file

`--root-id` posts into an existing thread. The channel id stays the same for
threaded and unthreaded posts; Mattermost threading is entirely a property of
the root post id.

Use `--request-id` from formulas so the message lands back in the original
conversation.

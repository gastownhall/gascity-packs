Reply to a Slack conversation by id, reading the body from a file. This is the verb gc's
inbound system-reminder tells a session to run; it posts through `post-message` and threads
under the mention when the adapter recorded its ts.

  gc slack-mini reply-current --conversation-id C0123 --body-file reply.md [--thread-ts <ts>]

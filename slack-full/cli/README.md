# gc-slack-cli

Operator CLI for the gc [slack-pack](../). The slack-pack's
`commands/<cmd>.sh` wrappers invoke this binary; each subcommand
operates on the on-disk slack runtime state under
`<city>/.gc/slack/` — the same files the slack-adapter reads at
startup and on SIGHUP.

Built as an independent Go module (`github.com/sjarmak/gc-slack-cli`)
that depends only on the standard library and `github.com/spf13/cobra`.
Like the adapter at [`../adapter/`](../adapter/), it does not import
gc internals so the slack-pack remains a self-contained example.

Phase 1 of the slack-cli relocation (gc-coe10) lands subcommands one
at a time. This module starts as a skeleton with only the cobra root
and a small `RuntimePath` helper.

# gc slack handle-alias

Register a handle -> session id mapping with the local Slack adapter.
Used for **cross-channel address-by-handle** routing.

## What it does

When a human posts `@<handle>: <message>` in any Slack channel the bot
sees, the adapter parses the handle. Normally, the inbound is delivered
to the session bound to that channel (and the bound PL decides whether
to respond based on whether the handle matches its rig). With handle
aliases registered, an additional dispatch fires: the adapter also sends
the inbound directly to the aliased session via gc's session-message
API, regardless of any channel binding.

This lets mayor / chief-of-staff be addressed from any channel even
though they aren't bound to most channels.

## Usage

```
gc slack handle-alias --handle <name> --session <session-id>
gc slack handle-alias --handle <name> --session ""    # remove
```

## Flags

- `--handle NAME` — handle without leading `@` (e.g. `mayor`, `cos`).
- `--session SID` — gc session id to route this handle to. Empty
  string removes the alias.

## Examples

```bash
gc slack handle-alias --handle mayor --session gc-2568
gc slack handle-alias --handle cos   --session gc-83347
gc slack handle-alias --handle mayor --session ""   # tear down
```

## Persistence

Aliases are stored at
`${HANDLE_ALIAS_STORE_PATH:-/tmp/gc-slack-adapter/handle-aliases.json}`
and survive adapter restarts.

# gc mattermost upload

Upload a local file to the Mattermost channel a session is bound to.
By default the upload is routed through gc, mirroring the text-reply
contract: gc records the upload in the conversation transcript and
fans out a peer notification to other sessions bound to the same
room. Pass `--via adapter` to fall back to the direct-to-adapter path
for diagnostics.

Either way the local adapter handles Mattermost's two-step upload
protocol (`POST /api/v4/files?channel_id=...&filename=...` to get a
`file_id`, then `POST /api/v4/posts` with that id in `file_ids`).

Use this instead of describing a file in text — Mattermost renders the
attachment inline (image preview, code preview, etc.) and keeps it
discoverable in the channel's file search.

## Usage

```
# Plain upload into the bound channel, no thread
gc mattermost upload --file ./out/plot.png

# With a comment that acts as the message body
gc mattermost upload --file ./out/plot.png --initial-comment "latest run, n=512"

# Threaded under the most recent inbound (parallels reply-current)
gc mattermost upload --file ./out/plot.png --thread-current

# Threaded under a specific thread root post
gc mattermost upload --file ./out/plot.png --root-id 2a4b6c8d0e2f4g6h8i0j2k4m6n
```

## Flags

- `--file PATH` — local file to upload (required).
- `--session SID` — session id whose binding to upload into. Defaults
  to `$GC_SESSION_ID`.
- `--filename NAME` — override the uploaded filename (defaults to
  `basename(--file)`). This is the `filename` query parameter on the
  file upload call and is what Mattermost displays.
- `--initial-comment TEXT` — post message text sent alongside the
  attachment. This is the `message` field of the created post.
- `--root-id <post_id>` — thread root post id to attach under.
  Mutually exclusive with `--thread-current`.
- `--thread-current` — attach under the thread of the latest inbound
  for this session, same logic as `gc mattermost reply-current`.
- `--idempotency-key KEY` — caller-supplied idempotency key for
  retries.
- `--via {gc,adapter}` — routing path. `gc` (default) records the
  upload in the transcript and fans out to peer sessions; `adapter`
  bypasses gc for diagnostics only.

## Required Mattermost access

The bot account needs the `upload_file` permission and must be a
member of the destination channel. Without membership the file call
returns HTTP 403 and the adapter returns
`{delivered: false, failure_kind: "auth", error: "forbidden"}` and
prints the receipt — no exception is raised. Steps to grant:

1. System Console -> Integrations -> Bot Accounts, confirm the bot is
   active.
2. Add the bot to the target team and channel.
3. For private channels, invite the bot explicitly.

There is no OAuth-scope reinstall step; the next
`gc mattermost upload` picks up the new membership immediately.

## Identity caveat

Files post under the bot account's identity. Mattermost's per-post
`override_username`/`override_icon_url` props only apply when the
server has `EnablePostUsernameOverride` turned on, and they are not
applied to the file attachment metadata itself. If per-session
identity matters more than the inline preview, post the file with
`gc mattermost upload` and follow up with `gc mattermost reply-current`
containing the explanatory text — that reply carries the per-session
identity.

## How it works

1. Resolves the session's active extmsg binding to find the target
   channel id.
2. **`--via gc` (default)** — POSTs the file metadata to
   `/v0/city/{city}/extmsg/outbound-file`. gc verifies the binding,
   hands off to the adapter via the FileTransportAdapter interface,
   appends an outbound transcript entry, and emits an
   `extmsg.outbound` event so peer sessions receive a nudge.
3. **`--via adapter`** — POSTs `{session_id, conversation, file_path,
   filename, initial_comment, root_id}` directly to the adapter's
   `/publish-file` endpoint. No transcript record, no peer fanout.
4. Either way, the adapter uploads the bytes, creates the post with
   the returned `file_ids`, and returns a receipt with
   `{delivered, file_id, failure_kind, error}`.

## Examples

```bash
# PL session: upload a generated plot threaded under the human's request
gc mattermost upload --file out/snr_plot.png \
                     --initial-comment "snr vs t for 50 inj/rec runs" \
                     --thread-current

# cos session: post a status digest with attached CSV
gc mattermost upload --file /tmp/digest.csv --initial-comment "overnight digest"
```

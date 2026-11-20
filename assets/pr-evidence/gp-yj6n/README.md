# gp-yj6n — accepted Slack posts and readback diagnostics

Fork base: `ad841a9a65a108a65769cb5bc5b668937611dead` (gp-obim, PR 47).
Incident adapter pin: `d1348d0f2e3e504e1101515e2c409db6b7991ca3`.
Round 1 diagnosis: `b07acec4`, cherry-picked as `e0aadb1d` onto this fresh
fork-main branch; its complete evidence is retained in `round1/`.

## Read-only reproduction and scope

No Slack posts were made, no channels were created, and no adapter was rebuilt
or restarted. The live long-thread/short-thread/plain-body matrix was explicitly
superseded by the Round 2 contract; those combinations were not attempted.

`round1/incident-readback.json` includes the production log at the incident:

```
2026/10/14 06:18:31 slack readback failed: Slack readback content mismatch for message 1791976711.647429
```

The original CLI receipt (from the bead's incident capture) was:

```json
{"delivered":false,"conversation_id":"C0BKF28CYUE","reply_to_message_id":"1787962615.345489","message_id":"1791976711.647429","thread_ts":"1787962615.345489","failure_kind":"permanent"}
```

`incident-readback.json` records a fresh GET using the adapter environment's bot
token and the exact production query: `conversations.replies`, parent `ts`,
`oldest=latest=1791976711.647429`, `inclusive=true`, `limit=2`. It returned the
parent and exact reply with `has_more=false`; the current parent reports 113
replies (114 messages including the parent). The response and original 3,429
character digest were kept in a private local fixture, with only hashes and
counts committed. No credentials or investor body text are in this PR.

Round 1's JSON is a summary, not the raw stored text promised by the bead.
Papercut `pc_5eb1da1f1017` records that discrepancy. The fresh read supplies the
missing text. The original body hash matches Round 1 exactly.

`TestReadBackInvestorDigest` sends that recorded response through
`readBackPublishedMessageOnce` and checks the query and normalized text equality.
At **ad841a9a**, this test already PASSES: gp-obim's
`slackNormalizeUnescapedLinks` folds both redundant mailto wrappers. A changed
body remains unconfirmed. `base-go.txt` records this result before any source
change. The same test uses a public synthetic long-thread/body shape in CI;
set `SLACK_READBACK_INCIDENT` to a private JSON fixture with `posted`, `channel`,
`message_ts`, `thread_ts`, and `response` to replay the real incident.

The original cause was the older normalizer retaining `mailto:` and the
duplicated address, followed by a readback-to-permanent-failure mapping.
Pagination and indexing lag did not cause this incident: the exact reply was
found, and the production error was specifically a content mismatch.

## Fix

The binding rebase narrows the work to receipt/CLI semantics, tests, and docs.
The fork's comparator and URL endpoint rules are unchanged. In
`adapter/publish_readback.go`, `confirmPublishReceipt` now treats an accepted
timestamp as delivered and keeps readback uncertainty only in metadata. gc's
closed failure vocabulary was verified in the local gc source snapshot
`.tasks/gp-twbe/core/internal/extmsg/types.go:193`; no new failure kind is added.

`publishReadbackConfirmed` separates confirmation from acceptance for cached
re-verification, concurrent confirmation ownership, and durable receipt updates.
Empty/mismatched reads cannot release an accepted key for reposting. Existing
cache lifetime, unkeyed behavior, and restart semantics remain unchanged.
Stored acceptance is `delivered=true, readback=pending`; later failed reads
retain their real classification rather than being stamped confirmed.

`scripts/slack_intake_common.py` preserves metadata in terse receipts and supplies
the exit/diagnostic behavior used by all three text CLIs. Timestamp-bearing
legacy receipts also exit zero and report their unconfirmed read on stderr.
This acceptance interpretation also prevents reply-current's auth fallback from
posting a second time when an old receipt describes readback auth failure.
Actual write failures and unknown receipt shapes remain nonzero.

## Validation

- Before source changes at ad841a9a: real incident test passes; all five accepted
  readback failure cases fail (six failing Go test results including their
  parent). `base-go.txt`.
- Before source changes: 99 Python matrix cases fail, 9 pass, 657 deselected.
  `base-python.txt` retains every failing case name.
- After: full Go adapter suite passes 12,577 cases (1,350 top-level), no failures
  or skips, with the real incident fixture enabled. `fork-go.txt` records the
  exact command, Go version, and relevant results. A subsequently added missing-ts
  control is also covered by the focused race run.
- After: `GC_NO_INSTALL=1 TMPDIR="${TMPDIR%/}" make test PYTEST_DIRS=slack-full/tests`
  passes 763, skips 2, with 2 existing `os.fork` deprecation warnings.
  `fork-python.txt`. No Node or pnpm tests or dependency changes were involved.

Focused concurrency/readback validation: 35 cases pass under the race detector,
including the missing-timestamp control and the public incident shape; see
`fork-race.txt`. Offline receipt examples are in `receipt-examples.json`.
The reviewed implementation SHA and final review record accompany the handoff.

Upstream main `520e95cb22992a8a1017f7a60da267f203497c7e` has the readback leg;
an upstream twin is required. It must be based on upstream main and adapted to
that older implementation, without pulling the fork's intervening features.

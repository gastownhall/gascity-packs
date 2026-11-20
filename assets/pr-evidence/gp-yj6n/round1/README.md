# gp-6dm7 investigation — blocked before implementation

Base: `d1348d0f2e3e504e1101515e2c409db6b7991ca3`. No implementation changes or test runs.

The mandatory reproduce-first matrix needs a non-founder Slack test channel
where the adapter bot is a member. The bead supplies no such channel ID.
The adapter environment identifies bot `U0BHE265YNN` in workspace
`T0AMLNGFBN1`; both `users.conversations` and `conversations.list` return
`missing_scope`. Its token has history and chat permissions but no channel
listing permissions. No test target could be established from the scoped
repository/configuration. No Slack messages were posted. Input request sent
to mayor as `ci-wisp-cs9aovz`; no answer was present at the handoff check.
Papercut: `pc_461e67d9fa68`.

## Confirmed incident diagnosis

`incident-readback.json` records a read-only call against the incident's
existing message with the adapter's exact query: `conversations.replies`,
parent timestamp, `oldest=latest=message timestamp`, `inclusive=true`,
`limit=2`. Slack returned the parent and exact posted reply, with
`has_more=false`. The query can reach the deep reply; pagination is not the
cause of this incident. The production log at posting time says **content
mismatch**, rather than absence, so indexing lag is not the cause either.

The 3,429-character original digest and stored text differ under the existing
entity and angle-span fold. Collapsing the two auto-generated
`<mailto:address|address>` spans to the bare address makes those folded
strings exactly equal. The evidence stores only a digest hash, counts,
timestamps and the relevant service log line; no digest text or credentials.

Source evidence at the base:

- `slack-full/adapter/publish_readback.go:232`: `slackNormalizeText` removes
  angle brackets but leaves the mailto prefix and repeated address.
- `slack-full/adapter/publish_readback.go:586`: normalized text mismatch
  produces `readback_unconfirmed` and does not retry that mismatch.
- `slack-full/adapter/publish_readback.go:151`: the mapper turns that detail
  into `permanent`.
- `slack-full/adapter/publish_readback.go:597`: confirmation replaces the
  accepted write's receipt with `delivered=false` and that failure kind.
- `slack-full/scripts/slack_intake_common.py:405`: the terse receipt drops
  receipt metadata, hiding which leg failed.

The local gc source snapshot at `.tasks/gp-twbe/core/internal/extmsg/types.go`
lines 193–225 has a closed documented failure vocabulary
(unsupported/transient/rate_limited/permanent/auth/not_found), plus receipt
Metadata. The metadata route requested by the bead avoids adding a gc kind.

Upstream `520e95cb22992a8a1017f7a60da267f203497c7e` contains
`slack-full/adapter/publish_readback.go`, so a completed fix needs the
requested upstream twin, independently based on upstream main. No PR or twin
was opened for this incomplete investigation.

## Missing acceptance work

The three live test-channel cases, recorded-response regression tests,
implementation/receipt changes, docs/changelog, test suites, Codex review and
draft PRs remain unexecuted. This report is a blocked investigation, not a
shipped fix. A test channel ID is required to resume the mandated first step.

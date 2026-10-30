# Upstream twin of gp-yj6n

Base: `520e95cb22992a8a1017f7a60da267f203497c7e` from upstream main.
This branch was created directly from that upstream ref, then cherry-picked
round 1 diagnosis and fork implementation `8af195fd57eb22e5b4adf2424c35c55e58f180cc`.
It is not based on the fork head. The accompanying main README and fork
transcripts describe the fork; this page describes the upstream adaptation.

Conflicts were resolved against upstream's existing implementation. The newer
fork's durable receipt store, marker removal, confirmation bookkeeping machinery,
terse output mode, emoji table and URL endpoint rules were not imported.
Upstream retains marker confirmation for keyed messages and its full JSON
result envelopes (which already include all receipt metadata).

The same acceptance semantics apply: an accepted timestamp cannot become a
publish failure, and all three CLIs exit zero with readback uncertainty on
stderr. Keyed retries never release an accepted timestamp for reposting.
Metadata copies protect concurrent rechecks, and slower unconfirmed reads
cannot downgrade cached confirmation. This is required by the expanded cache
coverage for timestamp-bearing mismatches.

Unlike fork base ad841a9a, this upstream base does not fold mailto labels.
The real recorded incident comparator fails before the upstream adaptation,
as do all five acceptance/readback regression cases (`upstream-base-go.txt`).
The twin adds structural redundant mailto/tel and URL-label folding, reference
ID label folding, and code-span preservation. Different destinations remain
distinct; additional Slack transformations still produce diagnostic uncertainty
without reversing acceptance. The real 3,429-character incident now passes.

Validation, GC_NO_INSTALL=1 throughout, no dependency installation or Slack posts:

- Full Go suite: 1,255 cases, 712 top-level, no failures/skips; real recorded
  incident enabled. See `upstream-go.txt` for the exact count and command.
- Python: 533 passed, 2 skipped, 2 existing os.fork warnings; the upstream base
  has no make test target, so its CI pytest runner was invoked through cached
  offline uv. See `upstream-python.txt`.
- Additional link-normalization and concurrent replay controls: focused race
  run passes 20 cases, no failures or skips; `upstream-race.txt`.

The fork's STANDARD Codex review of 8af195fd is CLEAN (`fork-review.txt`).
The upstream STANDARD gpt-6-astra review is also CLEAN (`upstream-review.txt`),
using the installed validated gate helper against upstream/main.

Fork draft PR: https://github.com/aphexcx/gascity-packs-prs/pull/48.
Upstream implementation reviewed at `9c398030d6945e96a42d829a35b8325b585b002d`; later changes are evidence only.

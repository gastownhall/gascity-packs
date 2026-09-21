# decompose wait-registration stop — RESOLVED 08:50Z; it was TRANSIENT, not deterministic

> **CORRECTION 2026-09-20T08:50Z.** The "deterministic, not transient" verdict below is
> **WRONG**. A third invocation of the same boundary, with no code change (workflows still
> at `81e311790`, `normalized_decompose_runner.py` untouched since 06:47) and with the
> `gc:wait` projection still returning **0 rows**, **succeeded**: exit **3**,
> `{"child_root_id":"gcg--9223372036854775263","input_convoy_id":"gp-d7pw4","phase":"waiting","status":"waiting"}`.
> The runner wrote `decompose-wait-attempt.json` (status `submitted`) then
> `decompose-wait-receipt.json` with wait `gcg--9223372036854775257`, and the exit-3 branch's
> `gc runtime drain-ack --json` was run and schema-validated. The bead stays **open** with no
> `gc.outcome`, now holding a registered durable wait rather than a park.
>
> Two consecutive exit-75s were **not** sufficient evidence of determinism — the real
> mechanism behind the 08:31/08:35 failures is still unexplained, since the empty projection
> I blamed is unchanged. Do not cite this document as proof that the `required=True` gate at
> `:1308-1309` is unreachable. The divergence from `normalized_child_launch.py:711-729`
> described below is still real as a code observation, but it is **not** a proven blocker.
>
> **The sealed wait attempt (`status: submitted`) must never be archived.**

## Original (superseded) analysis follows

# decompose hard stop #3 — wait registration is gated on a known false-empty projection

- Run: `issue-374-auto-20260915T000438Z`
- Root: `gcg--9223372036854775365` (reuse relaunch), decompose bead `gcg--9223372036854775297`, attempt 1
- Date: 2026-09-20 ~08:35Z
- Runner exit: **75** (`recoverable`), message:
  `decompose wait registration outcome is indeterminate; closed inventory unavailable`
- **Bead left OPEN / `in_progress`. No `gc.outcome` stamped. No drain-ack.**

## What advanced since the last stop

The previous blocker — the un-plumbed 15s child-launch root scan
(`decompose-hard-stop-diagnosis-20260920.md`) — is **fixed** upstream by workflows
`81e311790` ("run the decompose CLI under the documented 75s store budget"):
`--timeout-seconds` now defaults to `STORE_TIMEOUT_SECONDS = 75.0`. The root scan
passed on the first try this run.

Two things also had to be cleared first:

1. **Stale prior-generation receipts.** The shared run dir still held the receipts of
   decompose generation `gcg-699284130204933311`. The runner's nonce is derived from
   the *source bead*, so this generation computes a different nonce and fail-closed with
   `member bead receipt does not bind title`. That generation died **pre-sling** (no
   `launch-receipt.json`, no raw/helper temp, no child root), so its four receipts were
   **moved, not deleted**, to `generation-gcg-699284130204933311/` (see its `README.md`);
   member `gp-z8xzf` and convoy `gp-riems` are untouched and still open.
2. This generation then reconciled its own member bead + one-member convoy
   (`gp-d7pw4`) and **successfully launched the native child**.

## Current state — a live child with no registered wait

`decompose/launch-receipt.json` == `decompose/child.json`
(`978c45dc2274c5713a4cbc519105b6997cd73de4dd04b7f2144dda7944bf80aa`):

- child root `gcg--9223372036854775263`, formula `decomposition-base`, `status=in_progress`
- input convoy / source bead `gp-d7pw4`, launch nonce `3d79dab8…`
- `decompose/child-waiting.json` = `{child_root_id, status: "waiting"}`

The sling is done and idempotent: a second runner invocation reused the final receipt
and did **not** launch again (identical digest, same message, exit 75).

## Root cause: the decompose copy of the wait-registration gate diverged

`normalized_child_launch.py:711-729` states the rule explicitly:

> A fresh generation has not crossed the non-idempotent wait boundary yet; the supported
> open-wait query is sufficient to decide whether it may register. **The closed-wait
> projection is a split-store compatibility path and must never turn its false-empty
> result into a registration gate.**

`normalized_decompose_runner.py:1270-1309` re-implements that gate and inverts the rule.
Its `closed_evidence(required=…)` raises `WaitRegistrationUncertain` on
`WaitInventoryUnavailable`, and the fresh path calls it with `required=True`:

```python
if not exact:
    closed = closed_evidence(required=True)   # :1308-1309
```

(The docstring at `:1274-1276` asserts the opposite of the `child_launch` comment:
"A fresh generation, however, must obtain closed evidence before its first wait
mutation because absence authorizes registration.")

The projection it requires is the one `WaitInventoryUnavailable`
(`normalized_child_launch.py:30-35`, `:558-565`) is documented to distrust:

```
$ gc --city /data/projects/maintainer-city bd list --all --include-infra \
      --include-gates --label gc:wait --limit 0 --json
rows = 0
$ gc wait list --json
... "waits":[{"id":"mc-wisp-to2fae", ...}, {"id":"mc-wisp-9ow9p9", ...}, ...]
```

Waits on this city live in the **sessions** store, so the `gc:wait` label projection is
authoritatively empty — forever. `_closed_wait_evidence` therefore always raises
`WaitInventoryUnavailable`, and decompose can **never** register its first wait on this
city. **Deterministic, not transient** — reproduced twice back to back.

## Fix

Thread the `child_launch` tolerance into the decompose copy: on the fresh path
(`not exact`, no prior attempt fence) a `WaitInventoryUnavailable` must be treated as
`None`/non-gating exactly as `normalized_child_launch.py:718-729` does, keeping
`required=True` only where a **prior mutation fence** exists (`prior_attempt`), which is
the genuinely unobservable case. Then resume this same attempt: the runner will reuse the
existing launch receipt and the live child root rather than slinging again.

## Do not

- Do **not** re-run the boundary expecting a different result; it burns attempts on a
  deterministic stop (same mistake shape as the 15s scan).
- Do **not** write the seven blocked placeholders. That path is for the `blocked.json`
  run guard; there is no `blocked.json`, and stamping blocked receipts over a **live,
  launched child** would be contradictory evidence and a hard reconciliation stop.
- Do **not** close this bead pass or fail. The launch is real and mid-flight; a fail
  close would strand child root `gcg--9223372036854775263`.

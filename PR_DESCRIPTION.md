# fix(maintenance): stop rig-liveness-watchdog false-positive [INCIDENT] spam

## Problem

The `rig-liveness-watchdog` exec order was flooding inboxes with bogus
`[INCIDENT]` escalation mail on idle and suspended dev rigs. Three independent
bugs all contributed:

---

### Root cause 1 — Merge-freshness measured against stale local ref

**What was happening:** The stall-detection code measured "how long since the
last merge?" against the local `default_branch` ref (`refs/heads/main`). On a
quiet dev rig that isn't actively pulling, this local ref can lag hours behind
`origin/main`. The watchdog would see a stale local pointer, conclude nothing
had merged recently, and fire a stall alert even though merges were landing on
origin with no backlog at all.

**Compounding factor — branch-count as stall signal:** The old code also used
`git for-each-ref --no-contains <default>` to count "unmerged" branches and
treated a non-zero count as evidence of a backlog. This has a fundamental blind
spot: `git --no-contains` cannot see squash-merges (the standard merge strategy
for most PR workflows). A dev rig with 16 old local branches — all already
squash-merged into origin — would show `unmerged_branches=16` even though
nothing was actually queued. Combined with even one legitimately routed bead,
this manufactured a phantom 16-deep backlog and fired a false stall alert.

**Fix:** Freshness is now measured against `origin/<default-branch>` (the real
merge target) when a remote-tracking ref exists, falling back to the local ref
only when no remote exists. Unmerged-branch count is **demoted to evidence
only** — it appears in incident mail body for diagnostic context but no longer
gates the stall alert. The **routed-bead queue at or above `WATCHDOG_MIN_QUEUE`
is now the sole stall authority**. An idle rig with a sub-threshold queue is
treated as quiet, not stalled, regardless of local branch count.

---

### Root cause 2 — Startup flicker treated as instant death

**What was happening:** `creating`, `starting`, and `initializing` are normal
transient session states during a rig restart or a fresh spawn. The old
`is_dead_state()` function included `creating` in its hard-dead list (or
implicitly matched it via empty-string fallback), which meant every normal
startup cycle fired `[INCIDENT] refinery/witness creating`. On any rig that was
restarted, two bogus incidents landed before the agents had a chance to finish
starting.

**Fix:** Transient startup states are now handled by a separate `is_startup_state()`
predicate. A session in `creating | starting | initializing` is **not an
incident** until the state has persisted past `WATCHDOG_STARTUP_GRACE_MIN`
(default: 10 minutes). The grace window is anchored by a `first-seen` epoch
stored in the per-rig ledger, so the check is reliable across multiple ticks.
After the grace window expires, it is treated as a genuine stuck spawn and does
alert.

The `""` (empty-string) arm has been **removed** from `is_dead_state`. It was
dead code: `role_state` always returns `"absent"` (never an empty string) for a
missing session, and `is_startup_state` now owns the `creating` path. Removing
the arm makes the case statement an exact allowlist with no silent catch-all.

---

### Root cause 3 — Tick-modulo re-alert spamming every 3 minutes

**What was happening:** The deduplication mechanism used a tick-modulo counter
in the ledger: it stored a bare integer (number of times the incident was
observed) and re-sent mail every N ticks. With a 3-minute tick and a small
modulo, a persistent-but-benign condition (e.g. a suspended refinery's empty
queue) would generate a new `[INCIDENT]` mail every few minutes indefinitely.

**Fix:** The tick-modulo approach is replaced by a **hard wall-clock cooldown**
(`WATCHDOG_COOLDOWN_MIN`, default: 45 minutes), mirroring the per-key epoch
ledger used by `nudge-on-mail.sh`. The ledger entry shape is promoted from a
bare integer to a `{c, t, f}` object:

- `c` — total observation count (diagnostic)
- `t` — epoch of the last mail **actually sent** (cooldown clock)
- `f` — epoch the incident streak was **first seen** (startup grace anchor)

Within the cooldown window, a recurring incident is silently re-counted but
**not re-mailed**. When the cooldown expires, one mail fires and the clock
resets. Legacy ledgers storing bare integer counts are coerced on read so an in-
place upgrade does not crash or lose deduplication state.

---

### Additional hardening

- **Mail send failure no longer silently advances the cooldown clock.** If
  `gc mail send` fails, the ledger stamp (`t`) and `INCIDENTS` counter are NOT
  updated. The incident is marked as seen (so it survives ledger pruning and the
  streak is preserved), and a warning is logged to stderr. This prevents a
  transient mail failure from silently suppressing future alerts for up to
  `WATCHDOG_COOLDOWN_MIN` minutes.

- **Non-atomic ledger write replaced with temp-file + mv.** The final
  `printf > $LEDGER` is now a write-to-temp then `mv -f` to match the project
  convention for atomic file updates.

## What is NOT changed

- Suspended and non-running rigs are still skipped early — an intentionally
  suspended rig's sleeping agents are expected and generate no alerts.
- **Dead/crashed refinery escalation remains UNGATED.** A refinery in a hard-
  dead state (`crashed`, `failed-create`, `closed`, absent) is always an
  incident regardless of queue depth or cooldown, so a genuine silent death with
  real queued work still fires promptly.
- The witness heartbeat staleness check (alive witness with dead patrol loop) is
  unchanged in semantics; it benefits from the cooldown fix automatically.

## Upgrade notes

The per-rig ledger is stored at:

```
$GC_PACK_STATE_DIR/rig-liveness-incidents-<rig-slug>.json
```

Existing ledgers with bare-integer values are automatically coerced to the new
`{c,t,f}` object shape on next read; no migration step is required.

## Config knobs (all env-overridable)

| Variable | Default | Purpose |
|---|---|---|
| `WATCHDOG_COOLDOWN_MIN` | 45 | Min minutes between re-alerts for same (rig, incident-type) |
| `WATCHDOG_STARTUP_GRACE_MIN` | 10 | How long a transient startup state is tolerated before alerting |
| `WATCHDOG_MIN_QUEUE` | 2 | Min routed merge-queue depth required to call a merge stall |
| `WATCHDOG_FRESH_MIN` | 60 | Merge-freshness window in minutes |
| `WATCHDOG_WITNESS_STALE_MIN` | 30 | Witness heartbeat staleness threshold in minutes |
| `WATCHDOG_ESCALATE_TO` | mayor | Recipient for incident mail |

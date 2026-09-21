# fix(gastown): guard the refinery rebase against an already-based source

Closes issue 374.

`mol-refinery-patrol`'s `rebase` step ran `git checkout -b temp origin/$BRANCH`
followed by `git rebase origin/$TARGET` unconditionally. When `origin/$TARGET`
is already an ancestor of `origin/$BRANCH` the source is a pure fast-forward
candidate, and rebasing it drops merge commits together with their recorded
conflict resolutions — producing either an artificial conflict on an unchanged
SHA (the rejection treadmill) or a silent flattening that merge-push then
force-pushes over the source branch.

Three files change: the formula (guard + prose), the inference gate (repin), and
a new lifted-block regression suite.

| Commit | Contents |
| --- | --- |
| `8d087e0` | D4 — `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`, test-first |
| `9b89515` | D1+D2+D3 — formula guard, step prose, inference-gate repin, atomically |

All `:NNN` citations below are **re-derived against this branch**, not the
base-tree groundings used during design.

## The guard (`:298-:341`)

Ordered prune-fetch → halt → guard-fetch → probe → case. The pre-existing
`git fetch --prune origin` (`:248`) and the entire missing-`$TARGET` halt
(`:249-:297`) are **byte-identical to base** — verified by hashing the range,
not by inspection:

```
$ git show 05031f2c:gastown/formulas/mol-refinery-patrol.toml | sed -n '248,293p' | sha256sum
c7d4683f24ab5cc624f57de0bb2f6e7c9b858f2d2669234521e26f135cfc53ab
$ sed -n '248,293p' gastown/formulas/mol-refinery-patrol.toml | sha256sum
c7d4683f24ab5cc624f57de0bb2f6e7c9b858f2d2669234521e26f135cfc53ab
```

| Condition | Route | Bead | Clone |
| --- | --- | --- | --- |
| `$TARGET` missing on origin | halt `:249-:297`, unchanged (park + escalate + pour) | mutated by the halt, as today | unchanged, no `temp` |
| explicit fetch fails (unreachable origin; `$BRANCH` deleted) | STOP `:305-:307` | untouched | no `temp` |
| probe rc=0 | exit-checked checkout `:322`, `SKIP-REBASE:` `:327` | untouched by the decision | `temp` == `origin/$BRANCH`, merges intact |
| probe rc=0 but checkout fails (stranded stale `temp`) | STOP `:323-:325` | untouched | stale `temp` left exactly as found |
| probe rc=1 | bare checkout `:331` + preserved rebase `:332` → existing conflict path | as today | as today |
| probe rc>1 | STOP `:337-:339` | untouched | no `temp` |

The guard fetch (`:304`) must follow the halt: explicit-fetching a missing
`$TARGET` exits 128 and would swallow `target_branch_missing` into the generic
STOP, bypassing the halt's park, escalation and wisp-pour. Its exit is checked
because a failed fetch leaves stale tracking refs that can still satisfy
`--is-ancestor`, so the probe alone would skip-decide on fiction.

## Verification

### Red control (AC-374-04)

The **identical test file, byte-unmodified**, aimed at the unguarded base tree
via the env override — never a hand-copied formula, never an edit between runs:

```
git worktree add --detach /tmp/issue374-base-05031f2c 05031f2c
REBASE_GUARD_FORMULA=/tmp/issue374-base-05031f2c/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Outcomes **enumerated per leg, not counted**:

| Leg | Base (unguarded) | Guarded (this branch) |
| --- | --- | --- |
| 1 — skip preserves topology (EX-1 + EX-2) | FAIL (behavioral) | PASS |
| 1b — stranded `temp` fails closed at the skip-arm checkout | FAIL (behavioral) | PASS |
| 2 — diverged clean rebases as today | PASS | PASS |
| 3 — diverged conflicting keeps the conflict path | PASS | PASS |
| 4 — fetch failure stops before the probe (stale-ref trap) | FAIL (behavioral) | PASS |
| 5 — missing source branch | FAIL (behavioral) | PASS |
| 6 — probe error fails closed (`merge-base` shimmed to 128) | FAIL (behavioral) | PASS |
| 7 — structural backstop and ordering (static) | FAIL (static) | PASS |
| 8 — halt composition (target branch missing) | PASS | PASS |

This is exactly D4's prediction. The lift sentinel
(`git checkout -b temp origin/$BRANCH`) is present in both the unguarded and the
guarded formula, so the reds are behavioral, never lift errors — leg 7's reds
are the static half (its pinned strings do not exist at `05031f2c`). The
red-control capability is permanent in the file; CI keeps only the green side.

**Git versions exercised:** git 2.43.0 locally. Leg 3's `rc 1` assertion is
git's empirically stable rebase-conflict code (git documents only "non-zero on
conflict"), measured on 2.43 and **not yet re-confirmed against CI's git
2.52** — see Known limitations.

### Full sweep

| Step | Command | Result |
| --- | --- | --- |
| 3 | `bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` | all nine legs pass |
| 5 | `python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` | `89 passed` |
| 6 | `for t in gastown/tests/test_*.sh; do bash "$t"; done` | green, every test |

Step 6, per test (witness / heartbeat / polecat untouched):

```
  PASS  gastown/tests/test_gastown_pack_assets.sh
  PASS  gastown/tests/test_gastown_theme_scripts.sh
  PASS  gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
  PASS  gastown/tests/test_mol_witness_patrol_orphan_recovery.sh
  PASS  gastown/tests/test_polecat_churn_watcher.sh
  PASS  gastown/tests/test_polecat_push_gate.sh
  PASS  gastown/tests/test_witness_heartbeat_check.sh
```

### Pinned literals — sites enumerated, no count asserted

`mol-refinery-patrol` appears in `scripts/gascity_pack_inference_gate.py` at
three sites, re-derived by grep: `:91` (prose dict), `:122` (command dict — the
one repinned), `:823` (the `setup_formulas` registry entry, which names the
formula only and needs no change; it sat at `:790` before the insertion).

`GASTOWN_BUILD_WORKFLOW_CONTRACTS["mol-refinery-patrol"]`, each literal grepped
against the changed formula with its matching sites listed:

| Pin | Sites in the changed formula |
| --- | --- |
| `git rebase origin/$TARGET` (preserved) | `:332` |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:304` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:315` |
| `ANCESTOR_RC=$?` | `:316` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:305`, `:337` |
| `echo "SKIP-REBASE:` | `:327` |
| `gc bd list ${GC_RIG:+--rig="$GC_RIG"} --assignee=$GC_AGENT --status=open,in_progress` | `:174` |

The fail-closed sentence is a deliberate **two-site collective** pin: it
witnesses that the fail-closed family exists, so deleting or rerouting both
error paths without repinning breaks the gate, while deleting a single arm stays
satisfied by the other copy. Single-arm deletion is caught instead by leg 7's
per-arm literals (`tracking refs failed` `:305`, `errored (status ` `:337`,
`cannot materialize temp at origin/` `:323`) and behaviorally by legs 1b/4/6.
Those per-arm strings are deliberately **not** promoted to gate pins:
`errored (status ` also occurs in merge-push (`:881`), so under the gate's
whole-file containment a pin on it would be absorbed.

The `:122` command-dict pins for the merge step, and all five prose-dict
(`:91`) fragments, still match — the insertion removes no prose and D2's
amendments touch none of them.

## Recorded assumptions and deliberate asymmetries

### No-errexit execution assumption — measured, not asserted

The fence relies on the executing agent shell not running fences under `set -e`,
so a probe rc=1 falls through to the `case`. This is the exact status quo the
base `git rebase origin/$TARGET` line already depended on. Measured on git
2.43.0 / bash 5.2:

| Form | Diverged (real rc 1) | Probe error (real rc 128) |
| --- | --- | --- |
| shipped: bare probe, `ANCESTOR_RC=$?` next line, no errexit | captured `1` → rebase arm | captured `128` → STOP arm |
| same under `set -e` | shell dies at the probe; `case` never entered | shell dies at the probe |
| `ANCESTOR_RC=0; probe \|\| ANCESTOR_RC=$?` under `set -e` | captured `1` → rebase arm | captured `128` → STOP arm |
| `probe \|\| true; ANCESTOR_RC=$?` under `set -e` | captured `0` → **skip arm** | captured `0` → **skip arm** |

Any future errexit adaptation must use the `ANCESTOR_RC=0; … || ANCESTOR_RC=$?`
capture form. **Never `|| true`**: as measured above it collapses both rc 1 and
rc 128 to 0, routing a genuinely needed rebase *and* an unevaluable probe into
the skip arm — the two worst outcomes the guard exists to prevent.

### The `1)` arm's bare checkout is deliberate, not an oversight

The `0)` arm's checkout is exit-checked (`:322`); the `1)` arm's is bare
(`:331`). The asymmetry is intentional. The `1)` arm reproduces today's exact
adjacent checkout+rebase pair byte-identically, which is what makes AC-374-05
("diverged path unchanged") eye-verifiable and keeps the preserved gate pin
honest. The `0)` arm is exit-checked because the skip path is *new*: without the
check, a `temp` stranded by the pre-existing merge-push STOP wedge would be
silently consumed and mis-narrated as a skip, and merge-push would then
`--force-with-lease` over the source branch — the lease passing precisely
because the guard fetch just freshened `origin/$BRANCH`.

The rc=1 arm therefore carries the **same pre-existing** stranded-`temp`
exposure it has always had. That is scoped out of this change, recorded here so
it is never read as an oversight, and it adds zero new stranding sites. Clearing
a stale `temp` remains a human/merge-push-side concern.

### No STOP arm pours a successor wisp

Confirmed by line-scoped grep: the only `gc bd mol wisp` pour in the `rebase`
step is `:277`, inside the missing-`$TARGET` halt. The guard's three STOP arms
(`:306`, `:324`, `:338`) are echo + `gc runtime drain-ack` + `exit 1` and
nothing more — no `rejection_reason`, no delete/reopen-source, no polecat
reroute, no `gc bd update` of any kind. A tooling error is not a conflict. The
halt pours because parking one bead must not end the merge lane; the guard STOPs
do not, because they mutate nothing and the bead stays assigned.

### Verified STOP respawn source (replaces the design's assertion)

The design asserted from repo evidence that re-selection "relies on the rig's
patrol respawn cadence (reconciler/pour)" and required this to be measured
against a live rig. Measured against the live `maintainer-city` Gas City:

**The respawn source is the city-level `[session_sleep]` restart policy
(`noninteractive = "5m"`) applied by the session reconciler to the refinery's
`wake_mode = "fresh"` session — not a poured wisp, not a cron/order cadence, and
not `orphan-sweep`.** On restart, `find-work` re-selects the untouched work bead
(open, assigned, carrying `metadata.branch`), which is exactly the intended
retry-by-repatrol semantic.

Three candidate paths are provably inert for a guard STOP:

- **No cron/order cadence exists for this formula.** The city has exactly three
  `formula`-type cooldown orders (`randy-patrol` 3h, `seth-patrol` 15m,
  `wendy-patrol` 1h); none is the refinery, and the gastown pack ships no order
  definition for `mol-refinery-patrol`.
- **`orphan-sweep` does not reclaim the abandoned patrol wisp.** That core order
  (5m cooldown) resets only `in_progress` beads whose assignee fails
  `is_known_agent`, whose first test is `agent_exists` — and `<rig>/refinery`
  *is* a configured agent, so the wisp is skipped. Its scope is beads assigned
  to agents that no longer exist, not dead sessions of live agents.
- **`nudge-on-route` never fires.** It is event-triggered on `bead.updated`, and
  the STOP arms mutate no bead state. The zero-mutation property that makes the
  STOP safe is what makes this recovery path inert.

*Limitation:* `maintainer-city` does not instantiate the gastown rig agents (no
`refinery`/`witness`/`polecat` in `gc agent list`, no refinery session in
`gc session list --state=all`). The above measures the governing configuration
and traces the code paths that act on it end to end; it is not a direct
observation of a live refinery STOP→respawn cycle. The three exclusions are
config/code facts independent of that; the positive 5-minute restart claim would
be confirmed empirically on a rig that runs the refinery.

## Known limitations

- **Leg 3's `rc 1` is measured on git 2.43 only.** Git promises only non-zero on
  a conflicting rebase. If CI's git 2.52 returns a different non-zero code,
  leg 3 reds while the guard is still correct. This is the one assertion in the
  suite that could red on CI for a version reason.
- **Leg 7 pins composition order textually.** Legitimate reformatting of the
  fence (e.g. moving the prune fetch off line 1 of the block) reds leg 7 even
  with behavior unchanged. That is the intended backstop against silent
  mangling.
- **The gate is a deletion-only whole-file layer.** It cannot see arm structure
  or site counts, so the test must keep running in CI for the guard's per-arm
  structure to stay protected. Anti-fix rule, recorded beside the pin: the
  skip-arm checkout STOP must never be "covered" by rewording its echo to carry
  the collective sentence — the pin would then witness a false statement about
  what failed.
- **`BRANCH == TARGET` degeneracy** gives probe rc=0 and a no-op landing
  downstream; asserted, exercised by no leg, accepted as out of scope.

## Follow-up

The residual-precision-(b) family — a deleted-`$BRANCH` park mirror of the
`$TARGET` halt, plus the repeated stranded-`temp` checkout-STOP (the same
assigned head-of-line class) — is filed as tracked work, not left as committed
prose. Parking either would require bead mutation on an error path, which this
change's contract forbids, so both belong to a separate change.

**Tracked as `gp-2rn1y`** — "mol-refinery-patrol: assigned head-of-line family —
deleted-`$BRANCH` park mirror + repeated stranded-`temp` checkout-STOP (374
follow-up)" (P2, open, routed to `human`).

That item carries both members as one family, with the constraints this change
imposes on them. Member 1 — mirroring the `$TARGET` halt's park for a
permanently-deleted `$BRANCH` — needs its own design pass: parking on a
fetch-error path is exactly the bead mutation this contract forbids, and a park
there must reconcile with the mid-step `$TARGET` deletion race (one STOP, then
park next cycle, is the accepted behavior here and must not regress) and with
the STOP arms' no-successor-wisp semantics. Member 2 — the repeated
stranded-`temp` checkout-STOP — is healed on the merge-push side or at the
skip-arm STOP, never by widening this change's STOP semantics; the pre-existing
stranding sites at `:826-:829` and `:838-:841` stay out of scope.

Neither member may route tooling errors through the conflict-rejection path (no
`rejection_reason`, no delete/reopen-source, no polecat reroute), and neither
may weaken the missing-`$TARGET` halt, the guard's fetch/probe ordering, or
merge-push's ff-only tail.

Committed prose alone is not the tracking — the bead is.

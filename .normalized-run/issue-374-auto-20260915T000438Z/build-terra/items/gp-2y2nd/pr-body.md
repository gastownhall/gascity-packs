# fix(gastown/refinery): skip the rebase when the source is already based

Fixes #374.

`mol-refinery-patrol`'s `rebase` step used to check out `origin/$BRANCH` onto
`temp` and then run `git rebase origin/$TARGET` unconditionally. When
`origin/$TARGET` is already an ancestor of `origin/$BRANCH`, that rebase is
not a no-op: it flattens merge commits and drops the conflict resolutions
recorded in them.

Both failure modes were reproduced on `git version 2.43.0` while building
the fixtures, not inferred:

- **Merge-conflicting history (EX-1)** — linear replay hits an artificial
  conflict on an unchanged SHA (the rejection treadmill).
- **Clean history (EX-2)** — rebase succeeds but silently flattens; merge-push
  then force-pushes the rewrite over the source branch.

This lane's commits:

| Commit | Item |
| --- | --- |
| `83a2525e1a6956292144c1e82c1ba38b7a5e25c5` | W1 — regression suite (test-first) |
| `bb0c9de022cbc81dad012d509535d2feb766f251` | W2 — D1 guard + D2 prose + D3 gate repin, atomic |

The only permitted split is test-first, then formula-and-gate in one commit.
Shipping the formula without the gate repin in the same change violates
AC-374-07.

`push=false` / `open_pr=false` for this run: this file is the PR-body
record the design requires, not a GitHub pull request.

## The guard

Ordering is prune-fetch → halt → guard-fetch → probe → case. Every edge is
load-bearing:

- The explicit fetch **must follow** the missing-target halt. An explicit
  refspec fetch of a missing `$TARGET` exits 128, so running it first would
  swallow `target_branch_missing` into the generic STOP and skip the halt's
  park / escalation / wisp-pour.
- The fetch exit is **checked**. A failed fetch leaves stale tracking refs
  that can still satisfy `--is-ancestor`.
- The probe is captured bare into `ANCESTOR_RC` with `$?` on the next line
  (not `status`; zsh read-only), then discriminated three ways: rc 0 skips,
  rc 1 runs today's two lines, any other rc STOPs.
- The skip arm's checkout is **itself exit-checked**. The `1)` arm keeps
  today's bare `git checkout -b temp origin/$BRANCH`.

Every new STOP route is retry-later: echo, `gc runtime drain-ack`, `exit 1`.
No `rejection_reason`, no delete/reopen-source, no polecat reroute, no bead
mutation. Only the missing-`$TARGET` halt parks.

## Verification

All measurements on `git version 2.43.0`, inside worktree
`/data/projects/gascity-packs/worktrees/normalized-b41aca27b0b56f221e5914867fb18a5b64c1b69de6719c21a904b104e88ba141-terra`
at `bb0c9de022cbc81dad012d509535d2feb766f251`. `pwd -P` matched before any
source read, test, or hash.

### Red control (design step 4)

Mechanism, exactly as specified — the fix tree's test file is invoked
byte-unmodified against a detached worktree of the unguarded base; the
formula is never hand-copied and the test is never edited between runs:

```
git worktree add --detach /tmp/rc-base-374-terra-w3 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374-terra-w3/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Test file `sha256:45ff999a8e76ff58a2a055333b54c6bf5e699766bfd3a5b009a3eaa2b1efa307`,
identical across both runs. Unguarded formula
`sha256:c5a2da6391b1cb2c20334322e892bb5a95873d145f319c7946347a3816e0f1d8`
at `05031f2c`. Fixed formula
`sha256:95ae370a8f1531c277a23e8c0a6e7c171e24902558228e4232e502f2cd3fb64d`
at `bb0c9de`.

Outcomes enumerated per leg, never counted (unguarded, exit 1):

| Leg | Result | Why |
| --- | --- | --- |
| 1 | FAIL | fence rc=1 on EX-1 skip path (artificial conflict) |
| 1b | FAIL | fence rc=0; stranded `temp` checkout failed silently, then rebase ran against detached HEAD |
| 2 | PASS | diverged clean still rebases |
| 3 | PASS | diverged conflicting still rc=1 with rebase in progress |
| 4 | FAIL | missing fetch-STOP wording; stale-ref trap still reaches rebase |
| 5 | FAIL | missing source surfaces at checkout with rc=0, not a STOP |
| 6 | FAIL | missing probe-error STOP wording |
| 7 | FAIL | probe line occurs 0 times (static; strings absent at `05031f2c`) |
| 8 | PASS | missing-target halt still fires |

Then the identical file against the fixed tree (no `REBASE_GUARD_FORMULA`):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

exit 0; legs 1, 1b, 2, 3, 4, 5, 6, 7, 8 all PASS.

### Inference gate (design step 5)

```
PYTHONPATH=/home/ubuntu/.local/lib/python3.12/site-packages \
  python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
```

89 passed in 3.39s, exit 0. (This environment's user site is remapped, so
`python3 -m pytest` needs that `PYTHONPATH`.)

### Full gastown shell suite (design step 6)

```
for t in gastown/tests/test_*.sh; do bash "$t"; done
```

All seven files green: pack assets, theme scripts, rebase-guard, witness
orphan recovery, polecat churn watcher, polecat push gate, witness heartbeat.

### Pinned literals (design step 7)

Sites enumerated at fix time against this tree; never asserted as a count.

| Fragment | Formula site(s) | Gate site |
| --- | --- | --- |
| `git rebase origin/$TARGET` | `:332` (`1)` arm, unquoted) | `:124` |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:304` | `:125` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:315` | `:126` |
| `ANCESTOR_RC=$?` | `:316` | `:127` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:305` (fetch STOP) and `:337` (probe-error STOP) | `:128` |
| `echo "SKIP-REBASE:` | `:327` | `:129` |

`mol-refinery-patrol` also appears in the gate file at `:91` (prose dict:
`metadata.branch`, `fast-forward merge`, `run tests before merging`,
`metadata.target`, `closes the bead`) and `:795` (`setup_formulas` registry,
name only). Neither was changed.

## Step-8 records

### No-errexit execution assumption

The lifted fence captures `git merge-base --is-ancestor …` then
`ANCESTOR_RC=$?` and `case`s on it. A probe rc=1 **must** fall through to
the `case`. That is the same assumption base `:295` already depends on:
the recipe runs in a plain agent shell, not under `set -e`. Any future
errexit adaptation must use
`ANCESTOR_RC=0; git merge-base … || ANCESTOR_RC=$?` — never `|| true`,
which destroys the trichotomy.

### Deliberate `1)`-arm bare checkout

The `0)` arm is exit-checked (`if ! git checkout -b temp origin/$BRANCH;
then …` at `:322`). The `1)` arm keeps today's exact bare pair at
`:331-:332`. The rc=1-arm stranded-`temp` wedge is pre-existing and
scoped out of this change; recording it here so it is never read as an
oversight. The lift sentinel substring survives at both sites.

### No successor wisp on STOP arms

`gc bd mol wisp mol-refinery-patrol` sites in this formula, enumerated:
`:4`, `:124`, `:277`, `:383`, `:488`, `:587`, `:1288`.

Inside step `rebase` (`:223-:407`) the pours are `:277` (missing-`$TARGET`
halt, `:253-:297`) and `:383` (conflict-rejection tail). The guard block
`:298-:341` contains none: each STOP is echo + `gc runtime drain-ack` +
`exit 1` (`:305-:307` fetch, `:323-:325` skip-arm checkout, `:337-:339`
probe error). Line-scoped inspection of `:298-:341` finds no `bd update`
and no wisp. The halt alone pours, so one bead cannot end the merge lane;
a guard STOP deliberately can.

### Verified STOP respawn source (residual precision (a))

Measured 2026-09-22 against live `maintainer-city` (this pack's city),
replacing the design's repo-evidence-only assertion.

**Finding: the respawn source is the city-level `[session_sleep]` restart
policy applied by the session reconciler — not a poured wisp, not a
cron/order cadence, and not `orphan-sweep`.**

Resolved city config:

```
[session_sleep]
interactive_resume = "5m"
interactive_fresh  = "5m"
noninteractive     = "5m"
```

Pack-shipped `gastown/agents/refinery/agent.toml`: `wake_mode = "fresh"`,
`idle_timeout = "2h"`, `max_active_sessions = 1`. A patrol session is
non-interactive, so the reconciler restarts it on the `noninteractive =
"5m"` sleep policy. `find-work` already names the mechanism (`:217`):
"The session_sleep policy will restart this session after the configured
idle interval." The restarted session re-selects open beads assigned to
this refinery that carry `metadata.branch`.

Ruled out, each with the check:

1. **Not a poured wisp.** Guard STOP arms are echo + drain-ack + exit 1.
   The only rebase-step pour is the halt at `:277`.
2. **Not a cron/order cadence.** `gc order list` in this city has exactly
   three `formula`-type cooldown orders — `randy-patrol` (3h),
   `seth-patrol` (15m), `wendy-patrol` (1h) — and none for the refinery.
3. **Not `orphan-sweep`.** Core order, exec, 5m, "Reset beads assigned to
   dead agents back to the work pool". `is_known_agent`'s first real test
   is `agent_exists "$name"` against configured agent templates. A
   `<rig>/refinery` assignee is a configured agent, so a dead *session* of
   a live *agent* is not in scope. Header prose: beads "assigned to agents
   that don't exist in ANY rig".
4. **Not `nudge-on-route`.** Event trigger `bead.updated`. Guard STOP arms
   mutate no bead state, so no event fires. The zero-mutation contract is
   exactly what makes this recovery path inert.

This city currently has no live refinery session to time a STOP→respawn
cycle against; the mechanism is read off the live city config, the live
order table, and the formula's own find-work prose. Each restart re-runs
the decision from scratch against freshly fetched refs. A persistent
failure surfaces as a repeated STOP log rather than a mutation loop.

## Residual-precision-(b) follow-up

Filed as tracked work (design verification step 9). Committed prose is
not the tracking.

**Tracked item: [`gp-kwysx`](beads/gp-kwysx)** — *mol-refinery-patrol:
assigned head-of-line family — deleted-`$BRANCH` park mirror + repeated
stranded-`temp` checkout-STOP (issue 374 follow-up)*. Open, P2, assigned
to `human`. One family, not two tickets.

Constraints the family inherits from this change:

- Do not route these errors into the conflict-rejection path (no
  `rejection_reason`, no delete-source/reopen-source, no polecat reroute).
- Do not weaken the missing-`$TARGET` halt.
- Do not touch merge-push (already-merged gate, ff-only tail,
  force-with-lease).
- Do not widen the issue-374 guard STOP semantics as a side effect.

W3's sealed `items/gp-sc2pz/pr-body.md`
(`sha256:fdfb77ab3621628372fb24fb91aa269080fdd80526023f2a58d8e3f80e60e32f`)
is unchanged; this copy is the W4-linked body.

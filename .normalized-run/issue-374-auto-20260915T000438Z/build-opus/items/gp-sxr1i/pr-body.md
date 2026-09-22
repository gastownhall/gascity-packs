# fix(gastown/refinery): skip the rebase when the source is already based

Fixes #374.

`mol-refinery-patrol`'s `rebase` step ran `git checkout -b temp origin/$BRANCH`
followed by an unconditional `git rebase origin/$TARGET`. When `origin/$TARGET`
is already an ancestor of `origin/$BRANCH` the source is a pure fast-forward
candidate, and that rebase is not a no-op — it flattens merge commits and drops
the conflict resolutions recorded in them.

Both failure modes were reproduced directly on git 2.43.0 while building the
fixtures, not inferred:

- **Merge-conflicting history** — rebase replays the two sides of a resolved
  merge linearly and hits an artificial conflict on an unchanged SHA. This is
  the rejection treadmill: the bead is bounced to a polecat that cannot fix it,
  because nothing is actually wrong with the branch.
- **Clean history** — rebase succeeds, but silently flattens: merge count
  `2 -> 0` and `temp` is no longer SHA-identical to `origin/source`. merge-push
  then force-pushes that flattened history over the source branch.

## Commits

| Commit | Item |
| --- | --- |
| `4fb5642` | W1 — the regression suite (test-first, red on the unguarded tree by construction) |
| `2df2dca` | W2 — D1 guard insertion + D2 prose + D3 inference-gate repin, atomic |

The split is test-first then formula-and-gate-atomically, which is the only
split the approved design permits: shipping the formula without the gate repin
in the same change violates AC-374-07, because a gate whose pinned fragment no
longer exists silently stops witnessing the guard it protects.

## The guard

Ordering is prune-fetch -> halt -> guard-fetch -> probe -> case, and every edge
is load-bearing:

- The explicit fetch **must follow** the missing-target halt. Fetching an
  absent `$TARGET` with an explicit refspec exits 128, so running it first
  would swallow `target_branch_missing` into the generic STOP and bypass the
  halt's dedicated park, escalation and wisp-pour.
- The fetch exit is **checked**. A failed fetch leaves stale tracking refs that
  can still satisfy `--is-ancestor`, so the probe alone would decide on fiction.
- The probe is captured bare into `ANCESTOR_RC` with `$?` on the next line — no
  `if !` negation, no intervening command substitution — then discriminated
  three ways: rc 0 skips, rc 1 runs exactly the two lines this step always ran,
  any other rc STOPs rather than being read as "not an ancestor".
- The skip arm's checkout is **itself exit-checked**. Over a `temp` stranded by
  the pre-existing merge-push STOP wedge, an unchecked checkout would narrate a
  skip over a stale branch that merge-push then consumes by name and pushes with
  `--force-with-lease` — and the lease would pass, because the guard fetch just
  freshened `origin/$BRANCH`.

Every new STOP route is retry-later: echo, `gc runtime drain-ack`, exit. No
`rejection_reason`, no delete/reopen-source, no polecat reroute, no bead
mutation of any kind. A tooling error is not a conflict. Only the
missing-target case keeps its dedicated park.

## Verification

All measurements on `git version 2.43.0`. CI runs git 2.52; see the rc-discipline
note below for the single assertion that is version-sensitive.

### Red control

Mechanism, exactly as the design specifies — the fix tree's test file is
invoked **byte-unmodified** against a detached worktree of the unguarded base;
the formula is never hand-copied and the test is never edited between runs:

```
git worktree add --detach /tmp/rc-base-374 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Test file `sha256:e6ad1ae60e695d1f290f80e733df4e1e31aacdd891b539c7928a556bcce44bed`,
identical across both runs. Unguarded tree `05031f2c`, fixed tree `2df2dca`.

Outcomes enumerated per leg, never counted:

| Leg | Unguarded base `05031f2c` | Fixed tree `2df2dca` |
| --- | --- | --- |
| 1 — skip preserves topology (EX-1, EX-2) | FAIL (behavioural) | PASS |
| 1b — stranded `temp` fails closed | FAIL (behavioural) | PASS |
| 2 — diverged clean rebases as today | PASS | PASS |
| 3 — diverged conflicting keeps conflict path | PASS | PASS |
| 4 — fetch failure stops before the probe | FAIL (behavioural) | PASS |
| 5 — missing source branch | FAIL (behavioural) | PASS |
| 6 — probe error fails closed | FAIL (behavioural) | PASS |
| 7 — structural backstop + ordering | FAIL (static) | PASS |
| 8 — halt composition | PASS | PASS |

Suite exit `1` unguarded, `0` guarded. Legs 2, 3 and 8 are green controls on
both trees — 8 in particular pins that the fix neither replaced nor reordered
the pre-existing halt.

Each red is for its documented reason. Leg 7 is red statically because its
pinned strings do not exist at `05031f2c` (`expected the ancestry probe exactly
1 time(s) in the lifted block, found 0`). Leg 5's captured output shows the
unguarded failure surfacing late at the checkout with **rc 0** and no STOP
routing:

```
fatal: 'origin/source' is not a commit and a branch 'temp' cannot be created from it
Current branch main is up to date.
```

The behavioural-red capability is permanent in the file, because the lift
sentinel `git checkout -b temp origin/$BRANCH` exists on both trees — reds are
behavioural, never lift errors.

### Static gates

`python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` — **89 passed**.

Each pinned literal grepped in the changed formula with its sites enumerated,
never counted. All line numbers re-derived on the fix branch rather than copied
from the contract:

| Pin | Sites |
| --- | --- |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:303` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:314` |
| `ANCESTOR_RC=$?` | `:315` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:304`, `:336` |
| `echo "SKIP-REBASE:` | `:326` |
| `git rebase origin/$TARGET` (preserved, unquoted, rc=1 arm) | `:331` |

The collective sentence resolves at exactly its two intended arms. The
checkout-STOP arm at `:322` deliberately does **not** carry it: that arm's
failure is checkout materialization, not ancestry evaluation, so covering it by
rewording would make the collective pin witness a false statement. Single-arm
deletion is caught instead by leg 7's per-arm literals (`tracking refs failed`,
`errored (status `, `cannot materialize temp at origin/`) and behaviourally by
legs 1b, 4 and 6.

The gate's three `mol-refinery-patrol` sites were enumerated: the prose dict,
the command dict, and the `setup_formulas` registry entry (which names the
formula only and needs no change). The prose-dict fragments (`metadata.branch`,
`fast-forward merge`, `run tests before merging`, `metadata.target`,
`closes the bead`) all still resolve — the insertion removes no prose and D2
touches none of those five.

### Confinement

The formula diff is four hunks: the D2.3 intro sentence, the D1 insertion, and
the two D2 prose amendments. Base `:248-:293` is byte-identical, proven by
sha256 comparison rather than by reading the diff. The conflict tail and
merge-push are untouched; merge-push's already-merged gate survives at `:848`
(base `:795`, shifted by this insertion), still probing the reverse operand
order and still using the distinct `ANCESTOR_STATUS` capture name. The formula
still parses as TOML with all nine steps intact.

Full CI loop `for t in gastown/tests/test_*.sh; do bash "$t"; done` — all seven
files green.

## Recorded assumptions and deliberate asymmetries

**No-errexit execution assumption.** The step's fenced block runs in a plain
agent shell, without `set -e` and without `set -o pipefail`. The guard therefore
does not rely on errexit to stop: every fail-closed route is an explicit
`if ! ...; then ... exit 1; fi`, and the probe's status is captured explicitly
rather than being allowed to abort the block. The test harness executes the
lifted block under `set +eu` for the same reason — testing it stricter than it
ships would measure the wrong thing.

**The `1)` arm's bare checkout is deliberate, not an oversight.** The skip arm
(`0)`) exit-checks its `git checkout -b temp origin/$BRANCH`; the diverged arm
(`1)`) deliberately keeps the bare, unchecked checkout the step has always run.
The asymmetry is intentional and scoped: the rc=1-arm stranded-`temp` wedge is
pre-existing behaviour, out of scope for this change, and preserving it
byte-identical is what keeps AC-374-05 ("diverged source keeps the existing
rebase/conflict path") true and what keeps the existing gate pin matching.
Recorded here so it is never read as a missed case.

**No STOP arm pours a successor wisp.** Enumerated: the wisp-pour sites in this
formula are `:4`, `:124`, `:276`, `:381`, `:486`, `:585` and `:1286`. Of these,
`:276` is inside the missing-`$TARGET` halt. None of the guard's three STOP arms
(`:304-:306`, `:320-:324`, `:336-:338`) pours — each is echo, `gc runtime
drain-ack`, `exit 1`. The missing-`$TARGET` halt alone pours, which is exactly
the pre-existing behaviour leg 8 pins.

**STOP respawn source (residual precision (a)) — verified, with one gap stated.**
The refinery is declared in `gastown/pack.toml` as
`[[named_session]] template = "refinery", scope = "rig", mode = "on_demand"`,
and the pack documents its own wake semantics: `gc session wake` "starts a
stopped on_demand session" (`mol-polecat-work.toml:965`), the refinery carries
"a 2h idle timeout" (`mol-witness-patrol.toml:602`), `gc runtime drain-ack`
"tells the reconciler to kill this session" (`mol-polecat-work.toml:975`), and
a failed wake is non-fatal because "the refinery finds the work on its next
poll" (`mol-polecat-work.toml:967`).

The precise consequence for a guard STOP, which is worth stating because it is
not the obvious answer: **a STOP emits no `bead.updated` event.** The pack notes
that a `gc bd update` "generates a `bead.updated` event the refinery's
event-watch will see" (`mol-polecat-work.toml:963`) — but the whole point of
these STOP arms is that they mutate no bead state, so they cannot self-trigger
that event-watch path. The retry therefore rides on the reconciler's
`on_demand` start / the refinery's own next poll, or on a later external
`gc session wake` from a polecat submit-and-exit or a witness orphan handoff.
The bead itself stays assigned with `metadata.branch` intact, so `find-work`
re-selects it whenever the refinery next runs — the step is idempotent up to
the decision and has mutated nothing.

Gap, stated rather than papered over: this was verified from the shipped pack
contract and the formula text, **not** by observing a live respawn. No city on
the build host has a refinery agent configured (checked: `maintainer-city`,
`orchestration`, `trust`, `platform`, `gas-city-inc`, `substrate` — zero
refinery agents, zero refinery sessions), so a production-rig observation was
not available here. What would settle it is a single timed observation on a rig
that runs the gastown pack: force a guard STOP, then record the wall-clock delay
until the next refinery session starts and which of the three sources started it.

## Follow-up

The residual-precision-(b) family is filed as tracked work rather than narrated
here; committed prose alone is not tracking.

**[`gp-uqj8a`](#) — mol-refinery-patrol: assigned never-healing STOP family
(deleted `$BRANCH` park mirror + repeated stranded-`temp` checkout-STOP).**

One family, not two tickets: both members are the same operational class, an
assigned never-healing STOP that sits head-of-line in the refinery's merge
queue. Neither is addressed by this PR, and deliberately so — both remedies
require bead mutation on an error path, which this guard's contract forbids.
The tracked item carries the scope guards with it: do not widen these STOP
arms (their mutation-free property is pinned by legs 1b, 4 and 6), do not fix
merge-push as a drive-by, and leave the `1)` arm's bare checkout alone.

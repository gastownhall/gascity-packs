---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775485
  formula: do-work-item
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: do-work-item
  stage: implement-item
  attempt: 1
status: approved
trace:
  upstream:
    - path: beads/gp-zcsrt
      hash: bead:gp-zcsrt
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-05
        - AC-374-06
        - AC-374-07
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json
      hash: sha256:04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616
    - path: /data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md
      hash: sha256:057ad99d6da1db77b8fb68d5e7297b8d988eb7fffa697aea37d1638a32ce9738
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: sha256:0cf0a3937272c573821f05dbdd46fb2105572f09d600bde46d199505b9a21811
    - path: scripts/gascity_pack_inference_gate.py
      hash: sha256:262e133d1639740ab68e2b5ce3ab9f1fa21f5b3d9993266216b467eb7d283251
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:8d087e08c4d346ed2dfd7e169bc6ccf691cc9d17
  coverage:
    - id: AC-374-01
      status: covered
    - id: AC-374-02
      status: covered
    - id: AC-374-03
      status: covered
    - id: AC-374-05
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# issue-374 W2 — formula guard insertion and inference-gate repin (atomic)

## Summary

Drain item 1 (member `gp-n7z1g`, source anchor `gp-zcsrt`) of convoy `gp-1hy8b`.
Implements design sections **D1**, **D2** and **D3** in one commit, `9b89515` on
branch
`normalized/3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a/opus`,
parent `8d087e0` (W1's test-first commit) over base `05031f2`.

The atomicity constraint (AC-374-07) is honoured literally: the formula change
and the inference-gate repin are in the same commit, so no commit on this branch
ever carries the guard without the pins that protect it.

This item turns W1's deliberately-red suite green. W1 shipped the nine-leg
witness suite against an unguarded formula; with D1/D2/D3 applied, all nine legs
pass, which is the red→green transition D4 predicted.

## Intended Behavior

`mol-refinery-patrol`'s `rebase` step ran `git checkout -b temp origin/$BRANCH`
followed by `git rebase origin/$TARGET` unconditionally. When `origin/$TARGET`
is already an ancestor of `origin/$BRANCH` the source is a pure fast-forward
candidate, and rebasing it drops merge commits together with their recorded
conflict resolutions — producing either an artificial conflict on an unchanged
SHA (the rejection treadmill) or a silent flattening that merge-push then
force-pushes over the source branch.

**D1** inserts a guarded ancestry decision into the step's fenced block, ordered
prune-fetch → halt → guard-fetch → probe → case:

| Condition | Route | Bead | Clone |
| --- | --- | --- | --- |
| `$TARGET` missing on origin | the pre-existing halt, unchanged (park + escalate + pour) | mutated by the halt, as today | unchanged, no `temp` |
| explicit fetch fails (unreachable origin; `$BRANCH` deleted) | STOP | untouched | no `temp` |
| probe rc=0 | exit-checked checkout + `SKIP-REBASE:` narration, success path continues | untouched by the decision | `temp` == `origin/$BRANCH`, merges intact |
| probe rc=0 but checkout fails (stranded stale `temp`) | STOP | untouched | stale `temp` left exactly as found |
| probe rc=1 | checkout + the preserved rebase → existing conflict path | as today | as today |
| probe rc>1 | STOP | untouched | no `temp` |

Load-bearing properties, each of which the verification below exercises:

- The guard fetch **follows** the halt. Explicit-fetching a missing `$TARGET`
  exits 128 and would swallow `target_branch_missing` into the generic STOP,
  bypassing the halt's dedicated park, escalation and wisp-pour.
- The fetch exit is **checked** and fails closed. A failed fetch leaves stale
  tracking refs that can still satisfy `--is-ancestor`, so the probe alone would
  skip-decide on fiction.
- The refspecs are deliberately **unbraced** (`$BRANCH`/`$TARGET`), keeping this
  site string-distinct from merge-push's braced fetch so the D3.1 pin witnesses
  it uniquely. The fence comment recording that intent is preserved.
- The probe is captured by **bare invocation** with `ANCESTOR_RC=$?` on the next
  line — never `if !` (negation clobbers the status) and never a zsh reserved
  name (`status` is read-only).
- rc 1 reproduces today's two lines byte-identically, so clean divergence and
  the conflict/rejection tail behave exactly as before.
- Every STOP arm is echo + `gc runtime drain-ack` + `exit 1` only: no
  `rejection_reason`, no delete/reopen-source, no polecat reroute, no
  `gc bd update` of any kind. A tooling error is not a conflict, and the bead
  stays assigned for find-work to re-select next cycle.

**D2** adds the SKIP outcome as a first-class success, amends the conflict
preamble to the "and only then" wording, and appends one sentence to the step's
intro rationale. Nothing is removed. Prose keeps the backticked, colon-free
`SKIP-REBASE` spelling, which is what makes the echo-anchored D3.5 pin
unsatisfiable by prose.

**D3** repins `GASTOWN_BUILD_WORKFLOW_CONTRACTS["mol-refinery-patrol"]`. The
preserved `git rebase origin/$TARGET` pin keeps matching; five new fragments are
satisfiable only by the new block. The fail-closed sentence is a deliberate
two-site **collective** pin, and the skip-arm checkout STOP deliberately does
not carry it — rewording that echo to "cover" the pin would make it witness a
false statement, so the anti-fix rule is recorded in a comment beside the pin.
The per-arm wordings stay test literals rather than gate pins: `errored (status `
also occurs in merge-push, so as a gate pin it would be absorbed under the
gate's whole-file containment.

## Changed Files

| File | Change |
| --- | --- |
| `gastown/formulas/mol-refinery-patrol.toml` | D1 guard block replaces the two unconditional lines (+44); D2 prose: SKIP outcome paragraph, conflict-preamble amendment, intro sentence |
| `scripts/gascity_pack_inference_gate.py` | D3 repin: five added fragments plus intent comments, pure insertion (+33, no deletions) |

Both files are in the single commit `9b89515`. Four hunks in the formula and one
in the gate; the diff is confined to the D1/D2/D3 sites.

Untouched, as the item requires: the `git fetch --prune origin` line and the
whole missing-target halt are **byte-identical** to base (verified by hash, not
by inspection); find-work, the conflict tail below the amended preamble, and
merge-push in its entirety (its reverse-order probe, `ANCESTOR_STATUS`,
ff-only merge and `--force-with-lease`) are unmodified; the W1 witness suite is
unmodified. No backport to the `reconcile/worktree-20260814` vintage.

## Verification

All commands were run from the authoritative worktree recorded on the source
anchor,
`/data/projects/gascity-packs/worktrees/normalized-3f91225712f8005e7b62ea43969101c0aa92df53258931f464bdd57cc963f24a-opus`,
with `pwd -P` confirmed equal to it before any read, edit, test, hash, `git add`
or `git commit`. The context path
`/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json`
was validated: its sha256 is
`04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616`, matching
`normalized.contract_sha256` on the member bead.

**First verification command** (static half):

```
python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
```

Observed: **pass** — `89 passed in 3.08s`.

Each pinned literal was then grepped against the changed formula rather than
assumed, with occurrence counts recorded: the guard fetch, the probe and
`ANCESTOR_RC=$?` are single-site; the collective STOP sentence is two-site as
designed; `echo "SKIP-REBASE:` is single-site; the preserved
`git rebase origin/$TARGET` still matches. The prose-dict survival check also
passes — all five `GASTOWN_FORMULA_CONTRACTS` fragments still match.

Gate sites were **enumerated by grep and re-derived**, never counted from the
design: `mol-refinery-patrol` appears in the gate at `:91` (prose dict), `:122`
(command dict, the repinned one) and `:823` (the `setup_formulas` registry
entry, which names the formula only and needed no change). The registry entry
moved from its base citation `:790` to `:823` under the insertion.

**Final proof command** (behavioral half):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Observed: **pass** — `PASS: all legs passed`. Enumerated, not counted:

| Leg | Result |
| --- | --- |
| 1 (skip preserves topology, EX-1 + EX-2) | PASS |
| 1b (stranded `temp` fails closed at the skip-arm checkout) | PASS |
| 2 (diverged clean rebases as today) | PASS |
| 3 (diverged conflicting keeps the conflict path) | PASS |
| 4 (fetch failure stops before the probe, stale-ref trap) | PASS |
| 5 (missing source branch) | PASS |
| 6 (probe error fails closed, `merge-base` shimmed to 128) | PASS |
| 7 (structural backstop and ordering, static) | PASS |
| 8 (halt composition, target branch missing) | PASS |

Supporting checks:

- `git show <base>:gastown/formulas/mol-refinery-patrol.toml | sed -n '248,293p'`
  and the same range of the changed file hash **identically**
  (`c7d4683f24ab5cc624f57de0bb2f6e7c9b858f2d2669234521e26f135cfc53ab`),
  proving the prune fetch and the halt are byte-identical.
- The formula still parses as TOML (`tomllib`), and the gate still compiles
  (`py_compile`).
- `bash gastown/tests/test_gastown_pack_assets.sh` — **pass**.
- `git diff --stat` and the hunk headers confirm confinement: four formula hunks
  (intro sentence, D1 block, SKIP paragraph, conflict preamble) and one
  insertion-only gate hunk.

Environment: git 2.43.0, Python 3.12, jq 1.7 on Linux.

### AC coverage

The six acceptance criteria carried on source anchor `gp-zcsrt` (`gc.ac_ids`).
AC-374-04 is deliberately absent — the red→green regression test belongs to W1.

| ID | Status | Evidence |
| --- | --- | --- |
| AC-374-01 | covered | D1 fetch arm: exit-checked dual-refspec force-fetch after the halt, STOP before probe and checkout; pin D3.1 single-site. Legs 4 and 5 green, `$GC_LOG` oracle shows zero mutation |
| AC-374-02 | covered | D1 rc=0 arm (exit-checked checkout + `SKIP-REBASE:`) and D2.1 prose; pin D3.5 echo-anchored. Leg 1 green on EX-1/EX-2 (SHA equality, merge count 2, source ref unchanged); leg 1b green for the checkout-failure STOP |
| AC-374-03 | covered | D1 `*` arm, probe placed before any branch exists; pins D3.2–D3.4. Leg 6 green: `errored (status 128)` STOP, no `temp`, rebase unreached, no mutation |
| AC-374-05 | covered | D1 rc=1 arm reproduces today's adjacent checkout+rebase pair byte-identically; no line of the conflict path edited below the preamble. Legs 2 and 3 green |
| AC-374-06 | covered | Halt byte-identical by hash and nothing above it touched; STOP arms carry no rejection metadata, no reopen/delete, no reroute; merge-push unmodified. Leg 8 executes halt composition, leg 7 pins order statically |
| AC-374-07 | covered | Formula and gate land in the single commit `9b89515`. Gate pytest green on the changed tree (89 passed), every pinned literal grepped with counts, all three `mol-refinery-patrol` gate sites enumerated and line numbers re-derived |

## Remaining Risks

- **Leg 3's `rc 1` carve-out is still measured on git 2.43 only.** It is git's
  empirically stable rebase-conflict code, not a documented guarantee — git
  promises only non-zero on conflict. The suite is green here on 2.43; CI runs
  git 2.52, and W1 flagged this for re-confirmation at fix time. This item did
  not change that exposure and could not verify it without CI: it is the one
  assertion in the suite that could red on CI while the guard is correct.
  Carried to W3's full verification sweep.
- **Leg 7 pins composition order textually.** Legitimate future reformatting of
  the fence (for example moving the prune fetch off line 1 of the block) will
  red leg 7 even with behavior unchanged. That is the intended backstop against
  silent mangling, but it makes leg 7 the leg most likely to need a deliberate
  update alongside a future formula edit.
- **The collective pin is single-arm-tolerant by construction.** Deleting one
  fail-closed arm keeps the D3.4 pin satisfied by the other arm's copy; that
  case is caught by leg 7's per-arm literals and legs 1b/4/6, not by the gate.
  This is the designed division of labour (the gate is the deletion-only
  whole-file layer), but it means the gate alone is not sufficient protection
  for arm structure — the test must keep running in CI for the guard to stay
  protected.
- **The formula's rendered description collapses backslash-continued lines.**
  The step's `gc bd update $WORK \` block renders as one joined line under
  strict TOML parsing. This is pre-existing behaviour of the halt (unchanged by
  this item, and the halt is byte-identical to base), and the inserted block
  contains no backslashes, so nothing new is introduced. Recorded because it is
  visible in any `tomllib` read of the file and could otherwise be mistaken for
  damage from this change.
- **The guard's STOP routes are retry-later, not escalations.** A persistently
  unreachable origin will STOP the step every cycle with the bead still
  assigned, which is correct (no state mutated, idempotent up to the decision)
  but produces no escalation of its own; only the missing-`$TARGET` case keeps
  a dedicated park. Operators watching for a wedged refinery should read the
  STOP narration, which names the failing half explicitly.

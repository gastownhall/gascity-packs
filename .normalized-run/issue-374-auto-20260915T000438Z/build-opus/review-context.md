# Review context — issue-374 opus builder lane

Produced by `workflows-build-from-convoy.prepare-review` for the inherited
`build-from-review-base` suffix. Bookkeeping only: no code was reviewed or
changed in this step.

## Review inputs

| Input | Value |
| --- | --- |
| `artifact_root` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus` |
| `requirements_path` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json` |
| `context_path` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work-contract.json` |
| `plan_path` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/approved-design.md` |
| `plan_review_path` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/design-review/result.json` |
| `decomposition_path` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/decompose-graph.json` |
| `implementation_summary_path` | `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/implementation-summary.md` |
| `code_review_formula` | `review` |
| `review_fix_formula` | `fix-loop-base` |
| `implementation_formula` | `implement` |
| `implementation_item_formula` | `do-work-item` |
| `implementation_target` | `gascity-packs/claude-max` |
| `review_mode` | `agent` |
| `interaction_mode` | `headless` |
| `max_iterations` | `1` |
| `review_repair_policy` | `once` |

Every path above was stat-verified as existing at the time this file was
written.

## Implementation Worktrees

All four convoy items drained into a single shared worktree. Item directories
under `items/` are keyed by the **source anchor id**, not the convoy member id.

| Source anchor | Work unit | Implementation worktree (absolute) | Branch | Base revision | Diff range | Repo content changed |
| --- | --- | --- | --- | --- | --- | --- |
| `gp-0k3k0` | W1 | `/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus` | `normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus` | `05031f2c66e080865c379ff799c7369430560a8f` | `05031f2c66e080865c379ff799c7369430560a8f..HEAD` | yes |
| `gp-37c93` | W2 | `/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus` | `normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus` | `05031f2c66e080865c379ff799c7369430560a8f` | `05031f2c66e080865c379ff799c7369430560a8f..HEAD` | yes |
| `gp-sxr1i` | W3 | `/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus` | `normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus` | `05031f2c66e080865c379ff799c7369430560a8f` | `05031f2c66e080865c379ff799c7369430560a8f..HEAD` | no |
| `gp-w53bs` | W4 | `/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus` | `normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus` | `05031f2c66e080865c379ff799c7369430560a8f` | `05031f2c66e080865c379ff799c7369430560a8f..HEAD` | no |

Head revision: `2df2dca710ba79876f335300d9a37abbcb3d6d8b`

### Commits in range

```
2df2dca fix(gastown/refinery): skip the rebase when the source is already based
4fb5642 test(gastown): regression suite for the mol-refinery-patrol rebase guard
```

### Changed files

```
 gastown/formulas/mol-refinery-patrol.toml          |  61 +-
 .../tests/test_mol_refinery_patrol_rebase_guard.sh | 656 +++++++++++++++++++++
 scripts/gascity_pack_inference_gate.py             |  20 +
 3 files changed, 733 insertions(+), 4 deletions(-)
```

### Worktree cleanliness

```
git status --porcelain -> 0 entries
```

## Proof commands (from the item summaries)

Run from the implementation worktree above.

```bash
bash -n gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
for t in gastown/tests/test_*.sh; do bash "$t"; done
```

Red control against the unguarded base:

```bash
git worktree add --detach /tmp/rc-base-374 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

## Aggregate implementation summary

---
schema: gc.build.implementation-summary.v1
role: drain-aggregate
workflow:
  id: gcg--9223372036854774975
  formula: workflows-build-from-convoy
  step: workflows-build-from-convoy.prepare-review
convoy:
  id: gp-ydg59
  item_count: 4
  drain_policy: same-session
subject:
  branch: normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus
  work_dir: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus
  base_sha: 05031f2c66e080865c379ff799c7369430560a8f
  head_sha: 2df2dca710ba79876f335300d9a37abbcb3d6d8b
  diff_range: 05031f2c66e080865c379ff799c7369430560a8f..HEAD
status: approved
trace:
  upstream:
    - path: items/gp-0k3k0/implementation-summary.md
      hash: sha256:22b7796dab3a495136dea0579e01d399eebc7430398dbf2bd7c0e2ccb9ef2f34
    - path: items/gp-37c93/implementation-summary.md
      hash: sha256:54d65c6c608ed0fecc00bae3b6465df4b18ac708b9f99f682e00816cb996c0b7
    - path: items/gp-sxr1i/implementation-summary.md
      hash: sha256:3c3df78ad9929779145ede46088dca73c3521faf553305ca6b4dd30fa76044b3
    - path: items/gp-w53bs/implementation-summary.md
      hash: sha256:52dedc19d9055ab027e69510107de53b64997c05d0de8b90000a4f906cc26c55
    - path: items/gp-sxr1i/pr-body.md
      hash: sha256:1ae5612e0c7fe0a4c70210b64d8132dc559e30e01af25730255f2b00824c3c25
---

# Implementation aggregate — issue-374 opus builder lane

All four convoy items drained into **one shared worktree** on one branch. There
is no per-item worktree: the directory under `items/` is keyed by the item's
**source anchor id**, not by the convoy member id, and every item's evidence
refers back to the same tree below.

## Item index

| Item dir (source anchor) | Work unit | Commit | Repository content changed |
| --- | --- | --- | --- |
| `items/gp-0k3k0` | W1 — regression suite for the rebase guard | `4fb56420fdc48a5e447b2ca2331de92bd67ed420` | yes |
| `items/gp-37c93` | W2 — guarded ancestry decision + inference-gate repin (atomic) | `2df2dca710ba79876f335300d9a37abbcb3d6d8b` | yes |
| `items/gp-sxr1i` | W3 — red control, verification sweep, PR-body records | none (evidence only) | no |
| `items/gp-w53bs` | W4 — filed the residual-precision-(b) follow-up (`gp-uqj8a`) | none (evidence only) | no |

W1 is red by construction on its own commit; W2 is the commit that turns it
green, and W2 deliberately lands the formula change and the inference-gate
repin together (AC-374-07 forbids shipping one without the other). W3 and W4
mutate no repository content — W3 records the red/green control sweep and W4
appends the follow-up link to `items/gp-sxr1i/pr-body.md`.

## Changed files (`05031f2c..HEAD`, 3 files, +733 / -4)

```
gastown/formulas/mol-refinery-patrol.toml          |  61 +-
gastown/tests/test_mol_refinery_patrol_rebase_guard.sh | 656 +++++++++++++++++++++
scripts/gascity_pack_inference_gate.py             |  20 +
```

## Claims carried from the items

- The `rebase` step of `mol-refinery-patrol.toml` ran an unconditional
  `git rebase origin/$TARGET`, which flattens merge commits and drops recorded
  conflict resolutions when the target is already an ancestor of the source.
  W2 inserts the ancestry guard; the literal `git rebase origin/$TARGET` is
  preserved byte-identical so the existing inference-gate pin still matches.
- W2 adds five fragments to the `mol-refinery-patrol` command-contract tuple in
  `scripts/gascity_pack_inference_gate.py`.
- W3's sweep reports the suite red against the unguarded base and green against
  the fixed tree, per leg.
- `tests/test_gastown_lint_findings.py` fails locally on this branch, but the
  items establish by negative control that it fails identically at base
  `05031f2c` in a detached worktree carrying none of these changes. It is
  pre-existing and local-only, not a defect of this work.
- Leg 3 asserts git's rebase-conflict `rc 1` as a deliberate, commented
  version-sensitive carve-out.

Per-item risk sections are authoritative; read them in the item summaries
rather than relying on this digest.

## Item artifact — gp-0k3k0

Source: `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-0k3k0/implementation-summary.md`

---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774934
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
    - path: beads/gp-0k3k0
      hash: bead:gp-0k3k0
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-04
        - AC-374-05
        - AC-374-06
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: sha256:e6ad1ae60e695d1f290f80e733df4e1e31aacdd891b539c7928a556bcce44bed
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: git:05031f2c66e080865c379ff799c7369430560a8f
  coverage:
    - id: AC-374-01
      status: deferred
      rationale: >-
        Legs 4 and 5 encode the fail-closed explicit dual-ref fetch and are red
        against the unguarded base for the documented reason (leg 5 shows the
        failure surfacing late at the checkout with rc 0 and no STOP routing).
        The fetch arm itself is design element D1 and lands in W2 (gp-zcsrt);
        this item is the test-first half of the split and deliberately ships no
        formula change.
    - id: AC-374-02
      status: deferred
      rationale: >-
        Legs 1 (EX-1 and EX-2) and 1b encode SHA identity, the preserved merge
        count and the exit-checked skip-arm checkout. They are red on the
        unguarded base and green against a scratch tree carrying the D1 guard
        text. The skip behaviour itself lands in W2 (gp-zcsrt).
    - id: AC-374-03
      status: deferred
      rationale: >-
        Leg 6 encodes the probe-error fail-closed arm via a passthrough git shim
        and is red on the unguarded base because no probe exists there. The
        probe and its error arm land in W2 (gp-zcsrt).
    - id: AC-374-04
      status: covered
      rationale: >-
        This item is the whole deliverable for this AC. The EX-1 fixture is
        built to the shape the AC names (bare origin, target at T, source from T
        with two --no-ff merges whose recorded resolution differs from both raw
        sides, merge-base(target, source) == target) and the AC's own criterion
        is met and measured: the suite fails against the current unconditional
        step and passes with the fix.
    - id: AC-374-05
      status: deferred
      rationale: >-
        Legs 2 and 3 are the green controls for the preserved diverged clean and
        conflicting paths; they are green on the unguarded base and stay green
        against the scratch guarded tree. The guarantee that the rc=1 arm keeps
        that behaviour is a property of the W2 (gp-zcsrt) insertion.
    - id: AC-374-06
      status: deferred
      rationale: >-
        Leg 8 pins halt composition and is green on both trees; leg 7 pins the
        prune-fetch -> halt -> guard-fetch -> probe -> capture -> case ordering
        and the distinct per-arm STOP literals. Both become load-bearing only
        once W2 (gp-zcsrt) inserts the decision the composition claim is about.
---

# W1 — regression suite for the mol-refinery-patrol rebase guard

## Summary

Adds `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`, the executable
regression suite for design element D4, as the test-first half of the approved
split. No formula and no inference-gate change ships here: the approved design
permits only one split, "test-first (D4 plus its red control against the
unguarded base), then formula+gate atomically — never formula without gate
(AC-374-07)".

The `rebase` step of `mol-refinery-patrol.toml` runs `git checkout -b temp
origin/$BRANCH` followed by an unconditional `git rebase origin/$TARGET`. When
the source is already based on the target that rebase is not a no-op: it
flattens merge commits and drops the resolutions recorded in them. Both
outcomes were reproduced directly while building the fixtures on git 2.43.0 —
an artificial conflict on an unchanged SHA for merge-conflicting history
(EX-1), and a silent flattening that takes the merge count 2 -> 0 and breaks
SHA equality for clean history (EX-2).

The suite is red on this commit by construction. W2 lands the guard that turns
it green.

## Intended Behavior

The step's fenced block is lifted out of the shipped TOML and executed as one
unit, never transcribed; a transcription is a second copy that drifts silently
from the recipe that actually runs. The lift sentinel `git checkout -b temp
origin/$BRANCH` is present on both the unguarded and the guarded formula, so
aiming the file at an unguarded tree produces behavioural and static reds
rather than an extraction error.

`REBASE_GUARD_FORMULA` overrides the resolved formula path, which is what makes
the red control permanent and hand-copy-free: the identical file, byte
unmodified, can be aimed at another tree.

Nine legs: 1 and 1b cover the skip path's topology preservation and the
exit-checked skip-arm checkout over a stranded `temp`; 2 and 3 are green
controls for the preserved diverged clean and conflicting paths; 4 is the
stale-tracking-ref trap; 5 a deleted source branch; 6 a probe error failing
closed; 7 a static structural and ordering backstop over the lifted text; 8
halt composition.

Every leg runs even when an earlier one fails and the verdicts are summarised
per leg. That is deliberate: the red control has to enumerate outcomes per leg
rather than count them, which a first-failure abort could not produce in one
run.

Fixtures are hermetic — a bare origin plus a consumer clone per leg, with
`HOME` and `GIT_CONFIG_GLOBAL` redirected into the tmpdir and
`GIT_CONFIG_NOSYSTEM=1`, so neither a host `/etc/gitconfig` nor the git
2.43-vs-2.52 identity divergence can leak in. Assertions are kept
version-stable (the `SKIP-REBASE:` prefix, non-zero fetch rc, never a short-SHA
length), with exactly two scoped and commented carve-outs: leg 6's `status 128`
is the test shim's own deterministic exit, and leg 3's rc 1 is git's
empirically stable rebase-conflict code and the discriminator the step's prose
already keys on. `jq` is a declared hard dependency, preflighted in the
harness, because the halt leg pipes the wisp-pour answer through real `jq`.

## Changed Files

| File | Change |
| --- | --- |
| `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` | New. 656 lines. Lifting harness, `gc` PATH-shim mutation oracle, four fixtures (EX-1, EX-2, EX-3a, EX-3b) and nine legs. |

Commit `4fb56420fdc48a5e447b2ca2331de92bd67ed420` on branch
`normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus`,
one file, 656 insertions, base `05031f2c66e080865c379ff799c7369430560a8f`.

No formula, inference-gate, requirements, plan, plan-review or decomposition
artifact was touched.

## Verification

Measured on `git version 2.43.0`. CI discovers the file automatically through
the existing `gastown/tests/test_*.sh` loop in `.github/workflows/ci.yml`.

First verification command — syntax gate:

```
bash -n gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: pass.

Red control against the unguarded base (the shipped formula at `05031f2c`):

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 1, with outcomes enumerated per leg — `FAIL leg 1`, `FAIL leg 1b`,
`PASS leg 2`, `PASS leg 3`, `FAIL leg 4`, `FAIL leg 5`, `FAIL leg 6`,
`FAIL leg 7`, `PASS leg 8`. That is exactly the profile the design predicts:
legs 1, 1b, 4, 5 and 6 red behaviourally, leg 7 red statically (`expected the
ancestry probe exactly 1 time(s) in the lifted block, found 0` — its contained
strings do not exist at `05031f2c`), and legs 2, 3 and 8 green. Each red is for
its documented reason; leg 5's captured output shows the unguarded failure
surfacing late (`fatal: 'origin/source' is not a commit and a branch 'temp'
cannot be created from it` / `Current branch main is up to date.`) with rc 0 and
no STOP routing.

Final proof command — the identical file, byte unmodified, aimed at a scratch
tree carrying the design's D1 guard text:

```
REBASE_GUARD_FORMULA=/tmp/guarded-mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 0, all nine legs `PASS`, and two consecutive runs produced
byte-identical leg summaries. The scratch formula was assembled by splicing the
D1 block from the approved design between base lines `:293` and `:296`; its
leg-7 counts are the pinned ones (ancestry probe 1, lift sentinel 2, collective
STOP sentence `cannot evaluate rebase ancestry` 2).

Together these establish the two properties a test-first item must have: the
suite is red today for the right reasons, and it is satisfiable by the W2
guard rather than over-constrained.

| ID | Status |
| --- | --- |
| AC-374-01 | deferred |
| AC-374-02 | deferred |
| AC-374-03 | deferred |
| AC-374-04 | covered |
| AC-374-05 | deferred |
| AC-374-06 | deferred |

## Remaining Risks

The scratch guarded formula used for the green proof is a local splice of the
design's D1 text, not W2's committed insertion. It establishes satisfiability,
not equivalence: if W2's landed text differs from D1 as written, leg 7's three
count assertions and the ordering chain are what will catch it. W3 owns the
authoritative red-control transcript against the real fixed tree.

Leg 3's `rc 1` and leg 5's non-zero fetch rc were measured on git 2.43.0; CI
runs git 2.52. Leg 5 asserts only non-zero, so it is insensitive. Leg 3 asserts
the exact 1 as a deliberate, commented carve-out and is the one assertion that
should be re-confirmed on the CI git at fix time.

The suite shells out to real git for every fixture and runs four fixtures plus
nine legs, so it is slower than the other gastown shell tests. It is still well
inside the CI step's budget, but it is the first of these tests to build real
repositories per leg.

This commit leaves CI red on the branch until W2 lands, which is inherent to
the test-first split the design mandates and is not a defect of this item.

## Item artifact — gp-37c93

Source: `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-37c93/implementation-summary.md`

---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854775498
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
    - path: beads/gp-37c93
      hash: bead:gp-37c93
      ids:
        - AC-374-01
        - AC-374-02
        - AC-374-03
        - AC-374-05
        - AC-374-06
        - AC-374-07
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: sha256:10a202e0046ad4dd4bd9a310a60dec2eae1c19b98fcff490f9fe0348dc136af5
    - path: scripts/gascity_pack_inference_gate.py
      hash: sha256:c7554582c771b7caa467cd8b935006ce1bebe271091c2a209bbf7746b595562b
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:4fb56420fdc48a5e447b2ca2331de92bd67ed420
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

# W2 — guarded ancestry decision and inference-gate repin (atomic)

## Summary

Lands design elements D1 (formula insertion), D2 (step prose) and D3
(inference-gate repin) in one commit, `2df2dca710ba79876f335300d9a37abbcb3d6d8b`.
The atomicity is a requirement, not a preference: AC-374-07 forbids shipping
the formula without the gate repin in the same change, because a formula whose
pinned fragment no longer exists leaves the gate silently unable to witness the
guard it is supposed to protect.

The `rebase` step ran `git checkout -b temp origin/$BRANCH` followed by an
unconditional `git rebase origin/$TARGET`. When `origin/$TARGET` is already an
ancestor of `origin/$BRANCH` that rebase is not a no-op: it flattens merge
commits and drops the conflict resolutions recorded in them. Both failure
modes were reproduced directly on git 2.43.0 while building the W1 fixtures —
an artificial conflict on an unchanged SHA for merge-conflicting history, and a
silent flattening that takes the merge count 2 -> 0 and breaks SHA equality for
clean history, which merge-push then force-pushes over the source branch.

## Intended Behavior

Ordering is prune-fetch -> halt -> guard-fetch -> probe -> case, and the
sequence is load-bearing. The explicit fetch must follow the missing-target
halt: fetching an absent `$TARGET` with an explicit refspec exits 128, so
running it first would swallow `target_branch_missing` into the generic STOP
and bypass the halt's dedicated park, escalation and wisp-pour.

The guard fetch's exit is checked and fails closed, because a failed fetch
leaves stale tracking refs that can still satisfy `--is-ancestor` — the probe
alone would decide on fiction. The probe is invoked bare with `$?` captured on
the very next line into `ANCESTOR_RC` (no `if !` negation, no intervening
command substitution), then discriminated three ways:

- rc 0 — skip. `temp` is materialized at `origin/$BRANCH` and the step
  continues its success path; merge topology is untouched.
- rc 1 — exactly the two lines this step has always run, preserved
  byte-identical and unquoted.
- any other rc — STOP. A probe error is never read as "not an ancestor".

The skip arm's checkout is itself exit-checked. Over a `temp` stranded by the
pre-existing merge-push STOP wedge, an unchecked checkout would narrate a skip
over a stale branch that merge-push then consumes by name and pushes with
`--force-with-lease` — and the lease would pass, because the guard fetch just
freshened `origin/$BRANCH`.

Every new STOP route is retry-later: echo, `gc runtime drain-ack`, exit. No
`rejection_reason`, no delete/reopen-source, no polecat reroute, no bead
mutation of any kind — a tooling error is not a conflict. Only the
missing-target case keeps its dedicated park.

For D3, `git rebase origin/$TARGET` is preserved byte-identical so its existing
pin keeps matching, and five fragments are added, each satisfiable only by the
new block. The collective fail-closed sentence is deliberately a two-site pin
over the fetch and probe-error arms; the checkout-STOP arm deliberately does
not carry it, since it would then witness a false statement (its failure is
checkout materialization, not ancestry evaluation). Single-arm deletion is
caught instead by the regression suite's per-arm literals and by legs 1b, 4
and 6.

## Changed Files

| File | Change |
| --- | --- |
| `gastown/formulas/mol-refinery-patrol.toml` | D1 insertion into the `rebase` step plus the three D2 prose amendments. Four hunks, nothing removed. |
| `scripts/gascity_pack_inference_gate.py` | D3 repin: five fragments added to the `mol-refinery-patrol` command-contract tuple; the existing `git rebase origin/$TARGET` pin preserved. |

Commit `2df2dca710ba79876f335300d9a37abbcb3d6d8b`, 2 files, 77 insertions,
4 deletions, on branch
`normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus`.

## Verification

Both halves required, both run on `git version 2.43.0`.

First verification command — the static gate:

```
python3 -m pytest tests/test_gascity_pack_inference_gate.py -q
```

Result: `89 passed`.

Every pinned literal was grepped and its sites enumerated, never counted. All
line numbers are re-derived on this branch rather than copied from the
contract:

| Pin | Sites |
| --- | --- |
| `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"` | `:303` |
| `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` | `:314` |
| `ANCESTOR_RC=$?` | `:315` |
| `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` | `:304`, `:336` |
| `echo "SKIP-REBASE:` | `:326` |
| `git rebase origin/$TARGET` | `:331` |

The collective sentence resolves at exactly its two intended arms, and the
checkout STOP at `:322` correctly does not carry it. The gate's prose-dict
fragments (`metadata.branch`, `fast-forward merge`, `run tests before
merging`, `metadata.target`, `closes the bead`) all still resolve, so the
prose-dict survival check passes.

Confinement was checked rather than assumed. The formula diff is four hunks —
the D2.3 sentence, the D1 insertion, and the two D2 prose amendments. Base
`:248-:293` is byte-identical by sha256 comparison against `HEAD:` content.
Merge-push's already-merged gate survives untouched at `:848` (base `:795`,
shifted by this insertion), still probing the reverse operand order and still
using the distinct `ANCESTOR_STATUS` capture name. The formula still parses as
TOML with all nine steps intact.

Final proof command — the behavioural half, W1's suite against this changed
tree:

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 0, all nine legs `PASS`. The same suite exits 1 against the
unguarded base, so this commit is what converts it. The full CI loop
`for test_script in gastown/tests/test_*.sh` is green across all seven files.

| ID | Status |
| --- | --- |
| AC-374-01 | covered |
| AC-374-02 | covered |
| AC-374-03 | covered |
| AC-374-05 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Remaining Risks

`tests/test_gastown_lint_findings.py` fails locally, but it fails identically
at base `05031f2c` in a detached negative-control worktree with none of these
changes: five pinned `pack.toml` named-session waivers that the local `gc`
binary no longer reports. It is a local gc-version artefact, pre-existing and
unrelated to this change, and it is the pinned-waiver set rather than this
diff that will need attention when the upstream fix lands.

Leg 3 asserts git's rebase-conflict `rc 1` as a deliberate, commented
carve-out measured on git 2.43.0; CI runs git 2.52. It is the one assertion in
the suite that should be re-confirmed on the CI git, and W3's verification
sweep is where that happens.

The guard adds a second fetch to every patrol cycle on top of the existing
prune fetch. That is intentional — the prune fetch is best-effort with an
unchecked exit and feeds the halt's `show-ref`, so it cannot be reused as the
decision's input — but it is a real extra round-trip per cycle.

This item deliberately does not touch the conflict tail, merge-push, or the
residual-precision-(b) follow-up family; those belong to W3 and W4.

## Item artifact — gp-sxr1i

Source: `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-sxr1i/implementation-summary.md`

---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774672
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
    - path: beads/gp-sxr1i
      hash: bead:gp-sxr1i
      ids:
        - AC-374-04
        - AC-374-06
        - AC-374-07
    - path: gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
      hash: git:4fb56420fdc48a5e447b2ca2331de92bd67ed420
    - path: gastown/formulas/mol-refinery-patrol.toml
      hash: git:2df2dca710ba79876f335300d9a37abbcb3d6d8b
    - path: scripts/gascity_pack_inference_gate.py
      hash: git:2df2dca710ba79876f335300d9a37abbcb3d6d8b
  coverage:
    - id: AC-374-04
      status: covered
    - id: AC-374-06
      status: covered
    - id: AC-374-07
      status: covered
---

# W3 — red control, verification sweep, and PR-body records

## Summary

Executes design verification steps 3 through 8 against the fixed tree
`2df2dca710ba79876f335300d9a37abbcb3d6d8b` and produces the PR-body records the
design requires to be written down rather than narrated.

The headline result: the identical test file, byte-unmodified, exits **1**
against the unguarded base and **0** against the fixed tree, with per-leg
outcomes matching the design's predicted table exactly. That is the evidence
that the guard is real and that the suite is not vacuous.

This item mutates no product code. Its deliverable is the verification and the
records artifact at
`.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-sxr1i/pr-body.md`
(`sha256:9927ae7e63b12223dea3a8bc3481e4f2520b9040442d5202affbce1ef02adabc`).

## Intended Behavior

The red control uses the mechanism the design mandates and no substitute: a
detached worktree of the base
(`git worktree add --detach /tmp/rc-base-374 05031f2c`), with the fix tree's
test file aimed at it through `REBASE_GUARD_FORMULA`. The formula is never
hand-copied and the test is never edited between runs — the same file
(`sha256:e6ad1ae6…`) produced both runs, and only the environment variable
differed.

Outcomes are enumerated per leg rather than counted, which is why the suite
runs every leg and summarises verdicts instead of aborting at the first
failure. A first-failure abort could not produce the per-leg table in one run.

## Changed Files

| File | Change |
| --- | --- |
| *(none — product code untouched by construction)* | This item verifies and records; W1 and W2 carry the code. |

Verified tree: `2df2dca710ba79876f335300d9a37abbcb3d6d8b` on branch
`normalized/82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e/opus`.

## Verification

All measurements on `git version 2.43.0`.

First verification command — the red control against the unguarded base:

```
git worktree add --detach /tmp/rc-base-374 05031f2c66e080865c379ff799c7369430560a8f
REBASE_GUARD_FORMULA=/tmp/rc-base-374/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 1. Enumerated per leg — legs 1, 1b, 4, 5 and 6 FAIL behaviourally;
leg 7 FAILS statically; legs 2, 3 and 8 stay green. This is the design's
predicted table with no deviation.

Final proof command — the identical file against the fixed tree:

```
bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

Result: exit 0, all nine legs PASS.

Supporting sweep, all green on the fixed tree:
`python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` (89 passed);
the full CI loop `for t in gastown/tests/test_*.sh; do bash "$t"; done` (seven
files); TOML parse with all nine steps intact. Every pinned literal was grepped
and its sites enumerated in the records artifact, never counted, with all
`:NNN` re-derived on the fix branch. Leg 7 is green on the fixed tree and red on
the base tree, which is AC-374-07's static requirement.

The four step-8 records are written in full in `pr-body.md`: the no-errexit
execution assumption; the deliberately preserved bare checkout in the `1)` arm
and its asymmetry with the exit-checked `0)` arm; confirmation by enumeration
that no guard STOP arm pours a successor wisp (the wisp-pour sites are `:4`,
`:124`, `:276`, `:381`, `:486`, `:585`, `:1286`, of which only `:276` is in this
step, inside the halt); and the STOP respawn source.

| ID | Status |
| --- | --- |
| AC-374-04 | covered |
| AC-374-06 | covered |
| AC-374-07 | covered |

## Remaining Risks

**The STOP respawn source is verified from the pack contract, not from a live
rig.** This is the one place where the design asked for a production-rig
measurement and I could not take one: no city on the build host has a refinery
agent configured (`maintainer-city`, `orchestration`, `trust`, `platform`,
`gas-city-inc`, `substrate` — zero refinery agents, zero refinery sessions), so
there was no live refinery to observe. What the pack does establish is recorded
with citations, including a non-obvious consequence worth reviewer attention: a
guard STOP mutates no bead state, so it emits no `bead.updated` event and
therefore cannot self-trigger the refinery's event-watch wake path. The retry
rides on the reconciler's `on_demand` start, the refinery's next poll, or a
later external `gc session wake`. A single timed observation on a rig running
the gastown pack would settle it — force a guard STOP and record the delay
until the next refinery session and which source started it.

**Leg 3's rc carve-out is version-sensitive.** It asserts git's rebase-conflict
`rc 1`, measured here on git 2.43.0; CI runs git 2.52. Git documents only
"non-zero" on conflict. This is the single assertion in the suite that could
behave differently on the CI git, and it is deliberate and commented as such
because rc 1 is the discriminator the production step's prose already keys on.

**`tests/test_gastown_lint_findings.py` fails locally but is pre-existing.**
Confirmed by negative control: the same failure reproduces at base `05031f2c`
in a detached worktree with none of these changes (five pinned `pack.toml`
named-session waivers the local `gc` binary no longer reports). Unrelated to
this change.

The suite builds real git repositories per leg, so it is the slowest of the
gastown shell tests. It is well inside the CI step's budget, but it is the
first of these tests with that cost profile.

## Item artifact — gp-w53bs

Source: `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-w53bs/implementation-summary.md`

---
schema: gc.build.implementation-summary.v1
workflow:
  id: gcg--9223372036854774667
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
    - path: beads/gp-w53bs
      hash: bead:gp-w53bs
      ids:
        - AC-374-06
    - path: beads/gp-uqj8a
      hash: bead:gp-uqj8a
  coverage:
    - id: AC-374-06
      status: covered
---

# W4 — file the residual-precision-(b) follow-up family as tracked work

## Summary

Files the residual-precision-(b) family as a tracked work item with a stable
identifier, **`gp-uqj8a`**, and links it from the PR body. This discharges
design verification step 9, which is explicit that "committed prose alone is
not the tracking".

The item is filed as **one family rather than two tickets**, which is the
design's own framing: the deleted-`$BRANCH` park mirror and the repeated
stranded-`temp` checkout-STOP are the same operational class — an assigned,
never-healing STOP sitting head-of-line in the refinery's merge queue — and
they share a root cause in what the issue-374 guard deliberately may not do.

This item files tracking only. It implements neither remedy, widens no STOP
semantics, and does not touch merge-push.

## Intended Behavior

Both members are things the shipped guard deliberately leaves alone, and the
tracked item records *why* so a future reader does not mistake them for
oversights:

- **Member (a), deleted `$BRANCH`.** The step parks and escalates when
  `$TARGET` is missing, precisely because `find-work` re-selects open beads
  assigned to this refinery, so one bad bead blocks every other merge. A
  permanently-deleted `$BRANCH` has that same head-of-line shape but no
  equivalent park: after the guard it fails closed at the tracking-ref fetch
  and stays assigned, which is right for a transient failure and never-healing
  for a permanent one. The hard part of any remedy is discriminating a deleted
  branch from an unreachable origin — both surface as a non-zero fetch, and
  getting it wrong parks beads on a network blip. That constraint is written
  into the item.
- **Member (b), stranded `temp`.** The guard already converts this wedge from
  silent corruption into a loud fail-closed STOP that leaves the stale branch
  exactly as found. That is strictly better but not self-healing, so repeated
  hits are the same assigned head-of-line class.

The item also carries its scope guards forward, because the most likely way for
this follow-up to cause harm is someone "fixing" it inside the guard: the STOP
arms' mutation-free property is pinned by legs 1b, 4 and 6 of the regression
suite, merge-push must not be repaired as a drive-by from the rebase step, and
the `1)` arm's bare checkout is deliberately preserved byte-identical.

## Changed Files

| File | Change |
| --- | --- |
| *(none — no product code by construction)* | This item files tracking only. |
| `…/items/gp-sxr1i/pr-body.md` | Follow-up section now links the tracked item `gp-uqj8a`. |

No commit: this item mutates no repository content. The verified tree remains
`2df2dca710ba79876f335300d9a37abbcb3d6d8b`.

## Verification

Static, both halves of the item's stated verification:

The tracked item exists with a stable identifier —

```
gc bd create "mol-refinery-patrol: assigned never-healing STOP family …" \
  --body-file … --type task -p 2 --external-ref gh-374
gc bd show gp-uqj8a
```

Result: `gp-uqj8a`, type `task`, `[P2 · OPEN]`, `External: gh-374`, description
present. It is a first-class rig-store bead, not prose.

The PR body links it —

```
grep -n 'gp-uqj8a' …/items/gp-sxr1i/pr-body.md
```

Result: matched at line 220, inside the `## Follow-up` section, with the family
framing and scope guards alongside the identifier.

Behavioural: none, by construction — this item mutates no product code, so
there is nothing to exercise. Recorded explicitly rather than left blank,
because an empty verification section on a filing-only item is otherwise
indistinguishable from an unverified one.

| ID | Status |
| --- | --- |
| AC-374-06 | covered |

AC-374-06's trace here is by derivation rather than direct statement, as the
decomposition records: the design places this family under its STOP-routing
residuals, which is AC-374-06's scope (guard composition and error routing).
The basis is stated rather than implied.

## Remaining Risks

**`pr-body.md`'s digest moved, by design.** W3's summary cites the artifact at
`sha256:9927ae7e63b12223dea3a8bc3481e4f2520b9040442d5202affbce1ef02adabc`, its
value before this item added the follow-up link. It is now
`sha256:1ae5612e0c7fe0a4c70210b64d8132dc559e30e01af25730255f2b00824c3c25`. That
change is exactly what step 9 asks for — the PR body must link the tracked item
— but it does mean W3's recorded digest is the pre-link one. Flagged so a
reviewer comparing the two does not read it as drift.

**The tracked item is unassigned and unrouted.** That is deliberate for a
directed follow-up: it should be triaged and prioritised against other work
rather than pre-assigned by the item that filed it. The consequence is that it
will not be picked up by any pool worker until someone routes it, which is the
intended behaviour for a follow-up and not a defect — but it does mean filing
alone does not schedule the work.

**Neither member is fixed by this PR, and both remain live in production.** The
guard improves member (b)'s failure mode from silent to loud, and leaves member
(a) exactly as it was. A rig whose source branch is deleted permanently will
still accumulate a recurring assigned STOP until the follow-up lands.

## PR body record (gp-sxr1i)

Source: `/data/projects/gascity-packs/.gc/normalized-pilot/issue-374-auto-20260915T000438Z/work/builders/opus/items/gp-sxr1i/pr-body.md`

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

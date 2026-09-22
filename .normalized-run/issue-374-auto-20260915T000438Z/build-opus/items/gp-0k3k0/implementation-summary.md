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

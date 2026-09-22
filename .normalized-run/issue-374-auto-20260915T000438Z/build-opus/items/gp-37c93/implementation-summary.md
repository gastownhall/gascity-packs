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

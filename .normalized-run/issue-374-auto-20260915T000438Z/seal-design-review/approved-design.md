# Canonical design — issue 374 (judge-design)

Phase `judge-design` of `mol-normalized-issue-pr-work-v1`, run
`issue-374-auto-20260915T000438Z`, produced by the Fable judge
(`gascity-packs/claude-fable`) as the fan-in over the three parallel,
independent loop syntheses. This document is standalone: it is the complete
canonical design that downstream steps copy to
`design-review/review-candidate.md` and review; nothing below requires
reading the loop documents.

## Binding and input verification

- Work Contract: `work/work-contract.json`, sha256
  `04d51caeeb64a121224cab4ed2a331b11b17f864ae437041a684306e27ba9616`
  (recomputed this session from the file bytes via the canonical helper's
  own derivation; byte-identical to the run-root copy). contract_revision
  `issue-374-auto-20260915T000438Z.r1`; base_sha
  `05031f2c66e080865c379ff799c7369430560a8f` (the contract's own field);
  source_revision `2026-08-29T06:21:43Z` (the contract's
  `.source.source_revision`). Source: `gastownhall/gascity-packs` issue 374.
- All three loop-synthesis checkpoints passed the canonical helper's
  **require** gate with expected values recomputed from the actual files
  (contract digest re-hashed from bytes, base/revision read from the
  contract itself, every input re-hashed live), plus programmatic
  cross-field checks (status=complete, target `gascity-packs/claude-fable`,
  attempt 1, generation 1, binding work_contract, empty prior_generations,
  exact output paths) — never `verify` alone, never eyeball comparison:
  - `design-loops/1/synthesis.md` =
    `ce197461eb44b21ef240845f3748072a04b2ecfef2dbbd816223ad5185ac421d`
  - `design-loops/2/synthesis.md` =
    `f415f759c39569bcbf5fbd0920fab64652e4a8435b94fde22d85717cffa8d5ce`
  - `design-loops/3/synthesis.md` =
    `c97a3b8ed2e0882261065629b9a864a6e7eb0163eadca48a519552a580183467`
- Marker sweep clean: no `blocked.json` at the run root or under `work/`,
  no phase marker, no pre-existing `canonical-design.md` or judge
  checkpoint. The Fable judge target is this session. Fresh judging
  authorized; the durable-wait protocol was not needed.
- No reconciliation conflict: the three checkpoints bind the identical
  contract digest, base SHA, and source revision, and all three artifacts
  re-hash byte-exact. Cross-loop design divergences (below) are judged
  shape questions, not binding conflicts.

## Judge verdict

**Selected: the loop-1 unified design as the canonical skeleton, with five
majority-backed amendments (J-A through J-E below).** All three loops
converge on every contract `must`/`must_not` and on the load-bearing
architecture; their divergences are shape-level. Loop 1 is the most
precisely specified document (exact insertion point, full routing table,
complete 7-AC traceability, merged residual risks) and its control-flow
skeleton — probe before any branch exists — is shared by loop 2 (2-of-3)
and carries the strictly stronger invariant: every STOP leaves the
persistent rig worktree with **no `temp` branch, by construction**, with
zero cleanup code to fail. Loop 3's alternative (checkout kept at base
`:294`, error-arm cleanup `git checkout {{target_branch}} || true; git
branch -D temp || true`) is defensible but weaker: if its first cleanup
line fails, the shell is still on `temp`, the `branch -D` also fails, and
the branch is stranded anyway — the very wedge the cleanup exists to
prevent.

### Agreed core (all three loops, adopted verbatim)

1. Pure **insertion** into the `rebase` step's fenced block of
   `gastown/formulas/mol-refinery-patrol.toml`; `git fetch --prune origin`
   (base `:248`) and the missing-target halt (`:249–:293`) survive
   byte-identical, and the checked dual-refspec fetch sits **after** the
   halt (explicit-fetching a missing `$TARGET` exits 128 and would swallow
   `target_branch_missing` into a generic STOP, bypassing the halt's park +
   escalation + wisp-pour — weakening the halt is forbidden).
2. Explicit dual-refspec force-fetch of exactly the two decision refs, exit
   status **checked**, failing closed: echo + `gc runtime drain-ack` +
   `exit 1`, no probe, no checkout, no rebase, zero bead mutation. A failed
   fetch leaves stale tracking refs that can still satisfy the probe — the
   probe alone would skip-decide on fiction.
3. Probe `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"`
   (target→source, quoted) — the string-reverse of merge-push's `:795`
   source→target probe, which answers a different question and is
   untouched.
4. Capture by bare invocation + `$?` on the next line into a non-reserved
   variable — never `if !` (negation clobbers the status) and never a zsh
   reserved name (`status` is read-only).
5. Three-way `case`: rc 0 = skip (success path continues; `temp`
   SHA-identical to `origin/$BRANCH`, merge topology intact; merge-push's
   ff-only tail consumes it unchanged); rc 1 = the preserved, unquoted,
   byte-identical `git rebase origin/$TARGET`; any other rc = STOP, never
   read as "not an ancestor", never routed into the conflict-rejection
   path.
6. Inference-gate repin in the same change; the existing `git rebase
   origin/$TARGET` pin keeps matching because the literal survives
   verbatim; sites are enumerated by grep at fix time, never asserted as a
   count.
7. Regression test lifted from the shipped formula and executed (never
   transcribed), hermetic bare-origin fixtures in the EX-1/EX-2/EX-3
   shapes, logging `gc` stub as the bead-mutation oracle, red demonstrated
   against the unguarded step.
8. Untouched: merge-push in its entirety (`:790`/`:795`/ff-only/
   force-with-lease), the halt, find-work, the conflict tail, the witness
   suite; no backport to the stale `reconcile/worktree-20260814` vintage.

### Cross-loop divergences and judge resolutions

| # | Topic | Loop 1 | Loop 2 | Loop 3 | Resolution |
|---|---|---|---|---|---|
| J1 | Checkout placement | probe-first; checkout duplicated in `0)`/`1)` arms | same as loop 1 | checkout stays at `:294`; `*)` arm cleans `temp` locally | **Loops 1+2 (probe-first).** Majority, and the stronger invariant: no STOP path ever has a `temp` to clean; loop 3's two-line cleanup can itself fail and strand the branch. Cost — one duplicated checkout literal, byte-identical to base `:294` — is accepted by both adopting loops; whole-file containment accepts two sites; the `1)` arm keeps today's exact adjacent checkout+rebase pair, so AC-374-05 stays reviewable by eye. |
| J2 | Capture variable | `ANCESTOR_RC` | `REBASE_SKIP_STATUS` | `REBASE_PROBE_STATUS` | **`ANCESTOR_RC` (loop 1).** All three are non-reserved and base-unique; loop 1's is maximally string-distant from merge-push `:796`'s `ANCESTOR_STATUS=$?` in the suffix family (`…_RC` vs `…_STATUS`), so neither pin can ever be satisfied by the other site, and it is the shortest self-describing name. |
| J3 | Fetch refspec spelling + pin | braced `${BRANCH}` (idiom-identical to merge-push `:790`), deliberately **unpinned** | **unbraced** `$BRANCH`, string-distinct from `:790`, **pinned site-uniquely** | braced, pinned as a documented-weak two-site pin | **Loop 2.** 2-of-3 loops want the fetch pinned; between the pinned variants, a site-unique pin beats a weak two-site pin loop 3 itself calls "mostly-redundant". The gate is the designated fragment-drift mechanism, and the unbraced spelling (functionally identical — `:` and `/` both terminate the name) makes the pin witness THIS site only. The idiom divergence from `:790` is deliberate and commented in the fence; any future "normalization" breaks the pin loudly, which is coordination, not breakage. |
| J4 | STOP wording | fully static sentence, both arms | dynamic prefix + common phrase | common phrase pinned once for both arms | **Merged.** Fetch arm gets the informative loop-2/3 prefix (`$BRANCH`/`$TARGET` are literal text in the formula, so pinnability is unaffected); both arms end in loop 1's full static sentence `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` — pinned once, covering both fail-closed arms (loop 3's refinement), string-distinct from every merge-push analogue. |
| J5 | Skip message + pin | `SKIP-REBASE:` + two forensic short SHAs | `SKIP-REBASE:` + one full SHA | `SKIP_REBASE:` + full SHA + in-message operating instruction | **Merged, hyphen prefix.** 2-of-3 spell `SKIP-REBASE:` (house style per `FAIL-SAFE:`); message = loop 1's two-ref forensic short SHAs + loop 3's explicit instruction tail ("Proceed to run-tests; do not rebase, amend, or reset."). Pin the unique prefix `SKIP-REBASE:` alone — it witnesses the arm's existence (the anti-collapse pin); the probe pin already guards direction. Command substitutions run after the capture and on refs the guard fetch just pinned; a failure there degrades the message, not the decision. *(Review attempt 1 hardened this pin to the echo-anchored spelling — see D3.5.)* |
| J6 | AC-374-04 red mechanism | swap in the unguarded base blob; behavioral red | fix-only lift sentinel; mechanical red | both-trees sentinel; behavioral red | **Behavioral red (loops 1+3).** The identical test file lifts on both trees (sentinel `git checkout -b temp origin/$BRANCH` exists in base and guarded text; sentinel-indexed extraction handles its two guarded-text occurrences) and fails on the base tree by demonstrating the misbehavior — artificial conflict, flattening, stale-ref proceed — which is the strongest reading of "fails against the current unconditional step". A lift-error red proves less. |
| J7 | Halt-composition evidence | diff review only | dynamic halt arm | dynamic halt arm | **Dynamic halt arm (loops 2+3).** Delete `$TARGET` on the bare origin: the prune fetch still succeeds, `show-ref` fails, the halt fires — assert the park shape in the gc-stub log (assignee cleared, `gc.routed_to=human`, `halt_reason=target_branch_missing`, escalation mail, wisp-pour), no STOP message, no probe, no `temp`. Green on base and fix: a composition control that pins "the fix did not reroute the halt" executably (AC-374-06). |
| J8 | Test filename | `test_mol_refinery_patrol_rebase_guard.sh` | `test_mol_refinery_rebase_guard.sh` | `test_mol_refinery_patrol_rebase_guard.sh` | **Loops 1+3**: `test_mol_refinery_patrol_rebase_guard.sh` — matches the suite pattern `test_mol_<formula>_<subject>.sh` for `mol-refinery-patrol`. CI auto-discovers `gastown/tests/test_*.sh` either way. |
| J9 | Probe-error harness | passthrough git shim, `merge-base` → 128, no env knob | spy shim + `REBASE_GUARD_PROBE_RC` env knob | one-subcommand shim, real git resolved to an absolute path first | **Loops 1+3**: minimal passthrough shim intercepting only `merge-base` (real git resolved absolute first), no env knob. "Rebase never invoked" is already proven behaviorally (SHA equality, merge count, no `.git/rebase-merge`); the spy adds machinery without adding coverage. |

Amendments applied to the loop-1 skeleton: **J-A** = J3 (pinned unbraced
fetch), **J-B** = J7 (halt arm, new leg 8), **J-C** = loop 3's static
ordering assertions folded into the structural leg, **J-D** = J5's
instruction tail on the skip echo plus the explicit
do-not-abort/amend/reset sentence in the prose outcome (loops 2+3),
**J-E** = J4's informative fetch-STOP prefix.

### Transcription-defect note (documented, non-blocking)

The loop-2 and loop-3 synthesis documents each cite their sol lane
artifact's sha256 with a tail that diverges from the live file and from
every checkpoint after the first 16 hex characters (loop 2 prose
`2852a02267b41298b25d…` vs actual `2852a02267b412983776…`; loop 3 prose
`9c39423ee3cdf4f7e05a…` vs actual `9c39423ee3cdf4f752bd…`). The binding
chain is unaffected — lane checkpoints, synthesis checkpoints, and live
files are mutually consistent byte-exact (re-verified this session); the
prose digests were evidently typed rather than derived, which is exactly
why the checkpoint helper forbids hand-carried digests. Downstream must
never "correct" a checkpoint against synthesis prose. Every digest in THIS
document was recomputed by the judge from file bytes. Loop 1's cited
digests all verify.

## Canonical unified design

One PR, three files: `gastown/formulas/mol-refinery-patrol.toml`,
`scripts/gascity_pack_inference_gate.py`, new
`gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`. Nothing else
changes. If decomposition splits it, the only safe split is test-first (D4
plus its red control against the unguarded base), then formula+gate
atomically — never formula without gate (AC-374-07).

All `:NNN` line references are base-tree (`05031f2c`) groundings to be
re-derived on the fix branch (AC-374-07); the two lanes of every loop
agreed independently on each anchor.

### D1 — formula insertion (step `rebase`, between the halt's closing `fi` at :293 and :294)

Everything from `:248` through `:293` stays byte-identical. The fence from
`:294` onward becomes:

```bash
# Guarded ancestry decision (issue 374). Pin exactly the two tracking refs the
# decision reads: the prune fetch above is best-effort with an unchecked exit,
# and a decision read off stale refs would skip (or force) a rebase the source
# does not need. Refspecs deliberately unbraced — string-distinct from the
# braced merge-push fetch so the inference-gate pin witnesses this site
# uniquely. Fail closed here: no probe, no rebase, no bead mutation.
if ! git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" "+refs/heads/$TARGET:refs/remotes/origin/$TARGET"; then
  echo "git fetch of $BRANCH/$TARGET tracking refs failed (unreachable origin or missing branch); cannot evaluate rebase ancestry. STOP. Do not mutate bead state."
  gc runtime drain-ack
  exit 1
fi
# Already-based source (origin/$TARGET an ancestor of origin/$BRANCH) is a pure
# fast-forward candidate: rebasing it drops merge commits and their recorded
# conflict resolutions — artificial conflicts on an unchanged SHA (the
# rejection treadmill) or silent flattening that merge-push then force-pushes
# over the source branch. Probe BEFORE any branch exists so every STOP leaves
# the worktree clean for the next patrol cycle.
git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"
ANCESTOR_RC=$?
case "$ANCESTOR_RC" in
  0)
    # The materialization itself is exit-checked: over a stranded `temp` (the
    # pre-existing merge-push STOP wedge) this checkout fails, and proceeding
    # would mis-report a skip while downstream consumes the stale branch.
    if ! git checkout -b temp origin/$BRANCH; then
      echo "cannot materialize temp at origin/$BRANCH for the skip path (a stale temp branch may be stranded from a previous merge-push STOP). STOP. Do not mutate bead state."
      gc runtime drain-ack
      exit 1
    fi
    echo "SKIP-REBASE: origin/$TARGET ($(git rev-parse --short "origin/$TARGET")) is already an ancestor of origin/$BRANCH ($(git rev-parse --short "origin/$BRANCH")); temp materialized at origin/$BRANCH with merge topology preserved. Proceed to run-tests; do not rebase, amend, or reset."
    ;;
  1)
    # Genuinely diverged: exactly the two lines this step has always run.
    git checkout -b temp origin/$BRANCH
    git rebase origin/$TARGET
    ;;
  *)
    # A probe error is never "not an ancestor" (same idiom as merge-push's
    # already-merged gate error arm).
    echo "git merge-base --is-ancestor errored (status $ANCESTOR_RC); cannot evaluate rebase ancestry. STOP. Do not mutate bead state."
    gc runtime drain-ack
    exit 1
    ;;
esac
```

Ordering and rationale:

- **Prune-fetch → halt → guard-fetch → probe → case.** The explicit fetch
  must follow the halt: fetching a missing `$TARGET` with an explicit
  refspec exits 128, and running it first would swallow
  `target_branch_missing` into the generic STOP, bypassing the halt's
  dedicated park + escalation + wisp-pour (weakening the halt is
  forbidden). The prune fetch also feeds the halt's `show-ref` probe (a
  prune fetch succeeds when `$TARGET` is absent, which is what lets
  `show-ref` speak); keeping both fetches preserves the halt's trigger
  mechanics unchanged. After the halt, explicit-fetch failures are exactly
  AC-374-01's cases: unreachable origin, deleted `$BRANCH` (which now
  fails closed at the fetch instead of surfacing at checkout).
- **Fetch exit checked, fail closed.** A failed fetch leaves stale
  tracking refs that can still satisfy `--is-ancestor`; the probe alone
  would skip-decide on fiction. The STOP arm is echo + drain-ack + exit
  only — no `rejection_reason`, no delete/reopen-source, no polecat
  reroute, no `gc bd update` of any kind: a tooling error is not a
  conflict.
- **Three-way discrimination.** rc 0 = skip: `temp` SHA-identical to
  `origin/$BRANCH`, merges intact, normal success path into run-tests →
  merge-push (the ff-only tail consumes a fast-forward source unchanged;
  the `:795` gate probes the opposite direction and is untouched). The
  skip-arm checkout is itself exit-checked
  <!-- REVIEW: added per synthesis finding 1 (skip-arm checkout) -->: a
  failure (e.g. a `temp` stranded by the pre-existing merge-push STOP
  wedge) STOPs fail-closed instead of narrating a skip over a stale
  branch that merge-push would then consume by name (target-only fetches
  `:870`/`:878`, checkout `:938`)
  <!-- REVIEW: citation corrected per iter-2 (carried from iter-1) --> and
  `--force-with-lease` (`:939`) would push over the source — the lease
  passes because the guard fetch just freshened `origin/$BRANCH`. rc 1 =
  the preserved unquoted `git rebase origin/$TARGET`, so clean divergence
  and the conflict/rejection tail behave exactly as today. Any other rc
  (observed 128) = STOP, never interpreted as "not an ancestor", never
  reaches a rebase, never mutates the bead.
- **Capture discipline.** Bare probe invocation with `$?` assigned on the
  next line — no `if !` negation, no intervening command substitution —
  into `ANCESTOR_RC` (non-reserved under zsh; unique in the file; suffix
  family distinct from merge-push `:796`'s `ANCESTOR_STATUS`).
- **Every STOP route is retry-later** (fetch failure, probe error, and the
  skip-arm checkout failure alike)
  <!-- REVIEW: corrected per iter-2 (route count, carried from iter-1) -->.
  The bead stays assigned; find-work
  re-selects it next cycle; the step is idempotent up to the decision and
  has mutated nothing. Only the missing-TARGET case keeps its dedicated
  park.

Behavior table:

| Condition | Route | Bead | Clone |
|---|---|---|---|
| `$TARGET` missing on origin | halt `:249-:293` unchanged (park + escalate + pour) | mutated by the halt, as today | unchanged, no `temp` |
| explicit fetch fails (unreachable origin; `$BRANCH` deleted → 128) | STOP | untouched | no `temp` |
| probe rc=0 (EX-1/EX-2) | checkout + SKIP-REBASE, success path continues | untouched by the decision | `temp` == `origin/$BRANCH`, merges intact |
| probe rc=0 but checkout fails (stranded stale `temp`) | STOP | untouched | pre-existing stale `temp` left exactly as found; nothing created |
| probe rc=1 (EX-3) | checkout + existing rebase → existing conflict path | as today | as today |
| probe rc>1 | STOP | untouched | no `temp` |

### D2 — step-prose amendments (same step, nothing removed)

1. Insert before `:298` ("If rebase SUCCEEDED…"): *If the ancestry
   decision SKIPPED the rebase (`SKIP-REBASE` printed, probe rc=0): `temp`
   is already materialized at `origin/$BRANCH` with merge topology intact
   — treat this step as succeeded without a rebase and proceed to
   run-tests exactly as a successful rebase does. Do not abort, amend,
   reset, or re-run a rebase on it. Nothing was rewritten; merge-push
   consumes `temp` unchanged.*
2. Amend the conflict preamble `:300-:301` to: *If rebase FAILED
   (conflicts) — and only then: the guards above have already ruled out an
   unresolvable target, an already-based source, and fetch/probe tool
   errors, so what reaches a failed rebase is a genuine content conflict
   with `$TARGET`:*
3. One sentence appended to the step's intro rationale (`:235-:246`): *The
   same block also decides whether a rebase is needed at all: when
   `origin/$TARGET` is already an ancestor of `origin/$BRANCH`, the source
   is a pure fast-forward candidate and rebasing it would only destroy
   merge topology.*

### D3 — inference-gate repin

`GASTOWN_BUILD_WORKFLOW_CONTRACTS["mol-refinery-patrol"]` in
`scripts/gascity_pack_inference_gate.py` (command dict entry base `:122`;
substring containment enforced by
`validate_gastown_orchestration_contract`; live-pack pytest
`tests/test_gascity_pack_inference_gate.py`). The containment semantics
are whole-file, at-least-once, and deletion-only — `fragment not in text`
over `formulas/<formula>.toml` alone, so test-file literals can never
satisfy a pin and the gate cannot see arm structure or site counts.
<!-- REVIEW: added per synthesis missing-evidence (gate semantics) --> At
fix time enumerate every `mol-refinery-patrol` site in the gate file by
grep and re-derive line numbers; never assert a count (at base: the
command dict `:122`, the prose dict `:91`, and the `setup_formulas`
registry entry `:790`, which names the formula only and needs no change
under the repin).

- **Existing pins that keep matching (no churn):** `git rebase
  origin/$TARGET` — preserved byte-identical and unquoted in the `1)` arm.
  <!-- REVIEW: corrected per synthesis finding 3 (pin inventory) -->
  `git checkout -b temp origin/$BRANCH` is NOT a gate pin (the string is
  absent from the gate file); it is the test's lift sentinel and a
  leg-assertion subject. Its two post-change occurrences sit inside the
  one lifted fence and are irrelevant to the gate.
- **Five added fragments, each satisfiable only by the new block:**
  1. `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"`
     — the guard fetch; site-unique because merge-push `:790` uses the
     braced `${BRANCH}` spelling (deliberate string distinction, see the
     fence comment).
  2. `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` —
     the decision, direction-locked (merge-push `:795` probes the reverse
     order, a different string; flipping the new probe breaks the pin).
  3. `ANCESTOR_RC=$?` — the non-reserved capture (a rename — e.g. to
     zsh-read-only `status` — fails the gate at commit time, not patrols
     at runtime).
  4. `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` —
     the shared fail-closed sentence of the fetch and probe-error STOP
     arms. This is a deliberately two-site COLLECTIVE pin
     <!-- REVIEW: annotated per synthesis finding 2 (collective pin) -->:
     it witnesses that the fail-closed family exists, and deleting or
     rerouting both error paths without repinning breaks the gate — but
     deleting a single arm keeps the pin satisfied by the other arm's
     copy. Single-arm deletion is witnessed statically by leg 7's
     per-arm literals (`tracking refs failed`, `errored (status `,
     `cannot materialize temp at origin/`) and behaviorally by legs
     1b/4/6 <!-- REVIEW: third-arm witness added per iter-2 Major -->;
     the per-arm strings are deliberately leg-7 literals rather than
     extra gate pins (the gate is the deletion-only whole-file layer;
     per-arm structure belongs to the structural leg — concretely,
     `errored (status ` has exactly one base site outside the new
     block, merge-push `:826`, so promoted to a gate pin it would be
     absorbed under whole-file containment, while on the lifted fence
     it is unique <!-- REVIEW: absorption rationale per iter-2 -->).
     The checkout-STOP arm deliberately does NOT carry this D3.4
     sentence, and must never be "covered" by rewording its echo to
     carry it — the collective pin would then witness a false
     statement (that failure is checkout materialization, not ancestry
     evaluation); its witnesses are the leg-7 literal and leg 1b.
  5. `echo "SKIP-REBASE:` — the skip arm's existence; without it,
     collapsing the `0)` arm into `1)`/`*` would pass every other pin
     while deleting the feature. Pinned echo-anchored
     <!-- REVIEW: hardened per synthesis finding on prose absorption -->
     so no prose mention can ever satisfy it: D2.1 and all step prose
     spell the token backticked and colon-free (`SKIP-REBASE`), a
     convention to preserve — but even a future colon-bearing prose edit
     cannot absorb this pin.
- **Prose-dict survival check:** the gate's second `mol-refinery-patrol`
  fragment tuple (prose dict, base `:91` — `metadata.branch`,
  `fast-forward merge`, `run tests before merging`, `metadata.target`,
  `closes the bead`) must still pass; the insertion removes no prose and
  D2's amendments touch none of those five fragments.
- Optional, not required: a pytest rejection case that deletes the probe
  fragment from a temp copy and asserts `GateError` — include only if it
  costs nothing at review.

### D4 — regression test: `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`

Auto-discovered by CI's gastown shell-test loop. Witness-suite
conventions: `#!/usr/bin/env bash`, `set -euo pipefail` in the harness,
`mktemp -d` + `trap` cleanup, `fail()` helper, awk `lift_block`.

- **Lift, never transcribe.** The step's fenced ```bash``` block is lifted
  whole from the shipped TOML (sentinel: `git checkout -b temp
  origin/$BRANCH` — present in both the unguarded and guarded formula, so
  reds are behavioral, not lift errors; in the guarded text it appears
  twice within the one lifted fence, which the sentinel-indexed extraction
  handles) and executed as one unit, exercising fetch → probe → checkout
  ordering as behavior. Mechanical substitutions only
  (`{{target_branch}}`→`main`, `{{rig_name}}`→`testrig`,
  `{{binding_prefix}}`→``, `<bead>`-style ids→`TESTBEAD`), then `bash -n`.
- **Execution wrapper:** `set +eu` subshell sourcing under plain `bash`
  (the recipe runs in a plain agent shell; testing it stricter than it
  ships measures the wrong thing); stdout and rc captured per leg.
- **Hermetic fixtures:** bare `origin.git` + consumer clone per leg (fresh
  or reset); `git config user.name/email` in every committing repo,
  `HOME`/`GIT_CONFIG_GLOBAL` redirected into the tmpdir and
  `GIT_CONFIG_NOSYSTEM=1` set (git 2.43 local vs 2.52 CI identity
  divergence; a host `/etc/gitconfig` — e.g. `core.hooksPath` — must not
  leak either <!-- REVIEW: added per synthesis finding 6 (NOSYSTEM) -->);
  leg assertions stay version-stable: assert the `SKIP-REBASE:` prefix and
  non-zero fetch rc, never short-SHA length or an exact git-produced exit
  whose value is undocumented or version-variable (two scoped carve-outs
  <!-- REVIEW: rule scoped per iter-2 (leg-3 reconciliation) -->: leg 6's
  `errored (status 128)` is the shim's own deterministic exit, and leg 3's
  rc 1 is git's empirically stable rebase-conflict code — git's own
  documentation promises only non-zero on conflict; the 1 is measured
  (git 2.43; re-confirm on the CI git at fix time), and it is the very
  discriminator the production step's prose keys on
  <!-- REVIEW: basis reworded per retry-1 F7 (documented→empirically
  stable) -->).
  The formula path is resolved witness-style from the test's
  location with an env override
  (`FORMULA="${REBASE_GUARD_FORMULA:-$ROOT/gastown/formulas/mol-refinery-patrol.toml}"`)
  so the red control can aim the identical file at another tree
  <!-- REVIEW: added per synthesis finding 4 (identical-file mechanism) -->.
  env `BRANCH`/`TARGET`/`WORK` and `GC_BEAD_ID` supplied (the
  real step derives them in an earlier fence; exporting `GC_BEAD_ID` keeps
  the halt's empty-`GC_BEAD_ID` fallback parse — base `:271` — unreached,
  but that rationale does not extend to the halt's wisp-pour, which pipes
  its answer through real `jq` unconditionally whenever the halt fires
  (base `:273`), so leg 8 executes `jq` and the suite DOES carry a hard
  `jq` test dependency. Declare it: one-line preflight
  `command -v jq >/dev/null || fail "jq required (halt leg)"` in the
  harness — preferred over shadowing `jq` in the stub PATH, because the
  halt's pour-id extraction must genuinely parse the stub's JSON answer
  <!-- REVIEW: corrected per retry-1 F1 (jq is a real test dependency; old
  "no hard jq dependency" claim was false) -->). PATH-shim `gc` stub: logs
  every invocation to `$GC_LOG` (the bead-mutation oracle), serves
  `bd show`/`bd list` canned JSON, answers wisp-pour with
  `{"new_epic_id":…}` (the halt leg needs it), no-ops the rest; drain-ack
  inert but logged. Fixture shapes: **EX-1** already-based/conflicting
  (`main` at T; source from T with two `--no-ff` merges, the second
  resolving a two-sided same-line edit differently from both raw sides,
  plus a plain commit; fixture asserts
  `merge-base(origin/main, origin/source) == origin/main`), **EX-2**
  already-based/clean (merges touch disjoint files), **EX-3a**
  diverged/clean, **EX-3b** diverged/conflicting.
- **Legs:**
  1. **Skip preserves topology (EX-1 and EX-2; AC-374-02/04.)** Assert:
     rc 0; `SKIP-REBASE:` in stdout; `git rev-parse temp` ==
     `git rev-parse origin/source`; merge count still 2
     (`git rev-list --count --merges`); no
     `.git/rebase-merge`/`rebase-apply`; `origin/source` ref unchanged
     (source never rewritten); zero `bd update`/`workflow` in `$GC_LOG`.
     SHA identity plus intact merge count prove the rebase line was never
     reached. *Red on base:* artificial conflict (EX-1) or flattening
     breaking SHA equality / merges 2→0 (EX-2).
  1b. **Stranded `temp` fails closed at the skip-arm checkout (the
     behavior-table row "probe rc=0 but checkout fails"; executable
     witness of the review-hardened exit-check.)**
     <!-- REVIEW: leg added per iter-2 Major (witness-free arm) -->
     From EX-1: pre-create `temp` in the consumer clone at a recorded
     stale SHA (e.g. the fork point), with the clone's HEAD detached at
     `origin/main` so the base-side behavior is deterministic across
     git versions. Run the fence. Assert: rc != 0; the
     `cannot materialize temp at origin/` STOP wording; no
     `SKIP-REBASE`; `runtime drain-ack` logged; zero `bd
     update`/`workflow` in `$GC_LOG`; `git rev-parse temp` still equals
     the recorded stale SHA; no `temp2` and no branch switch (nothing
     created, nothing deleted — the stale branch left exactly as
     found). *Red on base:* the bare checkout fails silently (rc 128,
     branch untouched), no STOP routing exists, and the unguarded
     `git rebase origin/$TARGET` then runs against the quiescent
     detached HEAD (rc 0) — wrong rc, no STOP wording, so the
     assertions fail.
  2. **Diverged clean rebases as today (EX-3a; AC-374-05.)** Assert: no
     `SKIP-REBASE`; rc 0; `temp` != `origin/source` and
     `merge-base --is-ancestor origin/main temp` rc 0; no mutation during
     the block. Merge count deliberately not asserted (today's diverged
     flattening semantics are preserved, not re-litigated). Green control
     on both trees.
  3. **Diverged conflicting keeps the conflict path (EX-3b; AC-374-05.)**
     Assert: no `SKIP-REBASE`; rc 1 with a rebase in progress (the
     existing conflict tail's precondition); zero mutation during the
     block (rejection belongs to the prose tail); cleanup
     `git rebase --abort`. Green control on both trees.
  4. **Fetch failure stops before the probe (AC-374-01, stale-ref
     trap.)** From EX-1: advance the true `origin/main` past the fork
     (true ancestry now false), then repoint origin's URL at a nonexistent
     path — the stale local tracking refs would still satisfy an ancestor
     probe. Assert: rc != 0; STOP wording; no `SKIP-REBASE`; **no `temp`
     created** (stop precedes checkout); `runtime drain-ack` logged; zero
     `bd update`. Then restore the URL, re-run the fence, and assert it
     now takes the rc=1 path (rebase runs, no skip) — the stale refs never
     produced a decision. *Red on base:* the block proceeds on stale refs.
  5. **Missing source branch (AC-374-01.)** `git update-ref -d
     refs/heads/source` in the bare origin (prune local tracking first).
     Assert: the explicit fetch exits non-zero — implement strictly as
     `rc != 0`, with 128 recorded in a comment as observation only; this
     must never harden into a third exact-code carve-out
     <!-- REVIEW: per retry-1 F7 (leg-5 rc discipline) --> — and the
     fence stops there — no probe output, no `temp`, no mutation. *Red on
     base:* the failure surfaces later at checkout with no STOP routing.
  6. **Probe error fails closed (AC-374-03.)** EX-1 with a passthrough
     `git` PATH-shim delegating everything except `merge-base` → exit 128
     (real git resolved to an absolute path first; unavoidable stub
     because a healthy in-fence fetch heals any poisoned ref before the
     probe reads it). The shim is prepended to PATH only inside the
     lifted-fence execution subshell — fixture setup and assertions in
     every leg run with real git
     <!-- REVIEW: added per synthesis finding 6 (shim scoping) -->.
     Assert: rc != 0; `errored (status 128)` STOP
     wording; **no `temp`** (probe-first means nothing to clean); no
     rebase output; drain-ack logged; zero mutation. *Red on base:* no
     probe exists, so the STOP assertions fail.
  7. **Structural backstop + ordering (static, raw fence text.)** Three
     count assertions on the lifted text, each with a distinct duty: the
     probe line occurs exactly once
     <!-- REVIEW: added per synthesis finding 6 (lift concatenation) -->
     (guards `lift_block`'s concatenate-all-matching-fences semantics —
     but only against a future second fence that itself contains the
     probe); the lift sentinel `git checkout -b temp origin/$BRANCH`
     occurs exactly twice (closes the remaining concatenation gap: a
     probe-less sentinel-bearing fence would concatenate silently past
     the probe-uniqueness check, and any such fence necessarily adds a
     third sentinel occurrence
     <!-- REVIEW: added per retry-1 F3 (sentinel-count concatenation
     guard) -->); the collective STOP sentence substring
     `cannot evaluate rebase ancestry` occurs exactly twice (the
     executable witness of D3.4's anti-fix rule: rewording the
     checkout-STOP echo to append the collective sentence gains a third
     site and reds here, while the gate's at-least-once containment and
     all per-arm literals would stay green
     <!-- REVIEW: added per retry-1 F2 (checkout-STOP reword witness) -->).
     The lifted block also contains
     both explicit refspecs, `ANCESTOR_RC=$?`, and the per-arm STOP
     literals `tracking refs failed`, `errored (status `, and
     `cannot materialize temp at origin/`
     <!-- REVIEW: third literal added per iter-2 Major --> (so deleting
     any fail-closed arm alone — including the exit-checked skip-arm
     checkout — goes red statically here, not only behaviorally in legs
     1b/4/6); ordering holds:
     the prune fetch (`git fetch --prune origin`, line 1 of the lifted
     text) precedes the halt's `show-ref`
     <!-- REVIEW: edge added per retry-1 F4 (prune-fetch ordering; was
     covered only behaviorally by leg 8) -->,
     the halt's `show-ref` precedes the guard fetch, the guard fetch
     precedes the probe, the probe immediately precedes the capture, the
     capture precedes the `case`, and `git rebase origin/$TARGET` occurs
     only after the probe; `bash -n` passes. Catches silent mangling on
     shapes the fixtures don't reach and pins the composition order
     textually.
  8. **Halt composition (AC-374-06.)** Delete `main` on the bare origin:
     the prune fetch still succeeds, `show-ref` fails, the **halt** fires.
     Assert the park shape in `$GC_LOG` (`bd update` with assignee
     cleared, `gc.routed_to=human`, `halt_reason=target_branch_missing`,
     escalation mail, wisp-pour), no STOP message, no probe output, no
     `temp`, no rebase. Green on base and fix — this leg pins that the fix
     did not replace or reorder the halt.
- **Red control (fix time, transcript in the PR body):** run the identical
  test file against the unguarded base formula. Mechanism
  <!-- REVIEW: added per synthesis finding 4 (red-control spec) -->:
  `git worktree add --detach <tmp> 05031f2c`, then invoke the fix-tree's
  test file byte-unmodified with
  `REBASE_GUARD_FORMULA=<tmp>/gastown/formulas/mol-refinery-patrol.toml`
  — never hand-copy the formula or edit the test between runs; record the
  mechanism and the git version(s) exercised in the PR transcript.
  Expected outcomes, per leg (enumerated, never a count): legs 1, 1b, 4,
  5 and 6 FAIL behaviorally
  <!-- REVIEW: leg 1b added to the must-fail-on-base set per iter-2 -->;
  leg 7 FAILS statically (its contained strings
  do not exist at `05031f2c`); legs 2, 3 and 8 stay green. Then run
  against the fixed tree — all nine legs pass. CI keeps only
  the green side; the behavioral-red capability is permanent in the file
  because the sentinel lifts on both trees.

### Verification at implementation time (in order)

1. Apply D1+D2, D3, D4 on a branch off `main`; re-derive every `:NNN`
   cited here against that tree.
2. `git diff` confines formula changes to the D1 insertion and D2 prose;
   `:248`, `:249-:293`, the conflict tail, and merge-push are untouched.
3. `bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh` → all
   legs pass.
4. Red-control procedure → legs 1/1b/4/5/6 fail behaviorally and leg 7
   statically unguarded (2/3/8 green), all nine pass guarded; transcript
   (mechanism + git versions) into the PR body.
5. `python3 -m pytest tests/test_gascity_pack_inference_gate.py -q` →
   green (containment vs the changed tree).
6. Full suite as CI runs it (`for t in gastown/tests/test_*.sh; do bash
   "$t"; done`) → green (witness/heartbeat/polecat untouched).
7. Grep each pinned literal in the changed formula; enumerate the matching
   sites in the PR body — never assert a count.
8. The PR body additionally records
   <!-- REVIEW: added per iter-2 (recording requirements) -->: the
   no-errexit execution assumption (residual risks); the deliberately
   preserved bare checkout in the `1)` arm and its asymmetry with the
   exit-checked `0)` arm (the rc=1-arm wedge is pre-existing and scoped
   out — recorded so it is never read as an oversight); confirmation
   that no STOP arm pours a successor wisp (the missing-`$TARGET` halt
   alone pours); and the verified STOP respawn source per residual
   precision (a) — measured against a production rig, replacing the
   reconciler/pour assertion (the red control's git versions are already
   captured by step 4's transcript)
   <!-- REVIEW: recording added per retry-1 F5 -->.
9. File the residual-precision-(b) follow-up family (deleted-`$BRANCH`
   park mirror of the `$TARGET` halt + repeated stranded-`temp`
   checkout-STOP) as a tracked work item and link it from the PR body
   <!-- REVIEW: step added per retry-1 F6 (tracked follow-up) -->.

## AC ↔ design coverage matrix

| AC | Design element | Test/verification |
|---|---|---|
| AC-374-01 dual-ref force-fetch precedes decision, fails closed | D1 fetch arm (after halt, exit-checked, STOP pre-probe, pre-checkout); pin D3.1 | Legs 4 (unreachable + stale-ref trap + restore/re-run) and 5 (missing branch, real non-zero); gc-log oracle |
| AC-374-02 already-based skips, history intact | D1 rc=0 arm (checkout at healed ref + SKIP-REBASE) + D2.1; pin D3.5 | Leg 1 on EX-1/EX-2: SHA equality, merge count 2, source ref unchanged; leg 1b for the checkout-failure STOP; ff-only downstream acceptance rests on the sol E2 council evidence, not this suite — the lifted fence ends at the rebase step's boundary <!-- REVIEW: attribution per iter-2 -->; `:795` untouched |
| AC-374-03 probe errors fail closed | D1 `*` arm; probe-first (no `temp` to strand); pins D3.2-D3.4 | Leg 6: rc=128 STOP, no `temp`, rebase unreached, no mutation |
| AC-374-04 regression test red→green | D4 legs 1/1b/4/5/6 + both-trees sentinel + red-control procedure | Unguarded: legs 1/1b/4/5/6 fail behaviorally, leg 7 statically; guarded: all nine pass; transcript (mechanism + git versions) recorded in PR |
| AC-374-05 diverged path unchanged | D1 rc=1 arm reproduces today's adjacent checkout+rebase pair byte-identical | Legs 2 (clean) and 3 (conflicting, existing-tail precondition); no line of the conflict path edited |
| AC-374-06 composition & error routing | D1 ordering (halt first, nothing above it touched); STOP arms carry no rejection metadata, no reopen/delete, no reroute; merge-push untouched | Leg 8 executes halt composition; leg 7 pins the order statically; legs 3-6 bead-state oracle (zero `bd update` on STOP/decision paths); diff review vs base (verification step 2) |
| AC-374-07 gate repinned in lockstep | D3: preserved `git rebase origin/$TARGET` pin + five unique new pins + prose-dict survival; sites enumerated at fix time | Gate pytest on the changed tree; grep each literal, enumerate sites in the PR |

Contract must/must_not closure: dual-refspec force-fetch of both refs (D1
fetch line) · fetch rc checked, stop with no probe/rebase/mutation (D1
STOP) · target→source probe before any rebase (D1) · three-way rc
discrimination (D1 case) · non-reserved capture (`ANCESTOR_RC`) · skip
leaves `temp` at `origin/$BRANCH` for run-tests/merge-push (rc=0 arm) ·
gate repin in the same change (D3) · red→green test (D4) · no
prune-fetch-only freshness · no error read as "not an ancestor" · no error
routed into conflict-rejection · skip path never
rebases/amends/resets/force-pushes · `:795` gate, ff-only tail,
missing-target halt, and find-work all untouched.

## Residual risks (merged, judge-final)

- **Line drift:** every `:NNN` is a base-tree (`05031f2c`) citation; the
  checked-out `reconcile/worktree-20260814` vintage differs and is
  explicitly out of scope for backporting. Re-derive on the fix branch.
- **Duplicated checkout literal** (rc=0/rc=1 arms) is deliberate — bought
  for clean-STOP semantics in a persistent worktree and eye-verifiable
  AC-374-05 adjacency; no pin depends on the duplication. After the
  review hardening the `0)` arm's copy is exit-checked (`if ! git
  checkout -b temp origin/$BRANCH; then …`) while the `1)` arm keeps
  today's exact bare checkout+rebase pair byte-identical — the sentinel
  substring survives at both sites
  <!-- REVIEW: updated per synthesis finding 1 -->.
- **Fetch-idiom divergence is deliberate:** the guard fetch is unbraced
  (`$BRANCH`) where merge-push `:790` is braced (`${BRANCH}`) so the D3.1
  pin is site-unique. "Normalizing" the spelling breaks the pin loudly at
  commit time — that is the pin working, not breaking; the fence comment
  records the intent.
- **Pre-existing stranded-`temp` hazard at merge-push STOPs** (`:826-:829`,
  `:838-:841` leave `temp` behind; the next rebase-step checkout then
  fails): real, pre-existing, out of scope. This change adds zero new
  stranding sites; do not "fix" merge-push here. The skip arm's
  exit-checked checkout <!-- REVIEW: per synthesis finding 1 --> converts
  the wedged state into a loud fail-closed STOP (creating and deleting
  nothing — the stale branch remains exactly as found) instead of
  silently consuming the stale `temp` and mis-narrating a skip; clearing
  the stale branch itself stays a human/merge-push-side concern. A
  checkout-STOP hit repeatedly on the same stranded `temp` is
  operationally the same assigned head-of-line class as precision (b)
  below and belongs to that follow-up family
  <!-- REVIEW: cross-ref per iter-2 -->.
- **Two back-to-back fetches** (`--prune`, then explicit) are accepted
  redundancy: the first feeds the halt's `show-ref` probe and prunes
  deleted refs; the second pins and rc-checks exactly the two refs the
  decision reads. Collapsing them would reorder the halt (forbidden).
- **Fetch/probe/checkout STOP leaves the bead assigned** — retry-by-repatrol is the
  chosen semantic (correct for transient failures; persistent ones surface
  as repeated STOP logs). Only the missing-TARGET halt parks. Accepted,
  not widened. Two precisions
  <!-- REVIEW: added per synthesis finding 5 (STOP semantics) -->: (a) the
  STOP arms end the session via drain-ack WITHOUT pouring a successor
  wisp (unlike the halt, which pours precisely so one bead cannot end the
  merge lane — the same semantic as today's `:826`); re-selection
  therefore relies on the rig's patrol respawn cadence (reconciler/pour),
  not on this step — if that source is absent the lane stalls fail-closed
  rather than treadmilling. That respawn source is asserted from repo
  evidence only and cannot be proven in-repo: at fix time verify the
  concrete source (reconciler cadence vs poured wisps) against a
  production rig and record the finding in the PR body, replacing this
  assertion
  <!-- REVIEW: per retry-1 F5 (respawn source must be verified, not
  asserted) -->. (b) A permanently-deleted `$BRANCH` becomes
  an assigned, never-healing STOP — a head-of-line risk by the halt's own
  rationale; parking it would require bead mutation on an error path,
  which the contract forbids here — left as an explicit follow-up
  (mirror of the `$TARGET` halt). The follow-up is one family — the
  deleted-`$BRANCH` park mirror plus the repeated stranded-`temp`
  checkout-STOP (same assigned head-of-line class) — and at fix time it
  must be FILED as a tracked work item linked from the PR body;
  committed prose alone is not the tracking
  <!-- REVIEW: per retry-1 F6 (follow-up needs a tracked owner) -->.
- **Mid-step `$TARGET` deletion race**
  <!-- REVIEW: added per synthesis finding 5 (TARGET race) -->: deleted
  after the prune fetch but before the guard fetch, `show-ref` still
  passes on the not-yet-pruned tracking ref and the guard fetch exits
  128 — a generic STOP once; the next patrol's prune fetch prunes,
  `show-ref` fails, and the halt parks properly. One-cycle
  misclassification, fail-closed both ways, self-healing: a lone
  fetch-STOP log on a deleted target is this race, not a routing defect.
- **No-errexit execution assumption**
  <!-- REVIEW: added per synthesis finding 6 (errexit) -->: the fence
  relies on the executing agent shell not running fences under `set -e`
  (a probe rc=1 must fall through to the `case`) — the exact status quo
  base `:295` already depends on; record the assumption in the PR body.
  Any future errexit adaptation must use the
  `ANCESTOR_RC=0; git merge-base … || ANCESTOR_RC=$?` capture form —
  never `|| true`, which destroys the trichotomy.
- **`BRANCH == TARGET` degeneracy:** probe rc=0; the skip arm materializes
  `temp` at the shared ref and narrates; downstream behaves as a no-op
  landing (`:795` rc=0 → 0-commit fall-through → false-completion guard);
  asserted, exercised by no test leg — accepted
  <!-- REVIEW: noted per synthesis missing-evidence -->; metadata
  validation stays out of scope.
- **Sentinel/pin coupling:** the lift sentinel (`git checkout -b temp
  origin/$BRANCH`) and the pins share strings with the formula, at
  different layers <!-- REVIEW: corrected per synthesis finding 3 -->:
  renaming the capture variable breaks the GATE (D3.3) at commit time;
  renaming `temp` breaks the lift sentinel and the leg assertions — loud
  in CI, but no gate pin (the checkout string is not pinned). Both drifts
  are coordinated and loud by design, via different mechanisms.
- **Shim transparency (leg 6):** the `merge-base`-only git shim must exec
  real git (absolute path) for everything else; accidental interception
  fails multiple legs, not one.
- **Executing-agent improvisation** (formula steps are prose-driven): D2
  makes skip a first-class success outcome with an explicit
  do-not-rebase/amend/reset rule at the point of use (fence echo + prose);
  the gate pins the decision's literals; the lifted-block test goes red in
  CI if fence and behavior diverge.
- **Command substitutions in the skip echo** (`git rev-parse --short`) run
  after the capture and on refs the guard fetch just pinned; a failure
  there degrades the message, not the decision.

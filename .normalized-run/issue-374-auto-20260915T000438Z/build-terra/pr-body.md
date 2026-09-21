# PR body records — issue 374: `mol-refinery-patrol` rebase-skip guard

Branch: `normalized/06e7ae9267b1e212b5d55ab940d5b69a3df782f3810702fdfe5a7296a37540f9/terra`
(impl lane `terra`, run `issue-374-auto-20260915T000438Z`, base `05031f2c66e080865c379ff799c7369430560a8f`)

Commits (in order):

- `ced404d` — `test(gastown): regression suite for the refinery rebase ancestry guard (issue 374)` — design D4, work item gp-3zlmh (W1, test-first)
- `d465774` — `fix(gastown): guard the refinery rebase with an ancestry decision (issue 374)` — design D1+D2+D3 in one atomic commit, work item gp-g9s7a (W2)

> Ordering note (recorded, not hidden): the implementation drain dispatched
> its items in reverse order relative to the approved decomposition
> (W4→W3→W2→W1; escalated as mail `gcg--9223372036854775182` by drain item 0
> and as mail `gcg--9223372036854775176` by this session). Because the
> design's split rule is "test-first … then formula+gate atomically", the
> W3 item executed the dependency-correct sequence inside the shared
> session: the test commit first, then the atomic formula+gate commit, then
> the red control and this verification sweep. The W2/W1 work-store beads
> remain open for their drain items to verify and close against these
> commits.

## What changed

The `rebase` step of `gastown/formulas/mol-refinery-patrol.toml` previously
ran `git rebase origin/$TARGET` unconditionally after checking out the
source. When `origin/$TARGET` is already an ancestor of a merge-heavy
`origin/$BRANCH`, that rebase discards merge commits and their recorded
conflict resolutions: the patrol manufactures an artificial conflict on an
unchanged SHA (a deterministic reject-to-polecat treadmill) or silently
flattens the topology, which merge-push then force-pushes over the source
branch.

The fix inserts a guarded ancestry decision between the missing-target halt
and the rebase:

- an explicit dual-refspec force fetch of BOTH tracking refs
  (`+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH` and the `$TARGET`
  twin), exit-checked — a failed fetch leaves stale refs that could still
  satisfy the probe, so it must fail closed (STOP) before any decision,
  with no bead mutation;
- `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"`
  (target→source), probed BEFORE any branch exists so every STOP leaves the
  worktree clean, captured into `ANCESTOR_RC` (non-reserved under zsh);
- a three-way case: rc 0 materializes `temp` at `origin/$BRANCH`
  (exit-checked over a stranded stale `temp`) and narrates `SKIP-REBASE`
  down the normal success path; rc 1 runs exactly the two lines the step
  has always run; any other rc STOPs without rebasing and without mutating
  bead state.

Every STOP arm is echo + `gc runtime drain-ack` + `exit 1` only — no
`rejection_reason`, no reopen/delete-source, no polecat reroute. The prune
fetch, the missing-target halt (`:249-:293` at base), the conflict tail,
and merge-push are untouched. The inference gate is repinned in lockstep:
the preserved unquoted `git rebase origin/$TARGET` pin plus five fragments
satisfiable only by the new block.

## Red control transcript (design verification step 4)

Mechanism (exactly as the design directs — never hand-copy the formula,
never edit the test between runs):

```
git worktree add --detach <tmp> 05031f2c
REBASE_GUARD_FORMULA=<tmp>/gastown/formulas/mol-refinery-patrol.toml \
  bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh
```

The fix-tree test file runs byte-unmodified; only the formula pointer
moves. Versions exercised: git 2.43.0, GNU bash 5.2.21, jq 1.7 (host
`maintainer-city` runner). CI's gastown shell-test loop may run a newer
git; the only exact-exit assertion in the suite is leg 3's rc 1 (rebase
conflict; measured on 2.43, to re-confirm on the CI git — leg 5's fetch
failure is asserted strictly as non-zero, with 128 recorded as comment
only).

Unguarded base (`05031f2c`) — enumerated per leg, never counted:

| Leg | Outcome | Observed failure mode |
| --- | --- | --- |
| 1 (EX-1) | FAIL (behavioral) | rebase ran on the already-based source, stopped at "could not apply … side B" with `CONFLICT (content): Merge conflict in shared.txt`, rc 1 — the artificial conflict |
| 1 (EX-2) | FAIL (behavioral) | clean replay flattened the topology: SHA equality / merge-count assertions broke |
| 1b | FAIL (behavioral) | bare checkout failed silently (`fatal: a branch named 'temp' already exists`), unguarded rebase then ran against the quiescent detached HEAD — "HEAD is up to date", rc 0: wrong rc, no STOP wording |
| 2 (EX-3a) | PASS | diverged-clean control unchanged |
| 3 (EX-3b) | PASS | diverged-conflict control unchanged |
| 4 | FAIL (behavioral) | fetch to a repointed nonexistent origin failed but the block proceeded on stale tracking refs: no fetch-STOP wording, `temp` created, rebase ran |
| 5 | FAIL (behavioral) | missing source branch surfaced late at checkout (`'origin/source' is not a commit`), rebase ran, rc 0 — no STOP routing |
| 6 | FAIL (behavioral) | no probe exists on base, so the probe-error STOP wording never appears; checkout+rebase ran instead |
| 7 | FAIL (static) | probe line occurs 0 times in the lifted base fence (`cannot evaluate rebase ancestry` absent) |
| 8 | PASS | halt composition unchanged on base |

Suite exit: 1 (expected).

Fixed tree (HEAD `d465774`): all nine legs pass, suite exit 0. CI keeps
only the green side; the behavioral-red capability is permanent in the file
because the lift sentinel exists on both trees.

## Verification sweep (design verification steps 2–8)

2. **Diff confinement** — `git diff 05031f2..HEAD` touches exactly three
   files: the formula (+63/−4 in two hunks), the gate (+17), and the new
   test (+622). The formula's only deleted lines are the two fence lines
   absorbed verbatim into the `1)` arm and the two conflict-preamble lines
   amended by D2.2; `:248` (prune fetch), the halt `:249-:293`, the
   conflict tail, and merge-push are untouched.
3. **`bash gastown/tests/test_mol_refinery_patrol_rebase_guard.sh`** — all
   nine legs pass (observed: `rebase-guard suite: all legs pass`, rc 0).
4. **Red control** — transcript above (rc 1 on base, enumerated per leg).
5. **`python3 -m pytest tests/test_gascity_pack_inference_gate.py -q`** —
   `89 passed in 2.99s` on the changed tree.
6. **Full gastown suite as CI runs it** (`for t in gastown/tests/test_*.sh;
   do bash "$t"; done`) — all 7 test files pass, including
   `test_mol_witness_patrol_orphan_recovery.sh` (the only pre-existing
   `merge-base --is-ancestor` user, untouched).
7. **Pinned literals — sites enumerated in the changed formula (never
   counted):**
   - `git fetch origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"`
     → site `:304` only (merge-push's braced fetch at `:845` and its
     target-only fetches at `:925`/`:933` do not match the unbraced pin).
   - `git merge-base --is-ancestor "origin/$TARGET" "origin/$BRANCH"` →
     site `:315` only (merge-push's probe at `:850` runs the reverse
     direction — `"origin/$BRANCH" "origin/$TARGET"` — and does not
     match).
   - `ANCESTOR_RC=$?` → site `:316` only (merge-push captures
     `ANCESTOR_STATUS=$?` at `:851`, a different string).
   - `cannot evaluate rebase ancestry. STOP. Do not mutate bead state.` →
     sites `:305` and `:337`, both inside the new block (the collective
     two-site pin; the checkout-STOP echo deliberately does NOT carry this
     sentence).
   - `echo "SKIP-REBASE:` → site `:327` only (echo-anchored; step prose
     spells the token backticked and colon-free).
   - preserved pin `git rebase origin/$TARGET` → site `:332`, the `1)`
     arm, unquoted and byte-identical to base.
   - Gate-file `mol-refinery-patrol` sites, all enumerated: `:91` (prose
     dict — unchanged fragments all still present: `metadata.branch`,
     `fast-forward merge`, `run tests before merging`, `metadata.target`,
     `closes the bead`), `:122` (command dict — repinned here), `:807`
     (`setup_formulas` registry — names the formula only, no change
     needed).

   (Formula line numbers are fix-tree `d465774` groundings; gate line
   numbers likewise. All `:NNN` citations from the contract/design against
   `05031f2c` were re-derived at fix time as required.)

## Required records (design verification step 8)

- **No-errexit execution assumption.** The fence relies on the executing
  agent shell not running fences under `set -e` (a probe rc=1 must fall
  through to the `case`) — the exact status quo the base tree's
  `:295` already depends on. Any future errexit adaptation must use the
  `ANCESTOR_RC=0; git merge-base … || ANCESTOR_RC=$?` capture form — never
  `|| true`, which destroys the trichotomy. The regression suite executes
  the lifted fence under `set +eu` for precisely this reason: testing it
  stricter than it ships would measure the wrong thing.
- **Deliberate `1)`-arm bare-checkout asymmetry.** The `0)` arm's checkout
  is exit-checked (`if ! git checkout -b temp origin/$BRANCH; then …`) so a
  stranded stale `temp` STOPs fail-closed; the `1)` arm keeps today's
  exact bare `git checkout -b temp origin/$BRANCH` +
  `git rebase origin/$TARGET` pair byte-identical (AC-374-05's
  eye-verifiable adjacency). The rc=1-arm wedge is pre-existing and scoped
  out — recorded here so it is never read as an oversight.
- **No STOP arm pours a successor wisp.** Confirmed statically against the
  changed tree: `bd mol wisp` appears at 7 sites in the formula (`:4`,
  `:124`, `:277`, `:383`, `:488`, `:587`, `:1288`) and none of them falls
  inside the guard block (`:298`–`:341`); the halt's pour at `:277`
  precedes the guard. The STOP arms end the session via `drain-ack` only.
- **Verified STOP respawn source (residual precision (a)), measured
  against a production rig.** Measured on `maintainer-city`
  (the HQ rig hosting the `gascity-packs` workspace), 2026-09-20:
  session respawn after a drain-ack is driven by the **controller/
  reconciler cadence, not by poured wisps**. Concretely observed:
  (1) a live controller process
  (`/opt/gascity/releases/mc-enterprise7v-trust-bced92f662/gc nudge poll
  --city /data/projects/maintainer-city --session …`) manages sessions;
  (2) the pool-worker contract states the reconciler "will spawn a new
  worker when more work arrives", and this very session is an instance —
  spawned because bead work existed, per `gc hook --claim`;
  (3) the refinery formula's own find-work step ends idle cycles expecting
  "the session_sleep policy will restart this session after the configured
  idle interval" — a controller-side idle-interval restart, and the city's
  resolved config carries controller session-lifecycle settings (observed
  `idle_timeout = "2h"` on pool-agent stanzas). So a STOP that leaves the
  bead assigned (open/in_progress) is re-selected on the next reconciler-
  spawned or idle-restarted patrol — re-selection does not depend on the
  step pouring anything. If that source were absent the lane would stall
  fail-closed rather than treadmill, which is the accepted semantic. This
  measurement replaces the design's repo-evidence-only assertion.

## Tracked follow-up (design verification step 9)

The residual-precision-(b) family is filed as tracked work:
**`gp-2rn1y`** — "mol-refinery-patrol: assigned head-of-line family —
deleted-`$BRANCH` park mirror + repeated stranded-temp checkout-STOP (374
follow-up)" (P2, open). Filed by drain item 0 (W4); this PR body links it.
Committed prose alone is not the tracking — the bead is.

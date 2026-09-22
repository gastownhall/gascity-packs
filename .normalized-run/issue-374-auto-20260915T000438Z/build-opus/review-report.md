---
schema: gc.build.review.v1
workflow:
  id: gcg--9223372036854774975
  formula: workflows-build-from-convoy
methodology:
  pack: workflows
  name: expansion-review-pr
producer:
  formula: expansion-review-pr
  stage: review
  attempt: 1
status: changes_required
trace:
  upstream:
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/claude-review.md
      hash: sha256:b16d1a52a3d99886ac4d7332952c60c6c1e424666a0831c9e76d307d3566e2c9
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/codex-review.md
      hash: sha256:567e385d278a380736690077ba80ae7e1d95faa93ed14a64e4622ba9c4249fd0
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/gemini-review.md
      hash: sha256:24b44bfcd7a7e9f2831ce219ff59bb9822ededb978cb80cf46d3401fc409a650
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/synthesis.md
      hash: sha256:ba432975b668c2e6477650a8cabbdcc679f0dd90d0809efbc7991c14c59a0d2e
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus/.gc/reviews/gcg--9223372036854774975/attempt-1/quality-scorecard.md
      hash: sha256:92aec223d64d2e483b3199d1bc5ba39508753db29501b3764509cb74aa1bdf2b
    - path: beads/gp-ydg59
      hash: bead:gp-ydg59
    - path: /data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus
      hash: git:2df2dca710ba79876f335300d9a37abbcb3d6d8b
      role: review-subject
  coverage: []
---

# Review Report: issue-374 opus builder lane — mol-refinery-patrol rebase guard

## Verdict

**Status: `changes_required`.**

The verdict is computed deterministically from the completed review lanes; this
stage re-rates nothing.

- **Quality scorecard decision:** `request_changes`
- **Quality scorecard score:** 837
- **Quality scorecard threshold:** 850
- **`New Findings` counts (from `synthesis.md`):** `blocker=0, major=2, minor=2, nit=1`

Approval requires `blocker=0` **and** `major=0` **and** a scorecard with
`decision=approve`, `threshold=850`, and an integer `score >= 850`. Two of the
three approval predicates fail here: two `major` new findings are open, and the
scorecard both decides `request_changes` and scores 837, which is 13 points
below the 850 threshold. No lane is missing — `claude-review.md`,
`codex-review.md`, `gemini-review.md`, `synthesis.md`, and
`quality-scorecard.md` all exist — so this is `changes_required`, not `blocked`.

Review subject: worktree
`/data/projects/gascity-packs/worktrees/normalized-82406fd32929a75b9af846d4c47c20dc95c2f78536446123e25ab94bedc39e2e-opus`
at HEAD `2df2dca710ba79876f335300d9a37abbcb3d6d8b`, diff range
`05031f2c66e080865c379ff799c7369430560a8f..HEAD`.

## Findings

All five findings below are copied from `synthesis.md` `## New Findings`,
grouped under their original category headings, at their original severities.
Nothing is dropped, added, or re-rated.

### [Contract & Interface Fidelity]

- **Severity:** major (claude: major in [2]; gemini: major in [3]; codex: minor in [3] — corrected upward, see Not Carried #1)
- **Confidence:** high (codex/gemini rated medium; the measured table below is what raises it)
- **Source:** all
- **Quality dimension:** correctness
- **Gate impact:** major
- **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:994-996` (the retry instruction), `:989` (the heading "Push the **rebased** branch back to origin"), against the skip contract at `:326` and `:343-347`
- **Why it matters:** D2 makes "skip" a first-class success in the `rebase` step, but the `MERGE_STRATEGY=mr` path's lease-failure recovery still instructs *"STOP, fetch the latest branch, rebase your temp branch again, and retry with `--force-with-lease`"*. On the skip path `temp` is not a rebase product — it is `origin/$BRANCH` with its merges intact — so following that instruction literally performs exactly the rewrite the PR exists to prevent, and then force-pushes it onto the source branch. `mr` is the only downstream path that rewrites `$BRANCH`; the direct path's `--ff-only` merge (`:926`) consumes a skipped `temp` correctly. Measured across 7 rows in `mktemp -d` with identical retry text and only the `temp` shape differing: the already-based/skip shape goes from **2 merges to 0** and the other agent's commit is **LOST**; the first `--force-with-lease` was rejected in every row and the retry push succeeded in every row, so the lease protection is spent. Reachability does not require `merge_strategy=mr` to be configured: `:557-559` promotes a `direct` bead to `mr` whenever an existing PR is discovered. The text is byte-identical at base, but the **flatten** occurs only on the skip shape — a state this diff invented — so the "pre-existing on base" mitigation is unavailable for the gating half.
- **Required fix:** (prose only — no `merge-push` behaviour change, so the design's "do not repair merge-push as a drive-by" boundary holds) on lease failure, **return to the `rebase` step's ancestry decision** rather than rebasing in place: re-fetch both tracking refs, **re-materialize `temp` at the freshly fetched `origin/$BRANCH` first**, then probe — rc=0 → keep it as-is (no rebase); rc=1 → rebase onto `origin/$TARGET`; anything else → STOP. Retitle `:989` to "Push the branch back to origin" (the heading is false on the skip path). Because re-materializing changes the tested tree, say explicitly that the retry re-enters the step and `run-tests` re-runs — do not describe it as a push-level fixup. The re-materialize clause is not cosmetic and is not what either lane wrote (see Not Carried #2). Add a leg-7-style literal pin for the carve-out so the two prose halves cannot drift apart again (this also discharges codex's nit, which is the test counterpart of this finding).

### [Architectural Consistency]

- **Severity:** major (gemini: major/high; claude: minor/medium — severities two levels apart, policy keeps the stricter)
- **Confidence:** high
- **Source:** claude+gemini
- **Quality dimension:** correctness
- **Gate impact:** minor — the reasoning is in the mitigation row; it is required in this round for loop economics, not because the harm is major
- **Evidence:** `gastown/agents/refinery/prompt.template.md:335` (the "Correct command" row) **and `:209`** (the categorical MUST — a site neither lane's fix names); pairing precedent at `gastown/tests/test_gastown_pack_assets.sh:207`
- **Why it matters:** the pack treats the refinery formula and its prompt as one contract surface — `test_gastown_pack_assets.sh:207` loops `for path in "$refinery" "$refinery_prompt"` and pins the same literals in both. The prompt's Command Quick-Reference, under a column header literally titled **"Correct command"**, still publishes `| Rebase on target | git rebase origin/$TARGET |` unconditionally, with the fetch row (`:334`) naming only the best-effort `git fetch --prune origin` the new guard specifically refuses to decide from. Both rows were *correct* at base, because the step ran exactly those commands unconditionally; the diff is what made them wrong on one branch of the decision. Two sites, not one: `:209` **"After every merge, main moves. Next branch MUST rebase on new baseline."** closes the Sequential Rebase Protocol section (`:192-209`) in MUST form. For an already-based source D2's instruction is precisely *not* to rebase. `:209` is a conceptual overstatement where `:335` names an executable command, so it is the weaker of the two — but a `:335`-only patch leaves a MUST standing. Gate impact is minor rather than major because of three measurements on the shipped tree: (a) the formula is authoritative and says so twice (`propulsion.template.md:177`, `prompt.template.md:188` under `:176`); (b) the point-of-use imperative is in the artifact the agent executes (`:326`, `:343-347`); (c) the quick-reference is demonstrably a vocabulary lookup that already under-specifies other guarded operations (`:336`, `:337` vs `:906-908`, `:929`), and the formula never points at the cheat-sheet.
- **Required fix:** amend **both** sites — replace the `:335` row with the guarded decision (or delete the one-liner so it cannot override D2) and scope `:209`'s MUST to the diverged case. Extend the existing formula+prompt pin in `test_gastown_pack_assets.sh` so a bare `git rebase origin/$TARGET` cannot reappear as the prompt's "Correct command" without the probe context. **Do not land a `:335`-only patch** (Not Carried #3). *Scope instruction:* `prompt.template.md` is currently untouched by this diff. Touch only `:209`, `:334-335`, and the pack-assets pin; leave every other row alone — the `:336`/`:337` divergences are pre-existing and belong to a separate follow-up.

### [Test Evidence Quality]

- **Severity:** minor
- **Confidence:** high — claude was the sole flagger, which the policy defaults to medium; I reproduced its measurement exactly, which is what raises it
- **Source:** claude
- **Quality dimension:** maintainability
- **Gate impact:** minor
- **Evidence:** `scripts/gascity_pack_inference_gate.py:122-144` (the five new fragments); `tests/test_gascity_pack_inference_gate.py:1476-1478` pins only three older refinery fragments; precedent for the fix shape at `:1487` (`WITNESS_ORPHAN_GUARD_PINS`)
- **Why it matters:** the repin protects the formula, but nothing protects the repin. Measured in a `git archive` lab: baseline **89 passed**; with all five new tuple entries deleted from `GASTOWN_BUILD_WORKFLOW_CONTRACTS["mol-refinery-patrol"]`, still **89 passed**. So a future edit can retire the static half of AC-374-07 in silence, and AC-374-07's atomicity guarantee decays the moment someone trims the tuple. Bounded honestly: this is defence-in-depth erosion, not exposure — the shell suite is the behavioural net and it bites hard, and claude's complementarity probe shows the two nets cover different failure shapes by design.
- **Required fix:** ~6 lines in the same test, in the shape the file already uses for the witness — assert each of the five fragments is in `contracts["mol-refinery-patrol"]`.

### [Behavioral Correctness]

- **Severity:** minor
- **Confidence:** high
- **Source:** claude
- **Quality dimension:** correctness
- **Gate impact:** minor
- **Evidence:** `gastown/formulas/mol-refinery-patrol.toml:314-316` against the formula's own precedent at `:820` ("Two failure modes share this gate, so **evaluate them in one script that shares shell state**") and `:906` ("Run this as one script")
- **Why it matters:** the guard replaces two independent commands with a chain that only works inside one shell — `git merge-base` → `$?` → `ANCESTOR_RC` → `case`. The structurally identical sibling (the merge-state gate: same guarded dual-refspec fetch, same bare probe, same `X_STATUS=$?`, same `0/1/*` case, same STOP wording) is introduced by an explicit single-shell instruction; the rebase fence has none. If the fence is split at the probe line, `ANCESTOR_RC` reads `0` in the fresh shell, so the **skip arm fires on a genuinely diverged source** and `:343-347` then tells the agent to treat it as success. Bounded both ways: the downstream failure is loud, not corrupting — `merge-push`'s `--ff-only` (`:926`) aborts with `fatal: Not possible to fast-forward`, so the cost is a stalled cycle plus a log line asserting a false ancestry, not a damaged `$TARGET`; and `:247-249` partially mitigates by introducing the decision as "**the same block** also decides whether a rebase is needed at all" inside one fenced bash block.
- **Required fix:** one sentence above the fence, matching `:820`'s wording: run this block as one script — the probe's status is captured into `ANCESTOR_RC` on the next line and every STOP arm's `exit` must end the step.

### [Test Evidence Quality] — nits (non-gating, listed for the record)

- **Severity:** nit
- **Confidence:** high
- **Source:** claude+codex
- **Quality dimension:** maintainability
- **Gate impact:** none
- **Evidence:** `gastown/tests/test_mol_refinery_patrol_rebase_guard.sh:570-571`; `:347-368` vs `:411-412`; codex on `:146-161`
- **Why it matters:** (a) leg 7 requires the prune fetch to be *literally* line 1 of the lifted text, so a purely cosmetic leading comment reds the suite — fail-closed and self-explaining, so it is the right side to err on; recorded only so the next editor reads the red as cosmetic. (b) AC-374-02's verification clause names "downstream `git merge --ff-only` accepts the source", and leg 2 runs that assertion for the diverged path while leg 1 does not run it for the skip path — the path the AC is about. Nothing is unproven (it is entailed by leg 1's SHA-identity assertion plus probe rc=0). (c) Codex's "no leg aims at the `mr` retry" is the test counterpart of F1 and is absorbed into F1's required fix.
- **Required fix:** none gating. If (a) ever fires on a benign edit, relax it to "first non-comment line" rather than deleting the ordering anchor. For (b), copy leg 2's one-liner into leg 1 so the AC's named verification is executable rather than derived.

## Verification

### Quality scorecard summary

- **Quality Score:** 837 / 1000
- **Decision:** request_changes
- **Threshold:** 850
- **Caps Applied:** None
- **Required Changes:**
  - [major] Contract & Interface Fidelity: D2 makes "skip" a first-class success in the `rebase` step, but the `MERGE_STRATEGY=mr` path's lease-failure recovery still instructs the agent to rebase the temp branch again and retry with `--force-with-lease` (Evidence: `gastown/formulas/mol-refinery-patrol.toml:994-996`, `:989`).
  - [major] Architectural Consistency: amend **both** sites — replace the `:335` row with the guarded decision (or delete the one-liner so it cannot override D2) and scope `:209`'s MUST to the diverged case; extend the existing formula+prompt pin in `test_gastown_pack_assets.sh` (Evidence: `gastown/agents/refinery/prompt.template.md:335` **and `:209`**).
- **Non-Gating Follow-Up:**
  - [minor] Test Evidence Quality: ~6 lines in the same test asserting each of the five fragments is in `contracts["mol-refinery-patrol"]`.
  - [minor] Behavioral Correctness: one sentence above the fence, matching `:820`'s wording, that the block runs as one script.
  - [nit] Test Evidence Quality: relax leg 7's line-1 anchor to "first non-comment line" if it ever fires on a benign edit; copy leg 2's `--ff-only` one-liner into leg 1.
- **Scorecard dimension scores:** Correctness and Test Evidence 123/275; Maintainability and Architecture 214/225; Security and Defensive Design 250/250; Readability and Idiom 150/150; Scope Discipline and Review Hygiene 100/100.
- **Measured complexity (per scorecard):** status=ok, worst_changed cyclomatic=0, cognitive=0.

### Reviewer lanes that ran

- **claude:** present — `gascity-packs/gc.design-implementation-reviewer`, `claude-review.md` (sha256 `b16d1a52…`).
- **codex:** present — `gascity-packs/gc.implementation-reviewer`, `codex-review.md` (sha256 `567e385d…`).
- **gemini:** present — `gascity-packs/gc.design-test-risk-reviewer`, `gemini-review.md` (sha256 `24b44bfc…`). `skip_gemini=false`; the lane ran and produced a report.
- **synthesis:** present — `synthesis.md` (sha256 `ba432975…`), all three lanes carried with full cross-file coverage.
- **quality-scorecard:** present — `quality-scorecard.md` (sha256 `92aec223…`), produced by `gascity-packs/gc.implementation-reviewer`.

No lane is missing, so no `review_blocked` / `review_unavailable` state applies.
This stage analyzed and recorded only: no code was modified, no reviewer was
re-run, and no fix was applied.

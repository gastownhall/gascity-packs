
Validate graph.v2 target state before side effects.

This step is validation only. Do not edit source files in the launcher checkout,
any existing worktree, or any newly created path. Do not create, modify, or commit source code. Do not run implementation or test-fix loops.

Requirements:
- identify the current claimed step bead from `CLAIMED_BEAD_ID` in the startup
  claim output, or `$GC_BEAD_ID` if the claim output did not expose one;
  hard-fail if neither value is present
- read the claimed step JSON with `gc bd show "$CLAIMED_BEAD_ID" --json`, then
  read the current workflow root id from `metadata["gc.root_bead_id"]`
- read the current workflow root JSON with `gc bd show "$ROOT_ID" --json`
- resolve the implementation input convoy from the current workflow root
  metadata key `gc.input_convoy_id`
- verify the resolved input convoy id matches rendered runtime convoy
  `{{convoy_id}}`
- validate that input bead is a convoy or normalized singleton convoy with
  `gc bd show "<gc.input_convoy_id>" --json` before treating it as implementation
  work
- do not search repo, plan, report, artifact, session-log, or runtime files for
  convoy ids; stale files are not graph context
- hard-fail if metadata is missing, malformed, or ambiguous
- fail if the target is not a convoy or normalized singleton convoy
- reject legacy `issue`, `bead_id`, or user-supplied `convoy_id` inputs
- validate context_path {{context_path}} with `{{pack_root}}/assets/scripts/validate_context_bundle.py` when set
- reject drain_policy {{drain_policy}} values other than `separate` or `same-session`
- inspect the convoy target branch, defaulting to the repo default branch
- write a run-status artifact if summary_path {{summary_path}} or artifact root is provided
- record push {{push}} and open_pr {{open_pr}}

Close pass only after no workflow roots, drain controls, routed beads,
worktrees, refs, or publish records have been created before validation.

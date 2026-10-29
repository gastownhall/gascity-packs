
Recover context from bead metadata, not from a side-channel context file:

1. Read this step bead and the workflow root bead through `gc bd show --json`.
2. Read `gc.github.implementation_plan_path` and `gc.github.requirements_path` from the
   workflow root or completed implementation-plan/requirements steps.
3. Validate that `implementation-plan.md` exists. The plan may be `draft` or
   `approved` on entry; this review step owns final approval for downstream
   bead creation.
4. Derive the issue-fix run directory as `dirname(requirements_path)`.
5. Set `REVIEW_DIR=<run-dir>/design-review` and create it. Do not copy or
   delete any `.gc/scripts` tree in the rig: the review loop's
   `design-review-approved.sh` gate resolves from this pack's own assets.

Write `<REVIEW_DIR>/initial-implementation-plan.md` and update workflow root metadata:
- `gc.github.design_review_dir=<absolute REVIEW_DIR>`
- `gc.github.design_review_mode={mode}`
- `gc.github.design_review_status=running`

Close with `gc.outcome=pass`. Do not edit source files.

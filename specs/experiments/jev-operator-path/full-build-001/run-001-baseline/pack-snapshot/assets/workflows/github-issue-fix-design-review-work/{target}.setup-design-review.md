
Recover context from bead metadata, not from a side-channel context file:

1. Read this step bead and the workflow root bead through `gc bd show --json`.
2. Read `gc.github.implementation_plan_path` and `gc.github.requirements_path` from the
   workflow root or completed implementation-plan/requirements steps.
3. Validate that `implementation-plan.md` exists. The plan may be `draft` or
   `approved` on entry; this review step owns final approval for downstream
   bead creation.
4. Derive the issue-fix run directory as `dirname(requirements_path)`.
5. Set `REVIEW_DIR=<run-dir>/design-review`, create it, and copy this pack's
   scripts into the rig-local script cache:
   `rm -rf .gc/scripts && mkdir -p .gc && cp -R {{pack_root}}/assets/scripts .gc/scripts`.
6. Verify `.gc/scripts/checks/design-review-approved.sh` is executable.

Write `<REVIEW_DIR>/initial-implementation-plan.md` and update workflow root metadata:
- `gc.github.design_review_dir=<absolute REVIEW_DIR>`
- `gc.github.design_review_mode={mode}`
- `gc.github.design_review_status=running`

Close with `gc.outcome=pass`. Do not edit source files.

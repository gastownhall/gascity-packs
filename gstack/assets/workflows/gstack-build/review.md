Prepare for gstack code review.

Current review_mode is {{review_mode}}. Interactive review may apply fixes
through the graph fix lane. Report mode must produce findings and evidence
without changing code.

The review fanout maps upstream gstack review, qa evidence, cso security, and
gap analysis into Gas City lanes. Ensure implementation summaries, changed
files, test proof, and remaining risks are available in the review context.

Close this stage with `gc.outcome=pass` after context is ready.

Do not invoke provider-native subagents. The Gas City review fanout is the
delegation mechanism.

Artifact validation: this stage is gated by `../assets/scripts/checks/build-artifact-valid.sh`, which validates the artifact recorded at `gc.build.review_report_path` against schema `gc.build.review.v1`. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.

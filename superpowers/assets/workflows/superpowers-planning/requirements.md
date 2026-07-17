Run Superpowers brainstorming for `{{context_path}}` and write approved
requirements to `{{requirements_path}}` when supplied. The approval mode is
controlled by the formula variable, while adapter lifecycle state stays outside
this methodology step.

Only when the workflow root formula is exactly `superpowers-planning` may this
internal lane use context-only source mode: when no launch convoy exists,
`gc.var.context_path` must resolve to an existing regular file and remains the
authoritative planning scope. This
exception never applies to `superpowers-build` or any other real build root;
those roots must resolve and trace every direct member of their reserved launch
convoy.

Artifact validation: the expansion terminal is gated by `.gc/scripts/checks/build-requirements-source-valid.sh`, which validates the artifact recorded at `gc.build.requirements_path` (fallback `gc.var.requirements_path`) against schema `gc.build.requirements.v1` and verifies the internal planning context. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.

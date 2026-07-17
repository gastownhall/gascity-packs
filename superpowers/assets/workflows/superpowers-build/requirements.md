Run the Superpowers brainstorming graph for this build.

The graph preserves the stock design approval loop and the later written-spec
review/approval loop while producing the build-base requirements artifact
consumed by the planning lane.

The expansion must resolve the workflow root's reserved `gc.var.convoy_id`,
read every direct launch-convoy source, and preserve each exact source identity
in the requirements trace. Missing or unreadable launch context must fail
closed; methodology guidance is never permission to invent product scope.

Do not invoke provider-native subagents or upstream plugin runtime commands.

Artifact validation: the expansion terminal is gated by `.gc/scripts/checks/build-requirements-source-valid.sh`, which validates the canonical artifact and requires an exact trace for every direct launch-convoy source. On repair attempts (`gc.attempt` greater than 1), read the validator errors from `gc.attempt_log` on the validation loop control bead (the dependent of this step bead) and repair the artifact in place instead of rewriting it. Two bounded repair attempts follow the first failure; exhausting them closes this stage with `gc.outcome=fail` and machine-readable validation errors that block downstream stages. Never ask questions in headless mode; record unresolved ambiguity inside the artifact.

Enforce the build's plan-review approval precondition before decomposition.
This is the canonical outcome-aware decompose gate (platform bug dip-duj3e6):
do not invoke the task decomposer until the workflow root records an approved
plan review. On refusal this gate deliberately stays OPEN and BLOCKED — because
the decompose controller (and its iteration) depend on this still-open gate, the
task-decomposer never runs and cannot create an orphan convoy or work beads.

The claimed bead id is `$GC_BEAD_ID`. Run
`.gc/scripts/checks/plan-review-approved.sh` with that environment unchanged and
capture its exit code and single-line diagnostic output. Record the current UTC
timestamp. Never rewrite or bypass the guard.

If the script exits 0, update only the claimed gate bead with
`gc.outcome=pass`, `gc.build.plan_review_gate_decision=approved`, and
`gc.build.plan_review_gate_checked_at=<UTC timestamp>`. Close the gate bead with
reason `plan review approved; decomposition released`, read it back, and verify
it is closed with `gc.outcome=pass`. The decompose controller and iteration may
become ready only after this close. Do not create a report artifact on the
approved path. Your exact final action must be `gc runtime drain-ack`; emit no
text after it.

If the script exits non-zero, extract `plan_review_status=<value>` from the guard
diagnostic, using `MISSING` when it cannot be read. Build this refusal reason:

`decompose refused: plan_review_status=<value>, plan NOT approved — build halts at plan-review`

Update only the claimed gate bead with all of the following in one operation:

- status `blocked`
- `gc.outcome=blocked`
- `gc.failure_class=plan-review-not-approved`
- `gc.build.plan_review_gate_decision=refused`
- `gc.build.plan_review_gate_checked_at=<UTC timestamp>`
- `gc.build.plan_review_gate_diagnostic=<single-line guard diagnostic>`
- append the exact refusal reason to the bead notes

Read the claimed gate bead back and verify it is `status=blocked`, is not
closed, and records the refusal decision. If that read-back fails, leave the
gate unclosed and page the mayor with the verification failure.

Page the mayor with subject `BLOCKED: decompose plan-review gate refused` and a
body containing the gate bead id, workflow-root id, refusal reason, and guard
diagnostic. The message is required evidence that the fail-closed path fired.

On the refused path, do NOT close the gate bead, do NOT return a failing exit,
and do NOT update or close any decompose controller or iteration bead. The open,
blocked gate is the barrier: both decompose beads depend on it and therefore
remain blocked. Do not create or route a replacement decomposition bead,
implementation convoy, or work bead. Your exact final action must be
`gc runtime drain-ack`; emit no text after it.

Use `gc bd update <id> --set-metadata key=value` for metadata and `--status
blocked` for the refusal state. Close with `gc bd close <id> --reason <reason>`
only on the approved path. Do not invoke provider-native subagents.

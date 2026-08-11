Run the build-basic starter factory review loop.

The child beads are three review lanes plus synthesis and fix application:
acceptance/correctness, test evidence, and simplicity/maintainability. These are
starter factory lanes: broad enough to demonstrate Gas City fanout/fanin, but
small enough for first-time factory users to understand.

The apply-review-findings lane owns `code_review.verdict=done|iterate` and
`code_review.report_path=<starter review summary path>`. The implementation
review check repeats this loop until the latest verdict is `done`.

Honor interaction_mode {{interaction_mode}} at the loop approval — but note
this loop step is orchestrator-owned control (a check with children): no
worker executes THIS description. The human gate is the dedicated
`{target}.human-review-gate` child, sequenced after apply-review-findings,
so every iteration ends with it; its mechanics live in that bead's own
description (canonical form in `../build-base/interactive-human-gate.md`).

The implementation review check closes the loop only when the latest
verdict is `done` AND, in `interactive` mode, the workflow root records
`gc.build.review_gate=approved` — an empty or `waiting-human` gate, a
`revision_requested`, or a `rejected` all fail the check (fail-closed), so
a machine verdict can never conclude an interactive loop on its own. On
`revision_requested` the gate child records the human findings at
`gc.build.human_findings_path` (consumed by the next attempt's synthesis
and apply lanes) and the check schedules another iteration.

Do not invoke provider-native subagents. Continue only through this Gas City
graph loop.

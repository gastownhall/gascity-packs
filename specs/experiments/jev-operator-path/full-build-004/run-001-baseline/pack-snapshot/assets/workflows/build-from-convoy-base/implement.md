This is the `build-from-convoy-base` separate-session implementation drain.

Implement the work in the implementation convoy recorded as `gc.input_convoy_id`.
Use drain policy `separate`, route each item to {{implementation_target}}, and
preserve per-item traceability back to `{{requirements_path}}`,
`{{plan_path}}`, and `{{decomposition_path}}`.

Do not modify requirements, plan, plan-review, or decomposition artifacts from
this step. Keep implementation work isolated from the launcher checkout, run
focused tests as work progresses, and record item evidence so the inherited
review suffix can map changes back to the approved artifacts.

Close this step only after every drained implementation item has either passed
with evidence or has an explicit failure artifact.

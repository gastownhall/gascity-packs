This is the `planning-base` methodology contract preparation step.

Concrete methodology packs override this step to gather their native planning
context. Preserve the adapter-provided artifact paths and validate that
`{{artifact_root}}`, `{{context_path}}`, `{{requirements_path}}`, and
`{{plan_path}}` are plain paths before later planning steps write artifacts.

Validate `{{interaction_mode}}` is `interactive`, `autonomous`, or `headless`
and `{{review_mode}}` is `report`, `agent`, or `interactive` before planning
starts. In `headless` interaction mode, never ask questions; stop blocked with
a machine-readable `gc.blocked_reason` when required input is missing.

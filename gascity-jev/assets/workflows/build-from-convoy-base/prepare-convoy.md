This is the `build-from-convoy-base` convoy handoff step.

Validate the implementation convoy before implementation drains run. Accept the
convoy from `{{implementation_convoy_id}}` when supplied; otherwise read the
convoy ID recorded on the workflow root as `gc.input_convoy_id`.

The convoy must contain only runnable implementation work items for this build
continuation. Reject planning, review, workflow-control, or original request
convoys. Record the resolved convoy as both:

- `gc.input_convoy_id=<implementation-convoy-id>`
- `gc.build.implementation_convoy_id=<implementation-convoy-id>`

Close only after the convoy identity, drain policy {{drain_policy}}, selected
implementation target {{implementation_target}}, and source artifact paths are
validated and recorded.

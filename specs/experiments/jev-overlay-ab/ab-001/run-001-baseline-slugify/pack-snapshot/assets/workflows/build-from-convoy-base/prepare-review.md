This is the `build-from-convoy-base` handoff into the inherited review suffix.

Read the drain result for the implementation convoy and record the
implementation evidence path as `gc.implementation.summary_path` or
`gc.build.implementation_summary_path` on the workflow root. Then validate the
inputs required by `build-from-review-base`.

Do not review or fix code in this step. Close only after the review suffix can
consume the implementation evidence without inspecting drain internals.

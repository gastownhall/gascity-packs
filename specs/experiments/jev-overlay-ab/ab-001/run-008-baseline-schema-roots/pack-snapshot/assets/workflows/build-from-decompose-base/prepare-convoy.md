This is the `build-from-decompose-base` handoff into the inherited convoy suffix.

Validate that decomposition created or adopted an implementation convoy and
recorded it as `gc.input_convoy_id` and `gc.build.implementation_convoy_id`.

Do not implement work from this handoff step. Close only after the inherited
`build-from-convoy-base` suffix can drain the implementation convoy without
rerunning decomposition.

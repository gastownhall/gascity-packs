This is the `build-from-requirements-base` requirements handoff step.

Validate artifact_root {{artifact_root}}, context_path {{context_path}},
requirements_path {{requirements_path}}, interaction_mode {{interaction_mode}},
and the selected planning formula {{planning_formula}} before requirements work
starts.

Record `gc.build.continuation_entrypoint=requirements` when this suffix is
launched directly. Close only after the requirements stage can write or reuse
the selected requirements artifact.

Record one immutable source-to-formula translation at `{{artifact_path}}`.

Use `pstack.source-binding.v1` front matter with `id`, `source.path`,
`source.section`, `source.commit`, `target.formula`, `target.node`,
`realization_type`, `status`, and `rationale`. The realization type MUST be one
of `implemented`, `delegated`, `source-only`, or `unsupported`. Preserve the
source revision exactly; never imply runtime behavior for source-only or
unsupported material.

This runtime asset is executed by the Gas City graph.

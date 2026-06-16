This is the `code-review-base` methodology contract context validation step.

Concrete methodology packs override this step when their review needs extra
inputs. Validate the rendered configuration below before any reviewer writes a
report:

- subject_path: `{{subject_path}}`
- report_path: `{{report_path}}`
- context_path: `{{context_path}}`
- interaction_mode: `{{interaction_mode}}`
- review_mode: `{{review_mode}}`

`subject_path` must exist. `report_path` is the output path reviewers will
write, so it must be non-empty and its parent directory must be usable.
Do not require the `report_path` file to exist before review. `context_path` is
optional when it is empty. `interaction_mode` must be `interactive`,
`autonomous`, or `headless`. `review_mode` must be `report`, `agent`, or
`interactive`. Stop blocked with a machine-readable `gc.blocked_reason` on
unknown values.

The rendered values in this prompt are authoritative. Do not require
`interaction_mode` or `review_mode` to also appear in bead metadata or in a
`review-config.yaml` file. Only block when the literal rendered value is empty
or outside the allowed set.

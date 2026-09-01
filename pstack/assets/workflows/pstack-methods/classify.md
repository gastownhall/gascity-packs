This runtime asset is executed by the Gas City graph.
Read `pstack/mappings/playbooks.toml`. Tables are `[playbooks.<stem>]` plus `[unsupported].stems`.

If the stem has a `[playbooks.<stem>]` table, write `status: routed`, that stem, its `formula`, its `class`, `reason`, and `evidence`.
If the stem is in `[unsupported].stems`, write `status: unsupported`, formula `none`, class `unsupported`, `reason`, and `evidence`.
Do not sling the selected formula. Do not set `gc.graph_operator`.

The operator slings the `formula` field only when `status` is `routed`.

This runtime asset is executed by the Gas City graph.
Read `pstack/mappings/playbooks.toml`. Classify the request onto one Cursor playbook stem.

If the stem is in `[playbooks]`, write `status: routed`, that stem, its `formula`, and its `class`.
If the stem is in `[unsupported].stems`, write `status: unsupported`, formula `none`, class `unsupported`.
Do not sling the selected formula. Do not set `gc.graph_operator`.

The operator slings the `formula` field next.

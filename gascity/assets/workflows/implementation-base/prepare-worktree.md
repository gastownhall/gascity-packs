This is the `implementation-base` methodology contract worktree preparation
step.

Concrete methodology packs override this step only when their implementation
items need different setup. Preserve optional context `{{context_path}}` and do
not edit source files here.

Core separately drained implementations prepare their graph-owned workspace with:

```sh
gc gc workspace prepare --step-id "<claimed-step-id>" --input-ref "<input-revision>"
```

Use the returned `worktree_path` and `input_oid` as authoritative. The command
automatically reuses the convoy- or epic-owned worktree when this item follows a
completed item in the same owner. Confirm the workspace exists and its input
revision matches the intended source revision. Never reconstruct the workspace
or attempt destructive repair. Close preparation with pass only after the
command succeeds.

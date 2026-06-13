# LazyJJ Implementation Planning

This pack is copied from `gascity` and adapted for LazyJJ implementation work.
It provides the same manual planning skills and a LazyJJ implementation
coordinator:

- `gc.plan` gathers requirements and writes `requirements.md`.
- `gc.design` turns approved requirements into an engineering design.
- `lazyjj-implementation.decompose` turns an approved design into an approved LazyJJ
  bead plan, then creates beads.
- `implement-lazyjj` attaches the LazyJJ jedi workflow to each created bead,
  routes the resulting DAG to LazyJJ workers, waits for completion, and runs
  gap-analysis and review Ralph loops.

Import it with the `lazyjj-implementation` binding:

```toml
[imports.lazyjj-implementation]
source = "../gascity-packs/lazyjj-implementation"
```

Run the skills manually in order:

```text
Use skill lazyjj-implementation.plan
Use skill lazyjj-implementation.design
Use skill lazyjj-implementation.decompose
```

Then launch LazyJJ implementation from the target rig:

```sh
gc sling <coordinator-target> implement-lazyjj --formula \
  --var plan_slug=<plan-slug> \
  --var pack_root=/absolute/path/to/lazyjj-implementation \
  --var worker_target=<lazyjj-jedi-target>
```

`worker_target` should point at the LazyJJ jedi pool or named session. Each
implementation bead is expanded with `mol-polecat-lazyjj-work`, so workers
operate inside assigned jj workspaces and hand off review bookmarks plus stack
metadata.

By default artifacts go under the target rig:

```text
<rig-root>/.gc/plans/<plan-slug>/
  requirements.md
  design.md
  tasks.md
```

Each skill may use a different artifact root when the user explicitly asks for
one. The same `<plan-slug>/` structure should be used under the override root.

`lazyjj-implementation.decompose` uses `scripts/create_beads_from_tasks.py` after
approval. The script requires Python 3 with PyYAML available, and invokes
`gc bd --rig <target_rig>` so beads are created in the intended rig store with
LazyJJ formula metadata.

The `implement-lazyjj` formula uses `scripts/checks/*.sh` as Ralph convergence
checks. Pass `pack_root` explicitly so those scripts resolve from the imported
pack location instead of from any local checkout.

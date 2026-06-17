# gc packer pack-check

Run a compact pack validation pass.

```bash
gc packer pack-check <pack> [agent|--focused] [formula]
```

The command runs:

- `gc lint <pack>`
- `gc prime <agent> --strict` when `agent` is provided
- `gc formula show <formula>` when `formula` is provided

For `gastown-lazyjj`, the command also runs focused assertions for the LazyJJ
bead workflow:

- tasksmith routes normal implementation beads to `mol-polecat-lazyjj-work`
  and reserves tutorial formulas for tutorial beads
- workspace seed inputs are documented through `LAZYJJ_WORK_TITLE` and
  `--description-file`
- `mol-polecat-lazyjj-work` records `lazyjj_workspace` and
  `lazyjj_workspace_dir` metadata and seeds the current change from bead text
- the jjw workspace setup helper accepts the bead/title/description arguments

Focused LazyJJ smoke:

```bash
bash packer/commands/pack-check/run.sh gastown-lazyjj --focused
```

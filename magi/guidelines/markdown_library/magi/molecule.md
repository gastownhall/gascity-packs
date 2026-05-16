---
bootstrap_chain:
  - "doctor"
  - "install"
  - "bootstrap-project"
  - "status"
  - "analyze"
on_failure: "partial"
worst_child_rc: true
formula_path: "formulas/mol-magi-bootstrap.formula.toml"
---

# Molecule — Bootstrap Chain Rules

`magi_molecule.py` loads this file at startup.

## The bootstrap chain

`gc magi molecule bootstrap` instantiates a parent bead with five children in the order declared by `bootstrap_chain`:

1. `doctor` — every precondition check
2. `install` — `--target <name>` from `--var target`
3. `bootstrap-project` — `setup_utilities.sh -y` against `--var project_path`
4. `status` — read state.json plus open beads; reconcile orphans
5. `analyze` — bottom-up walk of `--var project_path`

Children are wired via `bd_dep`. `bd ready --label pack:magi` walks the chain.

## On-failure semantics

The per-step `on_fail` field selects between two behaviors:

- `on_fail = "stop"` — chain halts; parent bead closes with the failed step's rc.
- `on_fail = "continue"` — remaining children stay ready; parent stays open and carries `outcome:partial`.

`doctor` and `install` use `stop`. The remaining three use `continue` so a missing `MAGI_UTILITIES_SOURCE` or an LM Studio outage does not invalidate a successful install.

## Worst-child rc

`magi_molecule.py` exits with `max(child_rcs)`. A single `rc=1` propagates as `rc=1`. A `rc=2` plus any `rc=0` propagates as `rc=2`. All-zero propagates as `rc=0`.

## Bundled formula

The bundled formula at `formulas/mol-magi-bootstrap.formula.toml` declares two vars: `target` (default `claude`) and `project_path` (required). Instantiate via `gc magi molecule pour mol-magi-bootstrap` or via `bd mol pour mol-magi-bootstrap` directly.

## Operator recovery

When a child fails, `gc magi status` lists the open parent and the remaining ready children. Re-run the failed child by hand (e.g. `gc magi analyze /abs/path`); on success, close the molecule with `bd close <parent-id>`.

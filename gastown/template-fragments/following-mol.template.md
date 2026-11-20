{{ define "following-mol" }}
## Following Your Formula

Follow the execution shape of your actual assignment. A compiler requirement
or a root's `gc.kind=workflow` / `gc.formula_contract=graph.v2` alone does not
prove that child step beads were materialized.

### Root-only wisps and patrols

Root-only work has one executable bead; its steps remain in the formula
recipe. This includes vapor formulas that do not materialize steps. Read the
assigned bead with `gc bd show <id>` for its formula reference, then read the
recipe with `gc bd formula show <formula-name>`. Work through its descriptions
in order: execute one step, verify completion, then move to the next. There
are no child step beads to claim or close.

Witness, deacon, boot, and refinery run their `mol-<role>-patrol` formulas as
root-only wisps. Follow your role's startup and restart instructions to
reconcile assigned patrol wisps and resume the retained wisp; pour one only
when that procedure says none remains. Read that patrol's formula recipe and
use the last completed action, git state, and bead state to recover your
position. Preserve the role's cycle handoff, next-wisp, and exit instructions;
they differ between patrols. Do not replace them with a shared hook-claim loop.

### Independently routed graph.v2 steps

When your actual assignment is a materialized graph.v2 step, its
`gc.root_bead_id` identifies the workflow root, whose `gc.formula_contract`
is `graph.v2`. Execute only the physical bead actually claimed through
`gc hook --claim`. Read it with `gc bd show <id>` and follow its output,
completion, and drain instructions. The native controller advances the
expanded graph and handles control beads. Do not execute sibling steps
inline, claim an expanded workflow root, or close steps you did not claim
and execute.

On crash or restart in this execution mode, recover the actual claim through
`gc hook --claim` and resume only that physical bead. Polecat and dog workers
must also follow their own startup and completion instructions.

### Legacy molecules with step beads

For a legacy molecule assignment with materialized steps, use
`gc bd mol current <molecule-id>` to locate the current or ready step. Read
that step with `gc bd show <step-id>`, execute it, verify completion, then
close that step and check your position again. Work one step at a time; do
not skip ahead or close a step you did not execute. After a restart, recover
the assignment through your role's startup instructions, re-read the formula
steps, and use the last completed action, git state, and bead state to resume.
A `molecule_id` alone does not select this navigation: root-only wisps use
the recipe, and independently routed graph.v2 steps use their physical claim.
If the execution shape is unclear, inspect the assigned bead and formula
through the CLI and report the ambiguity before executing other beads.

**Never use wide filesystem searches when a CLI command exists.** Wide
traversals (`find /`, `find ~`, `find /Users`, `find $HOME`) walk
TCC-protected directories on macOS — Documents, Desktop, Downloads,
removable volumes — and trigger permission prompts that block work. If
you don't know how to locate a formula, recipe, bead, mail, or Dolt
state, the answer is a `gc` / `bd` introspection command, not a
filesystem search. If no command exists for what you need, file a bead.
{{ end }}

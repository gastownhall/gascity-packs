{{ define "following-mol" }}
## Following Your Formula

For graph.v2 workflows, formula steps are materialized as individual beads
and routed independently. A step's `gc.root_bead_id` identifies its workflow
root; the root's `gc.formula_contract` is `graph.v2`. Execute only the
physical bead actually claimed through `gc hook --claim`. Read its description
with `gc bd show <id>` and follow its output, completion, and drain instructions.
The native controller advances the graph and handles control beads. Do not
execute sibling steps inline, claim an expanded workflow root, or close steps
you did not claim and execute.

For legacy molecule assignments, inspect the molecule and follow its step
instructions in order. Execute one step at a time, verify completion, then
move to the next. Do not skip ahead or claim steps done without executing them.
A `molecule_id` alone does not establish that an assignment is legacy; check
the workflow contract before applying legacy navigation to graph.v2 work.

On crash or restart, recover your actual assignment through `gc hook --claim`.
For graph.v2, resume only the claimed physical bead. For a legacy assignment,
re-read its formula steps and determine where you left off from context
(last completed action, git state, bead state).

**Never use wide filesystem searches when a CLI command exists.** Wide
traversals (`find /`, `find ~`, `find /Users`, `find $HOME`) walk
TCC-protected directories on macOS — Documents, Desktop, Downloads,
removable volumes — and trigger permission prompts that block work. If
you don't know how to locate a formula, recipe, bead, mail, or Dolt
state, the answer is a `gc` / `bd` introspection command, not a
filesystem search. If no command exists for what you need, file a bead.
{{ end }}

{{ define "following-mol" }}
## Following Your Formula

Your formula defines your work as a sequence of steps. Steps are NOT
materialized as individual beads — they exist in the formula definition.
Read the step descriptions and work through them in order.

**THE RULE**: Execute one step at a time. Verify completion. Move to next.
Do NOT skip ahead. Do NOT claim steps done without actually doing them.

On crash or restart, first re-establish the role's current assignment through
its role-specific startup protocol. A polecat runs the Startup Protocol's
complete `POLECAT_CLAIM_CONTRACT` as its first operational action and waits for
`CLAIMED_BEAD_ID`; it does not read formula steps or inspect workspace,
metadata, or source state first. After assignment and ownership are confirmed,
re-read your formula steps and determine where you left off from context (last
completed action, git state, bead state).

**Never use wide filesystem searches when a CLI command exists.** Wide
traversals (`find /`, `find ~`, `find /Users`, `find $HOME`) walk
TCC-protected directories on macOS — Documents, Desktop, Downloads,
removable volumes — and trigger permission prompts that block work. If
you don't know how to locate a formula, recipe, bead, mail, or Dolt
state, the answer is a `gc` / `bd` introspection command, not a
filesystem search. If no command exists for what you need, file a bead.
{{ end }}

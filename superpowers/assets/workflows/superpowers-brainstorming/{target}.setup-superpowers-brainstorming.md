Prepare the Superpowers brainstorming context.

Resolve the build target, artifact root, design candidate path, requirements
artifact path, optional context bundle, and brainstorming approval mode. Use
workflow root metadata `gc.var.brainstorming_approval_mode` when present;
otherwise default to `autonomous`.

Create the brainstorming artifact directory under the build artifact root and
ensure the rig-local script cache contains the imported `gc` pack checks. If
`../assets/scripts/checks/design-review-approved.sh` is missing, locate the imported
`gc` formula search path with `gc formula show superpowers-build --json`, use
its sibling `../assets/scripts` directory as the source, and refresh
`.gc/scripts` from that directory.

Write a compact context note for the design-approval loop and written-spec
loop. Confirm that `../assets/scripts/checks/design-review-approved.sh` is
executable.

Do not invoke provider-native subagents or upstream plugin runtime commands.
This Gas City graph stage is the delegation mechanism.

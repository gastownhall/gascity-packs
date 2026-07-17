Refresh the build-basic review context before this Ralph iteration fans out.

Resolve the workflow root, its closed implementation convoy, canonical
`gc.build.implementation_summary_path`, absolute `gc.build.artifact_root`, and
`<artifact-root>/review-context.md`. This is a provenance refresh, not a fix
lane: never edit product bytes, commit, or change an implementation member's
recorded commit. Read root `gc.var.drain_policy`. For `separate`, require every
member commit to equal its authoritative worktree `HEAD`. For `same-session`,
require one shared worktree, each recorded commit to be an ancestor of terminal
`HEAD`, and at least one member to equal terminal `HEAD`; preserve earlier
ancestor-member commits. Let the deterministic helper enforce these rules; fail
this bead on any mismatch.

Rewrite the review context from current requirements, plan, decomposition,
canonical implementation summary, task evidence, changed files, proof commands,
and exact implementation member ids/commits. Record its canonical path as
`gc.build.code_review_context_path`. Never serialize or hash provenance by hand.

From the launcher Git root, run the installed deterministic helper after the
draft context and root paths exist:

```bash
python3 "<launcher-root>/.gc/scripts/verify_implementation_provenance.py" --emit-current --root-id "<workflow-root-id>" --expected-summary "<canonical-summary>" --validator "<launcher-root>/.gc/scripts/validate_build_artifact.py"
```

Use its exact `members` and `implementation_snapshot` values in the final
context. Run the same `--emit-current` command again after the final context
bytes are written. Publish only the second result:

```bash
gc bd update "<workflow-root-id>" --set-metadata 'gc.build.implementation_snapshot=<helper implementation_snapshot>' --set-metadata 'gc.build.review_input_snapshot=<helper review_input_snapshot>' --set-metadata 'gc.build.code_review_context_path=<artifact-root>/review-context.md'
```

Read the root back, then run the helper once without `--emit-current` and with
`--expected-snapshot <helper implementation_snapshot>`. Close this refresh bead
with `gc.outcome=pass` only when that strict verification succeeds. This child
runs on every attempt so reviewers never consume a pre-fix context.

Do not invoke provider-native subagents.

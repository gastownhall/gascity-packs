
Prepare the graph-owned workspace for this item. Items in the same convoy or
epic owner reuse one serialized worktree. This is infrastructure setup only;
do not edit source files during this step.

1. Validate the supplied context path {{context_path}}, file ownership, and
   verification policy for the source anchor represented by this workflow.
2. Prepare the workspace with:
   ```sh
   gc gc workspace prepare --step-id "<claimed-step-id>" --input-ref "<input-revision>"
   ```
   Use its returned `worktree_path` and `input_oid` as authoritative. Confirm
   the workspace exists and its input revision matches the intended source
   revision.
3. Close this step with `gc.outcome=pass` only after the command succeeds. A
   failure is hard; do not reset, checkout, prune, delete, adopt, or otherwise
   repair workspace state.

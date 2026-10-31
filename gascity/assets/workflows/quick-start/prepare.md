Read the claimed step and its `gc.root_bead_id`; use that workflow root for
all source-delivery commands. Read `gc convoy status {{convoy_id}} --json` and
require exactly one `.children` source task. Never use the wrapper convoy as
the source task. Read that task and its acceptance criteria.

Run `gc gc source-delivery prepare --root <root-id>
--source <source-task-id> --repo "$GC_RIG_ROOT" --workspace-root
"$GC_CITY_PATH/.gc/worktrees/<rig-name>" --verify-command <the literal
{{verify_command}} value as one shell argument>`. Use the configured rig name,
not a user-controlled task title, for the final workspace-root component.
Do not edit source. The helper pins input before provisioning and delegates
ownership and retry verification to native `gc worktree ensure`. It also links
the resolved source to native workflow finalization, so the source closes after
cleanup and all required stages pass. Keep source work open during execution.

Close only this step with gc.outcome=pass after the command succeeds. On a
failure retain the source task and worktree and report the exact error. Do not
close source work from setup, implementation or review. Drain the worker after
closing the claimed step using the normal claim protocol.

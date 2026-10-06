
Resolve `<source-anchor-id>` from the workflow ROOT, which is the SINGLE SOURCE
OF TRUTH for every step of this lane: read the claimed step bead's
`gc.root_bead_id`, then read that root's `gc.source_anchor_id` metadata.
`prepare-worktree` resolved the anchor deterministically and stamped it there,
so DO NOT re-derive it — close EXACTLY that id, and use exactly that value as
`<source-anchor-id>` everywhere below (worktree resolution AND every
`gc bd show` / `gc bd update --set-metadata` that names the source anchor).

FALLBACK — only if the root has NO `gc.source_anchor_id` (a workflow started
before `prepare-worktree` stamped it, or a hand-run step where
`prepare-worktree` never ran): derive it exactly as `prepare-worktree` does —
read the root's `gc.input_convoy_id` (if it is missing too, fail this step
without closing any bead) and that convoy with `gc bd show <input-convoy-id>
--json`. If the convoy has `gc.synthetic_kind=drain-unit-convoy`
use its `gc.drain_member_id`; else if it has `gc.synthetic=true` use its single
tracked member from `gc convoy status <input-convoy-id> --json` (hard-fail
unless `.children` has exactly one entry); otherwise use the input convoy id
itself. For such an unstamped single-item run, a pre-stamp `prepare-worktree`
persisted `work_dir` on the `gc.synthetic=true` input convoy, so when the
member has no `work_dir`, read `work_dir` from that convoy — but still close the
member, never the convoy. Never infer the anchor from dependency ids such as
the `prepare-worktree` or implementation step bead.

Before closing anything, sanity-check the resolved id (stamped or derived) and
fail this step without closing any bead if it does not hold: the source anchor
must not have `gc.synthetic=true`, and when the root has `gc.drain_member_id`
the source anchor must equal it.

Read `work_dir` from the source anchor and verify the implementation commit and
summary evidence are present in that worktree. Write per-item summary to
{{summary_path}} when set. If `summary_path` is not set, first use
`gc.implementation.summary_path` from the preceding implementation step when it
is present; otherwise use `{{artifact_root}}/task-<source-anchor-id>-summary.md`.

When reading beads with `gc bd show --json`, handle both an object and a
one-element list before reading metadata. `gc.work_dir` is the launcher rig
root, not the implementation worktree. If the source anchor `work_dir` (or,
in the unstamped single-item case above, the input convoy's) is missing, equals the launcher root, or points at a worktree without the
implementation commit, fail this step instead of closing the source anchor.

If the source anchor is already `status=closed` with `gc.outcome=pass` (a retry
of this step after the close landed), do not close it again; verify the
evidence and close this step.

On success, close only `<source-anchor-id>` with `gc.outcome=pass`. Include the
verified commit and summary path in the source-anchor close reason. Read the
source anchor back with `gc bd show <source-anchor-id> --json` and verify
`status=closed` and `gc.outcome=pass`; if either check fails, fix the source
anchor before closing this step. Do not close this step with pass while the source anchor remains open. Then close this step. Do not close the drain-unit
convoy, parent convoy, or broader workflow root from this step.

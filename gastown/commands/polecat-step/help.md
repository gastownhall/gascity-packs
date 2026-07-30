Execute inside the exact task artifact for, durably quarantine, or complete
one claimed nonterminal `mol-polecat-work` Graph-v2 stage.

Usage:

    gc gastown polecat-step exec \
      [--allow-workspace-transition] \
      --convoy <input-convoy-id> \
      --step-ref mol-polecat-work.<step-id> \
      -- <command> [args...]

    gc gastown polecat-step complete \
      --convoy <input-convoy-id> \
      --step-ref mol-polecat-work.<step-id>

    gc gastown polecat-step block \
      --convoy <input-convoy-id> \
      --step-ref mol-polecat-work.<step-id> \
      --code <stable-machine-code> \
      --reason <operator-readable-reason>

All actions resolve the current session identity and an exact step. Fresh
actions require exactly one matching in-progress step; completion and block
replays require their exact terminal or quarantined contracts. Every path
verifies the assignee, step reference, workflow root, Graph-v2 contract, exact
runtime rig, and input convoy. Workflow and source bead reads are pinned to the
runtime rig. Convoy reads bypass the controller cache and require the
direct-store JSON result to identify the requested convoy exactly.

`exec` is read-only with respect to workflow state. It additionally derives the
input convoy's sole open and unassigned source, reads its canonical
`metadata.artifact_dir`, validates the city/rig/bead layout, and proves that
the path is the exact registered linked worktree in the rig repository. It
removes inherited repository-selection Git variables, changes to that exact
worktree before its final authoritative state reads, repeats its physical,
Git-registration, and branch proofs, then replaces itself with the supplied
argv. It does not use `eval`; argv and stdin reach the executed command
directly, and the command's exit status is preserved. The supported stages
are `workspace-setup`, `preflight-tests`, `implement`, and `self-review`.
By default every supported stage requires both source metadata and worktree
HEAD to carry the exact `polecat/<source-id>` branch.

`--allow-workspace-transition` is accepted only by `workspace-setup exec`.
It permits source branch metadata to be absent and worktree HEAD to be
detached during deterministic branch/rebase setup; either may instead already
be the exact canonical task branch. A different named branch is always
rejected. Do not use this flag for ordinary workspace commands after branch
setup.

`complete` records and reads back `gc.outcome=pass` with `status=closed`.

`block` is the fail-closed path for a deterministic hard failure. It requires
a stable machine code and bounded, control-free reason; records an exact v1
incident signature on the convoy's sole open/unassigned source and current
step, preserves the source's previous route, and routes the incident source to
`human`; reads both rows back; revalidates root and convoy authority; then
changes the source and step to `blocked` in that order. The source route/status
transition removes generic pool demand while the still-in-progress step keeps
the current session recoverable. Once the step is blocked, neither row is wake
demand. Its assignee is retained for provenance and the workflow root stays in
progress for inspection. Only after a final exact snapshot does the command
acknowledge drain. A retry converges from each partial write state; once both
rows are blocked, it performs a read-only verification and retries only drain
acknowledgement. Conflicting incident signatures are never overwritten.

Supported step references are `load-context`, `workspace-setup`,
`preflight-tests`, `implement`, and `self-review`. The terminal
`submit-and-exit` stage is deliberately rejected because its stronger
publication/handoff-specific completion path must prove source state before
closing the workflow step.

It never calls the claim hook. A completion retry after a lost response
succeeds only when exactly one closed/pass step for the same actor, step
reference, and input convoy can be revalidated. A block retry requires one
exact blocked source/step signature for the same active root and convoy.
Ambiguous, malformed, or mismatched state fails closed without intentionally
advancing another step.

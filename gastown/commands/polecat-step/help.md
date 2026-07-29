Complete one exact claimed nonterminal `mol-polecat-work` Graph-v2 stage.

Usage:

    gc gastown polecat-step complete \
      --convoy <input-convoy-id> \
      --step-ref mol-polecat-work.<step-id>

The command resolves the current session identity, requires exactly one
matching in-progress step, verifies its assignee, step reference, workflow
root, Graph-v2 contract, and input convoy, then records and reads back
`gc.outcome=pass` with `status=closed`.

Supported step references are `load-context`, `workspace-setup`,
`preflight-tests`, `implement`, and `self-review`. The terminal
`submit-and-exit` stage is deliberately rejected because its stronger
publication/handoff-specific completion path must prove source state before
closing the workflow step.

It never calls the claim hook. A retry after a lost response succeeds only
when exactly one closed/pass step for the same actor, step reference, and
input convoy can be revalidated. Ambiguous, malformed, or mismatched state
fails closed without intentionally advancing another step.

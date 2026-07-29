Reconcile or complete the exact `mol-polecat-work.submit-and-exit` Graph-v2
step for the current polecat runtime.

Usage:

    gc gastown polecat-submit guard

    gc gastown polecat-submit complete \
      --convoy <input-convoy-id> \
      --source <source-bead-id> \
      --branch polecat/<source-bead-id> \
      --mode auto_push_false|refinery

`guard` resolves one in-progress submit step across the deduplicated current
runtime identities, verifies its Graph-v2 root, input convoy, sole source bead,
and configured refinery identity, then emits one compact
`polecat-submit.v1` JSON object:

- `action=proceed`, without mutation, only for an open, unassigned, tokenless
  source;
- `action=terminal`, without mutation, only when canonical branch, target, and
  `gc.polecat_submit_convoy` exactly bind the source to this workflow
  generation and the source is branch-ready, assigned to the exact configured
  refinery, or closed;
- exit 75, without mutation, for a conflict, stale token, incomplete current
  token, or other mismatch.

The terminal object carries the exact convoy/source/branch/mode tuple. A caller
must validate the full JSON schema, pass that tuple to `complete`, require
completion success, then require drain acknowledgement success. Neither
`guard` nor its closed-history replay path performs a bead update.

`complete` additionally binds the caller's exact convoy, source, and canonical
`polecat/<source>` branch to that durable graph context. Both completion modes
require source `metadata.target`, canonical `metadata.branch`, and
`gc.polecat_submit_convoy` to exactly match the root's base, source, and input
convoy.
`auto_push_false` requires open/unassigned plus `branch_ready=true` and
`halt_reason=auto_push_false`. `refinery` requires the exact configured
refinery assignment or an already-closed source. The command rereads evidence
immediately before closing and reading back the submit step as pass.

The same close update persists versioned source/convoy/branch/mode/session
evidence. If the response or later drain acknowledgement is lost, a retry may
replay exactly one coherent closed/pass record for the same immutable
`GC_SESSION_ID`, even after the workflow root becomes terminal. Legacy records
without replay metadata are ignored; partial, malformed, mismatched, or
duplicate current-session candidates fail closed.

Unreadable, malformed, ambiguous, or mismatched pre-transition state exits 75.
An update error is treated as ambiguous and accepted only when the exact
closed/pass state and complete replay tuple read back. The command never calls
the claim hook or acknowledges runtime drain.

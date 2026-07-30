Reconcile or complete the exact `mol-polecat-work.submit-and-exit` Graph-v2
step for the current polecat runtime.

Usage:

    gc gastown polecat-submit guard

    gc gastown polecat-submit execute

    gc gastown polecat-submit complete \
      --convoy <input-convoy-id> \
      --source <source-bead-id> \
      --branch polecat/<source-bead-id> \
      --mode auto_push_false|refinery

`execute` is the only normal terminal path. From any inherited provider
working directory it derives the exact live Graph-v2 authority, enters and
validates the source's recorded artifact, captures and rechecks final dirty
changes, invokes the deterministic lease submit exactly once unless its exact
create-only proof already exists, verifies the proof's context/head refs, then
performs the matching source transition, exact step close/readback, and drain
acknowledgement. It never trusts prompt-local `cd` or shell variables.

`guard` resolves one in-progress submit step across the deduplicated current
runtime identities, verifies its Graph-v2 root, input convoy, sole source bead,
and configured refinery identity, then emits one compact
`polecat-submit.v1` JSON object:

- `action=proceed`, without mutation, only for an open, unassigned, tokenless
  source;
- `action=terminal`, without mutation, only when canonical branch, target, and
  `gc.polecat_submit_convoy` exactly bind the source to this workflow
  generation and the source is branch-ready, assigned to the exact configured
  refinery, or closed, and the exact retained execute/proof receipt verifies;
- exit 75, without mutation, for a conflict, stale token, incomplete current
  token, or other mismatch.

The terminal object carries the exact convoy/source/branch/mode tuple.
`complete` is a recovery interface only: it requires the exact versioned
execute receipt plus the retained create-only Git proof before it may close a
still-live step. Mutable source terminal metadata by itself is never evidence.
Neither `guard` nor its closed-history replay path performs a bead update.

`complete` additionally binds the caller's exact convoy, source, and canonical
`polecat/<source>` branch to that durable graph context. Both completion modes
require source `metadata.target`, canonical `metadata.branch`, and
`gc.polecat_submit_convoy` to exactly match the root's base, source, and input
convoy.
`auto_push_false` requires open/unassigned plus `branch_ready=true` and
`halt_reason=auto_push_false`. `refinery` requires the exact configured
refinery assignment or an already-closed source. Live `metadata.auto_push`
must still match the selected proof mode, and live `metadata.artifact_dir`
must still name the proof-bound registered worktree. The sole artifact
exception is an already-closed refinery source whose exact head has a
read-backed completed-cleanup receipt and whose recorded worktree is now
absent. The command rereads this full evidence immediately before closing,
after step close, and before drain.

The same close update persists versioned source/convoy/branch/mode/session plus
submit-proof key/context/head evidence. If the response or later drain
acknowledgement is lost, `execute` may replay exactly one coherent closed/pass
record for the same immutable `GC_SESSION_ID`, even after the workflow root
becomes terminal. Legacy v1 records are never accepted as current proof;
partial, malformed, mismatched, or duplicate current-session candidates fail
closed after canonically irrelevant history is discarded.

Unreadable, malformed, ambiguous, or mismatched pre-transition state exits 75.
An update error is treated as ambiguous and accepted only when the exact
closed/pass state and complete replay tuple read back. The command never calls
the claim hook. Only successful `execute` or its exact closed replay
acknowledges runtime drain.

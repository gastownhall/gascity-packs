# gc gastown polecat-lease

Internal deterministic helper for `mol-polecat-work`.

It synchronizes an existing polecat branch, performs rejection-aware rebases
through atomic Git ref transactions, freezes the reviewed submit commit, and
uses an exact server-side force-with-lease only when a rebase requires it.

This is not a general-purpose force-push command. It requires exact Graph-v2
step/root/source provenance and the canonical `polecat/<source-id>` branch.
Deterministic conflicts block the source for human reconciliation, durably
notify the rig witness, close the exact workflow step as `fail/hard`, and only
then drain. Transport or unreadable-state failures preserve all state and do
not drain.

Usage:

```text
gc gastown polecat-lease workspace \
  --source ID --convoy ID --base BRANCH --branch polecat/ID --witness TARGET

gc gastown polecat-lease publish-rebase \
  --source ID --convoy ID --base BRANCH --branch polecat/ID --witness TARGET

gc gastown polecat-lease submit \
  --source ID --convoy ID --base BRANCH --branch polecat/ID --witness TARGET \
  --auto-push true|false
```

`gc gastown polecat-workspace execute` is the normal recovery interface after a
model resolves and stages a detached rebase conflict. Re-running that same
command continues the rebase, records a create-only candidate proof, and
publishes the exact proved result. `publish-rebase` accepts only that
lease-owned candidate proof; an arbitrary detached descendant, including the
captured base alone, is never eligible for publication.

`auto_push=false` is supported for ordinary, non-rejected work and performs no
push. It is deliberately unsupported once rejection recovery has published a
rebased lease: `submit` stops before freezing or pushing, keeps the live Graph
step and five recovery refs intact, and requires the source policy to be changed
to allow an exact automatic push or explicit human reconciliation.

Every successful `submit`, including `auto_push=false`, creates an immutable
two-ref proof under
`refs/gascity/polecat-submit-proofs/v1/<workflow-generation-key>/`. The
`context` ref targets a canonical context blob and the `head` ref retains the
exact submitted commit. Creation is create-only and verifies the canonical
branch in the same Git transaction. Exact retries return the same
`POLECAT_SUBMIT_PROOF` receipt; conflicting or partial proof state fails closed.
Proof refs survive worker drain so submit completion and response-loss replay
can verify them independently.

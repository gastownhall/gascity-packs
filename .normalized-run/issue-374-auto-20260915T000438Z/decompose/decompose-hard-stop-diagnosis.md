# decompose hard stop — graph.v2 source bead cannot be tracked by a convoy

Bead: gcg-699284130204907631 (decompose, attempt 1)
Root: gcg-699284130204907531
Run:  issue-374-auto-20260915T000438Z
When: 2026-09-15T09:2xZ

## What failed

The sole executable decompose boundary ran `normalized_decompose_runner.py`.
Its non-idempotent input-convoy create failed:

    gc --city /data/projects/maintainer-city --rig gascity-packs convoy create \
       normalized-decompose-88f8a6176e4b224f7289321a32c93da6ec0ffe794afd448515d23858b8ef8429 \
       gcg-699284130204907631 --owned --json
    -> exit status 1

A second invocation (the sanctioned retry) then refused to proceed:

    normalized_decompose_runner: input convoy create outcome is unknown; preserved evidence blocks retry

## Why the sanctioned adoption path cannot fire

The create was interrupted in exactly the shape the contract describes as
adoptable — the convoy row committed, the member attach did not:

  id      mc-djzpf
  title   normalized-decompose-88f8a6176e4b224f7289321a32c93da6ec0ffe794afd448515d23858b8ef8429  (exact)
  status  open
  members none  (progress 0/0)
  fence   decompose/.input-convoy-create.json.tmp-87buvdsq  (0 bytes, exactly one)

But `_interrupted_input_convoy` / `reconcile_input_convoy` classify from the
runner's authoritative inventory, which is RIG-scoped:

    gc --city /data/projects/maintainer-city --rig gascity-packs bd list --all --format=json
    -> 2086 rows, 0 rows with this title, 0 rows with an `mc-` id

The create lands an `mc-` (city-store) row; the readback can only see the rig
store. The reconciler therefore reports `absent` while the preserved fence
blocks another create — a permanent wedge. Re-running is deterministically
identical; this is not a transient.

## Root cause

Convoys track `bd` issues. Under graph.v2 the decompose source bead
`$GC_BEAD_ID` is a graph-resident `gcg-` id, which cannot be attached as a
convoy member. Across the whole city, **zero convoys track a `gcg-` member**.
The member attach fails, `convoy create` exits 1, and the orphaned row is
left in the city store.

This reproduces across runs — the same orphan shape exists for the previous
run of this step:

  mc-ksm74  normalized-decompose-e17830566a9cee644efc95f967fe9687ae4a47538e282c5e9cedc26f942458e5  open  0 members   (run issue-374-auto-20260913T165857Z)
  mc-djzpf  normalized-decompose-88f8a6176e4b224f7289321a32c93da6ec0ffe794afd448515d23858b8ef8429  open  0 members   (this run)

The earlier `STORE_TIMEOUT=15s -> 75s` fix (df9575cf5) addressed the timeout
symptom only; this create failure is a separate, still-live defect.

By contrast the parent run's input convoy succeeded because its member was a
real `bd` bead: gp-3drz6 tracks gp-z6saa.

## Disposition

Terminal hard per the bead's result contract: unreconcilable runner evidence
outside the `blocked` / `model_unavailable` recoverable classes. No child was
launched, no implementation convoy exists, and no decompose outputs were
adapted or published.

## Operator heal (do not re-run this bead first)

1. Decide the correct source binding for a graph.v2 decompose: either resolve
   the convoy member to the rig-store canonical bead (gp-z6saa) rather than the
   `gcg-` step bead, or scope the runner's create and its inventory readback to
   the same store.
2. Reap the two orphaned zero-member convoys mc-djzpf and mc-ksm74.
3. Consume `decompose/.input-convoy-create.json.tmp-87buvdsq` only as part of
   that heal; it is the durable proof this create was issued.
4. Then invalidate the decompose phase and its downstream suffix and re-serve.

Preserved deliberately: the fence file and both convoy rows. Do not delete
them ahead of the heal — they are the only evidence of the interrupted create.

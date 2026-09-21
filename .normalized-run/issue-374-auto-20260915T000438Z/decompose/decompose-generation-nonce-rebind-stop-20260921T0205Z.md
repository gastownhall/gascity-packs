# decompose hard reconciliation stop — re-minted generation cannot adopt prior receipts

Date: 2026-09-21T02:05Z
Root: gcg--9223372036854775089
Decompose bead (this generation): gcg--9223372036854775021
Prior generation decompose bead bound in the durable receipts: gcg--9223372036854775297

## What happened

The step ran its single executable boundary verbatim:

    normalized_decompose_runner.py --source-bead gcg--9223372036854775021 ...

It exited 2 with:

    normalized_decompose_runner: member bead receipt does not bind title

## Why

`decompose/member-bead-receipt.json` is a VALID, complete receipt from the prior
generation. The runner derives the deterministic nonce as

    sha256("<source_bead>|<formula>|<contract_sha256>|<base_sha>\n")

and the member bead title is `normalized-decompose-source-<nonce>`. Only the
source bead differs between generations, so:

    gcg--9223372036854775297 -> d6b29576aafeaf3f587a4b61226577948a54439702898e9cd74808e3707021f0  (stored)
    gcg--9223372036854775021 -> 744ff9dc8523eb63b10d764247bf626b65ab1e077ce5f3dbab5c2eb052397bb2  (this generation)

`_validate_member_bead_receipt` compares the stored `title` against the
recomputed one and fails closed on the first mismatched key (`title`, then
`source_bead`). No runner flag rebinds a receipt to a new source bead, and the
durable run-store restore replays the same source-bound bytes, so the reuse path
is unreachable for any re-minted decompose bead.

## State of the run (unchanged, nothing mutated by this attempt)

The decomposition itself already COMPLETED on 2026-09-20T09:04Z under the prior
generation and its checkpoint is intact:

- `checkpoints/decompose.json` generation 1, status `complete`
- `decompose.md`        84a9b1833164f4de4c61b8b700d73270a66fb1b5ec146e27ebc3fc58d1a26b5c
- `decompose.json`      ba2de296f17bf798bd10370521c67fc93902520634f835497c5099e349db4018
- `decompose-graph.json` d1eeeeff6057de5e438a2ffced9a51f40047ff6c64946fa10a143a852415a4a3
- implementation convoy `gp-cd130`, child root `gcg--9223372036854775263`
- input convoy `gp-d7pw4`, member bead `gp-ess07`

No convoy was created, no child was launched, no adapter was run, no receipt or
checkpoint was written or rewritten by this attempt. `blocked.json` is absent, so
the blocked/park arm does not apply; per the bead contract this is the
"every other state is a hard reconciliation stop" arm.

## Operator remedy (not attempted here — it is outside this step's boundary)

Either rebind the decompose phase of this generation to the completed prior
receipts (re-point `source_bead`/`nonce`, or teach the runner a generation-rebind
path), or relaunch decompose with the receipts for this generation's source bead
cleared so the runner sees `absent`. Upstream phases (prepare-design-review,
design-review reuse, seal-design-review) all closed pass in this generation and
their artifacts are hash-verified.

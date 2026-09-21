# Superseded decompose generation — source bead `gcg-699284130204933311`

These four receipts belong to the PRIOR relaunch generation of `decompose` in this
shared run dir. Their deterministic nonce
(`e4c7dd84…`) is derived from that generation's source bead, so the current
generation (source bead `gcg--9223372036854775297`, root `gcg--9223372036854775365`)
computes a different nonce and `normalized_decompose_runner.py` fail-closes with
`member bead receipt does not bind title`.

They are PRESERVED, not deleted, and nothing they name is mutated:

- member bead `gp-z8xzf` — rig store, still open
- input convoy `gp-riems` — still open, 1 member, 0 closed

The generation died **pre-sling** (the un-plumbed 15s child-launch root scan, see
`../decompose-hard-stop-diagnosis-20260920.md`; fixed upstream by workflows
`81e311790`, which defaults `--timeout-seconds` to `STORE_TIMEOUT_SECONDS=75.0`).
There is no `launch-receipt.json`, no raw/helper temporary, and no child root, so
moving these aside cannot orphan or double-launch a child; the current generation
simply reconciles its own member bead and one-member convoy.

Moved aside 2026-09-20 by bead `gcg--9223372036854775297`.

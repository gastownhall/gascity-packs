# decompose hard stop — 2026-09-20 (root `gcg-699284130204933345`, bead `gcg-699284130204933311`)

## The 2026-09-19 heal WORKED. This is a different, newly-exposed defect.

The `gcg-` convoy-member wedge (`decompose-hard-stop-diagnosis.md`, healed per
`heal-20260919.md`, workflows `9a75907a4`) is **fixed and verified**. This run got
strictly further than any prior run:

| artifact | value |
| --- | --- |
| member bead (rig store, `bd`) | `gp-z8xzf` |
| input convoy (rig store) | `gp-riems` |
| nonce | `e4c7dd8468efcaa9ce7793fc991290a1124be3a8fb5aed128036ada2d2247bc9` |

`member-bead-receipt.json`, `input-convoy-receipt.json`, `input-convoy-binding.json`,
and `launch-intent.json` are all written and mutually consistent. The convoy tracks a
real `bd` bead and landed in the **rig** store, exactly as the heal intended. No `mc-`
orphan was produced.

## New defect: the child-launch read timeout is an unfinished port of `df9575cf5`

`normalized_decompose_runner.py` raised its own store bound to
`STORE_TIMEOUT_SECONDS = 75.0` (`:42`), but that constant is applied **only** to the
direct member/convoy mutations (`:971`, `:1083`, `:1094`, `:1470`, `:1539`, `:1736`).

The pre-launch root-inventory scan runs under a *separate* parameter that nothing ever
sets:

- `normalized_decompose_runner.py:1389` — `def decompose(..., timeout_seconds: float = 15, ...)`
- `main()` (`:1833-1837`) calls `run_decompose(...)` **without** `timeout_seconds`, so the
  `15` default stands. There is no CLI flag (`:1816-1825`) and no env override.
- That value is passed straight through to `child_launch.launch_and_wait(...)` (`:1674`)
  and reaches `normalized_child_launch.py:141-154`, which loops
  `_ROOT_STATUSES = ("open", "in_progress", "blocked", "closed")` (`:41`) issuing one
  `gc ready --metadata-field gc.input_convoy_id=<convoy> --status <status> --limit 0 --json`
  per status, each bounded by that same 15s.

### Measured cost of those four scans (2026-09-20, this city)

| status | wall time |
| --- | --- |
| `open` | 14.74s |
| `in_progress` | 14.16s |
| `blocked` | 14.24s |
| `closed` | **19.86s** |

`closed` exceeds the 15s bound **every time**, so the scan can never complete. The other
three sit inside a ~0.3–0.8s margin and flake independently — observed directly: attempt 1
timed out on `open`, attempt 2 got past `open` and timed out on `closed`.

Total ≈ 63s, which fits comfortably inside the existing `STORE_TIMEOUT_SECONDS = 75.0`.
This is the tell that 75.0 was the intended bound for these reads too and the port simply
missed this parameter.

**Retrying is not viable.** This is deterministic, not transient: `closed` alone
guarantees failure. Two attempts were made and both died in the same scan loop.

## Impact and current state

The runner raises before the sling, so **no child was launched**. State is clean and
resumable:

- no `launch-receipt.json`, no raw/helper temp, no create fence
- no preserved-evidence blocker (contrast the 2026-09-15 stop, which wedged on a consumed fence)
- `decompose.md` / `decompose.json` / `decompose-graph.json` correctly absent
- the four receipts above are valid and should be **reused**, not recreated — the nonce is
  deterministic, so a resume reconciles `gp-z8xzf` / `gp-riems` rather than minting new ones

Residual `.decompose-runner.lock` and `.child-launch.lock` (both 0 bytes) are from the two
exited processes; clear them if a resume refuses on lock acquisition, as the 2026-09-19
heal had to.

## Suggested fix (one line, workflows repo)

Thread the existing constant into the child-launch reads — either default
`decompose(..., timeout_seconds: float = STORE_TIMEOUT_SECONDS)` at `:1389`, or pass
`timeout_seconds=STORE_TIMEOUT_SECONDS` from `main()` at `:1833`. Adding a
`--timeout-seconds` flag would also give operators an override this run did not have.

Consider separately why a single metadata-filtered `gc ready` costs ~15–20s in this city;
the four-status loop pays it four times for one launch.

## Disposition

Closed `gc.outcome=fail`, `gc.failure_class=hard`. Requires an operator fix in
`/data/projects/workflows` before decompose can be re-served. No fabricated artifacts, no
second decompose implementation, no blocked placeholder set (the run-wide `blocked.json`
guard was absent and the runner never reported a `blocked`/`model_unavailable` state —
this is a transport bound, not a provider block).

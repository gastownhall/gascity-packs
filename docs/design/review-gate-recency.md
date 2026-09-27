# Review gate recency and missing timestamps

Review gates cannot infer recency from bead IDs or creation times. A bead can
receive a new verdict long after it was created, and some readers omit its
update time entirely.

The implementation-review gate resolves each lane independently. Among the
nonempty candidates for a lane, it uses the newest `updated_at` only if every
candidate has one. Ties and partially dated sets retain all candidates, and any
non-approving value blocks approval. The top-level owner verdict keeps its
existing precedence over lane fallback.

Report mode retains the parent root's explicit report-path precedence. Its
member fallback uses the same fully-dated recency rule, but requires exactly one
distinct surviving path. Conflicting undated paths require another iteration;
choosing the lexicographically last bead would silently select an arbitrary
report.

Gastown's personal-work design gate applies the same recency and conflict rule
within its existing root and apply-step scope. It recognizes `approve`,
`approved`, `pass`, and `done`, case-insensitively. A `created_at` fallback cannot
resolve an update-order dispute.

## Observed deployment difference

On 2026-09-27, the installed `gc 1.4.1` returned 38 closed members of an Apicity
workflow with no `updated_at` fields. The exact same read with
`GC_BEADS_FORCE_FALLBACK=1` returned the same 38 rows with 38 timestamps. Both
The direct Beads CLI and `gc bd show` returned an update time for a recently updated member.
The override was applied to one command, without changing city configuration.

In Gas City source commit `cfea984`, the difference is in the adapters:

- `internal/beads/native_dolt_store.go`, `beadFromNativeIssue`, copies
  `CreatedAt` but omits `UpdatedAt` from the returned `Bead`.
- `internal/beads/bdstore.go`, `bdIssue.toBead`, copies both timestamps.
- `cmd/gc/cmd_ready.go`, `toReadyBead`, preserves the domain update time, but
  the wire struct omits a zero value (`omitempty,omitzero`).

Thus native-store selection can produce undated rows even after a verdict was
updated. The missing field is not proof of an untouched bead. Adapter repair
belongs in Gas City; these pack gates must work with both deployed reader
shapes regardless of when that repair is installed.

## Verification

The regression tests in `gascity/tests/test_formula_assets.py` cover 70 cases:
all three lanes, newer approvals and rejections, equal times, missing times in
either candidate, unanimous approvals, ambiguous report paths, and Gastown's
scope and approval vocabulary. Each scenario exchanges bead IDs. Against the
previous scripts, 36 cases fail across all three test methods; with these
repairs, all 70 pass.

# gc profiler collect

Assemble a durable profile capture for one formula run, retroactively, from
sources that already survive. Works on any workflow root bead id — including
runs that crashed, were never marked for profiling, or are still in flight.

## Usage

```bash
gc profiler collect <root-bead-id> [--rig <path>] [--city <path>] [--out <dir>]
```

Run it from the run's rig root, or pass `--rig`; the root bead must be
resolvable in that rig's store. Output defaults to
`<city>/.gc/runtime/profiles/<root-bead-id>/`.

## What it captures

`manifest.json` (schema `gc.profile.capture.v1`) plus the run's bead closure,
the city's session and nudge beads for the run window, the run's slice of the
durable event log, resolvable provider transcripts, the run's slice of the
usage sink, formula provenance, and rig git evidence.

## Read-only and best-effort

Every source is read only; nothing about the profiled run is mutated. A source
that is missing, unreadable, or unresolvable is recorded in the manifest's
`gaps` list rather than failing the capture — the one exception is the rig bead
store, without which there is no run to profile.

Two collects of the same closed run produce byte-identical `beads.json`, so the
per-file hashes in the manifest are comparable.

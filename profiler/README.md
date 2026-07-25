# profiler

Retroactive profiling of Gas City formula runs. Everything works from the
workflow root bead id against sources that are already durable — no core
changes and no launch-time opt-in required. Proposal and motivating data:
gastownhall/gascity#3925 (design) and gastownhall/gascity#3924 (measured
findings from a real 3.5-hour run).

Requires the `gascity` pack: `bench-nullop` routes its steps to
`gc.run-operator`, so `profiler/pack.toml` imports `../gascity` as `gc` the
same way the other derived packs in this repo do.

## Commands

```
gc profiler collect <root-bead-id> [--rig <path>] [--out <dir>]
gc profiler report  <root-bead-id> [--json] [--html] [--out <dir>]
gc profiler compare <root-a> <root-b>
```

The `profiler` prefix is the city's import binding for this pack, so it follows
whatever name the city imports it under (`[imports.profiler]` here).

`collect` assembles a capture under `<city>/.gc/runtime/profiles/<root>/`:

| File | Contents |
|---|---|
| `manifest.json` | schema (`gc.profile.capture.v1`), window, per-file hashes, disclosed gaps |
| `beads.json` | the run's full bead closure (root, steps, drain sub-workflows, convoys) |
| `session-beads.json` | agent session + nudge beads for the run window |
| `events.window.jsonl.gz` | the run's slice of the durable city event log |
| `transcripts/*.jsonl.gz` | provider transcripts resolved via session `work_dir` + `session_key` |
| `usage.window.jsonl` | usage facts (tokens / wall / cost) for the run |
| `formula-provenance.json` | formula identity, runtime vars, packs.lock |
| `git.json` | commit timestamps and refs from the rig |

`report` derives step spans (ready → started → closed, with dispatch waits
computed from blocker-close times), session lanes by role, totals, a
token/cost rollup, and findings tagged by fixable layer (`formula` / `config`
/ `platform`). `--html` writes a self-contained page with a step Gantt and
session lanes.

A run that has not finished profiles fine. The root has no `closed_at`, so the
report shows the run as in flight with elapsed time instead of a total, steps
that have started but not closed render as `running`, and the time axis is
anchored on the latest timestamp the capture observed (not on wall clock, so
re-rendering a capture later does not move the axis).

`compare` diffs two `report.json` files: total, dispatch wait, session count,
and per-step wait/active deltas for steps whose titles match.

Run `collect` from the rig root (or pass `--rig`); the root bead must be
resolvable in that rig's store.

## Agent + analysis formula

`profile-analyze` (routed to the pack's `profiler.profile-analyst` role) reads a
collected capture and writes `analysis.md` beside it: a narrative
interpretation of the mechanical report — why the slow steps were slow,
model-vs-tool-vs-dispatch attribution from transcripts, per-finding fixable
layer, and concrete suggested formula edits. Launch:

```
gc sling profiler.profile-analyst profile-analyze --formula --var root=<root-bead-id>
```

## Tokens and cost

Profiles cover **latency and cost**. `collect` copies the run's slice of the
city's usage sink (`.gc/usage.jsonl`, keyed on `run_id` / `session_id`) into
`usage.window.jsonl`, and `report` rolls those facts up per run and per step:
input / output / cache tokens, runtime wall-seconds, model invocation count,
and estimated USD.

What that rollup does and does not mean:

- Facts are deduped on `idempotency_key` before counting, because the sink
  can legitimately re-emit one.
- Cost is a **list-price estimate for decision support, not a charge**. Facts
  whose `(provider, model)` pair had no price are counted as `unpriced` and
  left out of the estimate — never treated as free. `report` prints that count
  alongside the total, matching `gc costs`.
- Per-step attribution joins a fact's `step_id` (a formula `gc.step_id`, not a
  bead id) to the step bead's `gc.step_id` metadata, and only when exactly one
  captured bead matches. Facts with no step id — ad-hoc, manual and idle
  sessions, plus compute facts emitted after the active-work pointer is
  cleared at teardown — count toward the run total and are reported as
  unattributed rather than spread across candidates.
- If the city runs with its usage provider set to `discard` or `exec:`, there
  is no local sink to capture; `collect` records the gap and `report` says the
  dimension is missing instead of reporting zero.

## Formula

`bench-nullop` — a chain of trivial steps plus a parallel fan-out that close
immediately with no real work. Profiling a bench-nullop run measures pure
orchestration overhead (dispatch, spawn/wake, claim, close) with zero LLM
variance: the noise floor for `compare`, and a regression canary for
platform latency.

## Known v0 limits (disclosed in the manifest where they apply)

- Events are read from the active city log only; rotated `.gz` archives are
  not yet scanned.
- Only Claude Code transcript layout is resolved (`~/.claude/projects`);
  other providers fall through to a manifest gap entry.
- Transcripts are read from the provider's own storage at collect time; this
  pack deliberately does not back them up (profiling reads what the user's
  existing storage holds). Sessions whose transcript files are already gone
  are listed as manifest gaps. Durable transcript correlation is a core
  enabler (E3 in the proposal), not pack scope.
- Reconciler trace slices are not captured (7-day/1-GiB retention upstream).

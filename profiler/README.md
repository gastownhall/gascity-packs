# profiler

Retroactive profiling of Gas City formula runs. Everything works from the
workflow root bead id against sources that are already durable — no core
changes and no launch-time opt-in required. Proposal and motivating data:
gastownhall/gascity#3925 (design) and gastownhall/gascity#3924 (measured
findings from a real 3.5-hour run).

## Commands

```
gc profile collect <root-bead-id> [--rig <path>] [--out <dir>]
gc profile report  <root-bead-id> [--json] [--html] [--out <dir>]
gc profile compare <root-a> <root-b>
```

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
computed from blocker-close times), session lanes by role, totals, and
findings tagged by fixable layer (`formula` / `config` / `platform`).
`--html` writes a self-contained page with a step Gantt and session lanes.

`compare` diffs two `report.json` files: total, dispatch wait, session count,
and per-step wait/active deltas for steps whose titles match.

Run `collect` from the rig root (or pass `--rig`); the root bead must be
resolvable in that rig's store.

## Order

`transcript-archive` (on `session.stopped`) gzips each managed session's
transcript into `.gc/runtime/profiles/_transcripts/` at close. Transcripts
are the one volatile source retroactive profiling depends on; archiving them
keeps per-turn timing evidence available for runs profiled later.

## Agent + analysis formula

`profile-analyze` (routed to the pack's `gc.profile-analyst` role) reads a
collected capture and writes `analysis.md` beside it: a narrative
interpretation of the mechanical report — why the slow steps were slow,
model-vs-tool-vs-dispatch attribution from transcripts, per-finding fixable
layer, and concrete suggested formula edits. Launch:

```
gc sling gc.profile-analyst profile-analyze --formula --var root=<root-bead-id>
```

Profiles cover **latency and cost**: the report rolls up tokens / wall /
estimated cost per step and per run from `usage.jsonl` when the city's usage
sink is enabled (transcript token usage is the fallback; the manifest
discloses a missing cost dimension).

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
- Sessions whose beads lack `work_dir`/`session_key`, or whose transcript
  files were cleaned before archival, are listed as gaps rather than copied.
- Reconciler trace slices are not captured (7-day/1-GiB retention upstream).

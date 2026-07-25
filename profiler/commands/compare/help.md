# gc profiler compare

Diff two profile reports: run totals, and per-step wait and active deltas for
steps whose titles match across the two runs.

## Usage

```bash
gc profiler compare <root-a> <root-b> [--city <path>]
```

Both captures need a `report.json`, so run `gc profiler report <root> --json`
for each first. Steps present in only one of the runs are counted, not diffed.

## Reading the output

Deltas are B minus A. Per-step rows are printed only when a wait or active
delta exceeds 0.05 m, so run-to-run jitter does not bury the real movement. A
value that cannot be computed — an in-flight run has no total, an unclosed step
has no active time — prints as `—` rather than as zero.

The intended baseline is a `bench-nullop` run: its steps do no real work, so
comparing two of them measures pure orchestration overhead with no LLM
variance.

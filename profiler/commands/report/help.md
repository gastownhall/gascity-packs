# gc profiler report

Render the timing and cost analysis for a capture written by
`gc profiler collect`. Formula-agnostic and deterministic: every figure comes
from the capture, nothing is estimated except the cost figure, which is labeled
as an estimate.

## Usage

```bash
gc profiler report <root-bead-id> [--capture <dir>] [--city <path>] \
                   [--json] [--html] [--out <dir>]
```

Default output is text on stdout. `--json` writes `report.json` (schema
`gc.profile.report.v1`, the input `gc profiler compare` reads) and `--html`
writes a self-contained `report.html` with a step Gantt and session lanes. Both
land in the capture dir unless `--out` says otherwise.

## What it derives

Step spans (ready → started → closed, where ready is the later of the bead's
creation and its last blocker's close, so dispatch wait is not confused with
blocked time), session lanes grouped by role, run totals, a per-run and
per-step token/cost rollup, and findings tagged with the layer that can fix
them (`formula` / `config` / `platform`).

## In-flight runs

A root with no `closed_at` reports as in flight: elapsed time instead of a
total, started-but-unclosed steps shown as `running`, and a time axis anchored
on the latest timestamp in the capture rather than on wall clock — so
re-rendering the same capture later does not move the axis.

## Reading the cost figure

Cost is a list-price estimate for decision support, not a charge. Facts with no
pricing are counted as unpriced and excluded from the estimate rather than
counted as free, and facts that resolve to no captured step are reported as
unattributed. Both counts print with the total; neither is silently folded in.

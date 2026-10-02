# gascity-jev overlay build A/B: live runs — September 29, 2026

Paired builds of the base `gascity` pack (`build-basic`, baseline) and the
`gascity-jev` overlay (`jev-route` → `jev-build`, jev) with real Claude
workers and live Jev. Each build ran in its own disposable, standalone Gas
City city, created by [`scripts/jev_build_ab.py`](../../../scripts/jev_build_ab.py)
the operator way: `gc init`, `gc import add --name gc <pack>` (the overlay
brings in `gascity` through its own import), `gc rig add` on a fixture cloned
from a local origin, and the rig's `roles` import. Work was started from the
command line: `gc gc jev-route <bead>` (jev) or
`gc sling gc.run-operator <bead> --on build-basic` (baseline).

- Host: Linux, 24 CPUs. `gc 1.5.0-dev-bb+8ab11cc90`, bd 1.3.0, Claude Code
  2.1.280, workers on `claude-sonnet-5` at low effort, Jev `jev-1.13.0`.
  Harness commit `9569c03`.
- Workers reach Claude through the host's Gas City environment file
  (`--gc-env-file ~/.cache/gascity/gasworks-gasworks.env`, the file the
  production `gc` supervisor sources). Claude variables inherited from the
  caller are removed first. Each run records the file's variable names, never
  values, in `subscription-preflight.json`. `gc init` ran with
  `--skip-provider-readiness` because its probe does not count a gateway login;
  the harness checks `claude auth status` in the city's environment instead.
- Workloads ([`scripts/jev_ab_workloads.py`](../../../scripts/jev_ab_workloads.py)):
  two planted defects (`slugify`, `durations`) and two real backlog items
  (`legacy-work-options`, `schema-roots`) whose hidden checks are the merged
  upstream commit's own test file. 4 workloads × 2 arms × 2 repetitions; each
  workload ran once with each arm first.
- Hidden pass is the harness's verdict on the result it selected.

## Experiments

| A/B | Pack | What it measured | Requests, Jev vs baseline | Hidden pass, baseline → Jev |
| --- | --- | --- | --- | --- |
| ab-001 (this page) | gate-only overlay | the first overlay: Jev decides only which Claude review lanes run | −17% planted, ±0 backlog | 6/8 → 4/8 |
| [ab-002](ab-002/README.md) | three-tier routing, gate fixes | 32 builds with the 30% day-one audit schedule | −26% overall; −46% compact, −38% direct | 9/16 → 11/16 |
| [ab-003](ab-003/README.md) | ab-002 plus fixes, 5% audits | 16-build confirmation run with the routes running as designed | **−43%** (time −42%, tokens −44–48%) | 6/8 → 6/8 |

ab-001's evidence is committed in full; from ab-002 on, only each A/B's
write-up and report are tracked and the raw runs stay on the host.

## ab-001 evidence

- [smoke-002](smoke-002/): one jev `slugify` build that passed end to end
  before the A/B.
- [ab-001](ab-001/): the 16 runs. [`report.md`](ab-001/report.md) is the full
  output of [`scripts/jev_ab_report.py`](../../../scripts/jev_ab_report.py);
  [`report.json`](ab-001/report.json) keeps the per-stage breakdown, which is
  computed from worker transcripts that stay on the host.

## Results

| Workload | Arm | Hidden pass | Minutes | Requests | Output tokens | Review gate |
| --- | --- | --- | --- | --- | --- | --- |
| slugify | baseline | 2/2 | 18.9 | 258 | 79,918 | - |
| slugify | jev | 2/2 | 17.9 | 219 | 66,405 | `jev` (test evidence skipped) |
| durations | baseline | 2/2 | 22.2 | 308 | 99,290 | - |
| durations | jev | 2/2 | 19.4 | 249 | 84,172 | `jev` (test evidence skipped) |
| legacy-work-options | baseline | 2/2 | 27.9 | 419 | 134,886 | - |
| legacy-work-options | jev | **0/2** | 23.9 | 401 | 127,352 | `escalate:receipts` |
| schema-roots | baseline | 0/2 | 30.2 | 399 | 139,638 | - |
| schema-roots | jev | 0/2 | 31.2 | 414 | 144,947 | `escalate:receipts` |

Means per build. Every build completed its workflow and all artifact check
loops passed.

Per stage (mean requests per build):

| Stage | Planted: baseline | Planted: jev | Backlog: baseline | Backlog: jev |
| --- | --- | --- | --- | --- |
| prepare → decompose | 68.5 | 62.7 | 74.0 | 71.5 |
| implement | 44.8 | 47.5 | 137.0 | 153.0 |
| summarize | 18.2 | 14.0 | 24.2 | 20.8 |
| review | 79.0 | 54.2 | 82.0 | 69.2 |
| publish | 4.8 | 0 | 6.2 | 0 |
| helpers (`bd.dog`) | 67.8 | 55.2 | 85.2 | 92.8 |
| **total** | **283.0** | **233.8** | **408.8** | **407.2** |

## Findings

1. **Where Jev answered, it cut cost without losing quality.** On the planted
   workloads the gate answered every time, skipped the test-evidence lane, and
   the jev arm used 17% fewer requests and 16% fewer output tokens than
   baseline, mostly in review (54 vs 79 requests). All eight builds passed the
   hidden checks.
2. **On real backlog work the gate never reached Jev.** All four jev backlog
   builds escalated on receipts: the implementation modified a pre-existing
   test file. Both tasks require adding regression coverage to that file
   (`gascity/tests/test_create_beads_from_tasks.py`,
   `gascity/tests/test_validators.py`), so the receipts rule cannot tell
   adding tests from editing existing ones. The harness records these as
   `failed` ("treatment not delivered"); they are counted here as jev results
   because escalation is what the overlay does on this work. Cost was then
   level with baseline.
3. **`legacy-work-options` split by arm, but not because of review.** Both jev
   builds left the legacy `gc.model` key in the emitted metadata, violating
   the requirement that legacy keys never appear, and failed 1 of 21 merged
   tests; both baseline builds passed. In all four runs every review lane
   approved on its first pass and changed nothing, so the difference was made
   by the implementation, not the review: baseline's review never faced the
   defect. The jev acceptance lane did record the violated criterion as
   `holds`, a real review miss. With two runs per arm, a 2–0 split has about a
   1-in-6 chance of happening with no arm effect.
4. **`schema-roots` failed in both arms** (one of 29 merged tests, not the same
   one each time), so it does not separate the arms.

## Fixed along the way

- The gate's criteria parser read a coverage table inside Acceptance Criteria
  as extra criteria (`09f7460`).
- The jev arm installed no check scripts, so in an earlier smoke run every
  artifact check was quarantined and never ran (`87e3749`); smoke-001 is that
  invalid run and is not committed.
- Candidate discovery resolved agents' relative summary paths against the
  harness's working directory, the pack repo, which then appeared as a quality
  candidate holding the merged fix (`6dfb1da`). The harness never selected it:
  planted modules do not exist in the repo and backlog modules there equal
  `origin/HEAD`, which `validate_result` rejects. The report now ignores all
  candidates except the selected result (`25e205b`).

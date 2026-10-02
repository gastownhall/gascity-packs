# ab-002 — September 30 to October 1, 2026

The second build A/B, after the overlay's redesign: three-tier intake routing
(`jev-build-compact`, `jev-build-direct`, `jev-build`), a review gate that
accepts test files which only gain tests and sends large files as excerpts, and
both arms with the `bd` pack's Dolt dogs suspended. Same harness and workloads
as [ab-001](../README.md); 4 workloads × 2 arms × 4 repetitions, each workload
run twice with each arm first.

- Pack commit `7cdbc22` for runs 1–28. Runs 29–32 failed when `/tmp`, a shared
  tmpfs, briefly filled; they were rerun as [ab-002-rerun](../ab-002-rerun)
  at `0da0f50`, which differs only in the harness's `--work-root` option, with
  workspaces on disk.
- Audits used the adaptive day-one schedule: 30% of act-band decisions per
  type run the full path.
- [`report.md`](report.md) and [`report.json`](report.json) cover all 32
  builds (`jev_ab_report.py ab-002 ab-002-rerun`). Raw run evidence stays on
  the host.

## Results

All 32 builds completed, and the review gate answered with Jev in every Jev
build (no escalations, no fail-open).

| Per build, all workloads | Baseline | Jev | Change |
| --- | --- | --- | --- |
| Minutes | 24.0 | 19.0 | −21% |
| Claude requests | 262.5 | 194.5 | −26% |
| Input + cache tokens | 20.7M | 15.1M | −27% |
| Output tokens | 68.0K | 46.9K | −31% |
| Hidden checks passed | 9/16 | 11/16 | |

By the formula each Jev build actually ran:

| | Builds | Hidden | Minutes | Requests | Output tokens |
| --- | --- | --- | --- | --- | --- |
| Planted, baseline | 8 | 8/8 | 20.5 | 213.5 | 53,275 |
| Planted, `jev-build-compact` | 3 | 3/3 | 12.4 | 115.3 | 25,077 |
| Planted, `jev-build` (audits) | 5 | 5/5 | 19.9 | 202.4 | 46,200 |
| Backlog, baseline | 8 | 1/8 | 27.5 | 311.5 | 82,708 |
| Backlog, `jev-build-direct` | 5 | 2/5 | 19.3 | 194.4 | 49,317 |
| Backlog, `jev-build` (audits) | 3 | 1/3 | 23.7 | 260.7 | 66,043 |

By workload (baseline → Jev): `slugify` 4/4 → 4/4, 207 → 176 requests;
`durations` 4/4 → 4/4, 220 → 164; `legacy-work-options` 0/4 → 2/4, 292 → 235;
`schema-roots` 1/4 → 1/4, 331 → 203.

## Findings

1. **The routes deliver.** Against baseline on the same workloads, the compact
   route used 46% fewer Claude requests and 40% less time; the direct route 38%
   fewer requests and 30% less time. Hidden-check results held or improved.
2. **Audits halved the measured effect.** Eight of 16 Jev builds were audits
   drawn by the 30% day-one schedule (3 compact and 5 direct decisions, well
   above the expected 4.8) and ran the full path. Arm-level savings therefore
   understate the routes.
3. **The compact breaker tripped on a measurement bug, not a Jev miss.** In run
   19 the gate counted the build's own `.gc/implementation-summary.md` and
   Python bytecode as changed files, so a one-file `durations.py` change read
   as four files and 128 lines and the compact decision was labeled a miss.
   From then on the planted tasks were routed direct instead of compact. Fixed
   in `ccaae5a`.
4. **Quality did not drop.** The Jev arm passed 11 of 16 hidden checks against
   baseline's 9. Backlog tasks were hard for low-effort Sonnet in both arms, and
   `legacy-work-options`, where ab-001's Jev arm failed twice, went 0/4 for
   baseline and 2/4 for Jev here: ab-001's split was noise.
5. **Every Jev intake decision but the mislabeled one was right** by the
   finished-diff proxy: 5 of 6 compact and 10 of 10 direct. In review, Jev
   cleared 25 acceptance criteria on its own (the 7 that audits checked were all
   right) and left 69 to Claude; no review decision was labeled a miss.

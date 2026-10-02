# ab-003 — October 2, 2026: confirmation run

The confirmation build A/B for the redesigned overlay, run the way a production
city would run it: the 5% audit floor for both the intake router and the review
gate (`--jev-audit-rate 0.05`, instead of the 30% day-one schedule that sent
half of [ab-002](../ab-002/README.md)'s Jev builds down the full path), fresh gate
state, and the fix that keeps build debris out of the gate's view of a change.
Same harness and workloads; 4 workloads × 2 arms × 2 repetitions, each
workload run once with each arm first; workspaces on disk.

- Pack commit `37a78e9` for every run.
- Three of the 16 first-pass builds hit the one-hour timeout and were rerun in
  their original arm order as `ab-003-rerun-legacy` and `ab-003-rerun-schema`.
  The stalled runs are kept on the host under `stalled/`:
  - runs 5 and 8 (both baseline): plan review closed, and Gas City never
    dispatched the decompose step for the rest of the hour, with no API errors
    in any session. Both stopped at the same point, which suggests a
    reproducible dispatch bug in Gas City, independent of the Jev pack;
  - run 6 (Jev): the worker finished `prepare`, then every Claude request got
    `503 admission_control_unavailable` from the Manifold gateway for about an
    hour.
- [`report.md`](report.md) and [`report.json`](report.json) cover the 13
  completed first-pass builds and the 3 reruns. Raw run evidence stays on the
  host.

## Results

All 16 builds completed. Every Jev build took the route Jev chose (4 compact,
4 direct; no audits fell in this sample), and the review gate answered with Jev
every time.

| Per build | Baseline | Jev | Change |
| --- | --- | --- | --- |
| Minutes | 31.8 | 18.3 | −42% |
| Claude requests | 265.2 | 151.9 | −43% |
| Input + cache tokens | 21.1M | 11.9M | −44% |
| Output tokens | 69.1K | 35.8K | −48% |
| Hidden checks passed | 6/8 | 6/8 | |

| | Builds | Hidden | Minutes | Requests | Output tokens |
| --- | --- | --- | --- | --- | --- |
| Planted, baseline | 4 | 4/4 | 28.2 | 219.5 | 53,540 |
| Planted, `jev-build-compact` | 4 | 4/4 | 13.3 | 119.2 | 25,791 |
| Backlog, baseline | 4 | 2/4 | 35.4 | 311.0 | 84,693 |
| Backlog, `jev-build-direct` | 4 | 2/4 | 23.3 | 184.5 | 45,890 |

By workload (baseline → Jev): `slugify` 2/2 → 2/2, 198 → 118 requests;
`durations` 2/2 → 2/2, 241 → 121; `legacy-work-options` 0/2 → 1/2, 324 → 188;
`schema-roots` 2/2 → 1/2, 298 → 181.

## Findings

1. **With the routes running as designed, Jev cuts a build roughly in half.**
   Compact builds used 46% fewer Claude requests and finished 53% sooner;
   direct builds used 41% fewer requests and finished 34% sooner. Across the
   arm, requests fell 43%, tokens 44–48% and wall-clock time 42%.
2. **Quality held.** Both arms passed 6 of 8 hidden checks. The planted tasks
   passed every time in both arms; the backlog tasks split 2/4 in each.
3. **Jev's routing decisions were all right**: 4 of 4 compact and 4 of 4 direct
   by the finished-diff proxy. In review, Jev cleared 17 acceptance criteria on
   its own and left 25 to Claude; no review decision was labeled a miss.
4. **The sample is small.** Eight builds per arm confirm the direction and size
   of ab-002's per-route result; they do not pin it down. Baseline builds were
   also slower here than in ab-002 (31.8 against 24.0 minutes), so the minute
   figures depend on the day, while request and token counts are steadier.

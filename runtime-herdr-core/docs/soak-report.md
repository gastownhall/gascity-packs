# runtime-herdr-core soak report

Not run yet: this is the template the first soak fills, following
[`soak/RUNBOOK.md`](../soak/RUNBOOK.md).

## Verdict

| Phase | Result | Notes |
|---|---|---|
| Pre-flight (live tier on the VM) | | |
| Bring-up (legacy) | | |
| Switch to v2 | | |
| Fault drills | | |
| 24-hour soak | | |

## What ran

- Host: Ubuntu 24.04.4 LTS, kernel <...>, systemd <...>, 4 vCPU, 8 GB, disposable.
- gc: gascity <commit> (pseudo-version <...>), Go 1.27.4, CGO_ENABLED=0. bd v1.3.4. dolt 2.6.0.
- herdr-core 0.1.19 (0.1.20 during the upgrade drill). Pack: gascity-packs <commit>.
  Harness: <commit>. Python 3.12.3. bpftrace <version>.
- City: <steady> always-on and up to <burst> on-demand scripted sessions, the formula
  dispatcher, the store's maintenance pool; `[session] provider = "herdr-core"`;
  store: bd-owned proxied Dolt for work, SQLite for infrastructure; nudge delivery: <lane | queue>.
- Agents: scripted only; no model credential on the host.

## Bring-up

| ID | Criterion | Measured | Result |
|---|---|---|---|
| B1 | doctor: no error | | |
| B2 | conformance: v2-ready, nothing failed | | |
| B3 | formula runs complete | | |
| B4 | no core left by the conformance run; city untouched | | |
| B5 | one first turn per incarnation | | |
| B6 | placement | | |
| B7 | 30 minutes without a predicate hit | | |

Disclosed doctor warnings:

| Check | Message | Why it is acceptable here |
|---|---|---|

## Switch to v2

| ID | Criterion | Measured | Result |
|---|---|---|---|
| V1 | boot log shows the v2 default | | |
| V2 | no Ownerless or Unknown box | | |
| V3 | restarts converge | | |
| V4 | a restart through v2 | | |
| V5 | one first turn per incarnation | | |

## Fault drills

| Drill | Injected at | Sessions back (s) | Children reaped (s) | Store pids kept | Orphans at 10 min | First turns | Specific criteria | Result |
|---|---|---|---|---|---|---|---|---|
| F1 place-store | | | | | | | | |
| F2 holder-kill | | | | | | | | |
| F3 holder-unit-kill | | | | | | | | |
| F4 core-kill | | | | | | | | |
| F5 core-restart | | | | | | | | |
| F6 agent-kill | | | | | | | | |
| F7 hc-update | | | | | | | | |
| F8 upgrade | | | | | | | | |
| F9 stop-wedged | | | | | | | | |
| F10 reboot | | | | | | | | |

## 24-hour soak

| ID | Criterion | Target | Legacy half | v2 half | Result |
|---|---|---|---|---|---|
| S1 | lost first turns | 0 | | | |
| S2 | duplicated first turns | 0 | | | |
| S3 | infrastructure processes killed, Dolt restarts | 0 | | | |
| S4 | unconfirmed message ops | < 1% | | | |
| S5 | controller-spawned pack ops / s / session | ≤ 0.30 / ≤ 0.05 | | | |
| S6 | core RSS within ±20% | yes | | | |
| S7 | no abort | yes | | | |

Warnings (target 0): nudges lost or duplicated <...>; orphans <...>; short-lived incarnations <...>;
unexplained core restarts / holder losses <...>; ops ended by a signal <...>; stale spawn files <...>;
workflows open after 30 min <...>.

## Measurements

| | Legacy | v2 |
|---|---|---|
| pack ops / s (all; controller-spawned; per session) | | |
| top ops by rate | | |
| op latency p50 / p95 / p99 (ms), by op | | |
| op CPU (ms), by op | | |
| controller-tree CPU (cores), mean / p95 | | |
| death-to-restart (s): n, p50, p95, max | | |
| core RSS (MiB): reference, max deviation | | |
| sizes at the end: R, hc state, .gc, .beads | | |

## Deviations and findings

<what differed from the runbook, and why; findings filed, with links>

## Artifacts

<where the data directories, captures and drill records are archived>

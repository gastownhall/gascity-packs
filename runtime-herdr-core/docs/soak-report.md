# runtime-herdr-core soak report

Soak 1: a scratch city on runtime herdr-core, brought up on the legacy
session reconciler, switched to v2, put through ten fault drills and then a
watched 24-hour soak (12 hours legacy, 12 hours v2) on a disposable VM,
following [`soak/RUNBOOK.md`](../soak/RUNBOOK.md). Run 2026-11-17 to
2026-11-19.

## Verdict

| Phase | Result | Notes |
|---|---|---|
| Pre-flight (live tier on the VM) | not run | Not run on the VM (recorded as not gating); the live tier's reference is gastownhall/gascity-packs#651. |
| Bring-up (legacy) | pass | B1 to B6 pass; B7's only hits were AP5 (pack cost), which the decisions made record-only. |
| Switch to v2 | pass | V1 to V5 pass at the A1 switch. At the soak's own switch V2 and V3 pass on the data; V1's check failed on a log-window artifact and a probe kill overlapped V3 (below). |
| Fault drills | 9 of 10 pass | F9 (stop a wedged runtime) failed its second-stop criterion on a gc-side race, fix open in gastownhall/gascity#9271. |
| 24-hour soak | pass on correctness, findings on cost and throughput | S1, S2, S4, S7 pass in both halves; S3 and S6 miss in the legacy half: S3 was caused by the harness's start method; S6 is an unexplained swing in the core's RSS that came back down, not a leak (both below). S5 over budget (record-only). No predicate hit in 24 h, no abort, nothing of the city left after the final stop. |

In 24 hours and 335 scripted incarnations the runtime lost no first turn,
duplicated none, lost or duplicated no nudge, left no message op
unconfirmed and left no orphan or core restart. What it did not do is run
cheaply: every pack op is a fresh Python process that costs about 150 ms of
CPU, so at 4 to 5 controller-spawned ops a second the pack used 0.6 to 0.8
of the VM's 4 cores. The city's workflow backlog grew for the whole soak
while the box was CPU-saturated and gc's claim path slowed as the store
grew. The runtime's per-op processes added to that saturation, but their
CPU share and the runtime's latency did not grow, so they do not explain the
trend. The soak harness's own workflow tracker confounded this with an
artifact, now fixed.

## What ran

- Host: Ubuntu 24.04.4 LTS, kernel 6.8.0-138-generic, systemd 255
  (255.4-1ubuntu8.17), 4 vCPU, 8 GB, cgroup v2, disposable.
- gc: gastownhall/gascity at commit `6cf1cccd640d` (pseudo-version
  `v1.4.3-0.20261117042201-6cf1cccd640d`), Go 1.27.4, `CGO_ENABLED=0`; the
  city's bundled `core` and `bd` packs at gascity `e38ce9cc55d1`. bd 1.3.4.
  dolt 2.6.0.
- herdr-core 0.1.19 (0.1.20 during the upgrade drill only). Pack:
  runtime-herdr-core as of gastownhall/gascity-packs#653 (hc config types)
  plus #652 (own-core identity) before #652's final review commit, copied to
  the VM and checked against its SHA256SUMS. Harness: the `soak/` harness in
  this change, without its post-soak fixes (the VM ran that tree for the
  soak, and earlier revisions of it during bring-up and the drills); the
  numbers below were recomputed with the final harness, which adds the
  op-end classes and the two fixes listed under findings. Python 3.12.3. bpftrace 0.20.2.
- City: 6 always-on and up to 10 on-demand scripted sessions (about 17 live
  with the formula dispatcher and the store's maintenance pool),
  `[session] provider = "herdr-core"`; store: bd's proxied Dolt for work,
  SQLite for the infrastructure classes (the default for a new city);
  nudges by `wait-idle` (80%), `immediate` (10%) and `queue` (10%).
- Load: a fan-out formula (5 steps on the on-demand pool) every 30 s, an
  always-on formula (one step) every 60 s, a nudge every 120 s; a probe
  `SIGKILL`s one always-on agent every 30 minutes.
- Agents: scripted only; no model credential on the host.

### Decisions for Soak 1 (task owner)

1. The performance predicate (AP5, reported as S5) is record-only: judged
   and recorded every check, never an abort.
2. The default store only: bd's proxied Dolt plus SQLite; no managed-Dolt
   city.
3. Scripted agents only; no model credentials on the VM.
4. The upgrade drill (F8) is a VM-local 0.1.20 pin edit that F9 restores to
   0.1.19; the pack's pin is never bumped.
5. The orchestrating session is the watcher (about every 30 minutes).

Disclosed deviations from a stock city: `max_wakes_per_tick = 25` and
`[beads] proxied_idle_timeout = "0"`; the bd pack's maintenance pool runs the
scripted agent and does nothing; first-turn handbacks are not applicable (the
pack has no `proc.launch` yet).

## Bring-up

| ID | Criterion | Measured | Result |
|---|---|---|---|
| B1 | doctor: no error | Pre-start: 0 failed once `beads.role` was set (the first run failed `beads-role`; the runbook now sets it). Running: 0 failed once the maintenance pool got the scripted agent's data directory (the first run failed `startup-health-episodes` on that pool; harness fix). | pass |
| B2 | conformance: v2-ready, nothing failed | `gc runtime check` 24 of 24; `gc runtime conformance` ok, `v2_ready`, 65 passed, 0 failed, 2 skipped (two runs) | pass |
| B3 | formula runs complete | both B3 roots closed. Recounted from the city's `bead.closed` events: 21 of the 22 roots slung during bring-up closed in it, sling to closed p50 36 s, max 129 s; the 22nd was slung less than a minute before the bring-up's event log ends | pass |
| B4 | no core left by the conformance run; city untouched | scratch-root cores stopped, no lock held, the city's core and boxes unchanged | pass |
| B5 | one first turn per incarnation | 23 of 23 exact | pass |
| B6 | placement | core in `hc-serve-*.service`, holder in `hc-hold-*.service`, agents in `run-*.scope` under `gascity-agents.slice` without `HC_SCOPE`, supervisor in its service | pass |
| B7 | 30 minutes without a predicate hit | 6 AP5 hits: 5 rate hits (controller-spawned ops 5.2 to 6.4/s against about 3.3/s) and 1 CPU hit (0.43 against 0.17 cores); no correctness hit | pass under decision 1 |

Disclosed doctor warnings (bring-up and every later doctor run):

| Check | Message | Why it is acceptable here |
|---|---|---|
| `provider-parity` | the scripted provider has no resume flag | scripted agents never resume |
| `order-dispatch-floor` | 4 orders fire more often than the dispatch floor | stock order intervals of the bundled packs |
| `jsonl-archive` | local-only mode | disposable VM, no remote |
| `agent-sessions`, `orphan-sessions` | agents without sessions / orphaned sessions | the checks matched running sessions only against names built from config and never read the session registry, so every pool session looked orphaned; fixed by gastownhall/gascity#9276 (merged) |
| `v2-session-migration`, `exec-runtime-identity` | the city leg was not read | bd refuses a read-only open of a proxied Dolt; the infrastructure leg was read and clean |
| `daemon-session-reconciler` (v2) | v2 chosen by default from the runtime's handshake | expected; it is V1 |
| `runtime-herdr-core:hc-core` | the core's herdr-core "came from the system package manager" | a misreading of the pack's own install; gastownhall/gascity-packs#656 |
| `fork-rate` | about 250 forks/s | the per-command data plane plus the pack's per-op processes (see Measurements) |
| `conversation-lanes` | no lane-status reply | pre-start runs only: the controller was not running yet; ok once it ran |
| `proxied-backup-coverage` | the store has no backup destination configured | pre-start runs only: the city's backup order had not run yet; ok once it ran |
| `order-tracking-retention` | 501 or more closed order-tracking beads | the A1 v2 doctor and the final doctor: stock order intervals over hours of running; advisory, and gc's retention watchdog prunes them |

## Switch to v2

| ID | Criterion | Measured | Result |
|---|---|---|---|
| V1 | boot log shows the v2 default | the supervisor names the city with `session reconciler: v2 (default: session_reconciler is unset)` | pass |
| V2 | no Ownerless or Unknown box | `ownerless-runtimes` ok before and after; `exec-runtime-identity` only warns that the city leg was not read | pass |
| V3 | restarts converge | core pid unchanged, all 5 boxes kept, no quarantine; one demand-pool box retired by gc as designed | pass |
| V4 | a restart through v2 | agent-kill: the killed session back in 13.1 s, children reaped in 12 s, no orphan | pass |
| V5 | one first turn per incarnation | 58 of 58 exact | pass |

The table is the A1 switch. The soak's own switch at T0 + 12 h ran V1 to V3
under load, without the agent-kill drill:

- V1: the harness printed `V1: FAIL: no v2 default line`, but the
  supervisor log has the city's `session reconciler: v2 (default:
  session_reconciler is unset)` line in the boot that followed the restart
  (about 13:48:00Z).
  The check read only the last 500 log lines 90 s later, and at soak log
  volume the line was already about 523 lines back: a harness artifact,
  fixed (the switch now reads 50000 lines).
- V2: `ownerless-runtimes` ok, 17 rows, none Ownerless or Unknown.
- V3: core pid unchanged, 15 boxes kept, one new demand box, no quarantine.
  The one always-on box the snapshot lists as ended was the probe's
  13:49:19Z kill: the probe timer kept running across the switch. The
  harness now pauses it from the snapshot before the restart to the one
  after it.
- First turns after the 30-minute settle: 189 of 189 exact.

## Fault drills

All on the v2 reconciler. "Sessions back" is the slowest always-on session
running again; "first turns" is every new incarnation with exactly one.

| Drill | Injected at (UTC) | Sessions back (s) | Children reaped (s) | Store pids kept | Orphans at 10 min | First turns | Specific criteria | Result |
|---|---|---|---|---|---|---|---|---|
| F1 place-store | 11-17 22:46 | n/a | n/a | restarted by design | 0 | n/a | the new store runs in the agent's `run-*.scope` without `HC_SCOPE` | pass |
| F2 holder-kill | 11-17 23:17 | 23.2 | 19.1 | yes | 0 | 9 of 9 | dispatcher (a demand session, new id) back in 78.7 s, recorded | pass (run 2) |
| F3 holder-unit-kill | 11-17 23:37 | 24 | 21.1 | yes | 0 | 9 of 9 | dispatcher back in 31.6 s, recorded | pass |
| F4 core-kill | 11-17 23:47 | no box ended | n/a | yes | 0 | n/a | a core answers in 3.5 s | pass |
| F5 core-restart | 11-17 23:57 | no box ended | n/a | yes | 0 | n/a | new core pid, same version; status says started by the pack | pass |
| F6 agent-kill | 11-18 00:07 | 19.2 | 17.0 | n/a | 0 | 1 of 1 | | pass |
| F7 hc-update | 11-18 00:17 | no box ended | n/a | n/a | n/a | n/a | `hc update` refused on the read-only install; core and pin unchanged | pass |
| F8 upgrade | 11-18 00:37 | 24.2 | 23.1 | n/a | 0 | 1 of 1 | `gc herdr-core upgrade` handed the core to 0.1.20 with every box running | pass |
| F9 stop-wedged | 11-18 01:10 | 10.4 after `gc start` | n/a | restarted by design | 0 | 8 of 8 | first stop fails and names the wedged runtime: pass; second stop prints `City stopped.` and exits 0: FAIL; a third stop stopped everything; pin restored to 0.1.19 | fail |
| F10 reboot | 11-18 01:31 | 8.6 after SSH answered | n/a | restarted by design | 0 | every session | doctor's identity checks clean after the reboot | pass |

F2's first run failed C2 on the formula dispatcher, a demand session that gc
replaces under a new id by design; the harness now judges C2 on the
always-on pool and records the dispatcher apart, and the rerun passed. F9's
first run failed its first-stop criterion on the harness's wording check and
then stopped on a harness bug (the pin restore assumed a git clone); both were
fixed before the rerun. Its second stop failed exactly as the rerun's did
(exit 1, sessions still running), so the gc race below reproduced in both
runs.

F9's failure is gc's: after the first stop failed and restored the city's
registration, the second `gc stop` found sessions still running 10 s after
the controller stopped, because nothing stopped a registered city's sessions
when no controller served it. gastownhall/gascity#9271 (open) makes `gc stop`
stop them in that case.

## 24-hour soak

T0 2026-11-18 01:47:31Z. Legacy to T0 + 12 h, v2 to T0 + 24 h, then 15
minutes to settle, the final check (exit 0), the city stopped and the final
scan (no remains, no canary hit). 290 check runs; 0 HIT lines; no abort.

| ID | Criterion | Target | Legacy half | v2 half | Result |
|---|---|---|---|---|---|
| S1 | lost first turns | 0 | 0 of 179 | 0 of 156 | pass |
| S2 | duplicated first turns | 0 | 0 | 0 | pass |
| S3 | infrastructure processes killed, Dolt restarts | 0 | 2 (one store restart at T0 + 0.3 s, seen at the T0 + 60 s sample) | 0 | legacy miss, caused by the harness's start method (below) |
| S4 | unconfirmed message ops | < 1% | 0 of 370 | 0 of 359 | pass |
| S5 | controller-spawned pack ops / s / session | ≤ 0.30 / ≤ 0.05 | 0.316 | 0.237 | over budget in both; record-only |
| S6 | core RSS within ±20% | yes | no: 81% max deviation | yes: 7.9% | legacy miss: an unexplained swing that came back down, not a leak (below) |
| S7 | no abort | yes | yes | yes | pass |

Warnings (target 0): nudges lost or duplicated 0 of 720; orphans 0 at every
hourly scan; short-lived incarnations 0; unexplained core restarts and
holder losses 0 (one core process for the whole 24 h); ops ended by a signal
454, all expected (below; 54 ops had no traced exit); stale spawn files 0; workflows open after
30 minutes: 345 legacy, 1431 v2 (corrected counts below).

### Workflows, recounted from the store

The VM report's workflow line came from the harness's tracker, which
checked at most 12 open roots per 5-minute check (oldest first, one
`gc bd show` each) against 180 slings an hour, stamped a root closed at the
check's time because the store keeps no `closed_at` for these roots, and
dropped roots slung more than a day before the final check. Its "closed" and
"sling to closed" numbers measured its own lag.

The recount reads every root the load slung (4309) in one read-only query
of the infrastructure store after the city stopped, and takes each close
time from the root's `bead.closed` event in the city's event log. Every
closed root has that event; the store's `updated_at` trails it by a median
of 20 s (the completion facts converge after the close), so it was not
used. "End" is T0 + 24 h.

| | Legacy | v2 |
|---|---|---|
| slung | 2159 (1439 fan-out, 720 always-on) | 2150 (1431 fan-out, 719 always-on) |
| closed by the end | 2159 | 1581 |
| still open at the end | 0 | 569; 37 closed between T0 + 24 h and the city stop (about 23 minutes), 532 were open when the city stopped (529 never started: first step open and unclaimed; 2 with the first step in progress; 1 with four of its five steps closed and collect unclaimed) |
| sling to closed p50 / p95 / max (s), all | 142 / 3585 / 4533 | 5097 / 15736 / 17157 (closed ones only, so low) |
| fan-out formula | 622 / 3878 / 4533 | 9611 / 16362 / 17157 (863 of 1431 closed) |
| always-on formula | 42 / 58 / 76 | 55 / 75 / 116 (718 of 719 closed) |
| open after 30 minutes | 345, all fan-out | 1431 (every fan-out root) |

Closures per hour against 180 slung per hour, and the backlog (slung, not
closed) at the end of each hour:

| Hour after T0 | 0 | 2 | 4 | 6 | 8 | 10 | 12 (switch) | 14 | 16 | 18 | 20 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| closed in the hour | 176 | 180 | 171 | 174 | 168 | 155 | 151 | 148 | 145 | 137 | 134 | 130 | 137 |
| backlog at its end | 4 | 6 | 15 | 26 | 51 | 93 | 144 | 201 | 269 | 349 | 432 | 528 | 569 |

The backlog is real and grew steadily through both halves, across the
switch with no change of slope; the always-on formula stayed under 2 minutes
throughout. It is the fan-out pool's capacity: 120 fan-out runs an hour need
600 steps an hour from 10 on-demand sessions, which they managed in hours 0
to 3 (588 to 601) and less after (361 at hour 21). Each step's scripted work
stayed at 20 s; the time around it grew: from a step's close to the
session's next claim 16 s at hour 0, 30 s at hour 5, 56 s at hour 22; the
agent's bd writes 3.5 to 4 times slower (create 1.0 to 3.9 s, close 2.6 to
9.4 s); failed claims (`timed out after 0s (caller deadline)`) from 2 to
about 240 an hour, on top of 540 to 770 rejected claims an hour from
sessions racing for the same step. Two conditions went with it: the soak
user's processes used 3.85 to 3.98 of the 4 cores from the first hour to the
last, and the store grew (the work store to 2.9 GiB). The runtime's per-op
processes took 0.6 to 0.8 of those 4 cores (0.77 legacy, 0.60 v2; about 45%
of the controller tree's 1.38 to 1.62), so they added to the saturation. But
they did not grow: their CPU share, the scripted step time and the
first-turn latency (0.84 s p50 throughout) did not move, and v2's lower pack
CPU did not change the backlog's slope, so they do not explain the trend.

Two gc observations, recorded only. gc's supervisor grew through both
halves: its RSS (hourly median) rose steadily from 149 MiB at hour 0 to 340
to 400 MiB in hours 21 to 24. One of gc's own orders,
`cascade-nudge-on-blocker-close`, timed out at its 5-minute limit 466 times
from T0 + 2.8 h on (the work store then about 0.5 GiB), at a flat ~22 an
hour; the cause is unknown.

### Anomalies

**S3: the store restart at T0 + 0.3 s (legacy, seen at the T0 + 60 s sample,
01:48:31Z). Caused by the harness's start method.** At T0 the proxied Dolt (`db-proxy-child` and its
`sql-server`) ran in the cgroup of the transient unit that ran the phase-4
start script, because the script's own `bd` and `gc` calls were the first to
touch the store. When the script exited right after the T0 note, systemd
stopped the unit and its leftover processes, so the store really was
killed; 0.3 s later (01:47:31.8Z) an always-on agent's `bd` call started a
new store in that agent's `run-*.scope`, where it
then ran unchanged for the remaining 24 h. The sampler saw both pids change
between its T0 and T0 + 60 s samples. No other store pid changed in 24 h.
Finding: bd's proxied store runs in the cgroup of whichever process first
touches it (F1 checks the agent case); Soak 2 should start the phase-4
script so that stopping its unit leaves other processes alone, or touch
the store from the supervisor before T0.

**Restarts: 26 "unexplained" legacy, 0 probe; 24 probe in v2. Explained.**
The legacy reconciler answers a probe kill by closing the killed always-on
session and starting a new session of the same template; v2 restarts the
session under its id. The harness matched a probe kill only to a later
boot of the same id, so in the legacy half all 23 probe kills went unmatched
and death-to-restart had no sample. With the fix (findings) the legacy half
reads 23 probe restarts, death-to-restart p50 / p95 / max 123.6 / 170.1 /
171.9 s, against v2's 18.3 / 36.1 / 36.8 s for 24 kills. The 26 unexplained
restarts are on-demand sessions, one to one with gc's 26
`session.drain_acked_with_assigned_work` events, all in hours 0 to 4 of the
legacy half, when gc created 38, 22, 17, 18 and 7 on-demand sessions in
T0 hours 0 to 4. In the
case traced end to end, the session reported idle (its drain
acknowledgement), claimed two steps in the next 51 s, and gc stopped it on
that acknowledgement while it held the second (SIGHUP to the agent). In
every case gc woke the same session 45.6 to 96.6 s after its last record and
the new incarnation reclaimed and finished the assigned step. No work
was lost (every legacy root closed), and each new incarnation had exactly
one first turn. v2 had no such event, with 5 to 16 on-demand stops an hour,
so the race was seen only under legacy, at higher churn; v2's stop path
emits the same event under the same condition, so its absence there is
suggestive, not proof that the race is legacy-only. Each stop was gc's own,
on the drain acknowledgement; the harness still counts them as
unexplained.

**S6: the legacy core RSS rose from 7.2 to 15.4 MiB and came back down
near 9.5 MiB. Unexplained; not a leak.** The same core process ran all
24 h, with a constant 17 live terminals from hour 4 on, so neither the
session count nor a core restart drove it. The hourly median rose from
7.2 MiB at hour 0 to 15.4 MiB at hour 9, fell to 11.3 MiB by hour 11 and to
9.5 MiB by hour 13, and stayed at 8.7 to 10.2 MiB through v2 hours 12 to 23:
the memory was given back. In the legacy half it tracked the summed age of
the live sessions (correlation 0.98), but that does not explain the swing.
In v2 the correlation is 0.24; the legacy fit (6.90 MiB + 0.149 MiB per
session-hour) over-predicts every v2 hour by 1.8 to 3.9 MiB (17 to 40%),
with a gap that grows; and at the same summed age the halves differ by
about 30% (legacy hour 6, 39.3 session-hours: 13.1 MiB; legacy hour 11,
37.8: 11.3 MiB; v2 hour 22, 41.2: 9.3 MiB). The swing was seen in the
legacy half only, and its mechanism inside herdr-core's core is unknown. A
heap profile of the core under the same load is the follow-up.

**S5: over budget in both halves (record-only).** Controller-spawned pack
ops per second per session: legacy 0.316 against 0.30, v2 0.237 against
0.05. v2 issues fewer ops in total (4.02/s against 5.10/s) but is still
4.7 times its budget; `is-running` alone is 2.45/s, then
`get-last-activity` 0.79/s and `get-meta` 0.67/s.

**The final doctor's failed check.** `dangling-blocking-edges` timed out
after 1 minute and was abandoned on the 2.9 GiB store (advisory, so
`blocking_failed` 0). The 6-hourly doctor runs in the legacy half reported
no failure; the three from T0 + 12 h on each reported one. gc doctor scaling
on a large store, not a runtime check.

**Ops ended by a signal.** Reclassified with the op-end classes: legacy 204 =
202 `watch-startup` closed by gc with `SIGKILL` (its designed close) + 2
canceled; v2 250 = 249 closed + 1 canceled; the 15-minute settle 18 closed.
No traced op was killed, overran its timeout or ended by any other signal.
54 op execs in the soak window (33 legacy, 21 v2, mostly controller-spawned
`is-running` and `get-meta`) have no traced exit, so this holds for the
traced exits only.

## Measurements

Controller-spawned pack ops, all on herdr-core 0.1.19 through the pack's
exec runtime.

| | Legacy | v2 |
|---|---|---|
| pack ops / s (all; controller-spawned; per session) | 5.64; 5.10; 0.316 (16.1 sessions) | 4.61; 4.02; 0.237 (17.0 sessions) |
| top ops by rate (/s) | is-running 2.81, get-meta 1.52, get-last-activity 0.39, observe 0.35, is-attached 0.29, inventory 0.09 | is-running 2.45, get-last-activity 0.79, get-meta 0.67, is-attached 0.31, observe 0.15, inventory 0.11 |
| op latency p50 / p95 / p99 (ms), by op | is-running 286 / 663 / 897; get-meta 259 / 643 / 899; get-last-activity 306 / 700 / 945; observe 276 / 654 / 893; is-attached 343 / 764 / 1017; inventory 391 / 867 / 1246 | is-running 282 / 689 / 956; get-last-activity 286 / 695 / 968; get-meta 331 / 817 / 1095; is-attached 297 / 742 / 1051; observe 250 / 773 / 1218; inventory 369 / 854 / 1163 |
| op CPU (ms), by op | mean 146 to 175 (is-running 148.7) | mean 147 to 174 (is-running 147.0) |
| controller-spawned op CPU (cores) | 0.77 | 0.60 |
| controller-tree CPU (cores), mean / p95 | 1.62 / 2.58 | 1.38 / 2.06 |
| all of the soak user's CPU (cores of 4) | 3.95 | 3.98 |
| death-to-restart (s): n, p50, p95, max | 23, 123.6, 170.1, 171.9 (new session) | 24, 18.3, 36.1, 36.8 (same session) |
| core RSS (MiB): reference, max deviation | 8.5 (the half's second hour), 81% | 9.5 (the half's second hour), 7.9% |
| sizes at the end: R, hc state, .gc, .beads, events | 39.5 KiB, 23 KiB, 264 MiB, 1.5 GiB, 279 MiB | 40 KiB, 23 KiB, 665 MiB, 2.9 GiB, 520 MiB |
| first turn: boot to first turn p50 / p95 (s) | 0.84 / 0.86 | 0.84 / 0.87 |
| nudges: CLI to received p50 / p95 (s) | 0.41 / 17.2 (131 delivered by the CLI, 229 queued) | 0.26 / 12.3 (150 delivered, 210 queued) |

The cost case for a long-lived pack process: an op costs about 150 ms of
CPU in both halves, the same as on the quiet bring-up box (135 ms), so the
cost is the process itself (interpreter start-up, imports, one RPC), not
the work. The runbook's pre-soak estimate was 15 ms quiet and 45 ms loaded,
so the soak's 150 ms is about 3 times the loaded estimate and the quiet
bring-up's 135 ms about 9 times the quiet one.
At v2's op rate that is 0.6 of a core for 17 sessions, about 0.035 core per
session, and it scales linearly with sessions and op rate; under load the
p50 latency doubles from about 145 ms to 250 to 390 ms. A resident pack
process (or batched ops) would remove the per-op start-up;
gastownhall/gascity-packs#657 cuts per-op CPU for the hottest ops meanwhile.

## Deviations and findings

Deviations: the five decisions and the disclosed tuning above; the
live-tier pre-flight was not run on the VM (recorded as not gating; the
live tier's reference is gastownhall/gascity-packs#651); harness fixes
landed between drills (F2 and F9 reruns); at the soak's switch the V1 check
read too short a log window and the probe timer kept running (both fixed
in the harness); the soak's VM report used a workflow tracker that
confounded the backlog (it overstated the legacy half's latency and open
count and undercounted v2's closes) and a restart attribution that missed
the legacy reconciler's probe answers (both recomputed here).

Findings:

1. Per-op cost is the runtime's main cost: about 150 ms of CPU per op,
   about 9 times the quiet estimate and 3 times the loaded one, and S5
   over budget on both reconcilers.
   In flight: gastownhall/gascity-packs#657 (cut per-op CPU for the ops gc
   calls most). A long-lived pack process is the structural fix.
2. A core was started for a city that was not running (a doctor read before
   the first start left a running core) and the doctor misread the pack's
   own herdr-core install as a package-manager one: gastownhall/gascity-packs#656
   (start a core only for a city that runs; recognise the pack's own install).
3. Earlier in this work, from the A0 to A2 runs: hc's config written with
   the types hc expects, gastownhall/gascity-packs#653 (merged); the pack's
   own core accepted on macOS and older systemd, with truthful inventory
   activity, gastownhall/gascity-packs#652 (merged); how gc ends ops (and
   that `watch-startup` always ends by `SIGKILL`) documented,
   gastownhall/gascity-packs#655; the live tier against a pinned herdr-core,
   including holder crashes, gastownhall/gascity-packs#651.
4. gc: `gc stop` leaves a registered city's sessions running when no
   controller serves it (F9), fix open in gastownhall/gascity#9271;
   doctor's `agent-sessions` and `orphan-sessions` matched running
   sessions only against names built from config and never read the
   session registry, so every pool session looked orphaned,
   gastownhall/gascity#9276 (merged); `gc runtime check` and conformance
   now run in a private city when none is set, gastownhall/gascity#9277
   (merged).
5. gc, not yet filed as fixes: gc stops an on-demand session on a stale
   drain acknowledgement while it holds a claimed step (26 times, no work
   lost; seen only under legacy, at higher churn); the claim path and the
   store's writes slow down as the store grows, so a pool sized for the
   load at hour 0 falls behind (the backlog above);
   `cascade-nudge-on-blocker-close` timed out about 22 times an hour from
   T0 + 2.8 h (about a 0.5 GiB store), cause unknown; doctor's
   `dangling-blocking-edges` times out on the 2.9 GiB store; the
   supervisor's RSS grew from 149 MiB to 340 to 400 MiB over the 24 h
   (recorded only).
6. bd's proxied store runs in the cgroup of whichever process first
   touches it (S3).
7. Harness, fixed on this branch with unit tests: the workflow tracker now
   settles every pending root from the `bead.closed` events it already
   reads (one read per check, the event's time, never the check's time) and
   keeps roots for the whole soak; the report pairs a probe kill with the
   new session the legacy reconciler starts in its place (within 10
   minutes, always-on pools only); a `watch-startup` killed at its
   deadline counts as an overrun; the switch reads enough supervisor log
   for V1 and pauses the probe timer around the restart.

What Soak 2 should add:

- The per-op cost and core-start fixes (gastownhall/gascity-packs#657 and
  #656), with S5 and the op CPU measured against Soak 1's numbers.
- A real agent (a model-backed session) alongside the scripted pool.
- The corrected workflow tracker, and a load the box can carry: either
  fewer fan-out runs or more on-demand seats, sized from Soak 1's per-step
  overhead, with the user's CPU kept under about 80% so cost and backlog
  can be told apart.
- The phase-4 start run so that stopping its unit leaves the store alone,
  and a heap profile of the core under the same load (S6).

## Artifacts

Kept outside this repository with SHA-256 sums: the soak's data directory
(agent logs, load log, samples, checks, faults, phases, doctor runs, final
scan, the VM's report), the per-op trace (compressed), the city's event log
and its mirror (compressed), the supervisor log, the soak user's journal for
the window, the store recount (every root's status) and the analysis
scripts and their outputs. The A0 to A2 evidence (bring-up, switch, drills)
is kept the same way.

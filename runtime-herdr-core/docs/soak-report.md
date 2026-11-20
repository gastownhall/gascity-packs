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
duplicated none 1 s or more apart (closer duplicates were not measured; see
the deviations), lost or duplicated no nudge, left no message op
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
| S2 | duplicated first turns | 0 | 0 (1 s or more apart) | 0 (1 s or more apart) | pass |
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
the legacy reconciler's probe answers (both recomputed here). The soak's
first-turn classifier counted input bursts with a beacon line, so a
duplicate typed less than 1 s after the first (the pack re-sends a first
turn the box refused as unavailable after 0.5 s) would have counted as
exact: every first-turn figure here (B5, V5, the drills' first turns and
C5, F10, S2, AP4) rules out only duplicates 1 s or more apart. The harness
now counts beacon lines; the agent logs kept with the artifacts have not
been re-read with it. S1 and S2 also counted a first turn in the half its
incarnation booted in, so neither counted the six steady sessions' first
incarnations, which `soak-phase4 start` boots before the legacy half
starts; the harness now counts a lost or duplicated first turn in the half
its verdict came in, and the data has not been re-read with that either.

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

## Soak 2

Soak 2: a shorter repeat on the same disposable VM, to confirm the per-op
cost cut (gastownhall/gascity-packs#657) and the core-start discipline
(#656) under the real herdr-core, following
[`soak/RUNBOOK.md`](../soak/RUNBOOK.md) section 12.1. Run 2026-11-19 to
2026-11-20.

### Verdict

| Phase | Result | Notes |
|---|---|---|
| Bring-up (legacy) | pass | doctor 0 failed (running and stopped); `gc runtime check` 24 of 24; conformance ok, `v2_ready`, 65 passed, 0 failed, 2 skipped, in a scratch city; no core started for an op that names no city or for a city never started; 25 of 25 first turns exact. |
| Switch to v2 | pass | V1 to V3 pass under load; the one always-on box that ended was a probe kill that raced the switch (deviations). |
| 12-hour soak | pass | S1 to S4, S6 and S7 pass in both halves. S5 over budget in both (record-only). No predicate hit, no abort, nothing of the city left after the final stop, no canary hit. |

Both fixes hold under the real herdr-core. The hot ops' mean CPU fell from
150 ms to 71 ms (legacy) and 78 ms (v2), and the pack's controller-spawned
ops took 0.47 and 0.40 cores instead of 0.77 and 0.60, though they ran more
often. No core ran for a city that was not running, and the doctor read the
pack's own herdr-core install correctly. The box was no longer saturated:
the soak user used 2.6 to 2.8 of the 4 cores instead of 3.95 to 3.98, and
every workflow closed (Soak 1 ended with a 569-run backlog). Soak 1's
store restart did not recur, the core's RSS stayed within 17%, and no first
turn, nudge or message op was lost or duplicated in 589 incarnations. What
remains is S5: per session the pack ran more ops than in Soak 1 (0.44 and
0.32 per second against budgets of 0.30 and 0.05), because the sessions
churned much more, and op latency was higher in the v2 half.

### What ran, and what changed since Soak 1

- The same VM, host, gc (`6cf1cccd640d`), bd 1.3.4, dolt 2.6.0, herdr-core
  0.1.19 and Python as Soak 1.
- Pack: runtime-herdr-core at the merge of #656, which also has #657; not
  the later #662 or #663. Copied to the VM and checked against its SHA256SUMS.
- Harness: the merged `soak/` harness plus this change's Soak 2 profile,
  scheduled switch and end, and scratch-city conformance run, before this
  change's rebase onto the review fixes of #661. The numbers below come from
  the rebased harness. They differ from the VM's report in one metric: the
  rebased harness measures nudge latency from when the nudge was sent, not
  from when the CLI returned.
- City and load: the same as Soak 1 on a fresh city: 6 always-on and up to
  10 on-demand scripted sessions, the default store (bd's proxied Dolt for
  work, SQLite for the infrastructure classes), `max_wakes_per_tick = 25`,
  `[beads] proxied_idle_timeout = "0"`, a fan-out formula every 30 s, an
  always-on formula every 60 s, a nudge every 120 s, and a probe `SIGKILL`
  every 30 minutes. Decisions 1 to 5 of Soak 1 held.
- Length: 6 hours legacy, then 6 hours v2 (Soak 1: 12 and 12). T0
  2026-11-19 19:17:12Z, switch 2026-11-20 01:17:13Z, end 07:17:15Z, then 15
  minutes to settle, the final check, the city stop and the final scan
  (07:33Z). 147 check runs, 0 HIT lines.

Bring-up, compared with Soak 1's bring-up: the hot ops' mean CPU fell from
136.2 ms to 62.4 ms (54% less). Controller-spawned ops per second per session
were unchanged (1.10 and 1.11). The op CPU fell from 0.80 to 0.66 cores at
about twice the op rate. The core-start probe ran the pack's ops with no city
path and with a city that never started. No-city ops exit 1 (`start`,
`is-running` and the other per-session ops) or answer `unknown` (`observe`,
`inventory`). A never-started city reads as empty, with a complete inventory.
Neither case left a herdr-core process or a new core directory. Doctor
before the first start, while running and after the stop reports `hc-core`
truthfully, with no "system package manager" misreading and no core started
by the read.

### Criteria

| ID | Criterion | Target | Legacy half | v2 half | Result |
|---|---|---|---|---|---|
| S1 | lost first turns | 0 | 0 of 233 | 0 of 356 | pass |
| S2 | duplicated first turns | 0 | 0 | 0 | pass |
| S3 | infrastructure processes killed, Dolt restarts | 0 | 0 | 0 | pass |
| S4 | unconfirmed message ops | < 1% | 0 of 191 | 0 of 178 | pass |
| S5 | controller-spawned pack ops / s / session | ≤ 0.30 / ≤ 0.05 | 0.445 | 0.319 | over budget in both; record-only |
| S6 | core RSS within ±20% | yes | yes: 16.7% max deviation | yes: 3.3% | pass |
| S7 | no abort | yes | yes | yes | pass |

The rebased harness counts every first turn by its beacon lines, so S2
here rules out duplicates of any spacing, not only those 1 s or more apart.
Warnings (target 0): nudges lost or duplicated 0 of 360; short-lived
incarnations 0; quarantines, unexplained core restarts and holder losses 0
(one core and one holder process for the whole soak); workflows open after
30 minutes 0; orphans 0 at every scan but one (below); ops ended by a
signal 233 legacy and 358 v2, all expected (below).

### Soak 1 against Soak 2

| | Soak 1 legacy | Soak 2 legacy | Soak 1 v2 | Soak 2 v2 |
|---|---|---|---|---|
| hot-op CPU, mean (ms) | 150.3 | 70.8 | 149.5 | 78.2 |
| `is-running` CPU, mean (ms) | 148.7 | 69.4 | 147.0 | 74.0 |
| controller-spawned op CPU (cores) | 0.77 | 0.47 | 0.60 | 0.40 |
| pack ops / s: all; controller-spawned | 5.64; 5.10 | 6.77; 6.55 | 4.61; 4.02 | 5.29; 5.04 |
| S5: per session (mean live boxes) | 0.316 (16.1) | 0.445 (14.7) | 0.237 (17.0) | 0.319 (15.8) |
| incarnations per hour | 14.9 | 38.8 | 13.0 | 59.3 |
| controller-tree CPU, mean / p95 (cores) | 1.62 / 2.58 | 1.59 / 2.68 | 1.38 / 2.06 | 1.30 / 1.99 |
| the soak user's CPU (cores of 4) | 3.95 | 2.71 | 3.98 | 2.57 |
| core RSS: hour-2 reference, max deviation | 8.5 MiB, 81% | 8.7 MiB, 16.7% | 9.5 MiB, 7.9% | 8.9 MiB, 3.3% |
| first turns exact; boot to first turn p50 / p95 (s) | 179 of 179; 0.84 / 0.86 | 233 of 233; 0.84 / 0.87 | 156 of 156; 0.84 / 0.87 | 356 of 356; 0.85 / 0.88 |
| nudges: received once; sent to received p50 / p95 (s) | 360 of 360; 14.7 / 29.9 | 180 of 180; 11.3 / 27.8 | 360 of 360; 17.7 / 28.4 | 180 of 180; 17.3 / 75.1 |
| store pid changes | 2 | 0 | 0 | 0 |
| workflows slung; closed; open after 30 min | 2159; 2159; 345 | 1080; 1080; 0 | 2150; 1581; 1431 | 1043; 1043; 0 |
| sling to closed p50 / p95 / max (s) | 142 / 3585 / 4533 | 106 / 149 / 233 | closed ones: 5097 / 15736 / 17157 | 121 / 162 / 203 |
| death to restart (probes): n; p50 / p95 / max (s) | 23; 123.6 / 170.1 / 171.9 | 12; 57.7 / 154.5 / 154.5 | 24; 18.3 / 36.1 / 36.8 | 13; 25.6 / 40.1 / 40.1 |
| sizes at the end of the half: work store, events | 1.5 GiB, 279 MiB | 994 MiB, 152 MiB | 2.9 GiB, 520 MiB | 1.7 GiB, 328 MiB |

Soak 1's nudge latencies here were recomputed with the rebased harness, from
the send (its report's 0.41 / 17.2 and 0.26 / 12.3 s were from the CLI's
return). Soak 1's workflow figures are its store recount; Soak 2's come from
the same recount (every root the load slung, read from the stopped city's
infrastructure store, closed at its `bead.closed` event).

Op latency p50 / p95 / p99 (ms), controller-spawned and other, by op:

| Op | Soak 1 legacy | Soak 2 legacy | Soak 1 v2 | Soak 2 v2 |
|---|---|---|---|---|
| `is-running` | 286 / 663 / 897 | 180 / 672 / 986 | 282 / 689 / 956 | 362 / 1181 / 1629 |
| `get-meta` | 259 / 643 / 898 | 152 / 588 / 924 | 331 / 817 / 1095 | 534 / 1414 / 1838 |
| `get-last-activity` | 306 / 700 / 945 | 194 / 707 / 1055 | 286 / 695 / 967 | 366 / 1203 / 1634 |
| `observe` | 276 / 654 / 891 | 174 / 634 / 976 | 250 / 773 / 1208 | 582 / 1578 / 2100 |
| `is-attached` | 343 / 764 / 1016 | 232 / 819 / 1193 | 297 / 742 / 1051 | 505 / 1500 / 1975 |
| `inventory` | 391 / 867 / 1245 | 337 / 1119 / 1647 | 369 / 853 / 1162 | 704 / 1924 / 2603 |

### Workflows: why Soak 1 had a backlog and Soak 2 did not

The fan-out pool needs 600 steps an hour. In Soak 2 it did 590 to 604 an
hour through hour 5 and 561 to 588 in hours 6 to 10. The backlog (slung, not
closed, at the end of an hour) never exceeded 7. In Soak 1 the pool fell to
554 steps in hour 4 and 473 by hour 10, and the backlog grew from hour 2 on.

The difference is box saturation, not store size. The store grew at the
same rate in both soaks: the work store was 994 MiB at the end of Soak 2's
hour 5 and 922 MiB at Soak 1's, and 1742 MiB against 1561 MiB at the end of
hour 11. At the same
hour and about the same store size, Soak 2's agents wrote faster: a step's
closing bd write took 1.9 to 4.1 s across hours 0 to 11, against 2.6 to 7.6
s. The time from a step's close to the session's next claim was 15 to 25 s,
against 16 to 37 s. The agents logged no failed claim, against 107 in Soak 1. The
soak user used 2.5 to 2.8 cores against 3.8 to 4.0. The pack's cut freed
about 0.3 cores directly. The rest of the 1.2-core drop is the saturated
box's own overhead (failed claims, slower writes, longer waits) that a
box with headroom does not pay; that part is inferred, not measured.

Store growth still costs throughput: the closing write doubled from 1.9 s to
4.1 s over the 12 hours, and the pool's steps per hour were falling at
hours 9 to 11 (568, 561, 534). Over Soak 1's 24 hours Soak 2 would probably
have built a backlog too, later; 12 hours does not show it. Hour 11 also had
less work offered (next paragraph), which flatters it.

The load generator offered less work in the v2 half. It runs every action
in one loop and skips a period it missed by a whole period. As the city's
commands slowed (a sling took 1.3 s at hour 0 and 6.8 s at hour 11; nudges
took up to 40 s), it slung 113 to 117 fan-out runs an hour in hours 6 to 10
and 105 in hour 11, against 120. Over the v2 half that is 684 of 720 fan-out
runs, 5% less fan-out work. Soak 1's load kept 118 to 120 an hour, with
shorter nudges.

### Anomalies

**47 "unexplained" legacy restarts: gc's stop on a stale drain
acknowledgement, the same as Soak 1's 26. Explained.** They match gc's 47
`session.drain_acked_with_assigned_work` events one to one: same session,
event between the two incarnations, none left over. All are on-demand
sessions. In each, gc woke the same session 6.6 to 35.6 s after the event
(13.9 to 88.2 s after the old incarnation's last record), and the step it
held closed 16 to 45 s after the new boot (47 of 47). No work was lost, and
each new incarnation had exactly one first turn. The rate is higher than in
Soak 1 (about 8 an hour for the whole half, against 26 in Soak 1's first 5
hours and none after). That follows the churn. Soak 1's backlog kept the
on-demand sessions busy after hour 4. In Soak 2 they ran out of work, drained
and were woken again all the time: 19 to 43 new on-demand sessions an hour
under legacy, and 233 incarnations in 6 hours against 179 in 12. The v2
half had none of these events, with 52 to 66 new on-demand sessions an hour
and 342 session stops. That is stronger evidence than Soak 1 had that the race
is in the legacy reconciler's stop path, but still not proof.

**Most orphans at one scan: 2 (legacy). Explained: a probe kill caught
mid-cleanup.** At the 20:17:37Z scan, the two processes were the
background children (`sleep 86400` and the agent's `python3 -I`) of the
always-on agent the probe had `SIGKILL`ed 21 s earlier, 20:17:16Z. The agent
recorded both pids at its boot, more than 10 minutes before. gc's `stop` op
for that session ran at 20:17:50Z, and the next scan found none. It was the
only scan in either half that fell between a probe kill and gc's stop.

**v2's op latency is about twice legacy's, at the same CPU per op. Partly
explained.** `is-running` p50 was 362 ms against 180 ms, and each op's CPU
was the same: 74 against 69 ms. The core and holder used about 0.006 and
0.001 cores throughout, and the soak user's CPU was lower in v2 (2.57 against
2.71). So the extra time is spent waiting, not working, and not in the core's
own CPU.

- Some of it is a trend over time that neither reconciler causes. Ops started
  with at most one other op in flight took 104 ms (p50) in hour 0, 230 ms in
  hour 5 (the last legacy hour) and 189 to 252 ms in v2's hours 6 to 11, so
  at equal concurrency the two halves are alike.
- The rest is concurrency from v2's op mix. v2 calls the slower ops more
  (`observe` 0.82/s, `is-attached` 0.51/s and `get-last-activity` 0.69/s,
  against 0.47, 0.31 and 0.45 under legacy) and the quick `get-meta` less
  (0.75/s against 1.94). The mean number of ops in flight went from 1.1 to
  2.0 at the switch, though the op rate fell. In v2, `is-running` took 277
  ms (p50) with 0 to 2 other ops in flight, 593 ms with 3 to 5 and 929 ms
  with 6 to 9.
- It is not batching. The share of controller-spawned ops started within
  50 ms of another was the same in both halves (19 to 20%), as was the mean
  number of such starts (0.21 and 0.22).
- It is not the box's CPU. Per sample interval, latency does not track the
  soak user's CPU (correlation −0.46 legacy, 0.19 v2).

Where the waiting is spent (run queue, file locks, the core's request
handling or I/O) was not measured. That, and the trend over time, are
unexplained. Soak 1 did not show the trend after its first 3 hours, but its
box was saturated, which would have hidden it.

**2 canceled ops in v2. Explained, expected.** Both were drain-metadata
writes on an idle on-demand session that gc was stopping: `remove-meta
GC_DRAIN_REASON` at 03:57:53Z and `set-meta
GC_DRAIN_ACK_REQUESTER_INSTANCE_TOKEN` at 07:01:19Z. Both got `SIGTERM`
about 0.2 s in, from a short-lived gc process (not the supervisor), 0.3 s
before the session's agent got its stop signal. Soak 1 had the same class:
2 legacy, 1 v2. The other ops ended by a signal were `watch-startup` closed
by gc, as designed (233 legacy, 356 v2). No op was killed, overran its
timeout or ended by another signal.

**The nudge tail in v2.** Every nudge was received exactly once. From the
send, v2's p95 was 75 s (wait-idle 75.1, immediate 75.9, queue 41.5; max
124 s), against 23 to 31 s under legacy and 28 to 32 s in Soak 1's v2 half.
Unexplained; not investigated beyond the per-mode split.

**S3: no store restart (Soak 1 had one).** One proxied Dolt process
pair ran from before T0 to the city stop. As in Soak 1, it ran in the cgroup
of the process that first touched the store. This time that was the
operator's SSH login session that ran `soak-phase4 start`, not a transient
unit, and the VM's logind leaves a closed session's processes running
(`KillUserProcesses=no`). So Soak 1's finding stands: bd's proxied store
runs where it is first touched. Soak 2 avoided the kill by how it was
started, not by a fix.

**S6.** The legacy core RSS rose from 7.2 to 9.9 MiB in hours 0 to 3, then
held at 9.6. Soak 1's legacy half rose the same way to hour 3 and then on
to 15.4 MiB by hour 9. Six hours is too short to tell whether the swing
recurs. No heap profile was taken.

**gc, recorded only.** `cascade-nudge-on-blocker-close` timed out at its
5-minute limit from T0 + 2 h, rising to about 21 times an hour from T0 + 5 h
(Soak 1: about 22 an hour from T0 + 2.8 h). The supervisor's RSS rose from
161 MiB in hour 0 to 218 to 295 MiB in hours 4 to 11 (Soak 1: 149 MiB to 340
to 400 MiB over 24 h).

### Deviations

- **The check and probe timers fired at T0.** Both timers have
  `OnActiveSec` and `OnUnitActiveSec`. The soak user's systemd manager had
  run since the reboot drill and kept each service's last activation: the
  probe's from Soak 1, and the check's from 8.5 minutes before T0 in the
  bring-up. Both intervals had already passed, so both services ran when the
  timers started. Three consequences followed:
  - The first probe kill came at T0 + 3 s, not T0 + 30 min.
  - The probe ran on a schedule aligned to T0, so one started 21 s into the
    scheduled switch (6 h is a multiple of 30 minutes). The switch stopped
    the probe timer 34 ms after that probe's service had started, and the
    probe killed an always-on agent at 01:17:44Z, during the supervisor
    restart. That is V3's one ended box (it came back under the same session
    id), so V3 is judged on the other 11 kept boxes.
  - Restarting the timer after the switch gave two probes 2 min 17 s apart
    (01:47:55Z and 01:50:12Z).

  Harness follow-up, not in this change: pausing the probe should also stop
  or wait for a probe already running, and the timers should not be
  started with a stale last activation.
- **The bring-up city was moved aside.** The bring-up (18:49Z to 19:12Z) ran
  on a city of the same name as the soak's. At 19:16:24Z, before the soak's
  city was created at 19:16:29Z, its city directory, its harness data and
  its core's herdr-core state were renamed aside, so the soak city and its
  core started fresh. The pack's own per-city state (its lock files, session
  metadata and activity cache, keyed by the city's path) was not moved and
  carried over from the bring-up. No soak session used any of the bring-up's
  entries.
- The load generator offered 5% less fan-out work in the v2 half (above).
- Not run: the real (model-backed) agent alongside the scripted pool, and a
  heap profile of the core, both suggested after Soak 1.

### Findings and what remains

1. The per-op cost cut (#657) works under the real herdr-core. The hot ops'
   CPU halved (about 150 ms to 71 to 78 ms), and the pack's share of the
   controller tree's CPU fell from about 45% to about 30%.
2. The core-start discipline (#656) works. No op without a city and no
   read of a never-started or stopped city started a core, and the doctor
   reads the pack's own install correctly.
3. S5 remains over budget, and is higher per session than in Soak 1. The
   rate follows session churn, which this load drove 2.6 to 4.6 times
   higher. Ops near a session's start or end ran at about 1.1 per second,
   against 0.3 to 0.4 in Soak 1, and idle on-demand sessions were probed
   more (`observe` at 0.54 per second outside starts and ends under v2,
   against 0.02). With 70 to 80 ms an op, the cost is about half Soak 1's
   per op, but the op count is not bounded by the fix. A long-lived pack
   process, or batched ops, is still the structural fix.
4. Op latency grows over the run at flat CPU per op, and v2's op mix
   raises it further. Not localized (above).
5. gc-side findings from Soak 1 that this soak saw again: the stop on a
   stale drain acknowledgement under legacy (47 times, no work lost);
   `cascade-nudge-on-blocker-close` timeouts; supervisor RSS growth; and
   throughput eroding as the store grows. gastownhall/gascity#9271 (the F9
   stop race) has since merged.
6. bd's proxied store still runs in the cgroup of whichever process first
   touches it (S3 above).
7. Harness, fixed in this change: the abort also stops a soak's scheduled
   switch and end timers. Harness, open: the timer start and the probe pause
   (deviations), and a load loop that drops periods when the city's
   commands slow down.

### Artifacts

Kept outside this repository with SHA-256 sums, checked against the VM's
before it was deleted:

- the Soak 2 data directory (agent logs, load log, samples, checks, faults,
  phases, the switch's snapshots, doctor runs, final scan, the VM's report);
- the per-op trace for the window and in full (compressed);
- the city's event log and its archive;
- the supervisor log;
- the soak user's journal for the window;
- the stopped city's infrastructure store and the workflow recount;
- the city's configuration;
- the bring-up's data and the notes on the bring-up city moved aside;
- the analysis scripts and their outputs.

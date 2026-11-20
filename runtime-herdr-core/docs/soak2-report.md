# runtime-herdr-core Soak 2 report

Soak 2: a shorter repeat of [Soak 1](soak-report.md) on the same disposable
VM, to confirm the per-op cost cut (gastownhall/gascity-packs#657) and the
core-start discipline (#656) under the real herdr-core, following
[`soak/RUNBOOK.md`](../soak/RUNBOOK.md) section 12.1. Run 2026-11-19 to
2026-11-20.

## Verdict

| Phase | Result | Notes |
|---|---|---|
| Bring-up (legacy) | pass | doctor 0 failed (running and stopped); `gc runtime check` 24 of 24; conformance ok, `v2_ready`, 65 passed, 0 failed, 2 skipped, in a scratch city; no core started for an op that names no city or for a city never started; 25 of 25 first turns exact. |
| Switch to v2 | pass | V1 to V3 pass under load; the one always-on box that ended was a probe kill that raced the switch (deviations). |
| 12-hour soak | pass | S1 to S4, S6 and S7 pass in both halves. S5 over budget in both (record-only). No predicate hit, no abort, nothing of the city left after the final stop, no canary hit. |

Both fixes hold under the real herdr-core. The hot ops' mean CPU fell from
150 ms to 71 ms (legacy) and 78 ms (v2), and the pack's controller-spawned
ops took 0.47 and 0.40 cores instead of 0.77 and 0.60, though they ran more
often. No core ran for a city that was not running, and the doctor read the
pack's own herdr-core install correctly. Every workflow closed (Soak 1 ended
with a 569-run backlog), but why is not established: the box was saturated
in both soaks, and in Soak 2 the work store ran outside the agents' cgroup
(below). Soak 1's store restart did not recur, the core's RSS stayed within
17%, and no first turn, nudge or message op was lost or duplicated in 589
incarnations. What remains is S5: per session the pack ran more ops than in
Soak 1 (0.44 and 0.32 per second against budgets of 0.30 and 0.05), because
the sessions churned much more. Op latency was higher in the v2 half, for
reasons not established.

## What ran, and what changed since Soak 1

- The same VM, host, gc (`6cf1cccd640d`), bd 1.3.4, dolt 2.6.0, herdr-core
  0.1.19 and Python as Soak 1.
- Pack: runtime-herdr-core at the merge of #656, which also has #657; not
  the later #662 or #663. Copied to the VM and checked against its SHA256SUMS.
- Harness: #661's `soak/` harness at its pre-review revision (without the
  switch's `probe.lock`), plus this change's Soak 2 profile, scheduled switch
  and end, and scratch-city conformance run. This change was then rebased
  onto #661 as merged, and the numbers below come from the rebased harness's
  report over the same data. They differ from the VM's report in one metric:
  the rebased harness measures nudge latency from when the nudge was sent,
  not from when the CLI returned.
- City and load: the same as Soak 1 on a fresh city: 6 always-on and up to
  10 on-demand scripted sessions, the default store (bd's proxied Dolt for
  work, SQLite for the infrastructure classes), `max_wakes_per_tick = 25`,
  `[beads] proxied_idle_timeout = "0"`, a fan-out formula every 30 s, an
  always-on formula every 60 s, a nudge every 120 s, and a probe `SIGKILL`
  every 30 minutes. Decisions 1 to 5 of Soak 1 held. The load was not
  lightened (deviations).
- gc's supervisor: the legacy half ran on the supervisor Soak 1's switch had
  started (2026-11-18 13:47:59Z), about 29.5 hours before T0, which had also
  served the bring-up. Soak 2's switch restarted it.
- Length: 6 hours legacy, then 6 hours v2 (Soak 1: 12 and 12). T0
  2026-11-19 19:17:12Z, switch 2026-11-20 01:17:13Z, end 07:17:15Z, then 15
  minutes to settle, the final check, the city stop and the final scan
  (07:33Z). 147 check runs, 0 HIT lines.

Bring-up, compared with Soak 1's bring-up: the hot ops' mean CPU fell from
136.2 ms to 62.4 ms (54% less). Controller-spawned ops per second per session
were unchanged (1.10 and 1.11). The op CPU fell from 0.80 to 0.66 cores at
about twice the op rate. The core-start probe ran the pack's ops with no city
path and with a city that never started. With no city, `start`, `is-running`
and the other per-session ops exit 1, `observe` answers `unknown` and
`inventory` answers incomplete (`{"complete":false}`). A never-started city
reads as empty, with a complete inventory. Neither case left a herdr-core
process or a new core directory. Doctor before the first start, while
running and after the stop reports `hc-core` truthfully, with no "system
package manager" misreading and no core started by the read.

## Criteria

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

## Soak 1 against Soak 2

| | Soak 1 legacy | Soak 2 legacy | Soak 1 v2 | Soak 2 v2 |
|---|---|---|---|---|
| hot-op CPU, mean (ms) | 150.3 | 70.8 | 149.5 | 78.2 |
| `is-running` CPU, mean (ms) | 148.7 | 69.4 | 147.0 | 74.0 |
| controller-spawned op CPU (cores) | 0.77 | 0.47 | 0.60 | 0.40 |
| pack ops / s: all; controller-spawned | 5.64; 5.10 | 6.77; 6.55 | 4.61; 4.02 | 5.29; 5.04 |
| S5: per session (mean live boxes) | 0.316 (16.1) | 0.445 (14.7) | 0.237 (17.0) | 0.319 (15.8) |
| incarnations per hour | 14.9 | 38.8 | 13.0 | 59.3 |
| controller-tree CPU, mean / p95 (cores) | 1.62 / 2.58 | 1.59 / 2.68 | 1.38 / 2.06 | 1.30 / 1.99 |
| the soak user's CPU (cores of 4), store included? | 3.95, yes | 2.71, no (about 1.3 more) | 3.98, yes | 2.57, no (about 1.3 more) |
| the box (sar): idle; run queue; 1-min load | 0.41%; 18; 18.4 | 0.76%; 25; 23.3 | 0.09%; 19; 17.4 | 0.11%; 36; 31.1 |
| core RSS: hour-2 reference, max deviation | 8.5 MiB, 81% | 8.7 MiB, 16.7% | 9.5 MiB, 7.9% | 8.9 MiB, 3.3% |
| first turns exact; boot to first turn p50 / p95 (s) | 179 of 179; 0.84 / 0.86 | 233 of 233; 0.84 / 0.87 | 156 of 156; 0.84 / 0.87 | 356 of 356; 0.85 / 0.88 |
| nudges: received once; sent to received p50 / p95 (s) | 360 of 360; 14.7 / 29.9 | 180 of 180; 11.3 / 27.8 | 360 of 360; 17.7 / 28.4 | 180 of 180; 17.3 / 75.1 |
| store pid changes | 2 | 0 | 0 | 0 |
| workflows slung; closed; open after 30 min | 2159; 2159; 345 | 1080; 1080; 0 | 2150; 1581; 1431 | 1043; 1035 (8 in flight at the end, closed in the settle); 0 |
| sling to closed p50 / p95 / max (s) | 142 / 3585 / 4533 | 106 / 149 / 233 | closed ones: 5097 / 15736 / 17157 | 121 / 162 / 203 |
| death to restart (probes): n; p50 / p95 / max (s) | 23; 123.6 / 170.1 / 171.9 | 12; 57.7 / 154.5 / 154.5 | 24; 18.3 / 36.1 / 36.8 | 13; 25.6 / 40.1 / 40.1 |
| sizes at the end of the half: work store, events | 1.5 GiB, 279 MiB | 994 MiB, 152 MiB | 2.9 GiB, 520 MiB | 1.7 GiB, 328 MiB |

Both soaks saturated the box. The soak user's CPU counts only what runs
inside the soak user's systemd manager. In Soak 1 the work store's bd proxy
and Dolt server ran there (in the agents' slice), so they were counted. In
Soak 2 they ran all soak long in the operator's SSH login session, outside
it (S3 below). That session's scope, which held the store and the shell
that started the soak, used 16 h 10 min of CPU between 19:16Z and 07:33Z,
about 1.3 cores on average. With it, Soak 2's figure is close to 4 cores,
as in Soak 1. The VM's sysstat agrees: idle at or below 1% in all four halves
(4 vCPUs), with a longer run queue and a higher load in Soak 2 than in
Soak 1.

Soak 1's nudge latencies here were recomputed with the rebased harness, from
the send (its report's 0.41 / 17.2 and 0.26 / 12.3 s were from the CLI's
return). Soak 1's workflow figures are its store recount; Soak 2's come from
the same recount (every root the load slung, read from the stopped city's
infrastructure store, closed at its `bead.closed` event; "closed" is by the
end of the soak, and the latencies cover those).

Op latency p50 / p95 / p99 (ms), controller-spawned and other, by op:

| Op | Soak 1 legacy | Soak 2 legacy | Soak 1 v2 | Soak 2 v2 |
|---|---|---|---|---|
| `is-running` | 286 / 663 / 897 | 180 / 672 / 986 | 282 / 689 / 956 | 362 / 1181 / 1629 |
| `get-meta` | 259 / 643 / 898 | 152 / 588 / 924 | 331 / 817 / 1095 | 534 / 1414 / 1838 |
| `get-last-activity` | 306 / 700 / 945 | 194 / 707 / 1055 | 286 / 695 / 967 | 366 / 1203 / 1634 |
| `observe` | 276 / 654 / 891 | 174 / 634 / 976 | 250 / 773 / 1208 | 582 / 1578 / 2100 |
| `is-attached` | 343 / 764 / 1016 | 232 / 819 / 1193 | 297 / 742 / 1051 | 505 / 1500 / 1975 |
| `inventory` | 391 / 867 / 1245 | 337 / 1119 / 1647 | 369 / 853 / 1162 | 704 / 1924 / 2603 |

## Workflows

The fan-out pool needs 600 steps an hour at the full load rate. In Soak 2
it did 590 to 604 an hour through hour 5. In hours 6 to 11 the load slung
117, 117, 117, 114, 113 and 105 fan-out runs (585 down to 525 steps
offered), and the pool did 587, 581, 588, 568, 561 and 534. Every hour the
pool did the work it was offered, its steps per hour tracked the offer, and
the backlog (slung, not closed, at the end of an hour) never exceeded 7. So
Soak 2 does not measure the pool's capacity. In Soak 1 the pool fell to 554
steps in hour 4 and 473 by hour 10, and the backlog (4, 6, 6 and 7 in hours
0 to 3) grew from hour 3 to 4 on.

Why Soak 2 had no backlog is not established. Two candidates:

- The store's placement. In Soak 1 the store competed for CPU inside the
  agents' slice; in Soak 2 it ran under its own top-level user slice, with
  its own CPU weight. Soak 2's agents wrote faster: a step's closing bd
  write took 1.9 to 4.1 s across hours 0 to 11, against 2.6 to 7.6 s, and
  the time from a step's close to the session's next claim was 15 to 25 s,
  against 16 to 37 s. The agents logged no failed claim, against 7 in Soak
  1's hours 0 to 11 (107 over its 24 hours).
- The pack's cut, which freed 0.30 cores (legacy) and 0.20 cores (v2).

Store size does not explain it: Soak 2's work store was 8 to 12% larger at
the same hour (994 against 922 MiB at the end of hour 5, 1742 against 1561
MiB at the end of hour 11).

The closing bd write grew from 1.9 s to 4.1 s over the 12 hours. Store
growth and the rising CPU contention (the run queue, below) are both
candidate causes; the soak does not separate them. Whether Soak 2 would
have built a backlog over 24 hours, 12 hours does not show.

The load generator offered less work in the v2 half. It runs every action
in one loop and skips a period it missed by a whole period. As the city's
commands slowed (a sling took 1.3 s at hour 0 and 6.8 s at hour 11; nudges
took up to 40 s), it slung 113 to 117 fan-out runs an hour in hours 6 to 10
and 105 in hour 11, against 120. Over the v2 half that is 684 of 720 fan-out
runs, 5% less fan-out work. Soak 1's load kept 118 to 120 an hour; its
slings were faster (4.8 s at hour 11) and its nudge tail shorter (max 26
against 40 s).

## Anomalies

**47 "unexplained" legacy restarts: gc's stop on a stale drain
acknowledgement, the same as Soak 1's 26. Explained.** They match gc's 47
`session.drain_acked_with_assigned_work` events one to one: same session,
event between the two incarnations, none left over. All are on-demand
sessions. In each, gc woke the same session 6.6 to 35.6 s after the event
(13.9 to 88.2 s after the old incarnation's last record), and the step it
held closed 16 to 45 s after the new boot (47 of 47). No work was lost, and
each new incarnation had exactly one first turn. The rate is higher than in
Soak 1: about 8 an hour for the whole half, against about 5 an hour in Soak
1's first 5 hours (26 in all) and none after. That follows the churn. Soak
1's backlog kept the on-demand sessions busy after hour 4. In Soak 2 they
ran out of work, drained and were woken again all the time: 19 to 43 new
on-demand sessions an hour under legacy, and 233 incarnations in 6 hours
against 179 in 12. The v2 half had none of these events, with 52 to 66 new
on-demand sessions an hour and 342 session stops. That is stronger evidence
than Soak 1 had that the race is in the legacy reconciler's stop path, but
still not proof.

**Most orphans at one scan: 2 (legacy). Explained: a probe kill caught
mid-cleanup.** At the 20:17:37Z scan, the two processes were the
background children (`sleep 86400` and the agent's `python3 -I`) of the
always-on agent the probe had `SIGKILL`ed 21 s earlier, 20:17:16Z. The agent
recorded both pids at its boot, more than 10 minutes before. gc's `stop` op
for that session ran at 20:17:50Z, and the next scan found none. No other
scan found an orphan.

**v2's op latency was higher than legacy's, at about the same CPU per op.
Unexplained.** `is-running` p50 was 362 ms against 180 ms. What the data
shows:

- Much of it is time, not the reconciler. `is-running`'s hourly p50 rose on
  one trend from 115 ms in hour 0 to 434 ms in hour 11, with no step at the
  switch (262 ms in hour 5, 287 ms in hour 6). `is-running` ops started with
  at most one other op in flight took 104 ms (p50) in hour 0, 230 ms in hour
  5 and 189 to 252 ms in hours 6 to 11.
- Two ops did step at the switch. At the same number of other ops in
  flight, the first v2 hour (from 5 minutes after the switch) against the
  last legacy hour: `get-meta` 202 to 323 ms with 0 or 1 other ops in
  flight and 306 to 503 ms with 2 or 3; `observe` 220 to 300 ms and 314 to
  515 ms. With 0 or 1 other ops in flight, `is-running` (231 to 196 ms)
  and `get-last-activity` (233 to 213 ms) did not step; with 2 or 3 they
  rose 20% and 11%, against 64% for `get-meta` and `observe`.
- v2 calls a different mix: `observe` 0.82/s, `is-attached` 0.51/s and
  `get-last-activity` 0.69/s, against 0.47, 0.31 and 0.45 under legacy, and
  `get-meta` 0.75/s against 1.94. More ops were in flight after the switch,
  but in the 30 minutes either side of it the op rate was the same (5.30
  and 5.38 per second). Ops in flight are rate times latency, so that rise
  restates the latency rise; it is not its cause.
- CPU per op rose a little: `is-running` 74 against 69 ms (7%), `get-meta`
  13%. The core and holder used about 0.006 and 0.001 cores throughout.
- Batching did not change. The share of controller-spawned ops started
  within 50 ms of another was the same in both halves (19 to 20%), as was
  the mean number of such starts (0.21 and 0.22).
- The box got busier. From the VM's sysstat, the 1-min load rose from about
  17 in T0's hour to an average of 23 in the legacy half and 31 in the v2
  half, with a run queue of 25 and 36 and idle at or below 1% on 4 vCPUs.
  Soak 1's load stayed at about 15 to 20, and its latency was flat after its
  first hours. Per sample interval, latency does not track the soak user's
  CPU (correlation −0.46 legacy, 0.19 v2), but that figure leaves out the
  store, so it says nothing about the box as a whole.

Where the waiting is spent (run queue, file locks, the core's request
handling or I/O) was not measured; the rising run queue and a v2-specific
cost in `get-meta` and `observe` are candidates, neither established.

**2 canceled ops in v2. Explained, expected.** Both were drain-metadata
writes on an idle on-demand session that gc was stopping: `remove-meta
GC_DRAIN_REASON` at 03:57:53Z and `set-meta
GC_DRAIN_ACK_REQUESTER_INSTANCE_TOKEN` at 07:01:19Z. Both got `SIGTERM`
about 0.2 s in, from a gc process that is not the supervisor, about 0.2 s
before the session's agent got its stop signal. Soak 1 had the same class:
2 legacy, 1 v2. The other ops ended by a signal were `watch-startup` closed
by gc, as designed (233 legacy, 356 v2). No op was killed, overran its
timeout or ended by another signal, of the traced exits; 17 legacy and 11
v2 execs have no traced exit.

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
started, not by a fix. The same placement took the store's CPU (about 1.3
cores) out of the soak user's measured CPU, and gave the store its own CPU
weight instead of a share of the agents' slice.

**S6.** The legacy core RSS rose from 7.2 to 9.9 MiB in hours 0 to 3, then
held at 9.6. Soak 1's legacy half rose the same way to hour 3 and then on
to 15.4 MiB by hour 9. Six hours is too short to tell whether the swing
recurs. No heap profile was taken.

**gc, recorded only.** `cascade-nudge-on-blocker-close` timed out at its
5-minute limit from T0 + 2 h, at about 21 times an hour by hour 4 (Soak 1:
about 22 an hour from T0 + 2.8 h). The supervisor's RSS (hourly median)
covers two processes. The legacy half's, already about 29.5 hours old at
T0, went from 161 MiB in hour 0 to about 220 MiB in hours 4 and 5. The
switch restarted it, and the new one went from 197 MiB in hour 6 to 227,
295 and 244 MiB in hours 9 to 11 (Soak 1: 149 MiB at hour 0 to 340 to 400
MiB in hours 21 to 24, also across the restart at its switch).

## Deviations

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

  The race with the switch came from the VM's pre-review harness. #661 as
  merged, which this change is rebased on, has the switch take `probe.lock`
  across both snapshots and wait for a probe already running, and every
  probe hold it from its flag check to its kill. Starting the timers with a
  stale last activation is still open (findings).
- **The bring-up city was moved aside.** The bring-up (18:49Z to 19:12Z) ran
  on a city of the same name as the soak's. At 19:16:24Z, before the soak's
  city was created at 19:16:29Z, its city directory, its harness data and
  its core's herdr-core state were renamed aside, so the soak city and its
  core started fresh. The pack's own per-city state (its lock files, session
  metadata and activity cache, keyed by the city's path) was not moved and
  carried over from the bring-up. No soak session used any of the bring-up's
  entries.
- **The load was not lightened.** Soak 1 recommended a load the box can
  carry, with the user's CPU under about 80%, so cost and backlog can be
  told apart. Soak 2 kept Soak 1's load rate, and the box was saturated
  again.
- The load generator offered 5% less fan-out work in the v2 half (above).
- Not run: the real (model-backed) agent alongside the scripted pool, and a
  heap profile of the core, both suggested after Soak 1.

## Findings and what remains

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
4. Op latency rose over the run at about flat CPU per op, while the box's
   run queue grew; at the switch `get-meta` and `observe` also stepped up
   at equal concurrency. Unexplained (above).
5. gc-side findings from Soak 1 that this soak saw again: the stop on a
   stale drain acknowledgement under legacy (47 times, no work lost);
   `cascade-nudge-on-blocker-close` timeouts; and supervisor RSS growth.
   gastownhall/gascity#9271 (the F9 stop race) has since merged.
6. bd's proxied store still runs in the cgroup of whichever process first
   touches it (S3 above), which here also moved its CPU out of the soak
   user's measured figure.
7. Harness, fixed in this change: the abort also stops a soak's scheduled
   switch and end timers; a switch the abort finds running edits nothing
   after it and leaves the probe timer stopped; the scheduled scripts
   refuse a city `~/soak-data/current` does not point at, and `end` stops
   the city even when its report fails; and a conformance run stops its
   scratch cores even when writing an output fails. The probe race at the
   switch is closed by #661's `probe.lock`, which the VM's harness did not
   have. Harness, open: starting the timers with a stale last activation
   (deviations), and a load loop that drops periods when the city's
   commands slow down.
8. Why Soak 2 had no backlog is not established (workflows above). A soak
   that answers it needs a load the box can carry and the store in a known
   cgroup.

## Artifacts

Kept outside this repository with SHA-256 sums, checked against the VM's
copies:

- the Soak 2 data directory (agent logs, load log, samples, checks, faults,
  phases, the switch's snapshots, doctor runs, final scan, the VM's report);
- the per-op trace for the window and in full (compressed);
- the city's event log and its archive;
- the supervisor log;
- the soak user's journal for the window;
- the stopped city's infrastructure store and the workflow recount;
- the city's configuration;
- the bring-up's data and the notes on the bring-up city moved aside;
- the VM's sysstat data for both soaks, and the system journal's session
  and unit lines (the store scope's CPU) with logind's setting;
- the analysis scripts and their outputs.

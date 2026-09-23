# Jev evidence assistance: experiment checkpoint

Updated 2026-09-20. Live paired evidence-classification tests now show lower
Claude token use and elapsed time on the small frozen synthetic suite, with
matching final labels. Complete Gas City workflow benefit remains unmeasured.
See the live results below; earlier baseline and runtime failures are preserved.

**Correction, 2026-09-23.** A later root-cause review found that this document
overstates the full-build failures as new upstream bugs. The original text is
kept; dated notes beside each claim give the corrected reading. In short:

- The tmux orphan-reaper failure is a known Gas City bug, already fixed on
  `main` by a6b72d832 "fix(proctable): never classify a tmux server as an agent
  root (#5392)" (2026-09-03). That commit is not in the v1.4.2 release used here.
  The local patch duplicated it. The harness's `patrol_interval = "1s"` (the
  documented default is 30s) probably made it appear sooner.
- The Beads forced-init preflight code is real (bd v1.3.0 `countExistingIssues`
  opens a writable store under a five-second deadline, and
  `runInitReinitPreflight` ignores its error), but it only matters when
  migrations take longer than five seconds. On this host a plain `bd init` took
  25–56 s under load averages of 20–74 on 18 CPUs, with swapping and concurrent
  Dolt servers. It is a latent, load-dependent Beads issue, not a demonstrated
  production bug. Gas City `main` has a related mitigation not in v1.4.2:
  8c2b970fe "fix(bd): corroborate a negative schema probe before
  force-reinitializing (#5330)" (2026-09-12).
- The worker closing a `do-work` latch relates to 449df7c4a "fix(hook): gate
  workflow root run_target fallback on gc.workflow_expanded (#5900)(#5901)"
  (2026-09-18, not in v1.4.2), plus a pack-side gap: the claim command did not
  check `gc.kind` and the worker template was contradictory.
- The other failures were caused by the harness, not the product: nested city
  inheriting the parent Git remote, `CLAUDE_CONFIG_DIR=~/.claude`, disabled trust
  seeding, a fixture without `origin`,
  the harness's own 120/600 s `gc sling` subprocess timeouts, 1,200/3,600 s
  workflow limits (the upstream gate uses 75 minutes), and the `HOME` override
  and 131-byte socket path in early probes.
- The gate PyYAML failure is an environment/dependency failure, not a Gas City
  bug; its exact cause is unestablished (see
  [gate-python](diagnosis/gate-python/README.md)).
- Early setup runs used locally patched `gc`/`bd` builds, and setup attempts
  001–002 imported core/bd packs from a Gas City `main` checkout with a 1.4.2
  binary (version skew).

No full build reached a Jev decision stage. None of these results bears on Jev,
and none demonstrates a new upstream bug. The harness is being reworked to
follow the documented operator path: standalone city, cloned fixture with
`origin`, `gc rig add`, default patrol interval, Gas City's own trust handling,
a 75-minute workflow limit, and a host-load preflight.

## Live paired results — September 20, 2026

The exact Dashlane note supplied by Chris unlocked Jev access. Credentials were
injected into process memory and never persisted in experiment artifacts.
A [live kind preflight](live-jev-preflight-001/report.json) verified Jev 1.13.0:
487 input tokens, 54 output tokens, 0.348 seconds, and a valid `bug` decision
for one synthetic issue. This verifies access and response handling only.

The evidence experiment then ran both arms in counterbalanced order, using the
existing v2 rubric and 0.85 threshold without changes between pilot and held-out
runs. Models: subscription Claude Sonnet 5 at low effort; Jev 1.13.0. Runtime:
Claude CLI 2.1.278, Gas City 1.4.2, Beads 1.3.0. Every attempt completed, and all
model usage counters were present. Source copies, hashes, inputs, raw outputs,
CLI commands, proof logs and timings are retained per attempt.

| Cohort / arm | Final correct | Claude tokens | Jev input / output tokens | Total assessment time |
| --- | ---: | ---: | ---: | ---: |
| pilot / Claude only | 6/6 | 40,569 | 0 / 0 | 70.35 s |
| pilot / Jev + Claude fallback | 6/6 | 0 | 6,418 / 348 | 7.31 s |
| heldout / Claude only | 14/14 | 95,095 | 0 / 0 | 166.14 s |
| heldout / Jev + Claude fallback | 14/14 | 13,582 | 14,742 / 811 | 40.44 s |

Pilot: three unique cases, two repetitions per arm. Held-out: seven unique
cases, two repetitions per arm. Repetitions are not independent new test cases.

On held-out cases, Jev plus fallback used **85.7% fewer Claude tokens** and
**75.7% less total assessment time** (4.11x ratio of summed elapsed times), with
14/14 correct final labels in each arm. There were no false `supported` results
among the ten non-supported held-out assessments per arm. These small synthetic
samples do not establish a general accuracy or safety guarantee.

Jev's **raw** held-out choices matched 12/14. On both ambiguous-contract repeats
it selected `missing_evidence` with confidence 0.04. The 0.85 cutoff routed those
two decisions to Claude, which returned the expected `unclear`. All twelve
other decisions stayed above threshold and needed no Claude call. Retain this
distinction: the treatment result belongs to Jev **plus fallback**, not Jev alone.

Held-out Claude token breakdown (all reported models):

| Counter | Claude-only arm | Jev + fallback arm |
| --- | ---: | ---: |
| Uncached input | 28 | 4 |
| Output | 701 | 177 |
| Cache reads | 63,658 | 9,094 |
| Cache creation | 30,708 | 4,307 |

Processed Claude tokens include cache reads and writes; CLI dollar estimates
are not actual subscription charges. Jev tokens are reported separately because
it uses a different model/tokenizer. Do not interpret the Claude-token reduction
as a reduction in all computation or as free Jev usage.

Timing spans fixture creation, actual proof execution, inference, fallback when
needed, and response validation. The Claude path starts a fresh CLI process
with no tools for each classification. Its startup and prompt overhead are
included. Existing Gas City sessions may amortize that overhead. Host load,
network and shared prompt caches are uncontrolled; order was counterbalanced.
No full-build runtime ran concurrently with these focused cohorts.

**Scope limit:** the focused treatment replaces a classification call with Jev
unless it falls back. The pack integration remains advisory and retains the
ordinary review lanes and their proof work. These results demonstrate potential
for offloading this bounded decision; they do not establish token savings,
quality preservation, or end-to-end speedup for the complete Gas City pack.
The previous full-build runtime failures still need resolution and matched runs.
A separate real-data kind comparison is now complete; see [KIND-RESULTS.md](KIND-RESULTS.md).

Artifacts: [pilot](pilot-paired-001/summary.json),
[held-out](heldout-paired-001/summary.json),
[paired metrics and per-case deltas](paired-comparison-001.json).
Regenerate the metrics into a **new** output file:

```sh
python3 specs/experiments/jev-evidence-routing/summarize-paired.py \
  specs/experiments/jev-evidence-routing/pilot-paired-001 \
  specs/experiments/jev-evidence-routing/heldout-paired-001 \
  --out /absolute/new/paired-comparison.json
```

## What changed

Branch `experiment/jev-evidence-routing`, based on upstream
`05031f2c66e080865c379ff799c7369430560a8f`, adds optional `jev_mode=assist`
to the `build-basic` test-evidence review lane. Default `off` preserves ordinary
review. The helper binds source and proof excerpts to file hashes and Git HEAD,
asks one Choice question per acceptance claim, validates the response, and
suggests verification, investigation, or ordinary LLM review. It never grants
approval or removes the acceptance, simplicity, synthesis, or fix lanes.

This first integration tests whether focusing evidence review helps. It also
adds bundle preparation and an extra inference call, so it may increase tokens
or latency. Only a successful paired full-workflow experiment can resolve that.

## Runtime and authentication

- Gas City upgraded from **1.4.1 to 1.4.2**; global supervisor restarted healthy.
- Beads upgraded from **1.2.2 to 1.3.0**.
- Dolt upgraded from 2.3.1 to 2.3.5; jemalloc from 5.3.1 to 5.4.0.
- Bash 5.3.20 installed because existing pack checks use syntax unsupported by
  macOS's bundled Bash.
- Official Gas City v1.4.2 source supplies the matching core/bd runtime packs.
- Claude uses the existing **Claude Max subscription**, not an API-key account.
  A preflight resolved the pinned model to `claude-sonnet-5`; telemetry also
  reports auxiliary `claude-haiku-4-5-20251001` work, which is included below.
- Claude's raw dollar estimates are retained for audit but are **not subscription
  charges**. No generative API budget or paid endpoint was used.
- Homebrew refreshed core metadata; its unrelated `csells/omacy` tap failed
  because its configured `/private/tmp/omacy-local-tap` source is missing.

## Focused evidence-assessment pilots

These measure classification of supplied source and actual test output, not
building code end to end. Both pilots used three cases, one observation per
case, subscription Claude Sonnet 5 at low effort, and no tools. All six calls
completed; each cohort matched two of three predefined labels. No unsupported
case was labelled `supported` (0/2 per cohort).

| Pilot | Rubric | Correct | Total elapsed | Mean per case | Processed LLM tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| [001](pilot-baseline-001/summary.json) | v1 | 2/3 | 18.992 s | 6.331 s | 24,721 |
| [002](pilot-baseline-002/summary.json) | v2 | 2/3 | 24.104 s | 8.035 s | 25,745 |

Do not pool these as repeated measurements: the question/rubric changed between
cohorts. Pilot 001 exposed overlap between a contradicted verification claim and
missing execution evidence. The v2 rubric explicitly reserves `contradicted`
for demonstrated product behavior violating the criterion; it also gives both
arms identical atomic questions. Pilot 002 still labelled `untested-negative`
`contradicted` instead of `missing_evidence`. The observed problem is routing to
implementation investigation rather than gathering proof, not a false pass.

Pilot 002 token breakdown across all reported models:

| Counter | Tokens |
| --- | ---: |
| Uncached input | 5,032 |
| Output | 133 |
| Cache reads | 13,317 |
| Cache creation | 7,263 |
| Total | 25,745 |

Totals count processed tokens, including cache reads/writes and auxiliary model
calls. They are not a billing estimate or unique-text token count. Timings use
monotonic wall time and include fresh fixture creation, proof execution, CLI
inference, and response validation. Model-call telemetry is separately retained.
Host load, network variability and shared prompt cache state are uncontrolled.
There is no confidence interval or claim of general accuracy from three cases.

Jev's row in preserved pilot summaries has zero attempts and zero aggregated
usage: that means **unmeasured**, not a zero-token successful treatment. No token
saving, quality improvement, or speedup can be computed from these pilots.

## Full build setup attempts

Follow-up: [root-cause diagnosis](diagnosis/README.md) identifies a mutating
five-second forced-init preflight and separate harness isolation errors.
The same installed binaries successfully initialize both databases when that
preflight is avoided; this was not established by the initial checkpoint.
A local Beads patch now makes the preflight read-only. Its real CLI regression
passes fresh schema creation, clean working set, refusal of unconfirmed
reinitialization, and preservation of an existing issue. See
[patch and validation](diagnosis/fix-validation/README.md). The global Beads
executable remains unchanged.

Correction, 2026-09-23: the preflight code path is real, but it only fails when
schema migration exceeds its five-second deadline. That happened here because
the host was heavily loaded (load 20–74 on 18 CPUs, swapping, concurrent Dolt
servers; plain `bd init` took 25–56 s). Treat it as a latent, load-dependent
Beads issue, not a demonstrated production bug. Gas City `main` already carries
a related mitigation (8c2b970fe, #5330) that is not in v1.4.2. The local patch
is a workaround for this host, not a required fix.


The initial setup attempts did not reach model dispatch. Each attempt has its own
manifest, raw log and result. Setup durations are not build-speed results.
The [patched setup](build-setup-patched-001/run-001-baseline/run.log) completed
city initialization, import install/check, configuration loading and the
`build-basic` formula check. Both city and rig databases reached schema v66.
This validates setup with the local patched Beads binary, not a completed build
or a Jev comparison.

| Attempt | Observed blocker / intervention |
| --- | --- |
| [001](build-setup-001/run-001-baseline/run.log) | Nested city inherited the parent Git remote. The harness now initializes the city as its own repository. |
| [002](build-setup-002/run-001-baseline/run.log) | Beads required explicit migration consent for a freshly created shared database. The harness permits migration only in its new disposable city. |
| [003](build-setup-003/run-001-baseline/run.log) | With version-matched runtime packs, migration failed on a pre-existing dirty `events` table in the fresh database. |
| [004](build-setup-004/run-001-baseline/run.log) | Preinitializing an embedded store succeeded, but managed-server initialization still failed on a dirty `child_counters` table. This unsuccessful workaround was removed. |

Correction, 2026-09-23: attempt 001 was a harness error; the documented setup
always uses a standalone city directory, which cannot inherit a parent remote.
Attempts 001 and 002 imported core/bd packs from a Gas City `main` checkout
while running the 1.4.2 binary, so their results carry version skew. The
dirty-table failures in 002–004 follow from the load-dependent preflight
timeout described above, not from a demonstrated production bug.

The exact migration error asks for a Dolt commit at the current schema before
migration. These are newly created experimental databases; no user database was
migrated or repaired. The local read-only-preflight patch now passes setup. Subsequent runs reached
model execution, as recorded below; a completed full build remains unvalidated. All four leftover disposable Dolt servers were
identified by their unique configuration paths and stopped; their data remain
local. The user's global supervisor and unrelated Dolt servers were retained.

Full-workflow token collection retains deduplicated assistant transcript
records and a filtered local Claude OTLP receiver. Two smoke tests
matched CLI counters exactly. The approved normal-mode probe recorded 39,473
processed tokens; the full diagnostic run also captured Haiku auxiliary requests
for session titles and prompt suggestions. See
[fix validation](diagnosis/fix-validation/README.md). Missing telemetry remains unknown. Full token-saving claims require
complete comparable coverage; transcript totals alone are insufficient.

## Approved Claude execution and startup corrections

| Attempt | Outcome | Comparison validity |
| --- | --- | --- |
| [Baseline 001](build-baseline-001/run-001-baseline/result.json) | Setup passed in 301.066 s; dispatch exceeded the old 120 s deadline before observed model calls. | Failed startup; not a build-speed measurement. |
| [Baseline 002](build-baseline-002/run-001-baseline/result.json) | Dispatch succeeded with a longer deadline. Produced requirements, then exceeded the 1,200 s workflow limit. Total elapsed 1,780.015 s. | Diagnostic recovery with manual authentication/trust interventions; exclude from A/B estimates. |
| [Baseline 003](build-baseline-003/run-001-baseline/result.json) | Started workers, then the macOS orphan reaper killed their shared tmux server. Aborted at 20m41s after confirming the defect. | 16 observed requests, 635,120 processed tokens; no completed build. |
| [Baseline 004](build-baseline-004/run-001-baseline/result.json) | Aborted at 38m44s after three missing-PyYAML gate failures. | 47 observed requests, 2,323,078 processed tokens; implementation unchanged. |
| [Baseline 005](build-baseline-005/run-001-baseline/result.json) | Requirements, plan and decomposition gates passed. Worktree preparation failed without an origin remote; workflow exceeded its 3,600 s limit. Total elapsed 4,166.829 s. | 142 observed requests, 7,689,642 processed tokens; all three original tests and independent hidden checks fail, implementation unchanged. |

Correction, 2026-09-23: the 120 s dispatch "deadline" in baseline 001 was the
harness's own subprocess timeout, not a Gas City limit. The 1,200 s and 3,600 s
workflow limits were too short: baseline 005 took about 46 minutes just to
reach implementation, and the upstream gate uses 75 minutes. The baseline 003
tmux failure is a known upstream bug already fixed on Gas City `main`
(a6b72d832, #5392), not a new finding. The baseline 004 PyYAML and baseline 005
missing-origin failures were caused by the harness (see below). None of these
runs is evidence about Jev.

The authentication failure was caused by the harness explicitly setting
`CLAUDE_CONFIG_DIR` to `~/.claude`. Although that is the usual data directory,
setting it changes the configuration/authentication namespace. The exact worker
environment reported logged out with that override and logged into Claude Max
when it was unset. No credential was copied or changed. The harness now preserves
the default unset state, while retaining a custom profile if explicitly supplied.
See [authentication probes](build-baseline-002/run-001-baseline/auth-environment-probe.json).

New fixture folders also required Claude's native trust prompt. The harness now
prepares only its own disposable fixture through an isolated tmux session before
Gas City starts workers. A [fresh-folder verification](native-startup-001/) reached
the subscription prompt in 10.288 s. The clean baseline's startup took 4.458 s.
No model events were observed during these startup checks; absent usage remains
unknown rather than a measured zero. Startup time is included in total elapsed time.

Correction, 2026-09-23: both problems were caused by the harness. Gas City never
asks for `CLAUDE_CONFIG_DIR` to be set. For the trust prompt, Gas City 1.4.2
auto-dismisses workspace-trust dialogs (`internal/runtime/dialog.go`), and the
upstream gate seeds trust; this harness had turned that off with
`seed_claude_state=False`. The separate tmux trust-preparation step works around
a harness choice, not a product gap.

Baseline 002 recorded **24 model requests and 1,258,960 processed tokens**:
4,890 uncached input, 10,072 output, 1,188,712 cache-read, and 55,286 cache-creation.
These include observed Sonnet and Haiku calls and are diagnostic consumption,
not evidence that the task was completed or that Jev saves tokens. The effective
effort in that run was unverified; the clean run explicitly sets low effort in
both CLI arguments and worker environment. Its
[assessment](build-baseline-002/run-001-baseline/assessment.json) records these
limitations separately from the raw result.

See the [confirmed tmux-reaper diagnosis and real-process regression](diagnosis/tmux-reaper/README.md). Baseline 004 used the local runtime fix and showed no observed shared-server reaping. It was aborted after 38m44s when the requirements gate exhausted three retries because its restricted PATH selected Python without PyYAML. Its 47 observed requests processed 2,323,078 tokens. Original tests remained unchanged and failed; no implementation was produced. These diagnostic totals are not a completed-build comparison. See [terminal record](build-baseline-004/run-001-baseline/result.json) and [gate-environment diagnosis](diagnosis/gate-python/README.md).

Correction, 2026-09-23: the "confirmed tmux-reaper diagnosis" describes a known
upstream bug, already fixed on Gas City `main` by a6b72d832 (#5392, 2026-09-03)
but not in v1.4.2. The local runtime fix duplicated it. The PyYAML failure is
an environment/dependency failure, not a Gas City bug: the gate PATH is
intentionally built from the bd/gc/dolt/jq directories and the pack requires
PyYAML there. Why the recorded probe's Homebrew Python lacked yaml is not
established; see [gate-python](diagnosis/gate-python/README.md).

### Task fidelity observed in baseline 004

The requirements producer marked its step passed, but its three
criteria describe the existence, schema and coverage table of a requirements
artifact. They omit `slugify`, its behavior and the unchanged-test constraint.
The original task is present in source bead `fi-ddp`; the workflow root links
its input convoy while its own description describes the formula. See
[input lineage](build-baseline-004/run-001-baseline/input-lineage-observation.json)
and the [unaltered initial artifact](build-baseline-004/run-001-baseline/requirements-initial.md).
The downstream validator subsequently requested a repair because its Python
environment could not import PyYAML; structural validation has not passed.
The stopped run underwent independent evaluation: the original tests are unchanged, the implementation remains a stub, and pytest fails.

This exposes a limitation of the current Jev hypothesis: checking evidence
against criteria that have already drifted from the user's task may validate
the wrong work. An earlier check of artifact fidelity to the original work item
is a candidate follow-up experiment. No Jev call has tested that hypothesis;
structural artifact validity is not sufficient output-quality evidence.

## Baseline 005 terminal findings

This run used the verified local Beads and macOS tmux patches plus the private
Python toolchain. Setup took 305.099 s. The controller rejected the missing
requirements coverage table, accepted its repair on attempt two, and passed the
plan and decomposition gates. This verifies the Python dependency repair in the
live workflow. No shared-tmux-server reaping was observed.

The implementation stage exposed a further **harness precondition failure**:
the fixture was created with `git init` and had no `origin`, while the workflow
requires `origin/HEAD` for its detached worktree. It correctly failed closed with
`missing-remote`. The next-run harness now provisions a local bare origin and
verifies its default branch before model dispatch. A real Git regression passes
with a non-main branch, fetch, and detached worktree creation. See the
[origin diagnosis](diagnosis/fixture-origin/README.md). This repair was not applied
to the running experiment, and the remaining full workflow has not been verified.

Correction, 2026-09-23: the documented operator path clones the repository and
runs `gc rig add`, which probes `origin`. A fixture without `origin` is a harness
deviation from that path, not a product failure. The replacement harness will
use a cloned fixture and `gc rig add` rather than a synthesized bare origin.

A separate observation is preserved: a worker claimed and closed a `do-work`
workflow latch without implementing the task. Its routing cause is not isolated;
the origin fix does not establish that this behavior is corrected.

Correction, 2026-09-23: this behavior relates to an upstream fix on Gas City
`main`, 449df7c4a "fix(hook): gate workflow root run_target fallback on
gc.workflow_expanded (#5900)(#5901)" (2026-09-18), which is not in v1.4.2. There
was also a pack-side gap: the claim command did not check `gc.kind`, and the
worker template gave contradictory instructions. The pack-side gap is being fixed
in the packs.

The later [implementation summary](build-baseline-005/run-001-baseline/produced-artifacts/implementation-summary.md)
correctly marked the work blocked, observed the unchanged stub, and recorded
three failing tests despite the earlier drain pass. The workflow did not reach
a successful final result; the evidence does not show a false final approval.

The initial requirements described slugify, unlike baseline 004, but omitted the
explicit unchanged-test constraint and did not clearly preserve ASCII-only scope.
The later plan specified ASCII handling. It also contained a placeholder upstream
hash that passed structural validation and was not flagged by the review's closing
reason. The independent [hash audit](build-baseline-005/run-001-baseline/artifact-hash-audit.json)
confirms this mismatch; decomposition's own hashes match. Semantic task fidelity
and deterministic provenance checks are distinct from schema validity.

Observed token breakdown, including Sonnet and auxiliary Haiku calls:

| Counter | Tokens |
| --- | ---: |
| Uncached input | 28,758 |
| Output | 27,455 |
| Cache reads | 7,396,339 |
| Cache creation | 237,090 |
| Total | 7,689,642 |

The collector reported zero parse/collection errors, and retained raw event totals
match the terminal report. Eleven task transcripts were archived locally with
SHA-256 manifests. All three unchanged fixture tests failed with NotImplementedError;
the four predefined hidden checks also failed. No alternative implementation was
found under the fixture. These are failed-run measurements, not a speed result for
a completed build. The 69m27s total includes setup, dispatch, timeout diagnostics
and shutdown; the workflow wait itself was capped at one hour.

Host load was uncontrolled (about 19.5 at model start and 24–25 later on ten logical
CPUs). Logs also show slow-storage and process-snapshot failures. Read-only monitoring
and small harness checks ran concurrently. Timing cannot establish a Jev benefit.
Only this run's processes and empty named tmux server were stopped; the pre-existing
global supervisor remained running. No user database was migrated.

See the [terminal audit](build-baseline-005/run-001-baseline/terminal-audit.json),
[independent quality checks](build-baseline-005/run-001-baseline/independent-quality.json),
and [five-run CSV index](build-run-index-005.csv). Regenerate a new index with
`python3 summarize-build-runs.py /new/output.csv`; existing snapshots are not overwritten.

## Validation

- [27 new helper, accounting and cleanup tests pass](final-jev-validation.log).
- Pack/formula validation run: 227 passed, 17 skipped, 2 failed, plus 9,467
  subtests. The two failures hit existing two-second claim-command timeouts.
- Both timeout failures reproduce using untouched upstream test and claim files;
  see [upstream reproduction](upstream-claim-validation.log).
- The 17 skipped integration tests were rerun against `/opt/homebrew/bin/gc`
  1.4.2 and all passed; see [integration log](integration-validation.log).
- `gc lint gascity` and Python compilation pass.
- Subscription-profile, native-startup, telemetry, gate-toolchain, interrupt-finalization and local-origin regression tests: **18 passed**. See [latest harness validation](diagnosis/fixture-origin/green.log).
- Previous startup-fix and telemetry validation: **122 passed**.
  [Validation log](final-startup-fix-validation.log).

Unit tests use synthetic responses to verify error handling and routing. These
are not Jev inference results. The complete workflow and live Jev response
contract remain unvalidated.

## Reproduction and next experiments

Use Python 3.11+ with pytest, PyYAML and jsonschema, modern Bash first on PATH,
current `gc` and `bd`, and a logged-in subscription Claude CLI. Set
`GASCITY_SOURCE_ROOT` to the matching Gas City source release for full builds.
Every `--out` directory must be new. Do not reuse a previous run directory.

```sh
python scripts/jev_ab.py --split pilot --arms baseline --repetitions 1 \
  --model claude-sonnet-5 --out /absolute/new/pilot-directory

# Requires a Jev credential supplied privately in the worker environment.
python scripts/jev_ab.py --split pilot --arms both --repetitions 2 \
  --model claude-sonnet-5 --jev-model jev-1.13.0 \
  --out /absolute/new/paired-pilot-directory

# Once the pilot treatment is frozen, without further tuning on held-out cases:
python scripts/jev_ab.py --split heldout --arms both --repetitions 3 \
  --model claude-sonnet-5 --jev-model jev-1.13.0 \
  --out /absolute/new/heldout-directory

# Use the recorded locally patched binary until the fix is in a release:
python scripts/jev_build_ab.py --arms baseline --repetitions 1 --setup-only \
  --bd-bin /absolute/path/to/patched/bd \
  --out /absolute/new/build-preflight-directory
python scripts/jev_build_ab.py --arms both --repetitions 2 --timeout 3600 \
  --gc-bin /absolute/path/to/patched/gc \
  --bd-bin /absolute/path/to/patched/bd \
  --out /absolute/new/build-directory
```

Correction, 2026-09-23: do not use the patched binaries above for new runs. The
tmux fix is already upstream (a6b72d832), and the Beads preflight issue only
appears under heavy host load. Future full builds should use released or
upstream binaries and follow the documented operator path described in the
correction summary at the top of this document.

Live Jev uses `TYPESAFE_API_KEY` injected privately from the exact Dashlane
secure note supplied by Chris. Earlier searches and secure-entry requests did
not supply a key; live access was verified on September 20. Generative model
work continues through subscription CLIs.
Verify the pinned Jev model with a real preflight and retain the resolved model.
A fallback-only full build is a treatment failure, not a successful Jev result.
Automatic approval review rejected a Claude probe outside safe mode because it
could include workspace instructions/configuration. The user subsequently approved the Claude run. The approved telemetry probe
matched CLI token counters exactly; baseline 003 exposed a separate macOS tmux-reaper defect after two
retained failed/diagnostic attempts. Jev access is now verified.

Correction, 2026-09-23: the "macOS tmux-reaper defect" was a known upstream bug
already fixed on Gas City `main` (a6b72d832, #5392), not a new finding.

Remaining work: working full-build execution and complete token telemetry;
paired full-build measurements; broader and repeated kind-triage evaluation. The generative baseline evaluated here is Claude. Codex or another
subscription-backed CLI needs its own adapter and separately reported cohort.

## Audit trail

[Append-only ledger](ledger.jsonl) records environment changes and experiments.
Each focused run retains input state, exact questions/prompt, command, raw
stdout/stderr, proof metadata, per-model usage and terminal result. Cohort source
copies and manifests preserve the code used at the time. Failed setup attempts
remain alongside successful classification calls; they are not discarded.

Disposable runtime cities, copied packs, and nested fixture Git repositories
stay local and are excluded from Git. Materialized source/proof state and suite
files preserve the focused experiment inputs without committing nested repos.

## Kind-triage extension

Julian's maintainer-city experience, relayed by Chris, motivates testing kind
classification separately from evidence review. The reported 96% is agreement
with the prior Opus Max classifier; sample size and raw data are unavailable.
Priority and initial adopt-pr complexity reportedly had mixed results and are
not enabled for automatic replacement.

The branch now has opt-in kind assistance for issue triage, a reusable helper
for issue/PR snapshots, an auditable historical backtest runner, and a paired
subscription Claude/fallback runner. See [KIND-TRIAGE.md](KIND-TRIAGE.md) for the
contract. Our own 32-item real-data evaluation is complete: raw Jev/Opus
agreement 31/32 (96.9%), final agreement 32/32 after seven fresh fallbacks,
77.9% fewer Claude tokens, and 71.2% less classification time. These measurements
are separate from evidence review and full-build experiments. See
[KIND-RESULTS.md](KIND-RESULTS.md) for the dataset, raw evidence and limitations.

Kind software validation: 71 relevant tests and 176 subtests passed, plus real
CLI validation-only and missing-key failure checks. Two broader claim-command
timeouts reproduce on the prior commit; details and retained artifacts are in
[the kind validation record](KIND-TRIAGE.md#recorded-software-validation).

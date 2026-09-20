# Jev evidence assistance: experiment checkpoint

Recorded 2026-09-19. **No measured A/B benefit is established.** The optional pack
integration and experiment harnesses are implemented, but live Jev access and
full-workflow validation remain unresolved. No Jev inference has
been performed. Held-out cases remain unevaluated.

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
| Baseline 003 | Fresh run with corrected authentication, automatic fixture trust, explicit low effort, unique city name, and 3,600 s workflow limit. | Running; no quality or speed result yet. |

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

Baseline 002 recorded **24 model requests and 1,258,960 processed tokens**:
4,890 uncached input, 10,072 output, 1,188,712 cache-read, and 55,286 cache-creation.
These include observed Sonnet and Haiku calls and are diagnostic consumption,
not evidence that the task was completed or that Jev saves tokens. The effective
effort in that run was unverified; the clean run explicitly sets low effort in
both CLI arguments and worker environment. Its
[assessment](build-baseline-002/run-001-baseline/assessment.json) records these
limitations separately from the raw result.

## Validation

- [27 new helper, accounting and cleanup tests pass](final-jev-validation.log).
- Pack/formula validation run: 227 passed, 17 skipped, 2 failed, plus 9,467
  subtests. The two failures hit existing two-second claim-command timeouts.
- Both timeout failures reproduce using untouched upstream test and claim files;
  see [upstream reproduction](upstream-claim-validation.log).
- The 17 skipped integration tests were rerun against `/opt/homebrew/bin/gc`
  1.4.2 and all passed; see [integration log](integration-validation.log).
- `gc lint gascity` and Python compilation pass.
- New subscription-profile, native-startup, and telemetry regression tests: **15 passed**.
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
python scripts/jev_build_ab.py --arms both --repetitions 2 \
  --out /absolute/new/build-directory
```

Live Jev requires `TYPESAFE_API_KEY` supplied privately. No key was found in the
available vault, and the secure-entry request timed out. Generative model work
continues through subscription CLIs.
Verify the pinned Jev model with a real preflight and retain the resolved model.
A fallback-only full build is a treatment failure, not a successful Jev result.
Automatic approval review rejected a Claude probe outside safe mode because it
could include workspace instructions/configuration. The user subsequently approved the Claude run. The approved telemetry probe
matched CLI token counters exactly; clean baseline 003 is running after two
retained failed/diagnostic attempts. The Jev
credential remains missing.

Remaining work: live paired pilot; frozen held-out evaluation; working full-build
execution and complete token telemetry; paired full-build measurements; final
comparative report. This checkpoint evaluates Claude only. Codex or another
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

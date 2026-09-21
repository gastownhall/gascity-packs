# All-enabled Jev results — September 20–21, 2026

All implemented integrations now default to auto when the worker has a Jev key:
issue/PR kind, duplicate ordering, test-evidence assessment, finding categories
and pair matching, and failure investigation routing. This follows the explicit
request to enable everything and measure quality loss. The prior promotion gate
no longer determines these defaults. Review requirements and confidence/error
fallbacks remain active; no credential means ordinary handling.

## Combined work-packet comparison

Eight frozen packets, twice per arm, produced 32 completed attempts with no
request failures or unknown usage. Each packet combines independent previously
evaluated work items; this is a regression workload, not a full Gas City run or
new holdout. It covers five PR and three issue kind inputs, eight finding and
failure cases, eight ranking cases, and seven unique evidence cases (one appears
twice). Both arms receive identical original evidence and produce a joint
source-quoted report plus a source-preserving candidate investigation packet.

| Metric, 16 attempts per arm | Claude baseline | All Jev enabled |
| --- | ---: | ---: |
| Total elapsed time | 642.85 s | 404.57 s |
| Mean per packet | 40.18 s | 25.29 s |
| Claude calls | 32 | 16 |
| Claude tokens, including cache counters | 254,714 | 168,527 |
| Jev calls | 0 | 80 |
| Jev input tokens | 0 | 74,702 |
| Jev output tokens | 0 | 6,402 |
| Expected categorical answers matched | 107/108 (99.07%) | 106/108 (98.15%) |
| Entire packet passes all measured checks | 15/16 | 14/16 |
| Known matching candidate ranked first | 12/12 | 12/12 |
| Complete candidate/source retention | 16/16 | 16/16 |
| Report coverage, consistency and source-quote checks | 16/16 | 16/16 |

The combined workload used **37.1% less elapsed time and 33.8% fewer Claude
tokens**, with **one additional wrong categorical answer** (0.93 percentage
points lower accuracy). Entire-packet pass rate decreased by 6.25 percentage
points. Ranking positives are six unique cases repeated twice; four runs have
no gold top candidate and are scored for retention only.

The baseline makes one ranking call and one joint report call; treatment uses
five bounded Jev calls followed by one joint report call. These savings cannot
be attributed to each classifier individually: removing the Claude ranking call
is part of the comparison. There is no ranking-only ablation in this cohort.

## Quality and fallback detail

| Feature | Claude correct | Raw Jev correct | Final assisted correct | Questions requiring ordinary reasoning | New paired regressions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kind | 16/16 | 16/16 | 16/16 | 2 | 0 |
| Finding categories/pairs | 59/60 | 58/60 | 59/60 | 27 | 0 |
| Failure routing | 16/16 | 14/16 | 15/16 | 4 | 1 |
| Evidence assessment | 16/16 | 14/16 | 16/16 | 2 | 0 |

No confidently accepted categorical Jev answer was wrong under these frozen
expectations. All six raw Jev mismatches were routed to ordinary reasoning;
that reasoning recovered four. This does not make the combined system perfect:
its final answers are what the comparison scores.

- **Regression:** packet-06, first repetition, `failure-schema`. The expectation
  is `environment`; baseline returned that, while the fresh assisted report
  returned `missing_evidence`. On repetition two both returned the expectation.
  The first error remains counted; the successful repeat does not erase it.
- **Shared error:** packet-08, first repetition, a vague finding expected
  `unclear`. Both arms returned `missing_evidence`. Both answered correctly on
  the second repetition. The expected label was not changed after inference.

The original boundary-case ambiguity remains relevant. Exact label matches and
source-preserving reports are executable quality checks, not proof of broad
correctness, meaningful prose quality, or safe final review decisions.

## Timing, tokens and cost

Claude used the logged-in subscription CLI, Opus 5 at max effort; Jev used
1.13.0. The two repetitions reverse arm order. No other experimental model
cohort ran concurrently. Read-only inspection, documentation/harness edits and
small local tests overlapped the first repetition. Host load and service/cache
conditions were uncontrolled; several second-repetition baseline calls took
longer. Timings include CLI startup, all model calls and report/packet writing;
fixture proof execution was shared before the paired timer. They exclude GitHub
retrieval, runtime scheduling, code changes, and publishing.

Claude token breakdown is in [the cohort summary](combined-001/summary.json).
Jev adds 81,104 tokens measured with its tokenizer; these are reported separately.
The Claude subscription fee is unchanged, usage counters are not measured quota
debits, and no billing evidence establishes actual dollar savings.

## Full runtime build comparison

Both full-runtime attempts failed before any Jev decision stage was reached.
They used the existing isolated slugify fixture, the same patched local gc 1.4.2
and bd 1.3.0 binaries, the repaired local-origin precondition, and subscription
Sonnet 5 low configuration. The controller never reached the 1,200-second
workflow-wait phase in either attempt.

| Full runtime attempt | Elapsed including setup/cleanup | Terminal result |
| --- | ---: | --- |
| Baseline | 436.82 s | `gc init`: Beads initialization for rig `fixture` exceeded the internal lifecycle deadline. |
| All enabled | 1,040.30 s | Setup passed in 307.83 s; `gc sling` exceeded its 600-second dispatch deadline. |

Neither attempt produced an implementation or a completed workflow. Both original
fixtures retained their original tests; all three tests and all four independent
hidden checks failed with the unchanged implementation stub. These are failed
setup/dispatch outcomes, not generated-code quality scores or a speed comparison.
There were no observed workflow model-request events; token totals remain
**unknown/null**, not measured zero. No completed evidence, finding or failure
Jev helper report was found. Issue/PR adapter workflows were not run end to end.

Host load rose from about 49 to 74 during the treatment dispatch. Controller
`dolt-health` and `beads-health` orders also failed. The observation does not
isolate the cause of the slowdown or implicate Jev: no Jev decision stage was
reached. The normal city-stop command timed out; the supervisor subsequently
stopped, the experiment-owned remaining Dolt process received termination, and
that PID was verified absent. Unrelated processes were left alone. Raw runtime
logs, failed outcomes, original-fixture checks and cleanup evidence are retained
under [full-build-001](full-build-001/); see [the runtime summary](full-runtime-summary.json).

The evidence supports the combined work-packet tradeoff above. Full-build or
full-triage performance with all integrations active remains unestablished.

## Validation and reproducibility

Relevant integration/helper/harness checks passed 55 tests and 26 subtests.
Final targeted formula checks passed five tests and 29 subtests. The build
harness's 13 tests passed, and its added independent-quality regression test
passed: edited passing tests cannot disguise an unchanged implementation stub.
All five production CLIs passed the actual no-key auto-mode check.

The [combined audit](audit-001.json) reconciles 48 Claude calls and 80 Jev calls
against raw responses, verifies identical original state/questions across arms,
checks preserved accepted answers and source hashes, and verifies the actual
credential is absent from publishable artifacts. All commands, raw responses,
usage, failed expectations and timing remain available in [combined-001](combined-001/).
Across the combined and runtime cohorts, all **34 attempts** are retained.
See [per-feature attribution](feature-analysis-001.json), the [frozen protocol](PROTOCOL.md),
[frozen inputs](suite.json), and [append-only ledger](ledger.jsonl).

The [final audit](final-audit-001.json) also verifies all 80 treatment helper
reports used auto mode, identical runtime source snapshots, retained fixture
failures, completed cleanup, and credential absence across the final artifacts.

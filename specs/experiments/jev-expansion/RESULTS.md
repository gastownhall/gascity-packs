# Jev expansion results — September 20, 2026

We implemented all four proposed uses and evaluated the decisions plus a downstream report stage. The results support selective integration: resource savings alone did not establish quality preservation, and standalone gains often vanished when Claude still wrote the report.

## First implementation: categorical decisions

Each task used eight evaluation cases, twice per arm, with reversed order on the repeat. Kind cases are a previously evaluated real-data regression subset; the other tasks use authored challenge fixtures. Expected-answer counts below count questions, including finding-pair questions, not independent real-world tasks.

| Task | Expected answers: Claude / treatment | Claude tokens: baseline → treatment | Time: baseline → treatment | Token reduction | Time reduction | New paired regressions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| duplicates | 28/32 / 28/32 | 80,664 → 70,698 | 219.50 → 217.55 s | 12.4% | 0.9% | 0 |
| failure | 14/16 / 13/16 | 77,954 → 21,456 | 199.00 → 70.91 s | 72.5% | 64.4% | 1 |
| findings | 59/60 / 58/60 | 88,835 → 70,672 | 232.41 → 188.17 s | 20.4% | 19.0% | 1 |
| kind | 16/16 / 16/16 | 96,640 → 13,946 | 197.75 → 35.16 s | 85.6% | 82.2% | 0 |

Treatment includes fresh Claude fallbacks, never reused baseline outputs. Both new regressions arose in fresh fallback calls: a vague finding and an unexplained timeout changed from the expected `unclear` to `missing_evidence`. These outcomes count against treatment even though raw Jev was not the source of every error. [Boundary-case analysis](ADJUDICATION.md) preserves the wording and the frozen expectations.

## Downstream generated report

Two preselected evaluation cases per task were measured with Claude also producing a source-quoted report. Every report preserved question coverage, agreed with its decision values and quoted actual supplied text. These checks do not establish arbitrary prose quality or complete triage correctness.

| Task | Claude-token reduction | Time reduction | Decision for this implementation |
| --- | ---: | ---: | --- |
| duplicates | 0.69% | 8.83% | auto |
| failure | 3.62% | -8.62% | off |
| findings | -0.86% | -12.15% | off |
| kind | -0.43% | 0.89% | off |

Negative reduction means an increase. The generated-report test had only two cases per task and uncontrolled host, network and cache effects; sub-percent differences are not a reliable production speed claim. The [registered gate result](default-gate-001.json) keeps kind, findings and failure classification opt-in. The relationship classifier barely improved consumption; it was replaced in the workflow by a ranking-only implementation, evaluated separately below.

## Why the ranking follow-up differs

The first duplicate experiment spent fallback calls distinguishing related from unrelated even though the consumer needs an investigation order. As descriptive analysis, raw Jev already ranked the known matching candidate first in 12/12 positive repeated cases. We retained that experiment and froze ten new ranking fixtures before testing a narrower operation.

The revised helper uses one Noul similarity question per candidate, stable sorting in code and the same deterministic source-preserving renderer as the baseline. It produces an investigation packet, not a duplicate verdict or generated rationale. Every candidate remains available; the original triager must confirm the shared trigger or requirement before declaring a duplicate. Low similarity is not treated as a reason to ask a second model merely to sort a list. Service failures still use ordinary investigation.

The ranking evaluation used eight new authored cases, twice per arm: six had a known matching candidate and two did not. Both arms ranked the expected match first in **12/12 positive repeated cases** (six unique positive cases). All candidate IDs and source text were retained in all 16 runs per arm, including unmatched/ambiguous cases. No duplicate verdict was generated and there were no failed attempts or unknown usage.

| Ranking plus rendered handoff | Claude baseline | Jev |
| --- | ---: | ---: |
| Total elapsed time, 16 runs | 193.09 s | 10.77 s |
| Mean per run | 12.07 s | 0.67 s |
| Claude tokens, including caches | 79,835 | 0 |
| Jev input / output tokens | 0 / 0 | 10,624 / 820 |
| Known-match top-1 | 12/12 | 12/12 |
| Candidate/source preservation | 16/16 | 16/16 |

This component took **94.4% less time (17.9× speed ratio)** and avoided all Claude ranking tokens. It still consumed Jev tokens. The small two-case pilot was separate and passed both arms; it is excluded from these totals. See [ranking metrics](rank-evaluation-001/summary.json) and [the frozen protocol](RANK-PROTOCOL.md).

**Default change:** `github-issue-triage` now sets `jev_duplicates_mode=auto`. It calls the ranking helper when a key is configured and otherwise preserves ordinary investigation without extra retrieval for Jev. Set the mode to `off` to disable it. Existing kind, evidence, finding/pair and failure classifiers remain opt-in. PR kind support is implemented and also opt-in.

This ranking gate checks the output the application actually uses—inspection order and complete evidence retention. It does not relabel or erase the earlier relationship-classification experiment, establish duplicate precision on production traffic, or claim the whole triage workflow is 17.9× faster.

## Evidence regression rerun

The unchanged seven-case evidence suite ran twice per arm with subscription Sonnet 5 at low effort and Jev 1.13.0. Claude produced 13/14 valid correct results; treatment produced 14/14. One baseline returned prose before the correct JSON, which violated the strict output contract. That failed attempt and its usage remain in the totals; the historical harness continued the schedule after failure, a recorded difference from the newer stop-on-failure runners.

All-attempt totals: Claude baseline 102,668 tokens and 177.11 seconds; treatment 14,612 Claude tokens and 48.71 seconds, including two fallbacks. This is not a clean all-success paired rerun. Evidence assistance remains opt-in, and its complete build-workflow benefit remains unmeasured.

## Cost, scope and reproducibility

Claude used the existing Max subscription through the CLI, not generative API keys. Usage totals include input, output, cache reads and cache creation. Those counters are not measured subscription quota debits or dollar savings. Monthly subscription charges did not become smaller in this experiment; Jev usage is additional and its tokens use a different tokenizer. No actual billing reduction is established.

All cohorts used pinned models, identical state/rubrics across arms, captured commands/prompts/responses, source copies/hashes, immutable output directories and append-only ledgers. The expanded runner used Opus 5 at max effort; the evidence rerun used Sonnet 5 at low effort. Different tasks and models are not pooled into one speed figure.

Timings include fresh Claude CLI startup and local artifact work. Ranking includes the rendered handoff, but excludes initial GitHub retrieval and subsequent full issue investigation/comments. The generated-report benchmark includes one report-generation call per arm. None is a measured full Gas City build or triage workflow; existing full-build runtime blockers were not resolved by these tests. Early integration tests overlapped the first decision cohort; load, network and shared caches were uncontrolled and are recorded.

The ranking and non-kind challenge datasets are small authored fixtures. Kind uses public snapshots whose exact title/body matched unauthenticated GitHub responses. Neither the sample nor the quality checks prove universal equivalence.

Artifacts: [protocol](PROTOCOL.md), [ranking protocol](RANK-PROTOCOL.md), [decision metrics](evaluation-summary-001.json), [report metrics](report-summary-001.json), [evidence rerun](evidence-rerun-001/summary.json), [public input checks](public-input-verification.json), [ledger](ledger.jsonl).


## Validation and audit

The expanded integration suite passed 132 tests and 9,435 subtests. Two
claim-command tests timed out at their existing two-second limits; their code
and the command are byte/AST-identical to the earlier failing baseline, with
[retained proof](known-timeout-verification.json). No timeout or claim behavior
was changed. Final targeted formula checks passed five tests and 20 subtests;
new helper/runner/retrieval checks passed 16 tests.

Actual CLI checks exercised public GitHub retrieval (20 candidates), 12 generic
no-key/off/assist paths, three ranking no-key paths, and live ranking/decision
calls. After model runs, the empty-candidate path was corrected to record a
code-computed empty result instead of a synthetic model response; requested
model/mode metadata was added. Nonempty question, scoring and rendering behavior
is unchanged, and cohort source copies retain the exact measured versions.

[Expanded-cohort audit](verification-001.json) reconciles 160 arm attempts,
124 Claude calls and 80 Jev calls with raw telemetry, identical inputs and
rubrics, and absence of the actual credential in artifacts. The separate
[ranking/evidence audit](rank-evidence-verification-001.json) covers the ranking
cohorts and the evidence rerun, including the failed baseline. Across all six
live cohorts this turn there were 224 arm attempts, 158 Claude calls and 112
Jev calls. Counter totals include every recorded failed attempt.

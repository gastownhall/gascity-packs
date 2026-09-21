# All-enabled evaluation, registered before inference

User direction: enable every implemented Jev path and measure/report quality loss,
not just successful or default-eligible paths. All modes default to auto when a
key is configured. Retain confidence fallbacks, original evidence, review gates,
and publication policy. Defaults are an explicit user choice, not a quality claim.

## Combined work-packet regression

Eight frozen packets combine the prior public kind snapshots (five PRs, three
issues), eight authored finding cases, eight failure cases, eight ranking cases,
and seven evidence cases (empty-string appears twice). Inputs and expectations
are reused regression cases, not an independent holdout. Components within a
packet concern independent work items; this is a controlled combined workload,
not an actual end-to-end Gas City run. Fixture proofs execute locally once before
paired measurements; their exact hash-bound state is shared by both arms.

Two repetitions per packet per arm = 32 attempts. Reverse order on repetition
two. No model-call concurrency. Baseline: subscription Opus 5 max orders the
candidate list and produces one joint report answering kind, evidence, finding
categories/pairs, and failure routing. Treatment: invoke all five production
Jev helpers using auto, then the same Opus report contract. Accepted decisions
are preserved; uncertain decisions are freshly reasoned in that call. Both arms
receive the complete ranked candidate packet; all original findings stay in
state. The components are batched into one report to avoid giving the baseline
an artificial requirement to make one Claude call per classifier.

Jev 1.13.0; thresholds mirror defaults: .85 evidence and issue kind, .90 PR kind,
finding categories and failure, .95 floor for finding pairs. Ranking preserves
all candidates and supplies no duplicate verdict. No prompts include expected
answers, historical labels, or the credential. Public snapshots previously
matched unauthenticated GitHub responses exactly (see ../jev-expansion/public-input-verification.json).

Measure total and per-call wall time, Claude input/output/cache-read/cache-create
counters, Jev input/output, fallback counts, operational failures, exact expected
answer matches per feature, paired regressions/improvements, ranking top-1 on
known positives, candidate/source preservation, report coverage, decision
consistency, and exact source-quote provenance. These report checks do not prove
arbitrary prose quality. Retain all attempts, failures and mismatches. Continue
the declared schedule after operational failures; no automatic retries or tuning.
Missing telemetry is unknown, not zero. Do not pool this run with older cohorts.

## Full runtime comparison

Run one fresh build-basic baseline and one all-enabled treatment on the existing
slugify fixture, using the same Sonnet 5 low subscription configuration and
locally tested runtime binaries (gc 1.4.2 tmux fix, bd 1.3.0 read-only preflight
fix). Use the repaired local-origin preflight and isolated gate Python. Do not
change global runtimes or touch user databases. Explicitly set evidence, findings,
and failure modes off in baseline and auto in treatment. Kind/ranking are issue
and PR adapter features and do not apply to this build workflow.

Cap workflow wait at 1,200 seconds per arm, setup at 900 and dispatch at 600.
Continue the paired schedule after a failed arm; no retry until green. No public
GitHub writes, pushes, or PR creation by the evaluated workflow. Record terminal
status, completed stages, unchanged fixture and independent hidden checks, all
observed Claude telemetry, Jev delivery/usage, and cleanup. A timeout, failed
proof or unexecuted integration is not a completed build. Compare successful
build latency only if both finish the original task with equal independent
quality; failed-run consumption is reported separately. If a concrete runtime
failure makes progress impossible, preserve evidence and terminate that attempt.

Record host load and any concurrent work. Timings are single-machine observations,
not controlled production estimates. Claude uses the fixed subscription; its CLI
list-price estimates do not establish billing or quota savings. Jev adds usage.

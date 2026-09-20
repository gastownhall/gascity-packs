# Jev kind triage: real Gas City issues and PRs

On September 20, 2026, we tested the same use case Julian described: let Jev
classify kind and compare it with Opus at maximum effort. On **32 real Gas City
items, raw Jev agreed with Opus on 31 (96.9%)**. At the frozen 0.85 confidence
threshold, Jev handled 25 items directly and sent seven to fresh Opus calls.
The final treatment agreed with the independent baseline on all 32 items.
This supports using the pack's opt-in kind assistance with fallback on this
sample. It does not validate priority or adopt-pr complexity decisions.

## Evaluation results

| Measurement | Opus baseline | Jev with Opus fallback |
| --- | ---: | ---: |
| Completed classifications | 32/32 | 32/32 |
| Agreement with independent Opus baseline | — | 32/32 final; 31/32 raw Jev |
| Match with existing repository label | 31/32 | 31/32 final; 30/32 raw Jev |
| Claude calls | 32 | 7 |
| Claude tokens, including cache categories | 173,146 | 38,183 |
| Jev input / output tokens | — | 42,341 / 1,735 |
| Total classification time | 364.42 s | 104.98 s |
| Median classification time | 10.94 s | 0.18 s |
| Failed attempts / missing telemetry | 0 / 0 | 0 / 0 |

Including all seven fallbacks, treatment used **77.9% fewer Claude tokens**
and **71.2% less classification time**. It avoided Claude on 25/32 items
(78.1% coverage), and all 25 direct Jev decisions agreed with Opus. Six of
the seven fallback cases already had matching raw Jev decisions; the fixed
threshold traded some savings for caution. We did not retune it after seeing
the results.

Claude token detail:

| CLI usage category | Baseline | Treatment fallback |
| --- | ---: | ---: |
| Input | 64 | 14 |
| Output | 6,706 | 2,795 |
| Cache read input | 79,136 | 17,311 |
| Cache creation input | 87,240 | 18,063 |
| Total | 173,146 | 38,183 |

These are observed token counters from the Claude Max subscription CLI, not
cash savings or a measurement of subscription quota debits. Jev tokens use a
different tokenizer and are reported separately. We did not use generative
API credentials. Retained CLI dollar estimates are not actual subscription
charges.

## Quality and boundary cases

| Existing repository kind | Cases | Raw Jev / Opus agreement | Fallbacks |
| --- | ---: | ---: | ---: |
| Bug | 8 | 8/8 | 0 |
| Feature | 8 | 7/8 | 4 |
| Docs | 8 | 8/8 | 0 |
| Chore | 8 | 8/8 | 3 |

The sole model disagreement was [PR #6405](https://github.com/gastownhall/gascity/pull/6405),
which exposes previously dropped Bead fields. Opus and the repository called
it feature; Jev called it bug with 0.37 confidence. Its title describes a new
feature, while its body describes data lost on decoding. Both interpretations
have support in the supplied text. The fallback produced feature, matching
the baseline, at 17.11 seconds versus the baseline's 9.14 seconds. This is a
useful example of fallback preserving agreement while making one item slower.

Both models called [PR #6392](https://github.com/gastownhall/gascity/pull/6392)
feature, while the repository label was chore. The PR adds a typed result for
internal cancellation paths while preserving signal behavior. That is an
internal API versus user-visible capability boundary in the rubric; neither
agreement nor Jev's 0.89 confidence establishes that feature is correct.

All fallback cases are retained, including ones where Jev already agreed:

| Item | Raw Jev | Confidence | Final treatment / baseline |
| --- | --- | ---: | --- |
| [#6376](https://github.com/gastownhall/gascity/pull/6376), mail superseding and blocker retirement | feature | 0.64 | feature |
| [#6386](https://github.com/gastownhall/gascity/pull/6386), teardown test synchronization | chore | 0.73 | chore |
| [#6321](https://github.com/gastownhall/gascity/pull/6321), configuration environment identity | feature | 0.70 | feature |
| [#6389](https://github.com/gastownhall/gascity/pull/6389), security dependency update | chore | 0.62 | chore |
| [#6399](https://github.com/gastownhall/gascity/pull/6399), container dependency pins | chore | 0.76 | chore |
| [#6423](https://github.com/gastownhall/gascity/issues/6423), order liveness detection | feature | 0.77 | feature |
| [#6405](https://github.com/gastownhall/gascity/pull/6405), Bead field projections | bug | 0.37 | feature |

This is agreement with an independent model call, not adjudicated accuracy.
Existing repository labels provide a second imperfect reference. Julian's
reported 96% motivated this experiment; our 96.9% is a separate measurement
on our own frozen data.

## Method and limits

The [protocol](kind-real-dataset-001/PROTOCOL.md) froze 36 public items before
inference: four pilot items and 32 evaluation items, with no overlap. Evaluation
contains nine issues and 23 PRs, eight items per kind. Selection took the most
recent eligible items by number within each kind; `kind/enhancement` normalized
to feature. Raw candidate projections, queries, exclusions, and the collection
script are retained. We made no GitHub writes.

Both arms received the same untruncated title/body and `gc.kind-question.v1`
rubric. Repository labels and reference answers were withheld. Original title
prefixes were preserved; 24/32 evaluation titles contain conventional kind
hints. This is a balanced sample of already labeled items, without unlabeled
or out-of-taxonomy examples. The small sample and title hints limit conclusions
about routine production traffic.

The pilot resolved `opus` to **claude-opus-5**; evaluation pinned that model
with `--effort max`, Claude CLI 2.1.278, and no tools. Jev was pinned to
**jev-1.13.0** at threshold 0.85. Each item had one call per arm, with order
alternating by item. Every fallback was a fresh Opus call, never a reused
baseline answer. We made no prompt or threshold changes between pilot and
evaluation. There were no failed calls or retries. Including the pilot, the
experiment made 43 Claude calls and 36 Jev calls across 72 arm attempts.

The separate four-item pilot had 4/4 raw and final agreement, no fallbacks,
20,789 Claude baseline tokens, and 5,330/217 Jev input/output tokens. Total
time was 48.52 seconds for baseline and 0.68 seconds for treatment. Pilot
results are excluded from the evaluation totals above.

Timing covers state preparation, inference, optional fallback, validation,
and intermediate artifact writes. It includes fresh Claude CLI startup and
excludes GitHub acquisition and the rest of Gas City's triage workflow.
An existing worker session could amortize CLI overhead. Host load, network,
and shared prompt caches were uncontrolled; the manifest records initial
load and verification records load after completion. Each case ran once per
arm, so these data do not measure repeatability or tail latency. No full-pack
token reduction, output quality, or execution speedup follows from this test.

## Artifacts and reproduction

- [Evaluation metrics and all 32 pairs](kind-evaluation-comparison-001.json)
- [Evaluation manifest and source hashes](kind-evaluation-paired-001/manifest.json)
- [Evaluation attempt ledger](kind-evaluation-paired-001/ledger.jsonl)
- [Pilot metrics](kind-pilot-comparison-001.json)
- [Frozen dataset](kind-real-dataset-001/suite.json) and [collector](kind-real-dataset-001/collect.py)
- [Audit of raw telemetry, matching inputs, frozen sources and credential absence](kind-verification-001.json)
- [Paired runner](../../../scripts/jev_kind_ab.py), [summary generator](summarize-kind.py), and [audit script](verify-kind.py)

Suite SHA-256: `7f31c5d6b0f857e2aa5e4d0b478b36ffa08c7b4e3364a2dfa85066048545900a`.
The runner and its imported source files are copied into each cohort with
hashes, based on repository revision `357a608c4ca115fe125d06fdd032eeafa6b6d275`.
Exact requests, prompts, commands, responses, stdout/stderr, model usage and
results are in the per-attempt directories. Outputs are never overwritten.
Focused harness/helper/telemetry tests passed: 27 tests before live inference.

From the repository root, with the Jev key privately injected into
`TYPESAFE_API_KEY` and Claude logged into the subscription:

```sh
python3 scripts/jev_kind_ab.py \
  specs/experiments/jev-evidence-routing/kind-real-dataset-001/suite.json \
  --out /absolute/new/kind-evaluation --split evaluation \
  --model claude-opus-5 --effort max --jev-model jev-1.13.0 --threshold 0.85
python3 specs/experiments/jev-evidence-routing/summarize-kind.py \
  /absolute/new/kind-evaluation --out /absolute/new/kind-summary.json
```

The pack's kind assistance remains opt-in. These measurements support trying
that bounded replacement with the existing fallback, while retaining the
ordinary investigation, priority, complexity and human approval steps.

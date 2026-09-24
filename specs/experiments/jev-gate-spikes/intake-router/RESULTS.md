# Intake-router spike: results

The question was whether Jev, reading only the request text, can route small, well-specified
work to a compact path without under-triaging big or risky work. On this small offline sample it
did: the routing rule caught 6 of the 10 compact PRs and sent none of the 50 larger ones to the
compact path. The sample is small, the ground truth is a proxy, and PR descriptions give away more
than a real intake request would, so treat this as a promising signal and not as validation.

Everything here is reproducible from the files in this directory. `PROTOCOL.md` sets the rules
(frozen before any Jev call, with one dated amendment made after the pilot). `prs.json` holds the
inputs and ground truth, `calls/<run>/` holds every request and response, `results.json` holds all
metrics and the per-PR rows, and the scripts are `collect.py`, `run_jev.py` and `analyze.py`.

## Setup in brief

- **Data:** 70 merged PRs to `main` in `gastownhall/gascity`, snapshot at 2026-09-24T16:21Z.
  Five PRs were excluded: 4 release backports and 1 sync merge. The 10 oldest PRs were the pilot
  set and the 60 newest were the evaluation set.
- **Ground truth (proxy):** `compact` means at most 3 files and at most 80 changed lines, with no
  risky path. `deep` means more than 15 files, more than 600 lines, or a change that touches
  design docs, `internal/api`/OpenAPI, schemas or migrations. Everything else is `standard`. The
  evaluation set has 10 compact, 30 standard and 20 deep PRs.
- **Jev input:** one `jev-1.13.0` call per PR. The state is the PR title and body plus the body of
  any issue the PR closes, capped at 6000 characters. The call asks four questions: `size`,
  `needs_design`, `risky_surface` and `well_specified`.
- **Rule under test:** a PR routes to compact only when the most likely size is compact with
  confidence ≥ t, `risky_surface` is none and `needs_design` is no.

## Headline (evaluation set, n = 60, frozen questions, single run)

| t | routed compact (coverage) | under-triage | over-triage (of 10 gt-compact) | compact precision / recall |
|---|---|---|---|---|
| 0.6 | 6 (10%) | **0** (0 deep) | 4 | 1.00 / 0.60 |
| 0.7 | 6 (10%) | **0** | 4 | 1.00 / 0.60 |
| 0.8 | 6 (10%) | **0** | 4 | 1.00 / 0.60 |
| 0.9 | 6 (10%) | **0** | 4 | 1.00 / 0.60 |

The threshold made no difference because all six routed PRs had size confidence of 0.90 or more.
The routed PRs were #6411, #6502, #6455, #5871, #6436 and #6450: a CI timeout bump, a mail
constant fix, a lint stub fix, a Dolt pool setting and two 5-line doc edits.

**Under-triage cases:** none at any threshold.

**Over-triage** (compact PRs that were routed up):

| PR | Change | What Jev said |
|---|---|---|
| #5913 | socket path length guard, 63 lines | standard, confidence 1.00 |
| #6545 | test wait fix, 35 lines | standard, confidence 0.85 |
| #6480 | test stdout fix, 34 lines | standard, p = 0.53 |
| #6453 | 5-line doc edit | compact, but confidence only 0.39 |

**Secondary variants** (both chosen before the run):

- **Also require `well_specified = clear_acceptance_criteria`:** routes 5 PRs with 0 under-triage.
  It drops #6450, which Jev called partially specified. This question barely discriminates: 57 of
  60 PRs came back as clear.
- **Use `P(compact) ≥ t` in place of argmax + confidence:** at t = 0.6 it routes 7 PRs with 0
  under-triage (it adds #6453). At t ≥ 0.7 it routes the same 6 as the primary rule.

**Near misses.** In each of these cases only one guard stopped a wrong compact routing:

- **#6460** (standard, 515 lines, 3 files): Jev said size compact with P = 0.89 and confidence 0.82.
  Only `risky_surface = security_or_auth` blocked it. At t ≤ 0.8, the size answer alone would have
  under-triaged it.
- **#6467** (standard, 140 lines): Jev's most likely size was compact, but the confidence of 0.35
  blocked it.

So the safety comes from combining the guards, and no single question provides it on its own.

**Size confusion matrix** (rows are ground truth, columns are Jev's most likely size):

| gt \ Jev | compact | standard | deep |
|---|---|---|---|
| compact (10) | 7 | 3 | 0 |
| standard (30) | 2 | 28 | 0 |
| deep (20) | 0 | 10 | 10 |

Overall agreement is 75%. Jev never called a deep PR compact. It did call half of the deep PRs
standard, several of them with confidence of 0.98 or more: #5990, #6534, #6518 and #6031. Many of
those are "deep" only because of a path rule, such as a 184-line change under `internal/api` or a
design doc added alongside a fix. The request text does not reveal that. **Do not use these
questions to route deep versus standard.**

The answer distributions were `risky_surface` none 31, security 12, persistence 9, API/schema 8,
and `needs_design` no 49, yes 11.

**Cost:** 125,518 input tokens and 11,139 output tokens for the 60 calls, about 2.1k tokens per
PR. Latency was 22.4 s in total, with a median of 0.36 s and a maximum of 0.76 s per call. No call
failed and none needed a retry.

## Pilot, reported separately (10 PRs: 1 compact, 5 standard, 4 deep)

- **pilot-1:** HTTP 422. The `score` criteria must be a list, not an object. There were no answers.
- **pilot-2 (v2 wording):** routed 3 PRs compact, and **all 3 were under-triage.** They were
  standard PRs of 125 to 368 lines that the description made sound small. Size agreement was 2/10.
- **pilot-3 (v3 wording, then frozen):** tightened the compact level ("a few lines in one spot",
  "judge by implied edits not tone", "when between two levels pick the larger"). It routed 0 PRs
  compact, with 0 under-triage, and missed the single compact pilot PR. Size agreement was 4/10.

The wording of the size rubric decided whether this worked. The v2 wording would have been unsafe.

## Secondary arm B: issue text only (n = 10 eval PRs that close an issue)

This arm is closer to a real intake request, because it has no post-hoc PR description. It routed
1 PR compact (#6411, correct), with 0 under-triage, and missed 1 of the 2 compact PRs. Size
agreement fell to 60%. **#6546** (deep, 958 lines, 18 files) came back with compact as the most
likely size (P = 0.60). A low confidence of 0.39 and a security flag stopped it. This is the case
that most weakens confidence in real intake use.

## Verdict

- **Viable as a conservative compact-path gate, as a next step toward a live trial.** It meets the
  bar set in advance: zero deep under-triage, at most 1 under-triage per 20 routed, and at least
  half of the compact PRs recovered.
- **The evidence is thin.** Zero errors in 6 routed PRs gives a one-sided 95% upper bound of about
  39% on the under-triage rate among routed PRs. It rules out only a very bad gate.
- **Coverage is low.** Only 10% of PRs took the compact path, because only 17% of recent gascity
  PRs are compact by this proxy. The gain is modest.
- **Keep every guard.** The size answer is persuaded by descriptions that sound small (pilot-2,
  #6460 and #6546). Keep the risk and design guards and a confidence floor, and treat t = 0.8 as
  the floor instead of 0.6.

## Limitations

- **The ground truth is a proxy.** Line and file counts include tests and generated files. The
  path rules are crude: any `internal/api` file counts as an API contract. The 80-line cutoff is
  arbitrary. Review rounds were recorded but not used.
- **The request text leaks the outcome.** Most requests are PR descriptions, often written by an
  agent after the work was done. They describe the implementation, the tests, and sometimes state
  "no API/schema changes." A real intake request carries less signal, and arm B (n = 10) suggests
  size accuracy drops.
- **n is small:** 60 PRs evaluated, only 10 of them compact. The data comes from one repo, with a
  few authors dominating.
- **One sample per PR.** Answer stability across repeated calls was not measured.
- **The wording was tuned on a pilot with only one compact PR,** so the effect of that tuning on
  coverage was not measured before freezing.

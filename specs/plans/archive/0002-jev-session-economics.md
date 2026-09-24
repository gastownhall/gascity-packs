# Jev as a session router, not a cheaper judge

Status: superseded by [0003](../0003-gascity-jev-redesign-design.md), which
records the decisions taken. Kept for its cost analysis; nothing here is
implemented.

## The observation that changes the problem

In the first complete `build-basic` A/B (see
[jev-operator-path](../../experiments/jev-operator-path/README.md)), the Jev arm
ran 14% longer even though every Jev call took under a second. Per-session
telemetry from both runs explains why:

- Claude cost is almost entirely *session overhead*. Output was 0.5% of all
  tokens. Every request starts with ~49.5K tokens of context and the median
  request carries ~60K, so cost ≈ requests × ~60K. The baseline's `implement`
  session produced 4,419 output tokens.
- Classification was never a cost center. A Jev decision inside a Claude
  session can save at most one turn (~60K tokens) and costs several turns to
  prepare. Today's integration keeps every Claude review and adds Jev on top —
  the cascade configuration in which, as with speculative decoding when the
  expensive stage always verifies, total cost can only rise (Leviathan et al.,
  <https://arxiv.org/pdf/2211.17192>).

We have been treating Jev as a cheaper judge inside agent steps. Treating it as
a **router that decides which agent sessions exist** makes large savings
possible, because each deleted session removes ~0.5–1.6M tokens and 20–220 s,
while a Jev decision costs a few thousand Jev tokens and under a second.

## Where the baseline's cost went

Each `build-basic` step is a fresh Claude session. Classified by what its
prompt asks for (baseline run, 16.6M tokens, 1,103 s):

| Kind | Steps | Tokens | Wall time |
| --- | --- | ---: | ---: |
| Generative (only an agent can do it) | requirements, plan, decompose, implement, summarize, simplicity review, finalize | 51% | ~63% |
| **Mechanical** (a script can do it exactly) | prepare, prepare-worktree, close-source-anchor, do-work latch, review setup, review finalize, publish no-op | **25%** | ~22% |
| Categorical judgment | plan-review, acceptance lane, test-evidence lane, synthesis, apply-findings | 19% | ~15% |
| Background maintenance | `bd` pack `mol-dog-stale-db` order spawning LLM "dog" sessions | 6% | — |

Mechanical steps are also where the defects come from. Every non-infrastructure
failure in this experiment series was an agent doing bookkeeping: a placeholder
upstream hash that passed validation (baseline 005), a skipped per-task summary
file that failed the drain yet let the build pass (full-build-003 baseline), and
a wrong agent-computed SHA-256 that cost a finding-and-fix cycle (full-build-003
Jev arm).

## What Gas City already allows (verified on release/v1.5.0)

A mechanics probe in a disposable city (no LLM sessions) confirmed:

1. **Script workers.** A pack agent with `prompt_mode = "none"`,
   `lifecycle = "one_shot"` and a shell `start_command` claims a routed step via
   `gc hook --claim --json`, works, sets `gc.outcome=pass` and closes it.
   ~150 ms session start; parallel up to `max_active_sessions`.
2. **Data-driven fanout.** A step's `gc.output_json` (an object such as
   `{"items":[...]}`) drives `on_complete` fanout; an empty list closes `pass`
   and spawns nothing; per-item fields select bond steps via `condition`.
3. **Event orders.** An exec order on `bead.closed` runs a script with `gc` on
   PATH — enough to re-sling a larger formula. It is not told which bead
   closed and fires in batches.

Constraints found: `waits_for` does not block, and nothing but
`workflow-finalize` waits for fanout sinks, so any synthesis that must follow
gated lanes has to live inside the same bond item (one item whose fields select
lanes, plus a synthesis template step that needs them — untested).

## Proposal

### 1. Mechanics become script workers (no Jev required)

Route the seven mechanical steps to a `gc.scribe` script role that computes
hashes, creates worktrees, gathers the review context, checks the approval and
records paths deterministically. Estimated −25% tokens and −22% wall time, and
it removes the class of bookkeeping defects above. This is the first move
because it has no quality risk to calibrate.

### 2. Judgments move to the graph edge, promoted by evidence

A `gc.judge` script worker runs deterministic checks first (tests pass,
protected files unchanged by hash — the question Jev scored 0.34 on is a
one-line hash comparison), then Jev on what remains. It writes a fanout item
naming only the lanes still needed; confidently settled lanes are never
spawned. Estimated −41% tokens combined with step 1.

Promotion is gated by data the current integration already produces. Today's
layered mode is effectively **shadow mode**: every run records Jev's verdict
and the Claude reviewer's conclusion for the same criterion (see
`test-evidence-report.md`). Log those pairs, and let a lane skip only after its
confident Jev accepts have been confirmed by reviewers enough times — zero
misses in about 60 accepts bounds the false-accept rate below 5% at 95%
confidence (rule of three), ~300 for 1%. Selective-prediction work sets
thresholds this way on held-out labels (Geifman & El-Yaniv,
<https://arxiv.org/abs/1705.08500>), and calibration degrades under shift
(Ovadia et al., <https://arxiv.org/abs/1906.02530>), so keep a sampled audit
after promotion.

### 3. A pre-run router picks the process depth

Before slinging, ask Jev triage-style questions that count *what the work
needs*, not what the answer is — the Emergency Severity Index asks how many
resource types a patient needs, and levels may only move up
(<https://media.emscimprovement.center/documents/Emergency_Severity_Index_Handbook.pdf>).
Here: does it touch a high-risk surface; is it fully specified; does it need
design, migration or several packages? Route to `build-compact` (one
implementation session, deterministic verification, one review), `build-basic`,
or design review plus the full lifecycle. Uncertain answers default up.
Pre-run routers pay only the router's cost (RouteLLM,
<https://arxiv.org/html/2406.18665>); single agents match or beat multi-agent
pipelines on single-issue coding tasks (Kim et al.,
<https://arxiv.org/abs/2512.08296>; Agentless,
<https://arxiv.org/html/2407.01489>).

Escalation is up-only and automatic: a failed compact verification closes as
fail and an event order re-slings the fuller formula. Nothing is pushed before
verification (Speculator's output-commit rule,
<https://people.eecs.berkeley.edu/~brewer/cs262/speculator-nightingale.pdf>).
Estimated compact cost is ~3.7M tokens versus 16.6M; it stays cheaper on
average unless more than ~78% of compact routes escalate.

## Uncertainties and how to settle them

| Claim | Status | Decisive test |
| --- | --- | --- |
| Session count drives cost | observed in two runs | holds across more runs |
| Mechanics as scripts: −25% tokens, −22% time, fewer defects | estimate | implement step 1; run ≥3 order-balanced pairs |
| Gated lanes keep review quality | untested | shadow-log Jev/reviewer pairs; promote at the bound |
| Router accuracy for compact work | untested | offline: route historical items, compare against actual diff size and review rounds |

Cache reads dominate the token totals and are billed far below uncached input,
so token percentages overstate dollar savings; wall time and request counts are
the more faithful measures for a subscription-backed factory.

The strongest objection: review lanes may catch specification errors no test
or classifier sees, and "would review have found something?" has no cheap
ground truth. Shadow logging answers it with the reviews we already pay for,
and step 1 does not depend on it.

# gascity-jev redesign: Jev replaces Claude work

Status: design settled in a grill session on 2026-09-24; nothing implemented yet.

`gascity-jev` becomes an overlay on `gascity` whose Jev gates decide, from
deterministic receipts, whether Claude sessions run at all. Jev acts on its own
in confident bands, Claude handles only the uncertain middle, every decision is
logged, a random audit sample measures misses, and a miss pauses that gate until
its bands are refit. Before the gascity vs gascity-jev comparison, spikes decide
where the gates go. The comparison then runs Sonnet 5 workers on a mix of
planted-defect fixtures and real backlog items in a temporary city.

## Terms

- **Jev gate** — a Jev decision, made on deterministic receipts, that decides
  whether a Claude session runs at all. *Avoid:* advisory check, Jev review.
- **band** — a confidence range for one decision: *act* (Jev decides), *confirm*
  (Claude handles only this item), or *escalate* (full Claude path).
  *Avoid:* threshold level.
- **receipts** — deterministic facts gathered by code before Jev is asked: test
  runner output, file hashes, diff, which commands ran after the last edit.
  *Avoid:* evidence bundle.
- **overlay pack** — a pack that imports `gascity` and overrides only the stages
  it changes, instead of copying the whole pack. *Avoid:* fork, variant copy.
- **audit sample** — a random share of act-band decisions where the skipped
  Claude lane runs anyway so its verdict can be compared with Jev's.
  *Avoid:* shadow run.
- **decision log** — one record per Jev decision: question, answer,
  probabilities, band, thresholds, receipts used, and the later outcome.
  *Avoid:* telemetry, ledger.

## Why

The goal, in the user's words: "the whole point of jev is to use it for the
things its good at so we don't have to use a general purpose llm to do that work
more slowly and more expensively."

The current pack does the opposite. `gascity-jev/assets/jev-decisions.md` states
that no Jev result supplies approval, retry or mutation authority, and every Jev
prompt tells Claude to redo the full check. In the first complete build A/B
(`specs/experiments/jev-operator-path/full-build-003`), the Jev arm took 14%
longer; its two Jev-enabled review stages added 316 s while the Jev calls took
0.37 s. Measured cost is Claude session overhead (output was 0.5% of tokens;
about 60K context tokens per request), so a Jev answer only saves money when it
stops a session from running.

## Locked decisions

### 1. Jev authority: bands (Q1)

A Jev decision acts on its own in the confident extremes; Claude handles only
the uncertain middle items. The "no authority" rule in `jev-decisions.md` goes.

- Rejected — *single threshold per decision:* no single cut is lossless (a
  community email-filter study lost 5 of 231 real requests at its best
  threshold), and it gives no middle ground for Claude to resolve.
- Rejected — *keep advisory:* this is the current design, and it can only add
  cost.

### 2. Pack structure: overlay (Q2)

`gascity-jev` imports `../gascity` as `gc` and exposes its own `jev-`-prefixed
formulas that extend the base formulas and override only the gated stages, the
convention the `superpowers` pack already uses (`superpowers-build` extends
`build-base`). Overridden stages must keep the base stage's artifact contract.

- Rejected — *keep the full copy:* it differs from `gascity` in only 46 files,
  forces every base fix to land twice, and cannot sit beneath the other
  methodology packs.
- Rejected — *fold Jev into gascity:* puts experimental behavior into the pack
  production cities import.

### 3. Experiment workload (Q3)

Sonnet 5 workers, a mix of planted-defect fixtures and real backlog items, run
in a temporary city created for this work. Never use `~/chris-city`.

- Rejected — *real backlog only:* gives no ground truth for miss rates.
- Rejected — *synthetic fixtures only:* says nothing about cost and time on
  real work.

### 4. Band thresholds on day one (Q4)

Start acting immediately with conservative per-decision bands, log every
decision with its outcome, and refit bands from the log. Jev Choice answers are
known to be over-confident, so day-one act bands are narrow; local
recalibration on 50–300 labeled outcomes is expected to widen them.

- Rejected — *shadow first:* delays any benefit until labels accumulate.
- Rejected — *one global band:* a wrong skip costs far more on a review gate
  than on a kind label.

### 5. First gate: decided by spikes (Q5)

Run whatever spikes are needed to decide how best to use Jev before the
gascity vs gascity-jev comparison. Candidates identified so far: review-lane
gating from receipts (runs on every build; lanes cost about 2.7M of 16.6M
baseline tokens), an intake router that picks the formula depth, failure
routing after failed steps, and a pre-review diff screen (one Noul per rule and
hunk). The spikes choose the gate(s); the comparison measures them.

### 6. Measuring misses: audit sample (Q6)

On a random share of act-band decisions, the skipped lane runs anyway and its
verdict is recorded against Jev's.

- Rejected — *downstream signals only:* late and blind to problems nobody
  notices.
- Rejected — *fixtures only:* cannot show behavior on real tasks.

### 7. Audit rate: adaptive (Q7)

Per decision type: 30% of act-band decisions until 60 audited accepts, then 10%
until 300, then a 5% floor. Zero misses in about 60 audited accepts bounds the
miss rate below 5% at 95% confidence; about 300 are needed for 1%. The floor
keeps catching drift from new task types or a Jev model update. Savings figures
must account for audited runs.

- Rejected — *fixed 10%:* six times slower to the first bound.
- Rejected — *audit everything, then stop:* no alarm when work or model changes.

### 8. Response to a caught miss: circuit breaker (Q9)

The user judged the Jev-checking design sufficiently specified and left the
remaining details to the recommended design. An audited miss folds that
decision type's act band into confirm until its bands are refit, and records the
miss. Refitting is a script, not a manual step. Other decision types keep
acting.

## Routine choices

- **Decision log location (Q8):** each gated step bead carries its decision as
  metadata, and a JSONL file under the build artifact root records the same;
  a pack script aggregates across runs. (Settled by the agent per the user's
  Q9 direction.)

## Verified facts

- **Cost model (full-build-003):** output tokens were 0.5% of Claude tokens;
  every request began with about 49.5K context tokens (median 60K); about 25
  Sonnet sessions of about 10 requests each. By step kind, baseline tokens split
  51% open-ended generation, 25% mechanical bookkeeping, 19% categorical
  judgment, 6% background `bd` "dog" maintenance sessions.
- **Gas City 1.5 mechanics (probe in a disposable city, no LLM):** a pack agent
  with `prompt_mode = "none"` and `lifecycle = "one_shot"` claims and closes
  routed steps (about 150 ms start); a step's `gc.output_json` object drives an
  `on_complete` fanout, an empty list closes `pass` with nothing spawned, and
  per-item fields select bond steps via `condition`; exec orders fire on
  `bead.closed`. `for_each` must be `output.<key>`; `waits_for` does not block;
  only `workflow-finalize` waits for fanout sinks.
- **Jev capabilities (official docs via awesome-jev):** three question types
  (Choice up to 255 options with probabilities and confidence; Score 2–10
  levels; Noul yes/no probability); many questions per call share one state at
  almost no extra latency; `jev-1.13.0` is pinnable; 64K tokens per request
  with state plus longest question under 32K; about 100–500 ms per call.
- **Jev failure modes (official docs):** reads questions literally; weak at
  arithmetic, counting and multi-step indirection; accuracy falls as the state
  fills with unrelated detail; adversarial text in the state can steer it; no
  structural consistency between a question and its negation.
- **Community patterns (author-reported, small samples):** narrow receipt-based
  questions beat broad "is it done" questions (smithers: 0/12 false fires vs
  8/12); regex receipts first let Jev see only 17.7% of cases (jev-belay);
  calling Jev from inside an agent session did not pay (jev-judge-mcp: 0 calls
  in 150 tasks); always include an `unknown` option.
- **In-run evidence:** in full-build-003 the Jev evidence assessment called
  AC-1..AC-3 `supported` (0.90–0.98) and AC-4 (tests unchanged) `missing_evidence`
  at 0.34 — a question a hash comparison answers exactly. The findings step's
  one finding scored `residual_risk` at 0.29 and went to ordinary review, which
  classed it `required_fix`.

## Risks

- **Undetected misses between audits:** a gate may skip a lane that would have
  caught a specification error; mitigated by bands, audits and the circuit
  breaker, not eliminated.
- **Calibration drift:** a Jev model update or new task types can shift
  confidence; pin the model and keep the audit floor.
- **Untrusted state:** issue, PR and log text is attacker-controllable and can
  steer Jev; gates must rely on receipts for anything security-relevant.
- **Fanout join limits:** synthesis cannot wait on gated lanes except inside the
  same bond item; the gated-review shape needs a spike to confirm.
- **Small first samples:** early bands will be too cautious to save much.
- **Gas City 1.5 teardown:** `bd db-proxy-child` and Dolt servers outlive
  `gc stop` and can respawn; the temporary city's cleanup must be scoped to its
  own paths.

## Deferred

None.

## Open threads

- ~~Which gates the spikes select (Q5) and in what order.~~ Settled by the
  [gate spikes](../experiments/jev-gate-spikes/README.md), in this order:
  1. **Review-lane gate:** receipts first (tests pass, test file unchanged),
     then one "is there any input that violates this criterion?" Noul per
     acceptance criterion; the lane runs only for criteria above the act band
     (day one: P ≤ 0.15 acts).
  2. **Smell screen:** one call with a Noul per (rule, hunk); confirmed smells
     go straight back to the implementer, and a fully clean screen drops the
     smell checks from the simplicity lane (design review still runs).
  3. **Compact intake route:** size compact at confidence ≥ 0.8, no risky
     surface and no design need send work to a compact formula; everything else
     takes the full path. Expected coverage is about 10% of work.
- Effort level for the Sonnet 5 workers was not specified; previous runs used
  low effort.

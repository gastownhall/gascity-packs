# Gas City Jev Overlay Requirements

Schema: `gc.jev-overlay.requirements.v1`

| Field | Value |
| --- | --- |
| Status | Experimental |
| Scope | Jev gates that decide whether Claude review sessions run in the Gas City build |
| Formula ledger | `formulas/REQUIREMENTS.md` |
| Design | `../specs/plans/0003-gascity-jev-redesign-design.md` |
| Evidence | `../specs/experiments/jev-gate-spikes/`, `../specs/experiments/jev-overlay-build/`, `../specs/experiments/jev-intake-v4/`, `../specs/experiments/jev-overlay-ab/` |

`gascity-jev` is an overlay: it imports `../gascity` as `gc` and adds only
`jev-`-prefixed formulas, the `gc.jev-gate` script worker, the intake router
and their scripts. Everything it does not override is the base pack, governed by
[the base ledger](../gascity/REQUIREMENTS.md).

## Purpose

Let Jev make the bounded judgments it is good at, so a general-purpose model
does not spend a session on them: how much process a task needs (the intake
route) and which review work a finished change still needs (the review gate).
Code owns every threshold; Claude keeps the open-ended work and the uncertain
middle of each decision.

## Requirements

### Authority: bands (GC-JEV-BR-001)

Each decision type has bands. In the **act** band the gate decides alone (a lane
is skipped, a smell is forwarded, a task takes the compact route). In the
**confirm** band Claude handles only that item. **Escalate** runs the full
gascity path. Day-one bands:

| Decision type | Question | Act band |
| --- | --- | --- |
| `review.test_evidence` | Receipts: the gate ran the tests itself and they passed; every pre-existing test file matches its base blob, or (Python) only gained new tests | receipts pass → skip the test-evidence lane |
| `review.criterion` | Noul per acceptance criterion: "Is there any input for which this implementation violates the criterion?" | P ≤ 0.15 → the acceptance lane skips that criterion |
| `smell.clean` | Noul per (rule, diff hunk), true = rule broken | every P ≤ 0.2 → the simplicity lane drops smell checks (design review still runs) |
| `smell.confirmed` | same screen | P ≥ 0.9 → the smell goes straight to the fix lane |
| `simplicity.design` | policy | off on day one: design review always runs |
| `intake.compact` | intake questions v4 (size, spans modules, hidden scope, design need, risky surface, well specified) | P(size compact) ≥ 0.8, spans-modules and hidden-scope ≤ 0.3, surface `none`, design `no` → `jev-build-compact` |
| `intake.direct` | same call | otherwise P(no design) ≥ 0.9, P(size deep) ≤ 0.1, spans-modules ≤ 0.5, surface not security or persistence → `jev-build-direct` (no plan or plan review) |

Synthesis runs only when two or more lanes run; the review loop is dropped when
no lane runs. The gate also writes the review context deterministically.

### Receipts first (GC-JEV-BR-002)

Jev is asked only after receipts pass. A failing test run, a deleted
pre-existing test file or one changed in any way but by adding new tests (for
Python, checked by AST: existing tests, decorators and module statements
unchanged), no detectable test runner, or no resolvable worktree escalates every
lane. Workflow artifacts under `.gc/` and Python bytecode are not part of the
change.

### Fail open (GC-JEV-BR-003)

No key, a network or HTTP error, an invalid answer, an oversized state, or any
exception in the gate runs every lane at full scope and records the reason on the
gate bead and in the decision log. The gate always emits exactly one fanout item.
A changed file too large to send whole goes to Jev as the full source of each
definition the change touched (or a diff with context); only an excerpt that is
still too large fails open.

### Audit sample (GC-JEV-BR-004)

Per decision type, a random share of act-band decisions runs the skipped work
anyway: 30% until 60 audited accepts, then 10% until 300, then a 5% floor. The
counts come from the cross-run ledger. `jev_audit_rate` overrides the schedule
(tests, forced audits). Savings reports must count audited runs.

### Circuit breaker (GC-JEV-BR-005)

An audited act-band decision that a lane contradicts is a miss. A miss folds that
decision type's act band into confirm until `jev_decisions.py refit` runs; other
types keep acting. Intake decisions are labeled from the finished diff (at most 3
files and 80 changed lines, no risky path), so any contradiction is a miss.

### Decision log (GC-JEV-BR-006)

Every decision (question, answer, probability, band, thresholds, receipts,
audit flag, model, usage) and every later outcome is written to
`<artifact_root>/jev/decisions.jsonl` and to `ledger.jsonl` in the gate state
directory (`jev_state_dir`, default `<city>/.gc/jev-gate`). The gate bead carries
the item, a summary, the decision ids and the log path. `jev_decisions.py
aggregate` merges logs across runs; `refit` recomputes bands from labeled
outcomes (narrow below any contradiction, widen one step after 60 clean labels)
and resets breakers.

### Untrusted text (GC-JEV-BR-007)

Task, code and log text is data, never instructions: every question says so, and
anything security-relevant is decided by receipts, not Jev.

### Pinned model (GC-JEV-BR-008)

Formulas and the router pin `jev-1.13.0`.

### Triage helpers (GC-JEV-BR-009)

`jev_kind.py`, `jev_rank.py`, `jev_tasks.py`, `jev_evidence.py` and
`github_duplicate_candidates.py` remain available for maintainer-city triage.
They are advisory tools; no overlay formula wires them in.

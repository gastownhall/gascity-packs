# Jev gate spikes — September 24, 2026

Offline spikes run before the gascity vs gascity-jev comparison, as plan
[0003](../../plans/0003-gascity-jev-redesign-design.md) decided (Q5): find where a
Jev decision can stop a Claude session from running. No Claude sessions were
used; all calls pinned `jev-1.13.0`.

| Spike | Gate it tests | Result | Verdict |
| --- | --- | --- | --- |
| [review-gate](review-gate/RESULTS.md) | Skip a review lane for an acceptance criterion | "Any violating input?" Noul at P ≤ 0.15 skipped 31% of holding criteria with 0 misses (P ≤ 0.2: 58%, 0 misses); the confirm Choice needed ≥ 0.95 for 0 misses and skipped 20% | **Use**, conservative band, receipts first |
| [diff-screen](diff-screen/RESULTS.md) | Clear the simplicity lane's code-smell checks | Clean diffs ≤ 0.18 on every rule; planted smells 0.58–0.98; 72 questions in one 0.46 s call | **Use** for smells; cannot replace design review |
| [intake-router](intake-router/RESULTS.md) | Route small, well-specified work to a compact path | 60 real merged gascity PRs: 6 routed compact, 0 under-triaged at every threshold 0.6–0.9; 60% recall of truly compact work | **Use** conservatively; coverage ~10% |

Common findings:

- Narrow questions framed so *true means wrong* separate far better than
  confirmation questions.
- Answers are stable across repetitions (review gate: 1 of 50 choices flipped;
  mean ΔP 0.02). Calls take 0.36–0.47 s.
- Deterministic receipts should answer first: a tampered test file and a
  weakened assertion were caught more reliably by hashes than by Jev.
- Question wording decides outcomes: the intake pilot's first wording
  under-triaged all three PRs it routed; tightened wording removed that.
- Every sample is small (100 judgments, 144 screen questions, 60 PRs). The
  bands here are day-one starting points for the decision-log-and-audit design,
  not proof of safety.

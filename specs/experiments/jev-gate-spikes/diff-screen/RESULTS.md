# Diff-screen spike — September 24, 2026

Question: can one Jev call clear the simplicity/maintainability lane for a
change, by screening each diff against narrow rules?

## Setup

[`spike.py`](spike.py) screens twelve small diffs — six clean, six with one
planted problem each (debug output, commented-out code, a swallowed exception,
an unused import, a weakened test, duplicated logic) — against six rules. Every
(rule, diff) pair is one Noul framed so that *true means the rule is broken*;
all 72 questions go in one call. Two repetitions, model `jev-1.13.0`.

## Results

Each call took 0.45–0.47 s with 6,971 input tokens for 72 questions.

- Every planted problem scored high on its rule: debug output 0.97–0.98, dead
  code 0.94, swallowed error 0.94, duplicated logic 0.94, unused import
  0.89–0.90, weakened test 0.58–0.59.
- No clean diff scored above 0.18 on any rule (highest: a new test flagged
  0.16–0.18 for "test weakened"; an environment-variable change flagged
  0.14–0.17 for "unused import").
- A diff-level rule "skip the lane when every rule scores ≤ 0.2" skipped all
  clean diffs in both repetitions and let no planted diff through.

## What this supports

For mechanical code smells, one batched Jev call separates clean from
problematic diffs with a wide margin. The weakest rule, "test weakened", is
better handled by a receipt (compare test-file hashes and assertion counts),
which already caught this case in the review-gate spike.

## Limitations

- The planted problems are obvious; the real simplicity lane also judges design
  quality (naming, structure, fit with the codebase) that these rules do not
  cover. The screen can clear smells, not replace design review.
- Twelve tiny diffs; real diffs need one state per hunk to stay within Jev's
  context limits and to keep states narrow.

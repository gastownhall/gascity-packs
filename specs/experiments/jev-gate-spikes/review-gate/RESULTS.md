# Review-gate spike — September 24, 2026

Question: can Jev decide from receipts that a review lane need not run for an
acceptance criterion, without waving through a real defect?

## Setup

[`spike.py`](spike.py) judges ten slugify implementations against five criteria
from the `build-basic` work item. Four implementations are correct; six carry a
planted defect that **passes every visible fixture test** (non-ASCII letters
kept, a fixed separator list, a leading hyphen, digits dropped, 20-character
truncation, camelCase splitting). A deterministic oracle over 32 inputs gives the
ground truth per (implementation, criterion): 80 criteria hold, 20 are violated
across the two repetitions. Receipts run first in code: a tampered test file was
caught by the hash check and never reached Jev.

One Jev call per implementation (state: task, implementation, tests, test run),
two framings per criterion, each call run twice. Model `jev-1.13.0`.

- **confirm** — Choice: confirmed / contradicted / insufficient_evidence / unknown.
- **violate** — Noul: is there any input for which the code violates the criterion?

## Results

20 calls, 0.37 s mean latency, 42,050 Jev input tokens in total. Answers were
stable: the confirm choice flipped on 1 of 50 criterion pairs between
repetitions, and P(violation) moved by 0.021 on average.

| Gate rule (skip the review lane when…) | Holding criteria skipped | Misses |
| --- | ---: | ---: |
| confirm = confirmed, confidence ≥ 0.95 | 16/80 (20%) | 0 |
| confirm = confirmed, confidence ≥ 0.9 | 20/80 (25%) | 1 |
| confirm = confirmed, confidence ≥ 0.8 | 49/80 (61%) | 4 |
| **violate P ≤ 0.15** | **25/80 (31%)** | **0** |
| **violate P ≤ 0.2** | **46/80 (58%)** | **0** |
| violate P ≤ 0.3 | 62/80 (78%) | 4 |
| violate P ≤ 0.2 and confirmed ≥ 0.7 | 44/80 (55%) | 0 |

- The "is there any violating input?" Noul separates far better than the
  confirmation Choice, matching the vendor's advice to frame questions so that
  *true means wrong*.
- Requiring both framings to agree adds little over the Noul alone.
- The misses are the two subtlest defects: non-ASCII letters kept (V04, C2) and
  a leading hyphen on inputs that start with punctuation (V07, C3). Jev was
  confidently wrong on both (confirmed at 0.80–0.90; P(violation) 0.23–0.28).
- The margin is thin: the lowest P(violation) on a violated criterion was 0.23,
  while the median on holding criteria was 0.18.
- As a detector, the Noul flagged 13 of 20 violations at P ≥ 0.5.

## What this supports

A day-one act band of **P(violation) ≤ 0.15** would skip about a third of the
per-criterion review work on this fixture with no misses, leaving a 0.08 margin
to the nearest miss. That is a conservative starting band for the
decision-log-and-audit design in plan 0003, not evidence of a safe band in
general.

## Limitations

- One tiny task, one language, authored defects, 100 judgments; the band will
  differ on real code and must be refit from audited outcomes.
- Ground truth comes from an oracle over a fixed corpus; defects outside the
  corpus are invisible to it.
- The receipts here are the full implementation source; larger diffs will need
  per-hunk states to stay within Jev's context limits.

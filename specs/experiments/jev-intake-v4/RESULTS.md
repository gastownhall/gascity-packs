# Intake v4 routing study: results — September 30, 2026

Rules and criteria are in [PROTOCOL.md](PROTOCOL.md), written before any test
call. Every request and response is under `calls/`; `analyze.py` reproduces
every number here. One `jev-1.13.0` call per record, 348 calls in all.

## Test set (100 fresh PRs, scored once)

| Router | compact routed | compact recall | standard → compact | deep → compact | direct routed | deep → direct |
| --- | --- | --- | --- | --- | --- | --- |
| v3 (today) | 6 | 3/14 | 2 | 1 | – | – |
| **v4 frozen** | 14 | 5/14 | 8 | 1 | 22 | 1/38 |

Against the pre-registered criteria:

1. **No deep change routed compact — failed**, by one PR that v3 also routes
   compact: #6684, a 38-line edit to two docs files, classed deep only because
   the files sit under `engdocs/`. It is a proxy artifact, but the criterion was
   written against the proxy.
2. **At most 5% of deep changes routed direct — passed**: 1 of 38 (#6711, a
   23-line test-sharding change that touches API and design-doc paths).
3. **Compact recall at least 50% — failed**: 5 of 14, against v3's 3 of 14.
4. **Standard changes routed compact**: #6813 (156 lines), #6692 (329), #6801
   (162), #6763 (255), #6708 (97, one changelog file), #6706 (172), #6666
   (135), #6663 (241). Mostly test, CI and narrow fixes that read as small.

On the development set the same rule routed 14 compact (10 of 15 compact, 4
standard, 0 deep) and 14 direct (1 deep).

## What this shows

- **Jev judges how big a change sounds, not how many lines it takes.** Its
  compact routes are conceptually narrow changes; 9 of 14 exceed the proxy's
  80-line or 3-file limit. The compact path still runs the full Jev review
  gate, so the cost of this error is skipped planning, not skipped review.
  Whether that costs quality is the build A/B's question, not this study's.
- **Most missed compact changes are one- to three-line CI and Bazel config
  edits** that Jev reads as touching several modules or a persistence surface.
  A miss only costs the full path.
- **The direct tier works as intended**: skipping only the plan stage when Jev
  is at least 0.9 sure no design is needed and the change is not large or
  multi-module routed 22% of fresh PRs with one deep change among them.
- **v4 sends more work down cheaper paths than v3, at a price.** Compact
  recall is 5 of 14 against 3 of 14, and the direct tier is new, but v4 routes
  8 standard changes compact where v3 routes 2.

## Post-test tightening

After scoring, the direct tier was found to take #6460 from the development set,
the intake spike's 515-line security near-miss. Skipping the plan on security or
persistence work is not acceptable, so direct now also requires a risky surface
other than `security_or_auth` or `persistence_or_migration`. This only narrows
the rule; `analyze.py` applies it (`SAFE_DIRECT`). On the test set it routes 19
direct instead of 22, still with one deep change (1 of 38); on the development
set, 9 instead of 14.

## Decision

Ship v4 with the frozen rule for both tiers, knowing the compact tier missed its
pre-registered bar. Its quality risk is measured directly by the next build A/B,
whose four workloads are all ground-truth compact. The direct tier ships on its
own merits.

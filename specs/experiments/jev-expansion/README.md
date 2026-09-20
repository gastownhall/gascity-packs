# Jev expansion experiments

Completed six live cohorts with 224 arm attempts. [Results and limitations](RESULTS.md)
include every negative result and failure. Duplicate-candidate ordering now
defaults to auto when Jev is configured; other classification paths remain opt-in.

- [Initial frozen protocol](PROTOCOL.md) and [new ranking protocol](RANK-PROTOCOL.md)
- [Initial suite](suite.json), [ranking suite](rank-suite.json), and their fixture generators
- [Public-input verification](public-input-verification.json)
- [Decision metrics](evaluation-summary-001.json) and [generated-report metrics](report-summary-001.json)
- [Ranking metrics](rank-evaluation-001/summary.json)
- [Evidence rerun with retained baseline format failure](evidence-rerun-001/summary.json)
- [Boundary-case analysis](ADJUDICATION.md) and [initial default gate](default-gate-001.json)
- [Expanded audit](verification-001.json) and [ranking/evidence audit](rank-evidence-verification-001.json)
- [Integration test log](integration-tests-001.txt), [known baseline timeout proof](known-timeout-verification.json)
- [Final formula checks](final-formula-tests.txt), [new helper checks](new-helper-final-tests-002.txt)
- [Append-only ledger](ledger.jsonl)

No public writes were performed. Generative calls used the Claude subscription.
Tokens are observed usage, not a claim of subscription-dollar savings. The
ranking component includes its deterministic handoff; complete Gas City workflow
savings remain unmeasured.

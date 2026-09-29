Write the review report (deterministic script worker; no LLM session).

The `gc.jev-gate` worker writes the normalized `gc.build.review.v1` artifact from
the review loop's final `code_review.verdict` (or, when the gate cleared every
lane, from the gate itself), records its path on the workflow root as
`gc.build.review_report_path`, and labels each gate decision from the
first-iteration lane verdicts. An audited decision that a lane contradicts is a
miss: it is logged and trips that decision type's circuit breaker until
`jev_decisions.py refit` runs.

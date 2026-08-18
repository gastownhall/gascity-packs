
If open_pr is {{open_pr}}, create a PR only after push succeeds and sanitized
title/body from final report {{final_report}} pass policy.

Before calling `gh pr create`, re-read the drafted title and body and reject
any that still contain internal tracking artifacts: bead/convoy/epic IDs
(e.g. `tlp-xxxxx`, `ga-xxx`), internal requirement labels like
`REQ-001`/`REQ-002`, gc workflow/formula names, or raw coverage tables
lifted from the implementation-summary artifact. Rewrite the title/body in
terms an external reviewer with no gc access would understand, following the
target repo's own PR conventions doc when one exists.

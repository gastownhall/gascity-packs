Run the gstack ship readiness lane.

Check branch cleanliness, test commands, coverage deltas, review approval,
QA approval, release notes, and whether publish flags permit push or PR work.
Do not push or open PRs from this lane.

Current review_mode is {{review_mode}}. In report mode, do not edit, stage, or
commit product source, release notes, or repository metadata; record every
required change in the findings artifact.

Write findings under the artifact root.

Close with `gc.outcome=pass`,
`gstack.release.ship_verdict=approve|iterate`, and
`gstack.release.output_path=<ship readiness report path>`.

Do not invoke provider-native subagents. You are the release-engineering lane.

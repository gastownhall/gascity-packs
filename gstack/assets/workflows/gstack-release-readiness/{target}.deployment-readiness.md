Run the gstack deployment readiness lane.

Check deploy strategy, environment assumptions, canary or health checks, and
rollback notes. If there is no deploy surface, mark this lane not applicable
and explain the release path that remains.

Current review_mode is {{review_mode}}. In report mode, do not edit, stage, or
commit product source or deployment configuration, and do not deploy or mutate
an environment; record the safe verification that remains instead.

Write findings under the artifact root.

Close with `gc.outcome=pass`,
`gstack.release.deploy_verdict=approve|iterate`, and
`gstack.release.output_path=<deployment readiness report path>`.

Do not invoke provider-native subagents. You are the deployment readiness lane.

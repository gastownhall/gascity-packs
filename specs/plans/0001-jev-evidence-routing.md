# Optional Jev evidence checking and A/B evaluation

1. Update Gas City and Beads to the current releases and record versions.
2. Add a bounded, optional evidence-checking helper to the Gas City pack;
   preserve current review authority, artifacts, and default behavior.
3. Test evidence binding, response validation, uncertainty, and failure handling.
4. Build a reproducible paired experiment harness using subscription CLIs.
5. Run a small pilot, freeze the configuration, then evaluate held-out cases.
6. Run full-workflow A/B tests where live runtime and Jev access permit.
7. Write measured results, uncertainty, limitations, and reproduction commands.

Generative model work uses subscription CLI authentication. API access for Jev
itself is pending clarification. Continue independent implementation work while
that question is pending; do not fabricate Jev results or substitute a mock.

## Checkpoint

Steps 1–4 complete. Step 5 has two baseline-only pilots; live Jev and held-out
evaluation remain pending. Step 6 reached approved Claude Max execution. The Beads forced-init preflight
and macOS tmux-reaper failures have local verified patches. The gate Python
repair passed live validation in baseline 005, which later failed on a missing
fixture origin and timed out. The local-origin repair passes a real Git worktree
regression, but the remaining workflow and observed latch routing still need
validation. No full build has passed. Live Jev still requires its credential. Step 7 has an interim measured report at
[RESULTS.md](../experiments/jev-evidence-routing/RESULTS.md). No A/B conclusion
is supported yet.

## Added scope: maintainer-city kind triage

Support Julian's kind-only use case before extending Jev to priority or adopt-pr
complexity. The reported 96% is agreement against Opus Max, with raw data and
configuration still needed. Kind helper, opt-in issue-triage instructions and
historical backtest runner are implemented; see
[the kind protocol](../experiments/jev-evidence-routing/KIND-TRIAGE.md).
Live replication, a paired subscription Claude/fallback runner for kinds,
independent adjudication, and end-to-end measurements remain outstanding.

# Optional Jev evidence checking and A/B evaluation

1. Update Gas City and Beads to the current releases and record versions.
2. Add a bounded, optional evidence-checking helper to the Gas City pack;
   preserve current review authority, artifacts, and default behavior.
3. Test evidence binding, response validation, uncertainty, and failure handling.
4. Build a reproducible paired experiment harness using subscription CLIs.
5. Run a small pilot, freeze the configuration, then evaluate held-out cases.
6. Run full-workflow A/B tests where live runtime and Jev access permit.
7. Write measured results, uncertainty, limitations, and reproduction commands.

Generative model work uses subscription CLI authentication. Jev access is
verified using the user-supplied Dashlane secure note, injected into process
memory. Live experiments retain real responses and complete usage records.

## Checkpoint

Steps 1–5 complete. Two baseline-only pilots are followed by a successful live
paired pilot and held-out cohort, with the same frozen v2 rubric and threshold. Step 6 reached approved Claude Max execution. The Beads forced-init preflight
and macOS tmux-reaper failures have local verified patches. The gate Python
repair passed live validation in baseline 005, which later failed on a missing
fixture origin and timed out. The local-origin repair passes a real Git worktree
regression, but the remaining workflow and observed latch routing still need
validation. No full build has passed. Step 7 has a measured focused comparison at
[RESULTS.md](../experiments/jev-evidence-routing/RESULTS.md). The classification
results do not establish full-pack savings or speedup.

## Added scope: maintainer-city kind triage

Support Julian's kind-only use case before extending Jev to priority or adopt-pr
complexity. The reported 96% is agreement against Opus Max, with raw data and
configuration still needed. Kind helper, opt-in issue-triage instructions and
historical backtest runner are implemented; see
[the kind protocol](../experiments/jev-evidence-routing/KIND-TRIAGE.md).
Live replication, a paired subscription Claude/fallback runner for kinds,
independent adjudication, and end-to-end measurements remain outstanding.

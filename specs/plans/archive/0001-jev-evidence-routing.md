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
[RESULTS.md](../../experiments/jev-evidence-routing/RESULTS.md). The classification
results do not establish full-pack savings or speedup.

Correction, 2026-09-23: the local patches were not fixes for new upstream bugs.
The tmux-reaper failure is a known bug already fixed on Gas City `main`
(a6b72d832, #5392) but not in v1.4.2. The Beads forced-init preflight is a
latent issue that only appears under heavy host load, as here. The latch
closure relates to an upstream fix not in v1.4.2 (449df7c4a) plus a pack-side
claim/template gap. The missing-origin failure was caused by the harness; the
gate Python failure was environmental, with its exact cause unestablished. Step 6 will resume with a harness that follows the documented
operator path and unpatched upstream binaries. See the
[RESULTS.md correction summary](../../experiments/jev-evidence-routing/RESULTS.md).

## Added scope: maintainer-city kind triage

Support Julian's kind-only use case before extending Jev to priority or adopt-pr
complexity. The kind helper, opt-in issue-triage instructions, historical
backtest and paired subscription Claude/fallback runner are implemented.
Our own real-data comparison is complete: 31/32 raw Jev/Opus agreement and 32/32
final agreement with seven fallbacks. See [kind results](../../experiments/jev-evidence-routing/KIND-RESULTS.md)
and [the protocol](../../experiments/jev-evidence-routing/KIND-TRIAGE.md).
Broader samples, repeated measurements, independent adjudication and full
workflow measurements remain outstanding.

## Separate experimental pack

The Jev-enabled pack now lives in `gascity-jev`, with all five integrations
remaining automatic when configured. The sibling `gascity` pack is restored
exactly to pre-Jev commit `05031f2c66e080865c379ff799c7369430560a8f`.
The full-build harness selects these separate packs, including matching roles
and validators, for future comparisons. Pack tests, real CLI installation and
formula/role loading, lint, and no-key fallbacks passed. Historical experiment
artifacts are unchanged; no new model comparison was run for this split.
Full-workflow performance and quality equivalence remain unestablished.

## Next

The redesign that lets Jev decisions replace Claude sessions, instead of
advising them, is settled in
[0003-gascity-jev-redesign-design.md](../0003-gascity-jev-redesign-design.md).
The first complete full-build pair is in
[jev-operator-path](../../experiments/jev-operator-path/README.md).

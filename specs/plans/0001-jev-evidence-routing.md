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
evaluation remain pending. Step 6 is blocked by fresh shared-database migrations
on gc 1.4.2 / bd 1.3.0. Step 7 has an interim measured report at
[RESULTS.md](../experiments/jev-evidence-routing/RESULTS.md). No A/B conclusion
is supported yet.

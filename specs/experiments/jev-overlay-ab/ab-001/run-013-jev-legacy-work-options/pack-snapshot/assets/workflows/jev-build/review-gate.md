Jev review gate (deterministic script worker; no LLM session).

The `gc.jev-gate` worker runs `assets/scripts/jev_gate.py worker` for this step. It:

- resolves the implementation worktrees from the implementation summary and
  workflow members, and writes the review context recorded as
  `gc.build.code_review_context_path` on the workflow root;
- gathers receipts: runs the tests in each worktree itself and compares every
  pre-existing test file with its base blob by hash;
- asks Jev (`{{jev_model}}`, mode `{{jev_mode}}`) one "is there any input for
  which this implementation violates the criterion?" question per acceptance
  criterion, plus one smell screen over the diff hunks;
- applies the bands in the gate state directory (audit sampling and circuit
  breaker included), logs every decision to `<artifact_root>/jev/decisions.jsonl`
  and the shared ledger, and closes with `gc.output_json` holding exactly one
  item for the `jev-review-tail` bond.

Any failure (no key, HTTP error, invalid answer, missing receipts) runs every
review lane at full scope and records the reason on this bead.

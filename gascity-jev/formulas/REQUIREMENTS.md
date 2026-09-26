# Jev Overlay Formula Requirements

Schema: `gc.jev-overlay-formulas.requirements.v1`

| Field | Value |
| --- | --- |
| Status | Experimental |
| Scope | The `jev-`-prefixed formulas in the `gascity-jev` overlay pack |
| Parent ledger | `../REQUIREMENTS.md` |
| Base ledger | `../../gascity/formulas/REQUIREMENTS.md` (every inherited formula) |

This ledger covers every formula this overlay adds. Everything else comes from
the imported `gascity` pack and is governed by the base ledger. Each row names
the behavior that must stay true when the formula graph, gate item, bond vars,
routing or prompt assets change.

## How To Reconcile

1. Update the row for the changed formula and `../REQUIREMENTS.md` when the
   change affects gate authority, bands, audits, or the fail-open contract.
2. Keep the gate item keys, the `on_complete` bond vars in every formula that
   bonds `jev-review-tail`, and `jev_gate.full_item()` identical;
   `../tests/test_jev_formula_assets.py` enforces this.
3. Replacing an inherited step is whole-step: restate metadata, checks and
   description files the replacement still needs.

## Global Invariants

- Every formula uses `contract = "graph.v2"` and extends a base formula or is a
  bond; none copies a base formula.
- Gate and report steps route to `gc.jev-gate` (binding-qualified; a bare
  target strands check retries).
- The gate emits exactly one fanout item. An empty item list would close the
  fanout as a pass and silently skip finalize and publish.
- Inherited `finalize` and `publish` are dropped only together (a whole-step
  replacement with an always-false condition); the bond owns them.

## Scenario Ledger

| ID | Formula | Type | Required behavior | Evidence |
| --- | --- | --- | --- | --- |
| GC-JEV-001 | `jev-build` | Cataloged overlay build | Extends `build-basic` and keeps every stage through `summarize-implementation`. Replaces `review` by id with the deterministic Jev gate (`jev.role = review-gate`, routed to `gc.jev-gate`) whose `on_complete` fans out one `jev-review-tail` bond per gate item. Drops inherited `finalize` and `publish` with `condition = "{{keep_inherited_tail}}"`. Declares `jev_mode`, `jev_model`, `jev_state_dir`, `jev_test_command`, `jev_test_timeout`, `jev_audit_rate` and `jev_intake_decision`. | `jev-build.formula.toml`; `../tests/test_jev_formula_assets.py`; `../../specs/experiments/jev-overlay-build/` |
| GC-JEV-002 | `jev-review-tail` | Bond (expansion) | Holds the review loop (a check with children, rerun by `implementation-review-approved.sh`) with the acceptance, test-evidence and simplicity lanes gated by `{{lane}} == run`; synthesis runs only when two or more lanes run; the loop is dropped when none runs. A script `review-report` step writes and validates `gc.build.review.v1` and labels gate decisions; `finalize` (validated `gc.build.final-report.v1`) and `publish` restate the build-basic contracts. Expansion-template text and metadata use single-brace `{var}`. | `jev-review-tail.formula.toml`; `../tests/test_jev_formula_assets.py`; `../../specs/experiments/jev-overlay-build/` |
| GC-JEV-003 | `jev-build-compact` | Cataloged compact route | Extends `jev-build`; drops requirements, plan, plan review, decompose and summarize-implementation; drains the sling's own input convoy through `do-work` right after `prepare`; restates the review gate after the drain. Launched only by the intake router (`gc <binding> jev-route`). | `jev-build-compact.formula.toml`; `../tests/test_jev_formula_assets.py`; `../../specs/experiments/jev-overlay-build/` |

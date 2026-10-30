# Compound Engineering Compatibility Ledger

This ledger proves that the Compound Engineering pack preserves the Gas City
`build-base` contract while layering vendored Compound Engineering methodology
on top. Each claim names the files that prove it; the Evidence Commands section
gives the exact commands that reproduce the proof.

This ledger is the pack-local evidence for `GC-METH-012` (external
implementation compatibility) in `gascity/REQUIREMENTS.md`;
`gascity/tests/test_derived_pack_compatibility.py` enforces the claims below
for every derived pack.

## Compatibility Claims

- Required-stage failure policy: the build inherits or overrides the native
  `build-body` scope and includes every required stage in its `needs`. Whole-step
  overrides preserve `gc.scope_ref`, `gc.scope_role`, and `gc.on_fail`; review
  expansions propagate optional `failure_scope` through setup, logical checks,
  and finalizers. Existing repair children and attempt limits remain unchanged,
  and standalone expansions use an empty scope default. The owning checks are
  `gascity/tests/test_build_failure_policy.py` and
  `tests/test_build_failure_policy_live_gc.py`.
- Import contract: `compound-engineering/pack.toml` imports the Gas City pack
  as `gc` from `../gascity`, so the pack inherits the shared `gc.*` surface
  (base formulas, role agents, template fragments) instead of re-defining it.
- Formula contract: `compound-engineering/formulas/compound-build.formula.toml`
  declares `extends = ["build-base"]` and preserves the inherited anchor order
  `prepare -> requirements -> plan -> plan-review -> decompose ->
  implement/implement-same-session -> review -> finalize -> publish`. The child
  overrides `requirements`, `plan`, `plan-review`, `implement`,
  `implement-same-session`, `review`, and `finalize` under their base ids in
  the base sequence; `prepare`, `decompose`, and `publish` remain inherited.
  No anchor is renamed, skipped, or reordered.
- Methodology selectors: the pack ships one derived formula per base
  methodology contract, each declared with `extends` on the matching base:
  `compound-planning` (`planning-base`), `compound-decomposition`
  (`decomposition-base`), `compound-review` (`code-review-base`), and
  `compound-fix-loop` (`fix-loop-base`). `compound-build` pins them as
  defaults via `planning_formula`, `decomposition_formula`,
  `implementation_formula` (`compound-implementation`),
  `implementation_item_formula` (`compound-work-item`), `code_review_formula`,
  and `review_fix_formula` vars, so adapters can select them through the
  standard selector surface.
- Interaction modes: `compound-build` inherits the `interaction_mode` var
  (`interactive` | `autonomous` | `headless`, default `interactive`) from
  `build-base` and declares all three values in
  `[metadata.gc.methodology].interaction_modes`. The README maps Compound's
  planning and human-gate behavior onto this axis.
- Review modes: `compound-build` inherits the `review_mode` var (`report` |
  `agent` | `interactive`, default `agent`) from `build-base` and declares all
  three values in `[metadata.gc.methodology].review_modes`. Compound's raw
  `mode:agent` maps to machine handoff/report behavior; interactive review maps
  to a direct build where the reviewer may own safe fix application.
- Drain policy: `[metadata.gc.methodology]` declares
  `implementation_strategy = "drain"` with
  `allowed_drain_policies = ["separate", "same-session"]`. The `separate` path
  drains `compound-work` item formulas with exclusive member access; the
  `same-session` path drains `compound-work-item` in one shared single-lane
  session with `on_item_failure = "skip_remaining"`. Both preserve the
  build-base drain lifecycle, convoy identity, and per-item evidence.
- Persona review lanes: plan review and code review fan out through the
  Gas City expansion formulas `compound-plan-review` and
  `compound-code-review` (finalization through `compound-resolution`). Every
  runnable expansion child routes via `gc.run_target` to a providerless pack-local
  agent (`compound-engineering.ce-*`, declared in `agents/*/agent.toml` with
  no provider pin), to a `gc.*` role (`gc.run-operator`,
  `gc.task-decomposer`), or to the caller-selected `{implementation_target}`
  for the apply-fix lane. No lane dispatches provider-native subagents.
- Base artifact contract: the pack writes lane and stage artifacts under the
  inherited `{{artifact_root}}` and preserves the `gc.build.*` handoff
  namespace (`requirements_path`, `plan_path`, `plan_review_*`,
  `reviewer_selection_*`, `code_review_*`, `review_fix_summary_path`, status
  and approval keys) on the workflow root bead. Structured artifacts follow
  the `gc.build.*.v1` schemas in `gascity/schemas/build/` (requirements, plan,
  decomposition, implementation-summary, review, final-report) validated by
  the shared `gascity/assets/scripts/validate_build_artifact.py`, which keeps
  traceability and coverage chains intact end to end.
- Review/fix loop behavior: `compound-code-review` runs always-on lanes
  (correctness, testing, maintainability, standards, agent-native, learnings
  research, gap analysis) as sibling beads, cheap selector gates that close
  skipped conditional lanes with no-op artifacts, a synthesis fan-in
  (`synthesize-code-review`), and an `apply-review-findings` lane that owns the
  loop verdict consumed by the inherited approval check. Required findings
  route back through the same fanout until approval; `compound-plan-review`
  applies the same loop shape to planning. `compound-fix-loop` carries the
  standalone review-fix contract for adapter use.
- Final-report expectations: the `finalize` override expands
  `compound-resolution` (`inventory-artifacts -> review-resolution ->
  synthesize-resolution`) and records the inherited build artifact trail on
  the workflow root; standalone `compound-review` runs write the
  adapter-consumable report to `{{report_path}}` without posting comments,
  pushing branches, or finalizing external state.
- Prompt hygiene: all agent prompt templates under `agents/*/prompt.template.md`
  include the public `gc-role-worker` fragment supplied by the `gc` import;
  Compound Engineering does not override that shared claim protocol. Lane
  assets and the
  skill-adopting agent prompts state "Do not invoke provider-native
  subagents, slash commands, task tools, or the upstream plugin runtime" and
  translate upstream subagent requests into Gas City lanes. The vendored
  skill texts under `skills/` are methodology references only; the graph owns
  all fanout.
- Vendor provenance:
  `vendor/compound-engineering-plugin/upstream.toml` records the upstream
  source repository, pinned commit, MIT license, and the vendored paths.

## Evidence Commands

Run these from the repository root:

```sh
sed -n '1,10p' compound-engineering/pack.toml
grep -n -E '^id = ' gascity/formulas/build-base.formula.toml
grep -n -E '^extends|^id = |^\[metadata\.gc\.methodology\]|policies|strategy|modes' compound-engineering/formulas/compound-build.formula.toml
grep -n -A 2 -E '^\[vars\.(interaction_mode|review_mode)\]' gascity/formulas/build-base.formula.toml
grep -n -E '^extends' compound-engineering/formulas/compound-planning.formula.toml compound-engineering/formulas/compound-decomposition.formula.toml compound-engineering/formulas/compound-review.formula.toml compound-engineering/formulas/compound-fix-loop.formula.toml
grep -n 'gc.run_target' compound-engineering/formulas/compound-plan-review.formula.toml compound-engineering/formulas/compound-code-review.formula.toml compound-engineering/formulas/compound-resolution.formula.toml
grep -rL 'gc-role-worker' compound-engineering/agents/*/prompt.template.md  # expect no output
gc lint compound-engineering
grep -rn 'Do not invoke provider-native subagents' compound-engineering/agents compound-engineering/assets | wc -l  # expect > 30
grep -rho 'gc\.build\.[a-z_.]*' compound-engineering/assets compound-engineering/formulas | sort -u
ls gascity/schemas/build
sed -n '1,20p' compound-engineering/vendor/compound-engineering-plugin/upstream.toml
python3 -m pytest gascity/tests/test_formula_assets.py -q
```

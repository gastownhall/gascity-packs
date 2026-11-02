# Superpowers Compatibility Ledger

This ledger proves that the Superpowers pack preserves the Gas City
`build-base` contract while layering vendored Superpowers skills on top. Each
claim names the files that prove it; the Evidence Commands section gives the
exact commands that reproduce the proof.

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
- Import contract: `superpowers/pack.toml` imports the Gas City pack as `gc`
  from `../gascity`, so the pack inherits the shared `gc.*` surface (base
  formulas, role agents, template fragments) instead of re-defining it.
- Formula contract: `superpowers/formulas/superpowers-build.formula.toml`
  declares `extends = ["build-base"]` and preserves the inherited anchor order
  `prepare -> requirements -> plan -> plan-review -> decompose ->
  implement/implement-same-session -> review -> finalize -> publish`. The
  child overrides `requirements`, `plan`, `plan-review`, `decompose`,
  `implement`, `implement-same-session`, `review`, and `finalize` under their
  base ids in the base sequence; `prepare` and `publish` remain inherited.
  `superpowers-build` adds no top-level stage of its own, and no base anchor
  is renamed, skipped, or reordered.
- Pack-added structure: the only pack-added steps live inside the item
  formulas, not the build anchor sequence. `superpowers-development` (extends
  `do-work`) and `superpowers-development-item` (extends `do-work-item`)
  insert the TDD lane `write-failing-test -> verify-test-fails ->
  implement-change -> verify-test-passes -> task-review ->
  record-item-result` between the inherited implement anchor and
  `close-source-anchor`. The declared insertion point for `task-review` is
  after `verify-test-passes` and before `record-item-result`; its gate is the
  `implementation-review-approved.sh` check loop owning
  `code_review.verdict=done|iterate`; its output is the per-task review
  artifacts and verdict metadata recorded before the item result is written.
  The behavior is methodology-specific (Superpowers subagent-driven
  development), not reusable base behavior.
- Methodology selectors: the pack ships one derived formula per base
  methodology contract, each declared with `extends` on the matching base:
  `superpowers-planning` (`planning-base`), `superpowers-decomposition`
  (`decomposition-base`), `superpowers-review` (`code-review-base`),
  `superpowers-fix-loop` (`fix-loop-base`), and `superpowers-implementation`
  (`implement`). `superpowers-build` pins them as defaults via
  `planning_formula`, `decomposition_formula`, `implementation_formula`
  (`superpowers-implementation`), `implementation_item_formula`
  (`superpowers-development-item`), `code_review_formula`
  (`superpowers-review`), and `review_fix_formula` (`superpowers-fix-loop`)
  vars, plus `implementation_target` (`superpowers.implementer`), so adapters
  can select them through the standard selector surface.
- Interaction modes: `superpowers-build` inherits the `interaction_mode` var
  (`interactive` | `autonomous` | `headless`, default `interactive`) from
  `build-base` and declares all three values in
  `[metadata.gc.methodology].interaction_modes`. The README maps the raw
  Superpowers design/spec approval experience onto this vocabulary:
  interactive runs preserve the brainstorm and spec approval halts, while
  autonomous and headless runs drive the same approval loops without user
  checkpoints. The `brainstorming_approval_mode` var (`autonomous` |
  `interactive`) carries that toggle into the brainstorming expansion.
- Review modes: `superpowers-build` inherits the `review_mode` var (`report`
  | `agent` | `interactive`, default `agent`) from `build-base` and declares
  all three values in `[metadata.gc.methodology].review_modes`. Report-only
  runs synthesize findings without applying fixes; agent/interactive runs
  feed the review-fix lane until the approval check passes.
- Drain policy: `[metadata.gc.methodology]` declares
  `implementation_strategy = "drain"` with
  `allowed_drain_policies = ["separate", "same-session"]`. The `separate`
  path drains `superpowers-development` item formulas with exclusive member
  access; the `same-session` path drains `superpowers-development-item` in
  one shared single-lane session with `on_item_failure = "skip_remaining"`.
  Both preserve the build-base drain lifecycle, convoy identity, and per-item
  evidence.
- TDD durability: the red/green discipline from the vendored
  `test-driven-development` skill is durable graph structure, not prose-only
  guidance. Both item formulas chain `write-failing-test`,
  `verify-test-fails`, `implement-change`, `verify-test-passes`,
  `task-review`, and `record-item-result` as formula steps with explicit
  `needs` edges, so every task's TDD pass is resumable and visible in the
  graph.
- Subagent conversion: upstream Superpowers dispatches implementer,
  spec-reviewer, and code-quality-reviewer subagents per task
  (`subagent-driven-development`) and requests reviewer subagents after
  implementation (`requesting-code-review` / `receiving-code-review`). The
  pack models every one of those handoffs as graph work: the
  `superpowers-task-review` expansion runs the spec-compliance lane first,
  applies spec findings through the implementation lane, then runs the
  code-quality lane and its apply lane; the `superpowers-code-review`
  expansion fans out sibling `request-code-review` and `gap-analysis-review`
  lanes with a `process-code-review` fan-in; the brainstorm, spec, and plan
  approval cycles are check-gated graph loops in `superpowers-brainstorming`
  and `superpowers-plan-review`. No lane dispatches provider-native
  subagents; the graph owns all fanout.
- Providerless routes: every runnable step in the pack's formulas routes via
  `gc.run_target` to a providerless pack-local agent (`superpowers.*`,
  declared in `agents/*/agent.toml` with no provider pin), to the
  `gc.run-operator` or `gc.task-decomposer` role, or to the caller-selected
  `{implementation_target}` for implementation and apply-fix lanes.
- Base artifact contract: the pack writes stage artifacts under the inherited
  `{{artifact_root}}` and preserves the `gc.build.*` handoff namespace on the
  workflow root bead (inherited base keys plus the brainstorm gate keys
  `design_path`, `design_status`, `design_gate_*`, `spec_gate_*`, the
  plan-review keys `plan_review_status`, `plan_review_approved_at`,
  `plan_review_report_path`, `plan_review_context_path`,
  `plan_review_apply_summary_path`, and the review keys
  `code_review_status`, `code_review_approved_at`,
  `code_review_report_path`, `code_review_context_path`,
  `gap_analysis_report_path`, `review_fix_summary_path`). Structured
  artifacts follow the `gc.build.*.v1` schemas in `gascity/schemas/build/`
  (requirements, plan, decomposition, implementation-summary, review,
  final-report) validated by the shared
  `gascity/assets/scripts/validate_build_artifact.py`, which keeps
  traceability and coverage chains intact end to end.
- Review/fix loop behavior: the `review` anchor expands
  `superpowers-code-review`: a setup node, then a check-gated loop wrapper
  (`implementation-review-approved.sh`, bounded attempts) whose child lanes
  are the sibling `request-code-review` and `gap-analysis-review` reviewers
  (no `needs` between them) and a `process-code-review` fan-in routed to
  `{implementation_target}` that owns the `code_review.verdict=done|iterate`
  loop consumed by the inherited approval check. The loop controller re-runs
  only through child lanes in the graph. Task development applies the same
  shape per item through `superpowers-task-review`.
  `superpowers-fix-loop` carries the standalone review-fix contract for
  adapter use.
- Final-report expectations: the review expansion target verifies the code
  review report, gap-analysis report, and review-fix summary paths, then
  records `gc.build.code_review_status=approved` and
  `gc.build.code_review_approved_at` on the workflow root; standalone
  `superpowers-review` runs write the adapter-consumable report to
  `{{report_path}}` without posting comments, pushing branches, or
  finalizing external state.
- Prompt hygiene: all agent prompt templates under
  `agents/*/prompt.template.md` include the public `gc-role-worker` fragment
  supplied by the `gc` import; Superpowers does not override that shared claim
  protocol. Agent prompts
  and skill-adopting lane assets carry explicit "Do not invoke
  provider-native subagents, slash commands, task tools, or the upstream
  plugin runtime" guards. The skill texts under `skills/` are methodology
  source material only — when Superpowers text asks for a subagent or task
  handoff, the consuming lane treats it as a Gas City lane or expansion
  child; the graph owns all fanout.
- Vendor provenance: `superpowers/vendor/superpowers/upstream.toml` records
  the upstream source repository, pinned commit, MIT license, and the
  vendored paths. The `skills/` catalog is the pack's working copy of those
  vendored skills.

## Evidence Commands

Run these from the repository root:

```sh
sed -n '1,10p' superpowers/pack.toml
grep -n -E '^id = ' gascity/formulas/build-base.formula.toml
grep -n -E '^extends|^id = |^\[metadata\.gc\.methodology\]|policies|strategy|modes' superpowers/formulas/superpowers-build.formula.toml
grep -n -A 2 -E '^\[vars\.(interaction_mode|review_mode)\]' gascity/formulas/build-base.formula.toml
grep -n -E '^extends' superpowers/formulas/superpowers-planning.formula.toml superpowers/formulas/superpowers-decomposition.formula.toml superpowers/formulas/superpowers-review.formula.toml superpowers/formulas/superpowers-fix-loop.formula.toml superpowers/formulas/superpowers-implementation.formula.toml superpowers/formulas/superpowers-development.formula.toml superpowers/formulas/superpowers-development-item.formula.toml
grep -n -E '^id = |^needs = ' superpowers/formulas/superpowers-development.formula.toml superpowers/formulas/superpowers-development-item.formula.toml  # TDD sequence as durable steps
grep -rn 'gc.run_target' superpowers/formulas/*.toml  # expect only superpowers.* agents, gc.run-operator, gc.task-decomposer, or {implementation_target}
grep -rL 'gc-role-worker' superpowers/agents/*/prompt.template.md  # expect no output
gc lint superpowers
grep -rn 'provider-native' superpowers/agents superpowers/assets | wc -l  # expect >= 40
grep -rho 'gc\.build\.[a-z_.]*' superpowers/assets superpowers/formulas | sort -u
ls gascity/schemas/build
sed -n '1,20p' superpowers/vendor/superpowers/upstream.toml
python3 -m pytest gascity/tests/test_formula_assets.py -q
python3 - <<'PY'
import pathlib
import tomllib

base = tomllib.loads(pathlib.Path('gascity/formulas/build-base.formula.toml').read_text())
child = tomllib.loads(pathlib.Path('superpowers/formulas/superpowers-build.formula.toml').read_text())

assert child['extends'] == ['build-base']
base_order = [step['id'] for step in base['steps']]
child_order = [step['id'] for step in child['steps']]
assert set(child_order) <= set(base_order)  # no pack-added or renamed top-level anchors
assert child_order == [s for s in base_order if s in child_order]  # base relative order preserved
assert set(child_order) == {
    'requirements', 'plan', 'plan-review', 'decompose',
    'implement', 'implement-same-session', 'review', 'finalize',
}
assert {'prepare', 'publish'} <= set(base_order) - set(child_order)

tdd = ['write-failing-test', 'verify-test-fails', 'implement-change',
       'verify-test-passes', 'task-review', 'record-item-result']
for name in ('superpowers-development', 'superpowers-development-item'):
    item = tomllib.loads(
        pathlib.Path(f'superpowers/formulas/{name}.formula.toml').read_text())
    ids = [step['id'] for step in item['steps']]
    assert [i for i in ids if i in tdd] == tdd
    steps = {step['id']: step for step in item['steps']}
    for prev, cur in zip(tdd, tdd[1:]):
        assert steps[cur]['needs'] == [prev]
    assert steps['close-source-anchor']['needs'] == ['record-item-result']
print('superpowers-build preserves base anchors with no pack-added top-level '
      'steps; the TDD sequence is durable formula structure in both item '
      'formulas')
PY
```

## Notes

- `superpowers/README.md` references this ledger so the pack documentation
  points to the compatibility contract directly.
- The ledger is pack-local; the base contracts remain defined by `gascity`
  and are inherited through `build-base`.

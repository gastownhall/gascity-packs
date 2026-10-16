# BMAD Compatibility Ledger

This ledger proves that the BMAD pack preserves the Gas City `build-base`
contract while layering vendored BMAD Method skills on top. Each claim names
the files that prove it; the Evidence Commands section gives the exact
commands that reproduce the proof.

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
- Import contract: `bmad/pack.toml` imports the Gas City pack as `gc` from
  `../gascity`, so the pack inherits the shared `gc.*` surface (base formulas,
  role agents, template fragments) instead of re-defining it.
- Formula contract: `bmad/formulas/bmad-build.formula.toml` declares
  `extends = ["build-base"]` and preserves the inherited anchor order
  `prepare -> requirements -> plan -> plan-review -> decompose ->
  implement/implement-same-session -> review -> finalize -> publish`. The
  child overrides `requirements`, `plan`, `plan-review`, `decompose`,
  `implement`, `implement-same-session`, and `review` under their base ids in
  the base sequence; `prepare`, `finalize`, and `publish` remain inherited.
  No base anchor is renamed, skipped, or reordered.
- Implementation readiness anchor: `implementation-readiness` is the only
  pack-added step in `bmad-build`. Its declared insertion point is after
  `decompose` and before either implementation drain (`needs = ["decompose"]`;
  both `implement` and `implement-same-session` need
  `implementation-readiness`). Its gate is the readiness review run by
  `bmad.readiness-reviewer` — readiness failures are blockers for the
  implementation drains. Its output is the readiness report path and outcome
  recorded on the workflow root bead before implementation begins
  (`bmad/assets/workflows/bmad-build/implementation-readiness.md`). The
  standalone `bmad-decomposition` methodology formula preserves the same
  anchor: decompose first, readiness immediately after.
- Methodology selectors: the pack ships one derived formula per base
  methodology contract, each declared with `extends` on the matching base:
  `bmad-planning` (`planning-base`), `bmad-decomposition`
  (`decomposition-base`), `bmad-review` (`code-review-base`), `bmad-fix-loop`
  (`fix-loop-base`), and `bmad-implementation` (`implement`). `bmad-build`
  pins them as defaults via `planning_formula`, `decomposition_formula`,
  `implementation_formula` (`bmad-implementation`),
  `implementation_item_formula` (`bmad-story-development-item`),
  `code_review_formula` (`bmad-review`), and `review_fix_formula`
  (`bmad-fix-loop`) vars, plus `implementation_target`
  (`bmad.story-implementer`), so adapters can select them through the
  standard selector surface.
- Interaction modes: `bmad-build` inherits the `interaction_mode` var
  (`interactive` | `autonomous` | `headless`, default `interactive`) from
  `build-base` and declares all three values in
  `[metadata.gc.methodology].interaction_modes`. The README maps BMAD's
  menu/checkpoint axis onto this vocabulary: interactive runs preserve halts
  and user choices, headless automation expects all required inputs up front.
- Review modes: `bmad-build` inherits the `review_mode` var (`report` |
  `agent` | `interactive`, default `agent`) from `build-base` and declares all
  three values in `[metadata.gc.methodology].review_modes`. Report-only runs
  synthesize findings without applying fixes; agent/interactive runs feed the
  fix loop until the approval check passes.
- Drain policy: `[metadata.gc.methodology]` declares
  `implementation_strategy = "drain"` with
  `allowed_drain_policies = ["separate", "same-session"]`. The `separate`
  path drains `bmad-story-development` item formulas with exclusive member
  access; the `same-session` path drains `bmad-story-development-item` in one
  shared single-lane session with `on_item_failure = "skip_remaining"`. Both
  preserve the build-base drain lifecycle, convoy identity, and per-item
  evidence.
- Providerless routes: every runnable step in the pack's formulas routes via
  `gc.run_target` to a providerless pack-local agent (`bmad.*`, declared in
  `agents/*/agent.toml` with no provider pin), to the `gc.run-operator` role,
  or to the caller-selected `{implementation_target}` for implementation and
  apply-fix lanes. No lane dispatches provider-native subagents.
- Base artifact contract: the pack writes stage artifacts under the inherited
  `{{artifact_root}}` and preserves the `gc.build.*` handoff namespace on the
  workflow root bead (inherited base keys plus the review keys
  `code_review_status`, `code_review_approved_at`, `code_review_report_path`,
  `code_review_context_path`, `review_fix_summary_path`). Structured
  artifacts follow the `gc.build.*.v1` schemas in `gascity/schemas/build/`
  (requirements, plan, decomposition, implementation-summary, review,
  final-report) validated by the shared
  `gascity/assets/scripts/validate_build_artifact.py`, which keeps
  traceability and coverage chains intact end to end.
- Review/fix loop behavior: the `review` anchor expands
  `bmad-code-review-flow`: a gather-context node, then always-on adversarial
  lanes (blind-hunter, edge-case, acceptance-audit, gap-analysis) as sibling
  beads, a synthesis fan-in (`synthesize-bmad-review` via
  `bmad.bmad-review-synthesizer`), and an `apply-bmad-review-findings` lane
  routed to `{implementation_target}` that owns the loop verdict consumed by
  the inherited approval check. The loop controller re-runs only through
  child lanes in the graph. Story development applies the same shape per
  item: implement, self-check, acceptance-audit, and an apply-story-findings
  fix lane. `bmad-fix-loop` carries the standalone review-fix contract for
  adapter use.
- Final-report expectations: the review expansion target verifies the
  synthesized report and review-fix summary paths, then records
  `gc.build.code_review_status=approved` and
  `gc.build.code_review_approved_at` on the workflow root; standalone
  `bmad-review` runs write the adapter-consumable report to `{{report_path}}`
  without posting comments, pushing branches, or finalizing external state.
- Prompt hygiene: all agent prompt templates under
  `agents/*/prompt.template.md` include the public `gc-role-worker` fragment
  supplied by the `gc` import; BMAD does not override that shared claim
  protocol. Agent prompts and
  skill-adopting lane assets carry explicit "Do not invoke provider-native
  subagents, slash commands, task tools, or the upstream BMAD runtime"
  guards. The skill texts under `skills/` are methodology source material
  only — when BMAD text asks for a sub-agent/task handoff, the consuming lane
  treats it as a Gas City lane or expansion child; the graph owns all fanout.
- Vendor provenance: `bmad/vendor/bmad-method/upstream.toml` records the
  upstream source repository, pinned commit, MIT license, and the vendored
  paths. The `skills/` catalog is the pack's working copy of those vendored
  skills.

## Evidence Commands

Run these from the repository root:

```sh
sed -n '1,10p' bmad/pack.toml
grep -n -E '^id = ' gascity/formulas/build-base.formula.toml
grep -n -E '^extends|^id = |^\[metadata\.gc\.methodology\]|policies|strategy|modes' bmad/formulas/bmad-build.formula.toml
grep -n -A 2 -E '^\[vars\.(interaction_mode|review_mode)\]' gascity/formulas/build-base.formula.toml
grep -n -E '^extends' bmad/formulas/bmad-planning.formula.toml bmad/formulas/bmad-decomposition.formula.toml bmad/formulas/bmad-review.formula.toml bmad/formulas/bmad-fix-loop.formula.toml bmad/formulas/bmad-implementation.formula.toml
grep -n -E '^id = |needs = ' bmad/formulas/bmad-build.formula.toml  # implementation-readiness sits between decompose and both drains
grep -rn 'gc.run_target' bmad/formulas/*.toml  # expect only bmad.* agents, gc.run-operator, or {implementation_target}
grep -rL 'gc-role-worker' bmad/agents/*/prompt.template.md  # expect no output
gc lint bmad
grep -rn 'provider-native' bmad/agents bmad/assets | wc -l  # expect >= 30
grep -rho 'gc\.build\.[a-z_.]*' bmad/assets bmad/formulas | sort -u
ls gascity/schemas/build
sed -n '1,20p' bmad/vendor/bmad-method/upstream.toml
python3 -m pytest gascity/tests/test_formula_assets.py -q
python3 - <<'PY'
import pathlib
import tomllib

base = tomllib.loads(pathlib.Path('gascity/formulas/build-base.formula.toml').read_text())
child = tomllib.loads(pathlib.Path('bmad/formulas/bmad-build.formula.toml').read_text())

assert child['extends'] == ['build-base']
base_order = [step['id'] for step in base['steps']]
child_order = [step['id'] for step in child['steps']]
assert [s for s in child_order if s != 'implementation-readiness'] == \
    [s for s in base_order if s in child_order]
assert set(child_order) - {'implementation-readiness'} == {
    'requirements', 'plan', 'plan-review', 'decompose',
    'implement', 'implement-same-session', 'review', 'build-body',
}
assert {'prepare', 'finalize', 'publish'} <= set(base_order) - set(child_order)
steps = {step['id']: step for step in child['steps']}
assert steps['implementation-readiness']['needs'] == ['decompose']
assert steps['implement']['needs'] == ['implementation-readiness']
assert steps['implement-same-session']['needs'] == ['implementation-readiness']
print('bmad-build preserves base anchors; implementation-readiness inserted '
      'between decompose and the implementation drains')
PY
```

## Notes

- `bmad/README.md` references this ledger so the pack documentation points to
  the compatibility contract directly.
- The ledger is pack-local; the base contracts remain defined by `gascity`
  and are inherited through `build-base`.

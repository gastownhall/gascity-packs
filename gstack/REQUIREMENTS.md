# gstack Compatibility Ledger

This ledger proves that the gstack pack preserves the Gas City `build-base`
contract while layering vendored garrytan/gstack skills on top. Each claim
names the files that prove it; the Evidence Commands section gives the exact
commands that reproduce the proof.

This ledger is the pack-local evidence for `GC-METH-012` (external
implementation compatibility) in `gascity/REQUIREMENTS.md`;
`gascity/tests/test_derived_pack_compatibility.py` enforces the claims below
for every derived pack.

## Compatibility Claims

- Import contract: `gstack/pack.toml` imports the Gas City pack as `gc` from
  `../gascity`, so the pack inherits the shared `gc.*` surface (base formulas,
  role agents, template fragments) instead of re-defining it.
- Formula contract: `gstack/formulas/gstack-build.formula.toml` declares
  `extends = ["build-base"]` and preserves the inherited anchor order
  `prepare -> requirements -> plan -> plan-review -> decompose ->
  implement/implement-same-session -> summarize-implementation -> review ->
  finalize -> publish`. The child overrides `requirements`, `plan`,
  `plan-review`, `decompose`, `implement`, `implement-same-session`,
  `summarize-implementation`, `review`, `finalize`, and `publish` under their
  base ids in the base sequence; `prepare` remains inherited. No base anchor
  is renamed, skipped, or reordered.
- QA and release-readiness anchors: `qa` and `release-readiness` are the only
  pack-added steps in `gstack-build`, and they stay anchored after `review`
  and before `finalize`. The declared insertion points are `qa` after the
  review anchor (`needs = ["review"]`) and `release-readiness` after QA
  (`needs = ["qa"]`); `finalize` is rewired to need `release-readiness`, and
  `publish` still needs `finalize`. Each anchor expands a check-gated loop
  (`implementation-review-approved.sh`; QA allows 6 attempts,
  release-readiness 4). QA synthesis records the semantic result; a
  mode-selected terminal owns `done|iterate` for agent/interactive mode or
  `reported` for non-mutating report mode. Release-readiness synthesis owns
  `done|iterate` in agent/interactive mode and feeds a current-attempt
  `reported` terminal in report mode. Their outputs are the QA summary recorded on the
  workflow root at `gc.build.qa_summary_path` before release readiness begins
  and the readiness summary at `gc.build.release_readiness_summary_path` before
  finalize begins. Those summaries preserve `approved`, `changes_required`, or
  `blocked`, and the final gate maps any report-mode findings to a blocked final
  report
  (`gstack/assets/workflows/gstack-build/qa.md`,
  `gstack/assets/workflows/gstack-build/release-readiness.md`).
  Each expansion finalizer is executable-check-gated so its root summary path
  must equal the sole report terminal from the current loop epoch; stale,
  duplicate, or non-canonical terminal evidence is rejected. The code-review
  loop uses the same current-attempt terminal contract in report mode rather
  than accepting a pre-existing workflow-root report path.
- Methodology selectors: the pack ships one derived formula per base
  methodology contract, each declared with `extends` on the matching base:
  `gstack-planning` (`planning-base`), `gstack-decomposition`
  (`decomposition-base`), `gstack-review` (`code-review-base`),
  `gstack-fix-loop` (`fix-loop-base`), and `gstack-implementation`
  (`implement`), plus the drain formulas `gstack-work` (`do-work`) and
  `gstack-work-item` (`do-work-item`). `gstack-build` pins them as defaults
  via `planning_formula`, `decomposition_formula`, `implementation_formula`
  (`gstack-implementation`), `implementation_item_formula`
  (`gstack-work-item`), `code_review_formula` (`gstack-review`), and
  `review_fix_formula` (`gstack-fix-loop`) vars, plus `implementation_target`
  (`gstack.implementer`), so adapters can select them through the standard
  selector surface.
- Interaction modes: `gstack-build` keeps the base `interaction_mode`
  vocabulary (`interactive` | `autonomous` | `headless`) and declares all
  three values in `[metadata.gc.methodology].interaction_modes`. The pack pins
  the default to `interactive` because raw gstack is intentionally
  conversation-heavy; autonomous and headless runs record assumptions instead
  of waiting on human gates.
- Review modes: `gstack-build` keeps the base `review_mode` vocabulary
  (`report` | `agent` | `interactive`) and declares all three values in
  `[metadata.gc.methodology].review_modes`. The pack pins the default to
  `interactive` to match the office-hours posture; report-only runs write
  findings and evidence without applying fixes or opening release paths.
- Drain policy: `[metadata.gc.methodology]` declares
  `implementation_strategy = "drain"` with
  `allowed_drain_policies = ["separate", "same-session"]`. The `separate`
  path drains `gstack-work` item formulas with exclusive member access; the
  `same-session` path drains `gstack-work-item` in one shared single-lane
  session with `on_item_failure = "skip_remaining"`. Both preserve the
  build-base drain lifecycle, convoy identity, and per-item evidence. The
  shared item formula first runs a machine-gated worktree preparation step
  that creates or reuses a deterministic sibling worktree, verifies common
  repository identity, and persists that path on each source anchor.
- Providerless routes: every step in the pack's formulas routes via
  `gc.run_target` to a providerless pack-local agent (`gstack.*`, declared in
  `agents/*/agent.toml` with no provider pin), to the `gc.run-operator` or
  `gc.publisher` role, or to the caller-selected `{implementation_target}`
  for implementation and apply-fix lanes. No lane dispatches provider-native
  subagents.
- Base artifact contract: the pack writes stage artifacts under the inherited
  `{{artifact_root}}` and preserves the inherited artifact path vars
  (`{{requirements_path}}`, `{{plan_path}}`, `{{decomposition_path}}`) in its
  methodology stage assets. It preserves the `gc.build.*` handoff namespace on
  the workflow root bead (inherited base keys plus the review keys
  `code_review_status`, `code_review_approved_at`, `code_review_report_path`,
  `code_review_context_path`, `review_fix_summary_path`, and the pack-added
  `qa_summary_path` and `release_readiness_summary_path`). Structured
  artifacts follow the `gc.build.*.v1` schemas in `gascity/schemas/build/`
  (requirements, plan, decomposition, implementation-summary, review,
  final-report) validated by the shared
  `gascity/assets/scripts/validate_build_artifact.py`, which keeps
  traceability and coverage chains intact end to end.
- Review/fix loop behavior: the `review` anchor expands `gstack-code-review`:
  a setup node that records the review context and planned report on the
  workflow root, then a check-gated loop wrapper
  (`implementation-review-approved.sh`, 8 bounded attempts) whose child lanes
  are the sibling staff, QA-evidence, CSO-security, and gap-analysis
  reviewers, a `synthesize-code-review` fan-in (`gstack.review-synthesizer`),
  and an `apply-review-findings` lane routed to `{implementation_target}`
  that owns the `code_review.verdict=done|iterate` loop verdict consumed by
  the loop check. The loop controller re-runs only through child lanes in the
  graph. The QA and release-readiness anchors apply the same check-gated loop
  shape. `gstack-fix-loop` carries the standalone review-fix contract for
  adapter use.
- Final-report expectations: the review expansion target verifies the
  synthesized report and review-fix summary paths, then records
  `gc.build.code_review_status=approved` and
  `gc.build.code_review_approved_at` on the workflow root; the overridden
  `finalize` step writes the sprint report (methodology, modes, stage
  artifact paths, QA and release-readiness summaries, residual risks, next
  human action) under the artifact root; standalone `gstack-review` runs
  write the adapter-consumable report to `{{report_path}}` without posting
  comments, pushing branches, or finalizing external state.
- Prompt hygiene: all agent prompt templates under
  `agents/*/prompt.template.md` include the public `gc-role-worker` fragment
  supplied by the `gc` import; gstack does not override that shared claim
  protocol. Agent prompts and
  lane assets carry explicit "Do not invoke provider-native subagents" guards
  and route delegation through Gas City graph lanes. The skill texts under
  `skills/` are methodology source material only — when gstack text asks for
  a subagent or slash-command handoff, the consuming lane treats it as a Gas
  City lane or expansion child; the graph owns all fanout.
- Vendor provenance: `gstack/vendor/gstack/upstream.toml` records the
  upstream source repository, pinned commit, and MIT license. The `skills/`
  catalog is the pack's working copy of those vendored skills.

## Evidence Commands

Run these from the repository root:

```sh
sed -n '1,10p' gstack/pack.toml
grep -n -E '^id = ' gascity/formulas/build-base.formula.toml
grep -n -E '^extends|^formula = |^\[metadata\.gc\.methodology\]|policies|strategy|modes' gstack/formulas/gstack-build.formula.toml
grep -n -A 2 -E '^\[vars\.(interaction_mode|review_mode)\]' gascity/formulas/build-base.formula.toml
grep -n -E '^extends' gstack/formulas/gstack-planning.formula.toml gstack/formulas/gstack-decomposition.formula.toml gstack/formulas/gstack-review.formula.toml gstack/formulas/gstack-fix-loop.formula.toml gstack/formulas/gstack-implementation.formula.toml gstack/formulas/gstack-work.formula.toml gstack/formulas/gstack-work-item.formula.toml
grep -n -E '^id = |needs = ' gstack/formulas/gstack-build.formula.toml  # qa needs review; release-readiness needs qa; finalize needs release-readiness
grep -rn 'gc.run_target' gstack/formulas/*.toml  # expect only gstack.* agents, gc.run-operator, gc.publisher, or {implementation_target}
grep -rL 'gc-role-worker' gstack/agents/*/prompt.template.md  # expect no output
gc lint gstack
grep -rn 'provider-native' gstack/agents gstack/assets | wc -l  # expect >= 60
grep -rho 'gc\.build\.[a-z_.]*' gstack/assets gstack/formulas | sort -u
ls gascity/schemas/build
sed -n '1,10p' gstack/vendor/gstack/upstream.toml
python3 -m pytest gascity/tests/test_formula_assets.py -q
python3 - <<'PY'
import pathlib
import tomllib

base = tomllib.loads(pathlib.Path('gascity/formulas/build-base.formula.toml').read_text())
child = tomllib.loads(pathlib.Path('gstack/formulas/gstack-build.formula.toml').read_text())

assert child['extends'] == ['build-base']
base_order = [step['id'] for step in base['steps']]
child_order = [step['id'] for step in child['steps']]
added = {'qa', 'release-readiness'}
assert [s for s in child_order if s not in added] == \
    [s for s in base_order if s in child_order]
assert set(child_order) - added == {
    'requirements', 'plan', 'plan-review', 'decompose',
    'implement', 'implement-same-session', 'summarize-implementation',
    'review', 'finalize', 'publish',
}
assert set(base_order) - set(child_order) == {'prepare'}
steps = {step['id']: step for step in child['steps']}
assert steps['qa']['needs'] == ['review']
assert steps['release-readiness']['needs'] == ['qa']
assert steps['finalize']['needs'] == ['release-readiness']
assert steps['publish']['needs'] == ['finalize']
print('gstack-build preserves base anchors; qa and release-readiness inserted '
      'between review and finalize')
PY
```

## Notes

- `gstack/README.md` references this ledger so the pack documentation points
  to the compatibility contract directly.
- The ledger is pack-local; the base contracts remain defined by `gascity`
  and are inherited through `build-base`.

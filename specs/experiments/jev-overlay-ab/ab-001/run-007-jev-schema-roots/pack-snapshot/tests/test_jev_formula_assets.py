"""Static checks on the gascity-jev overlay: formulas, bond vars, roles, command, ledgers."""
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'gascity-jev'
sys.path.insert(0, str(PACK / 'assets/scripts'))
import jev_gate  # noqa: E402

FORMULAS = {'jev-build', 'jev-build-compact', 'jev-review-tail'}


def formula(name):
    return tomllib.loads((PACK / f'formulas/{name}.formula.toml').read_text())


def steps(data, key='steps'):
    return {s['id']: s for s in data.get(key, [])}


def test_pack_is_an_overlay_without_copied_base_content():
    pack = tomllib.loads((PACK / 'pack.toml').read_text())
    assert pack['pack']['name'] == 'gascity-jev'
    assert pack['imports']['gc']['source'] == '../gascity'
    names = {p.name.removesuffix('.formula.toml') for p in (PACK / 'formulas').glob('*.formula.toml')}
    assert names == FORMULAS
    base = {p.name for p in (ROOT / 'gascity/formulas').glob('*.toml')}
    assert not base & {p.name for p in (PACK / 'formulas').glob('*.toml')}
    for copied in ('schemas', 'skills', 'template-fragments', 'assets/scripts/checks'):
        assert not (PACK / copied).exists(), copied


def test_roles_import_base_roles_and_add_the_gate_worker():
    roles = tomllib.loads((PACK / 'roles/pack.toml').read_text())
    assert roles['pack']['name'] == 'gascity-jev-roles'
    assert (PACK / 'roles' / roles['imports']['gc']['source']).resolve() == (ROOT / 'gascity/roles').resolve()
    agent = tomllib.loads((PACK / 'roles/agents/jev-gate/agent.toml').read_text())
    assert agent['prompt_mode'] == 'none' and agent['lifecycle'] == 'one_shot' and agent['scope'] == 'rig'
    script = agent['start_command'].split()[1].replace('{{.ConfigDir}}', str(PACK / 'roles'))
    assert Path(script).resolve() == (PACK / 'assets/scripts/jev_gate.py').resolve()


def test_jev_build_replaces_review_with_the_gate_and_drops_the_tail():
    data = formula('jev-build')
    assert data['extends'] == ['build-basic'] and data['contract'] == 'graph.v2'
    s = steps(data)
    review = s['review']
    assert review['needs'] == ['summarize-implementation']
    assert review['metadata'] == {'gc.run_target': 'gc.jev-gate', 'jev.role': 'review-gate'}
    assert 'expand' not in review
    assert review['on_complete']['for_each'] == 'output.items' and review['on_complete']['bond'] == 'jev-review-tail'
    for name in ('finalize', 'publish'):
        assert s[name]['condition'] == '{{keep_inherited_tail}}' and s[name]['title']
    assert data['vars']['keep_inherited_tail']['default'] == ''
    for var in ('jev_mode', 'jev_model', 'jev_state_dir', 'jev_test_command', 'jev_audit_rate', 'jev_intake_decision'):
        assert var in data['vars']
    assert data['vars']['jev_model']['default'] == 'jev-1.13.0'


def test_every_bonding_formula_passes_every_gate_item_key():
    keys = set(jev_gate.full_item('x'))
    bond_vars = set(formula('jev-review-tail')['vars'])
    assert keys <= bond_vars
    for name in ('jev-build', 'jev-build-compact'):
        passed = steps(formula(name))['review']['on_complete']['vars']
        assert keys | {'implementation_target'} == set(passed), name
        assert all(passed[k] == f'{{item.{k}}}' for k in keys), name


def test_bond_gates_lanes_synthesis_and_loop_and_restates_contracts():
    data = formula('jev-review-tail')
    assert data['type'] == 'expansion'
    templates = steps(data, 'template')
    loop = templates['{target}.review-loop']
    assert loop['condition'] == '{{loop}} == run'
    assert loop['check']['check']['path'] == '.gc/scripts/checks/implementation-review-approved.sh'
    children = {c['id']: c for c in loop['children']}
    for lane, var in (('acceptance-review', 'acceptance'), ('test-evidence-review', 'test_evidence'),
                      ('simplicity-review', 'simplicity'), ('synthesize-review', 'synth')):
        assert children[f'{{target}}.{lane}']['condition'] == f'{{{{{var}}}}} == run'
    apply = children['{target}.apply-review-findings']
    assert set(apply['needs']) == {f'{{target}}.{x}' for x in ('acceptance-review', 'test-evidence-review',
                                                                  'simplicity-review', 'synthesize-review')}
    assert apply['metadata']['gc.run_target'] == '{implementation_target}'
    report = templates['{target}.review-report']
    assert report['metadata']['gc.run_target'] == 'gc.jev-gate'
    assert report['metadata']['gc.build.artifact_schema'] == 'gc.build.review.v1'
    assert report['check']['check']['path'] == '.gc/scripts/checks/build-artifact-valid.sh'
    final = templates['{target}.finalize']
    assert final['needs'] == ['{target}.review-report']
    assert final['metadata']['gc.build.artifact_schema'] == 'gc.build.final-report.v1'
    assert templates['{target}.publish']['needs'] == ['{target}.finalize']


def test_expansion_templates_use_single_brace_vars_outside_conditions():
    text = (PACK / 'formulas/jev-review-tail.formula.toml').read_text()
    for line in text.splitlines():
        if '{{' in line:
            assert line.startswith('condition = '), line
    for path in (PACK / 'assets/workflows/jev-review-tail').glob('*.md'):
        assert not re.search(r'\{\{(acceptance_scope|simplicity_scope|forwarded_smells|gate|implementation_target)\}\}',
                             path.read_text()), path.name


def test_compact_route_drops_planning_and_drains_after_prepare():
    data = formula('jev-build-compact')
    assert data['extends'] == ['jev-build']
    s = steps(data)
    for name in ('requirements', 'plan', 'plan-review', 'decompose', 'summarize-implementation'):
        assert s[name]['condition'] == '{{keep_full_stages}}'
    assert s['implement']['needs'] == ['prepare'] and s['implement']['drain']['formula'] == 'do-work'
    assert s['review']['needs'] == ['implement', 'implement-same-session']
    assert s['review']['metadata']['gc.run_target'] == 'gc.jev-gate'


def test_every_description_file_exists():
    for name in FORMULAS:
        data = formula(name)
        entries = data.get('steps', []) + data.get('template', [])
        entries += [c for t in data.get('template', []) for c in t.get('children', [])]
        for entry in entries:
            if 'description_file' in entry:
                assert (PACK / 'formulas' / entry['description_file']).resolve().is_file(), entry['id']


def test_route_command_and_intake_questions_ship():
    assert (PACK / 'commands/jev-route/run.sh').stat().st_mode & 0o111
    assert 'jev_route.py' in (PACK / 'commands/jev-route/run.sh').read_text()
    frozen = (ROOT / 'specs/experiments/jev-gate-spikes/intake-router/questions.frozen.json').read_text()
    assert (PACK / 'assets/jev-intake-questions.json').read_text() == frozen


def test_ledgers_cover_every_formula():
    ledger = (PACK / 'formulas/REQUIREMENTS.md').read_text()
    assert 'gc.jev-overlay-formulas.requirements.v1' in ledger
    for name in FORMULAS:
        assert re.search(rf'\|\s*GC-JEV-\d{{3}}\s*\|\s*`{re.escape(name)}`\s*\|', ledger), name
    assert 'gc.jev-overlay.requirements.v1' in (PACK / 'REQUIREMENTS.md').read_text()

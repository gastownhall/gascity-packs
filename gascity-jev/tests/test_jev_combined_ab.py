"""Combined benchmark preserves source contracts and counts regressions."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('jev_combined_ab', ROOT/'scripts/jev_combined_ab.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_combined_inputs_keep_gold_out_and_scope_each_question(tmp_path):
    case = json.loads((ROOT/'specs/experiments/jev-all-enabled/suite.json').read_text())['cases'][0]
    state, questions, expected, bundle = runner.prepare(case, tmp_path/'inputs')
    assert set(questions) == set(expected)
    assert set(state) == {'kind', 'findings', 'failure', 'evidence'}
    assert state['findings']['findings'] == case['findings']['state']['findings']
    assert state['kind'] == case['kind']['state']
    assert 'expected' not in state and 'provenance' not in state['kind']
    for key, question in questions.items():
        assert f'`{key.split(":")[0]}`' in question['instructions']
    assert runner.evidence.materialize(bundle) == state['evidence']


def test_only_accepted_jev_values_enter_joint_report():
    report = {'status':'completed', 'decision':{'answers':{'finding_0':{'choice':'required_fix'},'finding_1':{'choice':'unclear'}},'fallback_questions':['finding_1']}}
    assert runner.accepted(report, 'findings') == {'findings:finding_0':'required_fix'}
    report = {'status':'completed','decisions':[{'choice':'supported','route':'reviewer_check'}, {'choice':'unclear','route':'llm_review'}]}
    assert runner.accepted(report, 'evidence') == {'evidence:evidence_0':'supported'}
    assert runner.accepted({'status':'failed'}, 'kind') == {}


def test_failed_attempts_and_paired_quality_losses_remain_in_summary(tmp_path):
    schedule = [{'case_id':'case','arm':arm,'repetition':1} for arm in ['baseline','jev']]
    runner.save(tmp_path/'schedule.json',schedule)
    for i,arm in enumerate(['baseline','jev'],1):
        d=tmp_path/f'run-{i:03d}-{arm}';d.mkdir()
        runner.save(d/'result.json', {'case_id':'case','arm':arm,'state_sha256':'same',
            'status':'completed' if arm=='baseline' else 'failed',
            'expected':{'failure:failure':'unclear'},
            'answers':{'failure:failure':'unclear'} if arm=='baseline' else {},
            'ranking_top1':None, 'llm_tokens':dict.fromkeys((*runner.accounting.TOKEN_FIELDS,'totalTokens'),3),
            'jev_tokens':dict.fromkeys(('input_tokens','output_tokens'),2)})
    result=runner.summarize(tmp_path)
    assert result['finished_attempts']==2
    assert result['regressions']==1
    assert result['arms']['jev']['failed']==1
    assert result['arms']['jev']['llm_tokens']['totalTokens']==3

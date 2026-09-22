import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/scripts'))
import jev_tasks as tasks


def response(questions, overrides=None):
    answers = {}
    for key, question in questions.items():
        choice, confidence = (overrides or {}).get(key, (next(iter(question['criteria'])), .99))
        probabilities = dict.fromkeys(question['criteria'], 0.)
        probabilities[choice] = 1.
        answers[key] = {'type': 'choice', 'choice': choice, 'confidence': confidence,
                        'probabilities': probabilities}
    return {'model': 'jev-1.13.0', 'answers': answers,
            'usage': {'input_tokens': 100, 'output_tokens': 20}}


FINDINGS = {'findings': [
    {'id': 'a', 'text': 'The parser discards errors.', 'source': 'acceptance.md:10'},
    {'id': 'b', 'text': 'Return the parse error to the caller.', 'source': 'tests.md:20'},
    {'id': 'c', 'text': 'No multi-platform proof was run.', 'source': 'tests.md:30'},
]}


def test_finding_groups_preserve_all_sources_and_do_not_merge_transitively():
    state, questions = tasks.prepare('findings', FINDINGS)
    raw = response(questions, {'pair_0_1': ('same', .99), 'pair_1_2': ('same', .99),
                               'pair_0_2': ('different', .99)})
    result = tasks.decide('findings', state, questions, raw, .90)
    assert result['findings'] == FINDINGS['findings']
    assert result['possible_duplicate_pairs'] == [['a', 'b'], ['b', 'c']]
    assert 'groups' not in result


def test_ambiguous_and_residual_findings_require_review():
    state, questions = tasks.prepare('findings', FINDINGS)
    raw = response(questions, {'finding_0': ('required_fix', .4),
                               'finding_1': ('residual_risk', .99)})
    result = tasks.decide('findings', state, questions, raw, .90)
    assert {'finding_0', 'finding_1'} <= set(result['fallback_questions'])


def test_ranking_retains_every_candidate_and_never_declares_a_duplicate():
    data = {'issue': {'title': 'crash on empty config', 'body': 'read panics'},
            'candidates': [{'id': 'x', 'title': 'config crash', 'body': 'empty file'},
                           {'id': 'y', 'title': 'docs', 'body': 'guide'}],
            'expected': 'must never reach the model'}
    state, questions = tasks.prepare('duplicates', data)
    assert 'expected' not in json.dumps(state)
    result = tasks.decide('duplicates', state, questions, response(questions), .9)
    assert set(result['ranked_candidate_ids']) == {'x', 'y'}
    assert 'verdict' not in result and 'close' not in result


def test_invalid_distribution_and_missing_usage_rejected():
    state, questions = tasks.prepare('failure', {'command': 'pytest', 'output': 'assert failed', 'context': 'unit tests'})
    raw = response(questions)
    raw['answers']['failure']['probabilities']['product'] = float('nan')
    with pytest.raises(ValueError): tasks.decide('failure', state, questions, raw, .9)
    raw = response(questions); del raw['usage']
    with pytest.raises(ValueError): tasks.decide('failure', state, questions, raw, .9)


def test_auto_without_key_and_off_never_make_network_calls(tmp_path, monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    def forbidden(*a, **kw): raise AssertionError('network called')
    monkeypatch.setattr(tasks.transport, 'evaluate', forbidden)
    source = tmp_path / 'input.json'; source.write_text(json.dumps({'title': 'New export', 'body': 'Adds CSV'}))
    for mode in ('auto', 'off'):
        out = tmp_path / mode
        assert tasks.main(['kind', str(source), '--output-dir', str(out), '--mode', mode]) == 0
        report = json.loads((out / 'report.json').read_text())
        assert report['status'] == 'skipped' and report['route'] == 'llm'
        assert report['reason'] == ('missing_credential' if mode == 'auto' else 'disabled')


def test_http_failure_is_recorded_and_requires_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'test-only')
    def fail(*a, **kw): raise RuntimeError('HTTP 503')
    monkeypatch.setattr(tasks.transport, 'evaluate', fail)
    source = tmp_path / 'input.json'; source.write_text(json.dumps({'title': 'x', 'body': ''}))
    out = tmp_path / 'out'
    assert tasks.main(['kind', str(source), '--output-dir', str(out)]) == 1
    report = json.loads((out / 'report.json').read_text())
    assert report['status'] == 'failed' and report['route'] == 'llm'
    assert report['usage'] is None and '503' in report['error']


def test_oversize_duplicate_ids_and_model_drift_are_rejected():
    with pytest.raises(ValueError):
        tasks.prepare('findings', {'findings': [FINDINGS['findings'][0]] * 2})
    with pytest.raises(ValueError):
        tasks.prepare('failure', {'command': 'x', 'output': 'x' * (tasks.transport.MAX_BYTES + 1), 'context': ''})
    state, qs = tasks.prepare('kind', {'title': 'x', 'body': ''})
    raw = response(qs); raw['model'] = 'other-model'
    with pytest.raises(ValueError): tasks.decide('kind', state, qs, raw, .9)

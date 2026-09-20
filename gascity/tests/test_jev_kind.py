"""Kind routing and backtest denominators; no live inference in this suite."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gascity/assets/scripts'))
import jev_kind as kind


def response(choice='bug', confidence=.95):
    probabilities = dict.fromkeys(kind.CHOICES, .01)
    probabilities[choice] = 1 - .01 * (len(probabilities) - 1)
    return {'model': 'jev-test', 'usage': {'input_tokens': 42, 'output_tokens': 0},
            'answers': {'kind': {'type': 'choice', 'choice': choice,
                        'confidence': confidence, 'probabilities': probabilities}}}


def test_snapshot_uses_only_title_and_body_to_avoid_reference_leakage():
    snapshot = {'title': 'Crash at startup', 'body': 'Steps to reproduce...',
                'labels': ['kind/bug'], 'reference': 'bug', 'priority': 'p1'}
    assert kind.materialize(snapshot) == {'title': snapshot['title'], 'body': snapshot['body']}


@pytest.mark.parametrize('snapshot', [{}, {'title': 'x', 'body': None},
    {'title': '', 'body': ''}, {'title': 'x', 'body': 'a' * 200_001}])
def test_invalid_snapshot_fails(snapshot):
    with pytest.raises(ValueError):
        kind.materialize(snapshot)


def test_confident_kind_can_replace_kind_decision_with_repo_label():
    labels = {**kind.LABELS, 'feature': 'kind/enhancement'}
    decision = kind.decide(response('feature'), .85, labels)
    assert decision['route'] == 'use_kind'
    assert decision['label'] == 'kind/enhancement'


@pytest.mark.parametrize('choice,confidence', [('bug', .4), ('unclear', .99)])
def test_abstentions_require_llm_and_emit_no_label(choice, confidence):
    decision = kind.decide(response(choice, confidence), .85, kind.LABELS)
    assert decision['route'] == 'llm_kind'
    assert decision['label'] is None


@pytest.mark.parametrize('bad', ['usage', 'questions', 'choice', 'confidence', 'probabilities', 'model'])
def test_malformed_response_never_produces_a_kind(bad):
    raw = response()
    if bad == 'usage': del raw['usage']
    elif bad == 'questions': raw['answers']['priority'] = {}
    elif bad == 'model': raw['model'] = ''
    else: raw['answers']['kind'][bad] = None
    with pytest.raises(ValueError):
        kind.decide(raw, .85, kind.LABELS)


def test_attempt_records_request_and_is_immutable(tmp_path, monkeypatch):
    snapshot = tmp_path / 'source.json'
    snapshot.write_text(json.dumps({'title': 'Crash', 'body': 'Fails at startup'}))
    out = tmp_path / 'attempt'
    def evaluate(state, **kw):
        assert kw['question_set'] == kind.questions()
        return response()
    monkeypatch.setattr(kind.transport, 'evaluate', evaluate)
    assert kind.main([str(snapshot), '--output-dir', str(out)]) == 0
    report = json.loads((out / 'report.json').read_text())
    assert report['status'] == 'completed'
    assert report['decision']['label'] == 'kind/bug'
    assert report['usage']['input_tokens'] == 42
    assert report['state_sha256']
    with pytest.raises(FileExistsError):
        kind.main([str(snapshot), '--output-dir', str(out)])


def test_missing_key_records_failure_and_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    snapshot = tmp_path / 'source.json'
    snapshot.write_text(json.dumps({'title': 'Crash', 'body': ''}))
    out = tmp_path / 'failed'
    assert kind.main([str(snapshot), '--output-dir', str(out)]) == 1
    report = json.loads((out / 'report.json').read_text())
    assert report['status'] == 'failed'
    assert report['decision']['route'] == 'llm_kind'
    assert report['usage'] is None


def test_backtest_counts_fallbacks_and_failures_in_denominator():
    spec = importlib.util.spec_from_file_location('kind_backtest', ROOT / 'scripts/jev_kind_backtest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [
        {'reference': 'bug', 'status': 'completed', 'decision': {'choice': 'bug', 'route': 'use_kind'}},
        {'reference': 'docs', 'status': 'completed', 'decision': {'choice': 'chore', 'route': 'use_kind'}},
        {'reference': 'bug', 'status': 'completed', 'decision': {'choice': 'bug', 'route': 'llm_kind'}},
        {'reference': 'feature', 'status': 'failed', 'decision': {'choice': None, 'route': 'llm_kind'}},
    ]
    report = module.summarize(rows)
    assert report['cases'] == 4
    assert report['failures'] == 1
    assert report['fallbacks'] == 2
    assert report['coverage'] == .5
    assert report['agreement_on_answered'] == pytest.approx(2/3)
    assert report['agreement_on_routed'] == .5
    assert report['matching_routed_fraction_of_all'] == .25
    assert report['confusion']['docs']['chore'] == 1
    assert report['confusion']['feature']['failed'] == 1


def test_shared_transport_sends_kind_question_and_retains_raw_response(tmp_path, monkeypatch):
    import io
    monkeypatch.setenv('TYPESAFE_API_KEY', 'test-only')
    def open_request(request, timeout):
        payload = json.loads(request.data)
        assert payload['questions'] == kind.questions()
        assert payload['state'] == {'title': 'Crash', 'body': ''}
        assert timeout == 30
        return io.StringIO(json.dumps(response()))
    monkeypatch.setattr(kind.transport.urllib.request, 'urlopen', open_request)
    source = tmp_path / 'source.json'
    source.write_text(json.dumps({'title': 'Crash', 'body': '', 'labels': ['kind/docs']}))
    out = tmp_path / 'attempt'
    assert kind.main([str(source), '--output-dir', str(out)]) == 0
    request = json.loads((out / 'request.json').read_text())
    assert 'labels' not in request['state']
    assert json.loads((out / 'response.json').read_text()) == response()


def test_backtest_runner_preserves_frozen_reference_and_filters_request(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('kind_backtest', ROOT / 'scripts/jev_kind_backtest.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = {'schema': 'gc.kind-backtest.v1', 'reference_model': 'synthetic-test',
             'reference_effort': 'none', 'reference_provenance': 'unit test fixture, not model output',
             'split': 'pilot', 'cases': [{'id': 'case', 'reference': 'bug',
             'snapshot': {'title': 'Crash', 'body': '', 'labels': ['kind/bug']}}]}
    source = tmp_path / 'suite.json'
    source.write_text(json.dumps(suite))
    def evaluate(state, **kw):
        assert set(state) == {'title', 'body'}
        return response()
    monkeypatch.setattr(kind.transport, 'evaluate', evaluate)
    out = tmp_path / 'run'
    assert module.main([str(source), '--out', str(out)]) == 0
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['agreement_on_routed'] == 1
    assert summary['observed_tokens'] == {'input_tokens': 42, 'output_tokens': 0}
    assert summary['live_baseline_measured'] is False
    assert summary['llm_fallback_measured'] is False
    assert json.loads((out / 'suite.json').read_text()) == suite
    assert 'reference' not in json.loads((out / 'input-0001.json').read_text())
    assert json.loads((out / 'manifest.json').read_text())['sources']


import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('jev_ab', ROOT/'scripts/jev_ab.py')
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


def test_usage_includes_auxiliary_models_and_caches():
    a = dict(zip(ab.TOKEN_FIELDS, [2, 4, 3289, 2703]))
    b = dict(zip(ab.TOKEN_FIELDS, [1291, 12, 0, 0]))
    report = ab.usage({'modelUsage': {'sonnet': a, 'haiku': b}})
    assert report['totals']['totalTokens'] == 7301
    assert report['totals']['cacheReadInputTokens'] == 3289
    assert report['totals']['inputTokens'] == 1293


def test_missing_usage_is_not_zero():
    with pytest.raises(ValueError): ab.usage({})
    with pytest.raises(ValueError): ab.usage({'modelUsage': {'sonnet': {'outputTokens': 4}}})


def test_summary_counts_failed_attempts_and_known_usage(tmp_path):
    import json
    for n, row in enumerate([
        {'arm':'baseline','status':'completed','correct':True,'false_support':False,
         'elapsed_seconds':1,'llm_usage':{'totals':{'totalTokens':10}}},
        {'arm':'baseline','status':'failed','elapsed_seconds':5,'llm_usage':{'totals':{'totalTokens':20}}},
        {'arm':'baseline','status':'failed','elapsed_seconds':7,'llm_usage':None},
    ]):
        p=tmp_path/f'run-{n}';p.mkdir();(p/'result.json').write_text(json.dumps(row))
    r=ab.summarize(tmp_path)['arms'][0]
    assert r['attempts']==3 and r['completed']==1
    assert r['accuracy_all_attempts']==pytest.approx(1/3)
    assert r['elapsed_seconds_all_attempts']==13
    assert r['known_llm_tokens_all_attempts']==30
    assert r['llm_usage_unknown_attempts']==1


def test_failed_jev_fallback_keeps_missing_llm_usage_unknown(tmp_path, monkeypatch):
    state={'items':[{'id':'AC-1'}]}
    monkeypatch.setattr(ab,'fixture',lambda *a:{})
    monkeypatch.setattr(ab.jev,'materialize',lambda *a:state)
    monkeypatch.setattr(ab.jev,'evaluate',lambda *a,**k:{'model':'jev-1.13.0','usage':{'input_tokens':20,'output_tokens':0}})
    monkeypatch.setattr(ab.jev,'decisions',lambda *a:[{'id':'AC-1','choice':'unclear','route':'llm_review'}])
    def timeout(*a,**k):
        raise TimeoutError('CLI did not return telemetry')
    monkeypatch.setattr(ab,'cli_assess',timeout)
    result=ab.run({'id':'example','expected':'unclear'},'jev','sonnet',tmp_path/'run','jev-1.13.0',0.85)
    assert result['status']=='failed'
    assert result['llm_usage'] is None
    assert result['jev_usage']['input_tokens']==20

import importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import jev_tasks_ab as ab


def test_report_rejects_invented_quotes_but_keeps_usage(tmp_path,monkeypatch):
    state,questions=ab.tasks.prepare('kind',{'title':'Add CSV export','body':'New capability'})
    body={'answers':{'kind':'feature'},'report':[{'id':'kind','choice':'feature','quote':'Made up evidence'}]}
    raw={'result':json.dumps(body),'modelUsage':{'claude-opus-5':dict.fromkeys(ab.accounting.TOKEN_FIELDS,1)}}
    monkeypatch.setattr(ab.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(raw),stderr='',returncode=0))
    with pytest.raises(ValueError,match='quote'):
        ab.claude(state,questions,{},tmp_path/'call','claude-opus-5','max','report')
    assert json.loads((tmp_path/'call/telemetry.json').read_text())['totals']['totalTokens']==4


def test_baseline_prompt_excludes_expected_label_and_private_key(tmp_path,monkeypatch):
    state,questions=ab.tasks.prepare('kind',{'title':'Add CSV','body':'New export'})
    raw={'result':json.dumps({'answers':{'kind':'feature'}}),'modelUsage':{'claude-opus-5':dict.fromkeys(ab.accounting.TOKEN_FIELDS,1)}}
    monkeypatch.setenv('TYPESAFE_API_KEY','test-only-secret')
    def fake(*args,**kwargs):
        assert 'TYPESAFE_API_KEY' not in kwargs['env']
        payload=json.loads(kwargs['input'].split('\n',1)[1])
        assert set(payload)=={'state','questions','accepted_decisions'} and payload['accepted_decisions']=={}
        return SimpleNamespace(stdout=json.dumps(raw),stderr='',returncode=0)
    monkeypatch.setattr(ab.subprocess,'run',fake)
    answers,usage=ab.claude(state,questions,{},tmp_path/'call','claude-opus-5','max','decision')
    assert answers=={'kind':'feature'}


def test_fallback_resolves_only_unaccepted_decisions(tmp_path,monkeypatch):
    state,questions=ab.tasks.prepare('failure',{'command':'test','output':'timeout','context':'unknown'})
    raw={'result':json.dumps({'answers':{'failure':'product'}}),'modelUsage':{'claude-opus-5':dict.fromkeys(ab.accounting.TOKEN_FIELDS,1)}}
    monkeypatch.setattr(ab.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(raw),stderr='',returncode=0))
    with pytest.raises(ValueError,match='Accepted decision'):
        ab.claude(state,questions,{'failure':'environment'},tmp_path/'call','claude-opus-5','max','decision')

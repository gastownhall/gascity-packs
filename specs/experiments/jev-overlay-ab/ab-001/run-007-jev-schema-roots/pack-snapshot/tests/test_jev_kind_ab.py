import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import jev_kind_ab as ab


def test_prompt_excludes_reference_and_snapshot_metadata():
    case={'id':'one','reference':'bug','snapshot':{'title':'A title','body':'A body','labels':['kind/bug']}}
    prompt=ab.prompt_for(ab.kind.materialize(case['snapshot']))
    assert 'kind/bug' not in prompt and 'reference' not in prompt and 'A title' in prompt


def test_low_confidence_dispatches_fresh_claude_and_keeps_both_usage(tmp_path,monkeypatch):
    def jev(state,directory,model,threshold):
        return {'choice':'chore','route':'llm_kind','confidence':.1},{'input_tokens':80,'output_tokens':40},model
    monkeypatch.setattr(ab,'jev_assess',jev)
    calls=[]
    def claude(state,directory,model,effort):
        calls.append((state,effort))
        return 'feature',{'totals':{**dict.fromkeys(ab.evidence.TOKEN_FIELDS,1),'totalTokens':4},'models':{model:{}}}
    monkeypatch.setattr(ab,'claude_assess',claude)
    result=ab.run({'id':'one','snapshot':{'title':'Add export','body':'New command'}},'jev',tmp_path/'run','opus','max','jev-test',.85)
    assert result['status']=='completed' and result['choice']=='feature'
    assert result['raw_choice']=='chore' and result['fallback'] is True
    assert len(calls)==1 and result['llm_usage']['totals']['totalTokens']==4
    assert result['jev_usage']['input_tokens']==80


def test_failed_fallback_never_reports_zero_usage(tmp_path,monkeypatch):
    monkeypatch.setattr(ab,'jev_assess',lambda *a:({'choice':'unclear','route':'llm_kind','confidence':1},{'input_tokens':80,'output_tokens':40},'jev-test'))
    def fail(*a):raise TimeoutError('test timeout')
    monkeypatch.setattr(ab,'claude_assess',fail)
    r=ab.run({'id':'one','snapshot':{'title':'Unclear','body':''}},'jev',tmp_path/'run','opus','max','jev-test',.85)
    assert r['status']=='failed' and r['llm_usage'] is None and r['jev_usage']['input_tokens']==80


def test_invalid_decision_retains_claude_telemetry(tmp_path,monkeypatch):
    usage={k:1 for k in ab.evidence.TOKEN_FIELDS}
    raw={'result':'not JSON','modelUsage':{'claude-opus-test':usage}}
    from types import SimpleNamespace
    monkeypatch.setattr(ab.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(raw),stderr=''))
    with pytest.raises(ValueError):
        ab.claude_assess({'title':'x','body':''},tmp_path,'claude-opus-test','max')
    assert json.loads((tmp_path/'telemetry.json').read_text())['totals']['totalTokens']==4

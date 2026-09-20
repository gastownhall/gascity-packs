import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'assets/scripts'))
import jev_rank as rank

STATE={'issue':{'title':'CSV BOM rejected','body':'Valid UTF-8 with BOM fails.'},'candidates':[
 {'id':'a','title':'CSV quote escaping','body':'Commas need quoting.'},
 {'id':'b','title':'Import BOM failure','body':'UTF-8 CSV with BOM fails.'}]}

def test_rank_is_stable_retains_every_candidate_and_does_not_make_verdicts():
 raw={'model':'jev-1.13.0','answers':{'candidate_0':{'type':'noul','noul':.2},'candidate_1':{'type':'noul','noul':.9}},'usage':{'input_tokens':100,'output_tokens':10}}
 result=rank.decide(STATE,raw)
 assert result['ranked_candidate_ids']==['b','a'] and result['candidates']==STATE['candidates']
 assert result['requires_investigation'] is True and 'verdict' not in result
 raw['answers']['candidate_1']['noul']=.2
 assert rank.decide(STATE,raw)['ranked_candidate_ids']==['a','b']

def test_unknown_or_invalid_scores_cannot_remove_candidates():
 raw={'model':'jev-1.13.0','answers':{'candidate_0':{'type':'noul','noul':1}},'usage':{'input_tokens':1,'output_tokens':1}}
 with pytest.raises(ValueError):rank.decide(STATE,raw)
 raw['answers']['candidate_1']={'type':'noul','noul':float('nan')}
 with pytest.raises(ValueError):rank.decide(STATE,raw)

def test_renderer_copies_source_text_without_inventing_a_duplicate_claim():
 text=rank.render(STATE,['b','a'])
 assert text.index('Import BOM failure') < text.index('CSV quote escaping')
 assert 'Valid UTF-8 with BOM fails.' in text
 assert 'No duplicate verdict' in text


def test_empty_candidates_are_a_code_result_not_a_fabricated_model_response(tmp_path,monkeypatch):
 import json
 monkeypatch.delenv('TYPESAFE_API_KEY',raising=False)
 def forbidden(*a,**kw):raise AssertionError('empty ranking called the network')
 monkeypatch.setattr(rank.transport,'evaluate',forbidden)
 source=tmp_path/'input.json';source.write_text(json.dumps({'issue':STATE['issue'],'candidates':[]}))
 out=tmp_path/'out'
 assert rank.main([str(source),'--output-dir',str(out),'--mode','assist'])==0
 report=json.loads((out/'report.json').read_text())
 assert report.get('model') is None and report['reason']=='empty_candidates'
 assert report['decision']['ranked_candidate_ids']==[]
 assert not (out/'response.json').exists()

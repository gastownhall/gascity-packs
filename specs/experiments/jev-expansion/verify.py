#!/usr/bin/env python3
"""Reconcile frozen expanded cohorts with raw service/CLI artifacts; no model calls."""
import argparse,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]

def read(path):return json.loads(path.read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('cohorts',nargs='+',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 key=os.environ['TYPESAFE_API_KEY'].encode();assert len(key)>10
 fields=['inputTokens','outputTokens','cacheReadInputTokens','cacheCreationInputTokens']
 totals={'attempts':0,'claude_calls':0,'jev_calls':0,'failed_attempts':0};cohorts=[]
 for root in a.cohorts:
  manifest=read(root/'manifest.json');suite=read(root/'suite.json');cases={c['id']:c for c in suite['cases']}
  for name,sha in manifest['sources'].items():assert digest(root/name)==sha
  schedule=read(root/'schedule.json');assert len(schedule)==2*manifest['repetitions']*sum(c['split']==manifest['split'] for c in cases.values())
  pair_states={}
  for i,s in enumerate(schedule,1):
   run=root/f'run-{i:03d}-{s["arm"]}';result=read(run/'result.json');totals['attempts']+=1
   assert result['case_id']==s['case_id'] and result['arm']==s['arm']
   state=read(run/'input.json');questions=read(run/'questions.json');case=cases[s['case_id']]
   assert state==case['state']
   sha=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest();assert sha==result['state_sha256']
   pair=(s['case_id'],s['repetition']);assert pair_states.setdefault(pair,sha)==sha
   if result['status']!='completed':totals['failed_attempts']+=1
   if s['arm']=='jev':
    request=read(run/'jev/request.json');response=read(run/'jev/response.json');report=read(run/'jev/report.json')
    assert request=={'model':manifest['jev_model'],'state':state,'questions':questions}
    assert response['model']==manifest['jev_model'] and response['usage']==report['usage']==result['jev_usage']
    assert {k:v['choice'] for k,v in response['answers'].items()}==result['raw_answers']
    assert report['decision']['fallback_questions']==result['fallback_questions']
    totals['jev_calls']+=1
   if (run/'claude/telemetry.json').exists():
    raw=read(run/'claude/stdout.json');telemetry=read(run/'claude/telemetry.json')
    assert set(raw['modelUsage'])=={manifest['model']}
    usage={f:sum(v[f] for v in raw['modelUsage'].values()) for f in fields};usage['totalTokens']=sum(usage.values())
    assert result['llm_usage']['totals']==telemetry['totals']==usage
    prompt=json.loads((run/'claude/prompt.txt').read_text().split('\n',1)[1]);assert prompt['state']==state and prompt['questions']==questions
    trusted=prompt['accepted_decisions'];assert all(v==result['raw_answers'][k] and k not in result['fallback_questions'] for k,v in trusted.items())
    if s['arm']=='baseline':assert trusted=={}
    command=read(run/'claude/command.json');assert command[command.index('--model')+1]==manifest['model'] and command[command.index('--effort')+1]==manifest['effort']
    assert command[command.index('--tools')+1]=='' and '--safe-mode' in command
    if result['status']=='completed':assert read(run/'claude/parsed.json')['answers']==result['answers']
    totals['claude_calls']+=1
   else:assert result['llm_usage']['totals']['totalTokens']==0
   if result['status']=='completed':
    assert set(result['answers'])==set(case['expected'])
    assert result['correct']==sum(result['answers'][k]==v for k,v in case['expected'].items())
    assert result['quality_pass']==(result['answers']==case['expected'])
  cohorts.append({'cohort':root.name,'manifest_sha256':digest(root/'manifest.json'),'attempts':len(schedule)})
 files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p)]
 files+=list((REPO/'gascity/assets/scripts').glob('jev*.py'))+[REPO/'scripts/jev_tasks_ab.py']
 for path in files:
  if key in path.read_bytes():raise SystemExit('Credential found in artifact; value suppressed')
 report={'at':datetime.now(timezone.utc).isoformat(),'status':'passed',**totals,'cohorts':cohorts,'raw_usage_reconciled':True,'matched_state_and_questions':True,'ground_truth_excluded_from_requests':True,'known_credential_absent':True,'files_scanned':len(files),'host_load_average':os.getloadavg()}
 with a.out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(report))

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Audit ranking and evidence rerun artifacts, retaining the failed baseline."""
import hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
FIELDS=['inputTokens','outputTokens','cacheReadInputTokens','cacheCreationInputTokens']
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def usage(raw):
 totals={f:sum(v[f] for v in raw['modelUsage'].values()) for f in FIELDS};totals['totalTokens']=sum(totals.values());return totals

counts={'rank_attempts':0,'rank_claude_calls':0,'rank_jev_calls':0,'evidence_attempts':0,'evidence_failed_attempts':0,'evidence_claude_calls':0,'evidence_jev_calls':0}
for name in ['rank-pilot-001','rank-evaluation-001']:
 root=ROOT/name;manifest=read(root/'manifest.json');cases={c['id']:c for c in read(root/'suite.json')['cases']};pairs={}
 for source,sha in manifest['sources'].items():assert digest(root/source)==sha
 for i,s in enumerate(read(root/'schedule.json'),1):
  run=root/f'run-{i:03d}-{s["arm"]}';r=read(run/'result.json');state=read(run/'input.json');qs=read(run/'questions.json');case=cases[s['case_id']]
  assert r['status']=='completed' and state==case['state'] and r['arm']==s['arm'] and r['case_id']==case['id']
  assert r['state_sha256']==hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
  assert pairs.setdefault((case['id'],s['repetition']),r['state_sha256'])==r['state_sha256']
  ids=[c['id'] for c in state['candidates']];order=r['ranked_candidate_ids'];assert len(order)==len(ids) and set(order)==set(ids)
  assert r['top1_correct']==(order[0] in case['gold_top_ids'] if case['gold_top_ids'] else None)
  packet=(run/'candidates.md').read_text();assert all(c['title'] in packet and c['body'] in packet for c in state['candidates'])
  assert state['issue']['title'] in packet and state['issue']['body'] in packet and 'No duplicate verdict' in packet
  if s['arm']=='baseline':
   raw=read(run/'stdout.json');assert set(raw['modelUsage'])=={'claude-opus-5'}
   assert r['llm_usage']['totals']==read(run/'telemetry.json')['totals']==usage(raw)
   prompt=json.loads((run/'prompt.txt').read_text().split('\n',1)[1]);assert prompt=={'state':state,'questions':qs}
   counts['rank_claude_calls']+=1
  else:
   request=read(run/'jev/request.json');raw=read(run/'jev/response.json');report=read(run/'jev/report.json')
   assert request=={'model':manifest['jev_model'],'state':state,'questions':qs}
   assert raw['model']==manifest['jev_model'] and raw['usage']==report['usage']==r['jev_usage']
   assert set(raw['answers'])==set(qs)
   assert report['decision']['ranked_candidate_ids']==order and report['decision']['candidates']==state['candidates']
   assert report['decision']['requires_investigation'] is True
   assert r['llm_usage']['totals']['totalTokens']==0
   counts['rank_jev_calls']+=1
  counts['rank_attempts']+=1
root=ROOT/'evidence-rerun-001'
for path in root.glob('run-*/result.json'):
 r=read(path);run=path.parent;counts['evidence_attempts']+=1;counts['evidence_failed_attempts']+=r['status']=='failed'
 telemetry=run/('fallback/telemetry.json' if (run/'fallback').exists() else 'telemetry.json')
 if telemetry.exists():
  raw=read(telemetry.parent/'stdout.json');assert r['llm_usage']['totals']==read(telemetry)['totals']==usage(raw)
  assert set(raw['modelUsage'])=={'claude-sonnet-5'};counts['evidence_claude_calls']+=1
 if (run/'jev-response.json').exists():
  raw=read(run/'jev-response.json');assert r['jev_usage']==raw['usage'];counts['evidence_jev_calls']+=1
 elif r['arm']=='jev':
  # Historical harness names the raw response response.json.
  raw=read(run/'response.json');assert r['jev_usage']==raw['usage'];counts['evidence_jev_calls']+=1
assert counts['evidence_attempts']==28 and counts['evidence_failed_attempts']==1
key=os.environ['TYPESAFE_API_KEY'].encode();assert len(key)>10
files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'fixture' not in p.parts]
for p in files:
 if key in p.read_bytes():raise SystemExit('Credential found; value suppressed')
report={'at':datetime.now(timezone.utc).isoformat(),'status':'passed',**counts,'raw_usage_reconciled':True,'candidate_source_preserved':True,'key_absent':True,'files_scanned':len(files),'host_load_average':os.getloadavg()}
with (ROOT/'rank-evidence-verification-001.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))

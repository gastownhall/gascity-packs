#!/usr/bin/env python3
"""Summarize frozen experiment attempts; failures and missing usage stay visible."""
import argparse,json,statistics
from pathlib import Path


def summarize(root):
 manifest=json.loads((root/'manifest.json').read_text());suite=json.loads((root/'suite.json').read_text())
 cases={c['id']:c for c in suite['cases'] if c['split']==manifest['split']}
 schedule=json.loads((root/'schedule.json').read_text());rows=[];pairs={}
 for i,s in enumerate(schedule,1):
  path=root/f'run-{i:03d}-{s["arm"]}'/'result.json'
  if not path.exists():continue
  r=json.loads(path.read_text());assert r['case_id']==s['case_id'] and r['arm']==s['arm']
  r['repetition']=s['repetition'];rows.append(r);pairs.setdefault((r['case_id'],r['repetition']),{})[r['arm']]=r
 result={'cohort':root.name,'pipeline':manifest['pipeline'],'planned_attempts':len(schedule),'finished_attempts':len(rows),'tasks':{},'mismatches':[]}
 for task in sorted({c['task'] for c in cases.values()}):
  records=[r for r in rows if r['task']==task];arms={}
  for arm in ['baseline','jev']:
   group=[r for r in records if r['arm']==arm];complete=[r for r in group if r['status']=='completed'];usage=[r['llm_usage'] for r in group if r.get('llm_usage') is not None]
   arms[arm]={'attempts':len(group),'completed':len(complete),'failed':len(group)-len(complete),
       'expected_matches':sum(r['correct'] for r in complete),'questions':sum(r['questions'] for r in complete),
       'quality_pass_cases':sum(r['quality_pass'] for r in complete),'fallback_cases':sum(bool(r['fallback_questions']) for r in group),
       'fallback_questions':sum(len(r['fallback_questions']) for r in group),'jev_service_failures':sum(r['jev_failed'] for r in group),
       'llm_usage_unknown':len(group)-len(usage),'llm_tokens':{k:sum(u['totals'][k] for u in usage) for k in ['inputTokens','outputTokens','cacheReadInputTokens','cacheCreationInputTokens','totalTokens']},
       'jev_tokens':{k:sum(r['jev_usage'][k] for r in group if r.get('jev_usage') is not None) for k in ['input_tokens','output_tokens']},
       'jev_usage_unknown':sum(r.get('jev_usage') is None for r in group) if arm=='jev' else 0,
       'seconds':sum(r['elapsed_seconds'] for r in group),'median_seconds':statistics.median([r['elapsed_seconds'] for r in group]) if group else None}
  valid=[p for (key,rep),p in pairs.items() if cases[key]['task']==task and set(p)=={'baseline','jev'} and all(r['status']=='completed' for r in p.values())]
  metrics={'unique_cases':sum(c['task']==task for c in cases.values()),'paired_attempts':len(valid),'arms':arms,
           'raw_agreement':0,'final_agreement':0,'paired_questions':0,'baseline_correct_treatment_wrong':0,'treatment_correct_baseline_wrong':0}
  for pair in valid:
   b,j=pair['baseline'],pair['jev'];assert b['state_sha256']==j['state_sha256']
   expected=cases[b['case_id']]['expected']
   for key,e in expected.items():
    bv,jv=b['answers'][key],j['answers'][key];raw=(j['raw_answers'] or {}).get(key)
    metrics['paired_questions']+=1;metrics['raw_agreement']+=bv==raw;metrics['final_agreement']+=bv==jv
    metrics['baseline_correct_treatment_wrong']+=bv==e and jv!=e
    metrics['treatment_correct_baseline_wrong']+=jv==e and bv!=e
    if bv!=e or jv!=e or raw!=e:
     result['mismatches'].append({'case_id':b['case_id'],'repetition':b['repetition'],'question':key,'expected':e,'baseline':bv,'raw_jev':raw,'final_treatment':jv,'fallback':key in j['fallback_questions']})
  b,j=arms['baseline'],arms['jev']
  full=len(valid)==metrics['unique_cases']*manifest['repetitions'] and not any(a['failed'] or a['llm_usage_unknown'] or a['jev_usage_unknown'] for a in arms.values())
  metrics['claude_token_reduction']=1-j['llm_tokens']['totalTokens']/b['llm_tokens']['totalTokens'] if full and b['llm_tokens']['totalTokens'] else None
  metrics['time_reduction']=1-j['seconds']/b['seconds'] if full and b['seconds'] else None
  metrics['speed_ratio']=b['seconds']/j['seconds'] if full and j['seconds'] else None
  result['tasks'][task]=metrics
 return result


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('cohort',type=Path);p.add_argument('--out',type=Path);a=p.parse_args();s=summarize(a.cohort)
 if a.out:
  with a.out.open('x') as f:json.dump(s,f,indent=2);f.write('\n')
 print(json.dumps(s,indent=2))

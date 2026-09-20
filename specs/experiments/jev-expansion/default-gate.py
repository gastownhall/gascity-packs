#!/usr/bin/env python3
"""Apply the registered promotion rule to completed decision and report cohorts."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('decision',type=Path);p.add_argument('report',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
d=json.loads(a.decision.read_text());r=json.loads(a.report.read_text());result={}
for task in ['kind','findings','failure','duplicates']:
 reasons=[]
 for name,source in [('decision',d),('report',r)]:
  metrics=source['tasks'][task]
  if source['finished_attempts']!=source['planned_attempts']:reasons.append(name+': incomplete cohort')
  if metrics['baseline_correct_treatment_wrong']:reasons.append(name+': observed expected-answer regression')
  for arm in metrics['arms'].values():
   if arm['failed'] or arm['llm_usage_unknown'] or arm['jev_usage_unknown']:reasons.append(name+': failed or unmeasured attempt')
  if metrics['claude_token_reduction'] is None or metrics['claude_token_reduction']<=0:reasons.append(name+': no measured Claude token reduction')
  if metrics['time_reduction'] is None or metrics['time_reduction']<=0:reasons.append(name+': no measured time reduction')
 result[task]={'default':'off' if reasons else 'auto','reasons':reasons,'scope':'Observed benchmark gate only; does not prove universal quality or full-workflow speed.'}
with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result,indent=2))

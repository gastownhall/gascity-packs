#!/usr/bin/env python3
"""Order duplicate candidates; preserve all evidence and require investigation."""
import argparse,json,os,time
from pathlib import Path
from datetime import datetime,timezone
import jev_tasks as tasks
transport=tasks.transport
MODEL=tasks.MODEL
QUESTION_VERSION='gc.duplicate-ranking.v1'


def prepare(data):
 state,_=tasks.prepare('duplicates',data)
 questions={f'candidate_{i}':{'type':'noul','instructions':tasks.UNTRUSTED+
    f'Do issue and candidates[{i}] describe the same underlying problem or requested capability?',
    'criteria':{'true':'Matching trigger and affected behavior or matching requested capability; resolving one would resolve the other.',
                'false':'Only related keywords/component, distinct trigger or independently necessary fix, or insufficient evidence of equivalence.'}}
    for i in range(len(state['candidates']))}
 return state,questions


def decide(state,response,model=MODEL):
 questions=prepare(state)[1]
 if not isinstance(response,dict) or response.get('model')!=model:raise ValueError('unexpected model')
 answers=response.get('answers');usage=response.get('usage')
 if not isinstance(answers,dict) or set(answers)!=set(questions):raise ValueError('missing or excess candidate scores')
 if not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('input_tokens','output_tokens')):raise ValueError('invalid usage')
 if any(not isinstance(v,dict) or v.get('type')!='noul' or not transport.unit(v.get('noul')) for v in answers.values()):raise ValueError('invalid candidate score')
 order=sorted(range(len(state['candidates'])),key=lambda i:(-answers[f'candidate_{i}']['noul'],i))
 return {'ranked_candidate_ids':[state['candidates'][i]['id'] for i in order],
         'scores':{state['candidates'][i]['id']:answers[f'candidate_{i}']['noul'] for i in range(len(state['candidates']))},
         'candidates':state['candidates'],'requires_investigation':True}


def render(state,order):
 candidates={c['id']:c for c in state['candidates']}
 if len(order)!=len(candidates) or set(order)!=set(candidates):raise ValueError('ranking must preserve all candidate IDs')
 lines=['# Duplicate investigation order','', 'No duplicate verdict is supplied. Investigate candidates before applying the existing triage policy.',
        '', '## Source issue',state['issue']['title'],state['issue']['body']]
 for i,key in enumerate(order,1):
  c=candidates[key];lines.extend(['',f'## Candidate {i}: {key}',c['title'],c['body']])
 return '\n'.join(lines)+'\n'


def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output-dir',required=True,type=Path)
 p.add_argument('--model',default=MODEL);p.add_argument('--mode',choices=['auto','assist','off'],default='auto');a=p.parse_args(argv)
 a.output_dir.mkdir(parents=True,exist_ok=False);started=time.monotonic()
 report={'schema':'gc.duplicate-ranking.v1','question_version':QUESTION_VERSION,'requested_model':a.model,'mode':a.mode,'route':'ordinary_investigation','usage':None,'started_at':datetime.now(timezone.utc).isoformat()}
 try:
  state,questions=prepare(json.loads(a.input.read_text()));transport.save(a.output_dir/'state.json',state)
  transport.save(a.output_dir/'request.json',{'model':a.model,'state':state,'questions':questions})
  report['state_sha256']=transport.digest(json.dumps(state,sort_keys=True).encode())
  if a.mode=='off' or (a.mode=='auto' and not os.environ.get('TYPESAFE_API_KEY')):
   report.update(status='skipped',reason='disabled' if a.mode=='off' else 'missing_credential')
  elif not questions:
   decision={'ranked_candidate_ids':[],'scores':{},'candidates':[],'requires_investigation':True}
   report.update(status='completed',route='investigate_ranked_candidates',decision=decision,
                 usage={'input_tokens':0,'output_tokens':0},reason='empty_candidates')
   (a.output_dir/'candidates.md').write_text(render(state,[]))
  else:
   response=transport.evaluate(state,model=a.model,question_set=questions)
   transport.save(a.output_dir/'response.json',response)
   usage=response.get('usage') if isinstance(response,dict) else None
   if isinstance(usage,dict) and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens')):report['usage']=usage
   decision=decide(state,response,a.model)
   report.update(status='completed',route='investigate_ranked_candidates',decision=decision,model=response['model'],usage=response['usage'])
   (a.output_dir/'candidates.md').write_text(render(state,decision['ranked_candidate_ids']))
 except Exception as e:report.update(status='failed',error=f'{type(e).__name__}: {e}')
 report['elapsed_seconds']=time.monotonic()-started;transport.save(a.output_dir/'report.json',report)
 print(json.dumps({'status':report['status'],'route':report['route'],'report':str(a.output_dir/'report.json')}));return int(report['status']=='failed')


if __name__=='__main__':raise SystemExit(main())

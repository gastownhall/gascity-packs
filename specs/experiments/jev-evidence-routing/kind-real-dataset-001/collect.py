#!/usr/bin/env python3
"""Repeat the original read-only sampling rule; current GitHub results may differ."""
import argparse,hashlib,json,subprocess,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
args.out.mkdir(parents=True,exist_ok=False)
labels={'bug':['kind/bug'],'feature':['kind/feature','kind/enhancement'],'docs':['kind/docs'],'chore':['kind/chore']}
all_kinds={label:kind for kind,ls in labels.items() for label in ls}
queries=[];selected=[]
for kind,names in labels.items():
    candidates={}
    for label in names:
        endpoint='repos/gastownhall/gascity/issues?'+urllib.parse.urlencode({'state':'all','labels':label,'sort':'created','direction':'desc','per_page':30})
        result=subprocess.run(['gh','api',endpoint],capture_output=True,text=True,timeout=40)
        result.check_returncode();data=json.loads(result.stdout)
        queries.append({'endpoint':endpoint,'returned':len(data)})
        for row in data:
            record={k:row[k] for k in ('number','html_url','title','body','created_at','updated_at')}
            record['labels']=[x['name'] for x in row['labels']]
            record['source_type']='pr' if 'pull_request' in row else 'issue'
            candidates[row['number']]=record
    pool=sorted(candidates.values(),key=lambda r:r['number'],reverse=True)
    (args.out/f'candidates-{kind}.json').write_text(json.dumps(pool,indent=2)+'\n')
    eligible=[r for r in pool if {all_kinds[l] for l in r['labels'] if l in all_kinds}=={kind}
              and not any(l.startswith('kind/') and l not in all_kinds for l in r['labels'])
              and isinstance(r['body'],str) and r['title'].strip()
              and len(json.dumps({'title':r['title'],'body':r['body']}).encode())<=100_000]
    if len(eligible)<9:raise SystemExit('Insufficient eligible cases for fixed sampling plan')
    for i,row in enumerate(eligible[:9]):
        selected.append({'id':f'gascity-{row["number"]}','split':'pilot' if i==0 else 'evaluation',
            'url':row['html_url'],'source_type':row['source_type'],'reference':kind,
            'reference_source':'existing repository kind label; not adjudicated truth',
            'snapshot':{'title':row['title'],'body':row['body']},'captured_labels':row['labels'],
            'updated_at':row['updated_at']})
    print(f'{kind}: selected 9 of {len(eligible)} eligible items',flush=True)
selected.sort(key=lambda c:hashlib.sha256(c['id'].encode()).hexdigest())
suite={'schema':'gc.kind-ab-suite.v1','captured_at':datetime.now(timezone.utc).isoformat(),
       'selection':'Nine highest-numbered eligible per canonical kind; latest pilot, next eight evaluation; SHA256(id) order.',
       'queries':queries,'cases':selected}
(args.out/'suite.json').write_text(json.dumps(suite,indent=2)+'\n')

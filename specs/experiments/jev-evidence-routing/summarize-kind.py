#!/usr/bin/env python3
"""Compare the retained outputs of a paired kind-triage cohort."""
import argparse,json,statistics
from pathlib import Path


def summarize(root):
    manifest=json.loads((root/'manifest.json').read_text())
    suite=json.loads((root/'suite.json').read_text())
    cases={c['id']:c for c in suite['cases'] if c['split']==manifest['split']}
    schedule=json.loads((root/'schedule.json').read_text())
    rows={}
    for i,item in enumerate(schedule,1):
        p=root/f'run-{i:03d}-{item["arm"]}'/'result.json'
        if p.exists():
            row=json.loads(p.read_text());assert row['case_id']==item['id'] and row['arm']==item['arm']
            rows[item['id'],item['arm']]=row
    pairs=[]
    confusion={k:dict.fromkeys(['bug','feature','docs','chore','unclear','failed'],0) for k in ['bug','feature','docs','chore','unclear']}
    for key,case in cases.items():
        b=rows.get((key,'baseline'),{});j=rows.get((key,'jev'),{})
        complete=b.get('status')==j.get('status')=='completed'
        if complete:assert b['state_sha256']==j['state_sha256']
        raw=j.get('raw_choice');bc=b.get('choice');jc=j.get('choice')
        if bc:confusion[bc][raw or 'failed']+=1
        pairs.append({'id':key,'url':case['url'],'source_type':case['source_type'],
            'repository_kind':case['reference'],'claude_kind':bc,'raw_jev_kind':raw,
            'confidence':j.get('confidence'),'fallback':j.get('fallback'),
            'final_jev_arm_kind':jc,'complete':complete,
            'raw_agreement':complete and raw==bc,'final_agreement':complete and jc==bc,
            'baseline_seconds':b.get('elapsed_seconds'),'jev_arm_seconds':j.get('elapsed_seconds')})
    arms={}
    token_fields=['inputTokens','outputTokens','cacheReadInputTokens','cacheCreationInputTokens','totalTokens']
    for arm in ('baseline','jev'):
        group=[r for (key,a),r in rows.items() if a==arm]
        successful=[r for r in group if r['status']=='completed']
        usage=[r['llm_usage']['totals'] for r in group if r.get('llm_usage') is not None]
        ju=[r['jev_usage'] for r in group if isinstance(r.get('jev_usage'),dict) and all(type(r['jev_usage'].get(k)) is int for k in ('input_tokens','output_tokens'))]
        arms[arm]={'planned':len(cases),'finished':len(group),'completed':len(successful),
            'failed':sum(r['status']!='completed' for r in group),'missing':len(cases)-len(group),
            'repository_label_matches':sum(r['choice']==cases[r['case_id']]['reference'] for r in successful),
            'llm_usage_unknown':len(cases)-len(usage),
            'llm_tokens':{k:sum(u[k] for u in usage) for k in token_fields},
            'jev_usage_unknown':len(cases)-len(ju) if arm=='jev' else 0,
            'jev_tokens':{k:sum(u[k] for u in ju) for k in ('input_tokens','output_tokens')},
            'elapsed_seconds':sum(r['elapsed_seconds'] for r in group),
            'median_seconds':statistics.median(r['elapsed_seconds'] for r in group) if group else None,
            'fallbacks':sum(r.get('fallback',False) for r in group)}
    b,j=arms['baseline'],arms['jev']
    comparable=all(p['complete'] for p in pairs) and not (b['llm_usage_unknown'] or j['llm_usage_unknown'] or j['jev_usage_unknown'])
    routed=[p for p in pairs if p['complete'] and not p['fallback']]
    per_kind={}
    for k in ['bug','feature','docs','chore']:
        group=[p for p in pairs if p['repository_kind']==k]
        per_kind[k]={'cases':len(group),'raw_agreement':sum(p['raw_agreement'] for p in group),
                     'final_agreement':sum(p['final_agreement'] for p in group),
                     'fallbacks':sum(bool(p['fallback']) for p in group),
                     'claude_repository_matches':sum(p['claude_kind']==k for p in group),
                     'raw_jev_repository_matches':sum(p['raw_jev_kind']==k for p in group)}
    return {'scope':'Real title/body kind triage; agreement, not ground-truth accuracy or full workflow',
        'cohort':root.name,'model':manifest['model'],'effort':manifest['effort'],'jev_model':manifest['jev_model'],
        'cases':len(cases),'arms':arms,'pairs_complete':sum(p['complete'] for p in pairs),
        'raw_agreement':sum(p['raw_agreement'] for p in pairs),
        'final_agreement':sum(p['final_agreement'] for p in pairs),
        'routed_without_claude':len(routed),'routed_agreement':sum(p['raw_agreement'] for p in routed),
        'per_repository_kind':per_kind,'confusion_claude_to_raw_jev':confusion,
        'llm_token_reduction_fraction':1-j['llm_tokens']['totalTokens']/b['llm_tokens']['totalTokens'] if comparable and b['llm_tokens']['totalTokens'] else None,
        'elapsed_reduction_fraction':1-j['elapsed_seconds']/b['elapsed_seconds'] if comparable else None,
        'pairs':pairs}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cohort',type=Path);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    report=summarize(args.cohort)
    with args.out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('pairs','confusion_claude_to_raw_jev','per_repository_kind')}))

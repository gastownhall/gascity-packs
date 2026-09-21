"""Detailed all-enabled feature attribution from retained attempts."""
import json
from pathlib import Path

ROOT=Path(__file__).parent
COHORT=ROOT/'combined-001'


def analyze():
    summary=json.loads((COHORT/'summary.json').read_text())
    rows=[json.loads(p.read_text()) for p in sorted(COHORT.glob('run-*/result.json'))]
    features={}
    for task in ('kind','findings','failure','evidence','ranking'):
        entries=[r['helpers'][task] for r in rows if task in r['helpers']]
        quality={'helper_attempts':len(entries),'helper_completed':sum(e['status']=='completed' for e in entries),
                 'helper_seconds':sum(e['elapsed_seconds'] for e in entries),
                 'jev_tokens':{k:sum((e.get('usage') or {}).get(k,0) for e in entries) for k in ('input_tokens','output_tokens')},
                 'unknown_usage':sum(e.get('usage') is None for e in entries)}
        if task!='ranking':
            quality.update(raw_correct=0,raw_questions=0,accepted_questions=0,accepted_wrong=0,fallback_questions=0)
            for r in rows:
                if task not in r['helpers']:continue
                e=r['helpers'][task]
                expected={k.split(':',1)[1]:v for k,v in r['expected'].items() if k.startswith(task+':')}
                if e['status']!='completed':continue
                if task=='evidence':
                    raw={f'evidence_{i}':d['choice'] for i,d in enumerate(e['decisions'])}
                    fallback=[f'evidence_{i}' for i,d in enumerate(e['decisions']) if d['route']=='llm_review']
                else:
                    raw={k:v['choice'] for k,v in e['decision']['answers'].items()}
                    fallback=e['decision']['fallback_questions']
                for key,gold in expected.items():
                    quality['raw_questions']+=1
                    quality['raw_correct']+=raw.get(key)==gold
                    quality['fallback_questions']+=key in fallback
                    quality['accepted_questions']+=key not in fallback
                    quality['accepted_wrong']+=key not in fallback and raw.get(key)!=gold
            quality['baseline']=summary['arms']['baseline']['features'][task]
            quality['final_jev']=summary['arms']['jev']['features'][task]
            quality['paired_regressions']=sum(m['regression'] and m['question'].startswith(task+':') for m in summary['mismatches'])
            quality['paired_improvements']=sum(m['improvement'] and m['question'].startswith(task+':') for m in summary['mismatches'])
        features[task]=quality
    b,j=summary['arms']['baseline'],summary['arms']['jev']
    return {'features':features,'claude_token_reduction':1-j['llm_tokens']['totalTokens']/b['llm_tokens']['totalTokens'],
            'time_reduction':1-j['elapsed_seconds']/b['elapsed_seconds'],
            'mean_seconds':{a:summary['arms'][a]['elapsed_seconds']/summary['arms'][a]['attempts'] for a in ['baseline','jev']},
            'all_attempts_included':True,'scope':summary['scope']}


if __name__=='__main__':
    result=analyze()
    with (ROOT/'feature-analysis-001.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))

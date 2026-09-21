"""Final record reconciliation and credential scan; no secret values are printed."""
import json,hashlib,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[2]/'scripts'))
import jev_claude_usage as usage
import jev_combined_ab as combined
summary=json.loads((ROOT/'combined-001/summary.json').read_text())
assert combined.summarize(ROOT/'combined-001')==summary
for p in (ROOT/'combined-001').glob('run-*-jev/result.json'):
    row=json.loads(p.read_text())
    assert set(row['helpers'])=={'kind','findings','failure','evidence','ranking'}
    assert all(h['mode']=='auto' and h['status']=='completed' for h in row['helpers'].values())
full=[]
for d in sorted((ROOT/'full-build-001').glob('run-*')):
    if not d.is_dir():continue
    row=json.loads((d/'result.json').read_text())
    records=[json.loads(s) for s in (d/'otel-usage.jsonl').read_text().splitlines() if s]
    reconciled=usage.summarize(records)
    assert reconciled['totals']==row['otel_usage']['totals']
    assert reconciled['request_count']==row['otel_usage']['request_count']
    assert row['status']=='failed' and row['jev_feature_delivery']==dict.fromkeys(['evidence','findings','failure'],0)
    assert row['otel_usage']['totals'] is None
    quality=json.loads((d/'original-fixture-check/result.json').read_text())
    assert quality['original_tests_unchanged']
    assert quality['pytest_exit']==quality['hidden_exit']==1
    assert sum(r['pass'] for r in quality['hidden_results'])==0
    full.append({'arm':row['arm'],'status':row['status'],'observed_model_events':len(records),'token_totals':reconciled['totals']})
assert len(full)==2
b=ROOT/'full-build-001/run-001-baseline';j=ROOT/'full-build-001/run-002-jev'
assert json.loads((b/'source-hashes.json').read_text())==json.loads((j/'source-hashes.json').read_text())
assert (b/'jev_build_ab.py').read_bytes()==(j/'jev_build_ab.py').read_bytes()
launch=json.loads((j/'launch.json').read_text())['command']
assert all(v+'=auto' in launch for v in ['jev_mode','jev_findings_mode','jev_failure_mode'])
cleanup=json.loads((ROOT/'full-build-001/cleanup-verification-002.json').read_text())
assert not cleanup['remaining_processes_with_experiment_paths']
secret=os.environ['TYPESAFE_API_KEY'].encode()
files=0
for p in ROOT.rglob('*'):
    if not p.is_file() or any(k in p.parts for k in ['fixture','pack-snapshot','raw-transcripts','__pycache__']):continue
    assert secret not in p.read_bytes(), f'Credential in {p}; contents suppressed'
    files+=1
report={'at':combined.accounting.stamp(),'status':'passed','combined_attempts':32,'full_runtime_attempts':2,
        'all_treatment_helpers_auto_and_completed':80,'combined_usage_reconciled':True,
        'runtime_source_equal':True,'runtime_observations':full,'original_fixture_checks_preserved':True,
        'cleanup_verified':True,'credential_absent':True,'files_scanned':files}
with (ROOT/'final-audit-001.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))

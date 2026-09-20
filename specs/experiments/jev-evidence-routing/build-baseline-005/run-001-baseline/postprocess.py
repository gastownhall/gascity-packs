from pathlib import Path
import json,hashlib,subprocess,os,gzip,re,datetime,importlib.util
base=Path('/Users/csells/.bb/personal-workspaces/env_tcfp9gdfcc');repo=base/'gascity-jev';out=repo/'specs/experiments/jev-evidence-routing/build-baseline-005/run-001-baseline'
result=json.loads((out/'result.json').read_text());root=Path(json.loads((out/'runtime-path.json').read_text())['root']);rig=root/'fixture'
def save(name,value):
 with (out/name).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def copy(source,name):
 with (out/name).open('xb') as f:f.write(source.read_bytes())
print('[1/4] Capture final runtime evidence',flush=True)
for source,name in [(root/'gc-home/supervisor.log','supervisor.log'),(root/'city/.gc/runtime/packs/dolt/dolt.log','dolt.log'),(root/'city/.gc/events.jsonl','events.jsonl')]:
 if source.exists():copy(source,name)
art=rig/'.gc/inference-gate/build-basic';(out/'produced-artifacts').mkdir()
for p in art.glob('*.md'):copy(p,Path('produced-artifacts')/p.name)
latest={}
for line in (out/'events.jsonl').read_text().splitlines():
 try:row=json.loads(line)
 except json.JSONDecodeError:continue
 if row.get('subject','').startswith('fi-') and row.get('payload',{}).get('title'):latest[row['subject']]=row['payload']
save('beads-from-events.json',latest)
print('[2/4] Independent original tests and hidden checks',flush=True)
gold=json.loads((out/'quality-oracle.json').read_text())['original_test_sha256']['tests/test_slugger.py'];qualities=[]
for n,subject in enumerate(sorted(rig.rglob('slugger.py'))):
 directory=subject.parent;env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'};python=str(base/'jev-venv/bin/python')
 test=directory/'tests/test_slugger.py';unchanged=test.exists() and hashlib.sha256(test.read_bytes()).hexdigest()==gold
 r=subprocess.run([python,'-m','pytest','-q','-p','no:cacheprovider','tests/test_slugger.py'],cwd=directory,env=env,text=True,capture_output=True,timeout=60)
 with (out/f'independent-pytest-{n}.log').open('x') as f:f.write(r.stdout+r.stderr)
 hidden="import slugger; cases=[('  Hello, World!  ','hello-world'),('a---b___c','a-b-c'),('123 ABC','123-abc'),('!@#','')]; assert all(slugger.slugify(x)==y for x,y in cases)"
 h=subprocess.run([python,'-c',hidden],cwd=directory,env=env,text=True,capture_output=True,timeout=30)
 with (out/f'independent-hidden-{n}.log').open('x') as f:f.write(h.stdout+h.stderr)
 copy(subject,f'produced-slugger-{n}.py')
 qualities.append({'directory':str(directory),'pytest_exit':r.returncode,'original_tests_unchanged':unchanged,'hidden_exit':h.returncode,'implementation_changed':hashlib.sha256(subject.read_bytes()).hexdigest()!=json.loads((out/'initial-fixture.json').read_text())['files']['slugger.py']})
primary=next(q for q in qualities if q['directory']==str(rig));save('independent-quality.json',{'scope':'Independent checks after terminal workflow failure; original test hash pinned before dispatch',**primary,'candidates':qualities})
print('[3/4] Archive only this runtime’s Claude transcripts',flush=True)
projects=Path.home()/'.claude/projects';encoded=re.sub(r'[^a-zA-Z0-9]','-',str(root.resolve()));archive=out/'raw-transcripts';archive.mkdir();manifest=[]
for directory in projects.iterdir():
 if directory.name!=encoded and not directory.name.startswith(encoded+'-'):continue
 for p in directory.rglob('*.jsonl'):
  data=p.read_bytes();dst=archive/directory.name/(str(p.relative_to(directory))+'.gz');dst.parent.mkdir(parents=True,exist_ok=True)
  with dst.open('xb') as f:f.write(gzip.compress(data,mtime=0))
  manifest.append({'source':str(p),'local_archive':str(dst.relative_to(out)),'source_sha256':hashlib.sha256(data).hexdigest(),'archive_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'bytes':len(data)})
save('transcript-archive.json',{'retention':'All jsonl files under project directories matching this unique runtime; compressed copies excluded from Git, hashes retained.','files':manifest})
print('[4/4] Reconcile saved telemetry and terminal report',flush=True)
s=importlib.util.spec_from_file_location('usage',repo/'scripts/jev_claude_usage.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);usage=m.summarize([json.loads(l) for l in (out/'otel-usage.jsonl').read_text().splitlines()]);assert usage['totals']==result['otel_usage']['totals']
save('terminal-audit.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':result['status'],'observed_requests':usage['request_count'],'observed_tokens':usage['totals'],'raw_events_match_terminal_totals':True,'transcripts_archived':len(manifest),'load_average':os.getloadavg()})
copy(Path(__file__),'postprocess.py')
print(json.dumps({'status':result['status'],'elapsed_seconds':result['elapsed_seconds'],'usage':usage,'independent_quality':primary,'transcripts':len(manifest)},indent=2),flush=True)

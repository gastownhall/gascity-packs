"""Independent original-fixture checks, even when runtime setup never produced worktrees."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
assert (root/'result.json').exists(), 'Wait for the runtime attempt to finish'
workspace=Path(json.loads((root/'runtime-path.json').read_text())['root'])
fixture=workspace/'fixture'
out=root/'original-fixture-check';out.mkdir()
env=dict(os.environ)
for key in ('TYPESAFE_API_KEY','ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL'):
    env.pop(key,None)
initial=subprocess.check_output(['git','rev-list','--max-parents=0','HEAD'],cwd=fixture,text=True).strip()
assert '\n' not in initial
original=subprocess.check_output(['git','show',initial+':tests/test_slugger.py'],cwd=fixture)
current=(fixture/'tests/test_slugger.py').read_bytes()
(out/'original-tests.py').write_bytes(original)
(out/'current-tests.py').write_bytes(current)
(out/'slugger.py').write_bytes((fixture/'slugger.py').read_bytes())
report={'scope':'original fixture after runtime termination; not a successful workflow output','initial_commit':initial,
        'original_tests_unchanged':original==current,'original_test_sha256':hashlib.sha256(original).hexdigest()}
commands={'pytest':[sys.executable,'-m','pytest','-q','tests/test_slugger.py'],
          'hidden':[sys.executable,'-c',"import importlib.util,json; s=importlib.util.spec_from_file_location('subject','slugger.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); cases=[('  Hello, World!  ','hello-world'),('a---b___c','a-b-c'),('123 ABC','123-abc'),('!@#','')]; results=[]\nfor x,y in cases:\n try: actual=m.slugify(x); results.append({'input':x,'expected':y,'actual':actual,'pass':actual==y})\n except Exception as e: results.append({'input':x,'expected':y,'pass':False,'error':type(e).__name__})\nprint(json.dumps(results)); raise SystemExit(0 if all(r['pass'] for r in results) else 1)"]}
for label,command in commands.items():
    p=subprocess.run(command,cwd=fixture,capture_output=True,text=True,env=env,timeout=60)
    (out/(label+'.txt')).write_text(p.stdout+p.stderr)
    report[label+'_exit']=p.returncode
    if label=='hidden':report['hidden_results']=json.loads(p.stdout)
(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

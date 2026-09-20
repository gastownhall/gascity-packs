from pathlib import Path
import subprocess,json,os,tempfile,shlex
base=Path('/Users/csells/.bb/personal-workspaces/env_tcfp9gdfcc');out=base/'gascity-jev/specs/experiments/jev-evidence-routing/diagnosis/gate-python';out.mkdir();root=Path(tempfile.mkdtemp(prefix='jev-gate-python-',dir='/tmp'));script=root/'check.sh';script.write_text('#!/bin/sh\ncommand -v python3\npython3 -c "import yaml, jsonschema; print(yaml.__file__)"\n');script.chmod(0o755)
env={**os.environ,'PATH':str(base/'jev-venv/bin')+':'+str(base/'gascity-runtime-diagnosis/build')+':'+str(base/'beads-init-diagnosis/build/bin')+':'+os.environ['PATH']};rows=[]
for label in ('red','green'):
 if label=='green':
  shim=root/'bin';shim.mkdir();(shim/'bd').symlink_to(base/'beads-init-diagnosis/build/bin/bd');p=shim/'python3';p.write_text('#!/bin/sh\nexec '+shlex.quote(str(base/'jev-venv/bin/python3'))+' "$@"\n');p.chmod(0o755);env['PATH']=str(shim)+':'+env['PATH']
 print('Testing '+label+' condition environment',flush=True);r=subprocess.run([str(base/'gascity-runtime-diagnosis/build/condition-probe'),str(script),str(root)],env=env,capture_output=True,text=True,timeout=60);d={'label':label,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr};rows.append(d);print(json.dumps(d),flush=True)
(out/'result.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'probe.py').write_bytes(Path(__file__).read_bytes())

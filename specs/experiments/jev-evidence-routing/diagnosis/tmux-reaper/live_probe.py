from pathlib import Path
import subprocess,uuid,json,time,shutil
base=Path('/Users/csells/.bb/personal-workspaces/env_tcfp9gdfcc')
out=base/'gascity-jev/specs/experiments/jev-evidence-routing/diagnosis/tmux-reaper'
socket='jev-reaper-probe-'+uuid.uuid4().hex[:10]
retired=socket+'-retired';active=socket+'-active';city='/private/tmp/'+socket
prefix=['tmux','-L',socket]
def tmux(*args):return subprocess.check_output([*prefix,*args],text=True,stderr=subprocess.STDOUT,timeout=30)
report={'socket':socket,'signals_to_scanned_processes':False}
try:
 tmux('-f','/dev/null','new-session','-d','-s','retired','-e','GC_SESSION_ID='+retired,'-e','GC_CITY='+city,'/bin/sleep 300')
 tmux('new-session','-d','-s','peer','-e','GC_SESSION_ID='+active,'-e','GC_CITY='+city,'/bin/sleep 300')
 server=int(tmux('display-message','-p','-t','peer','#{pid}').strip());report['server_pid']=server
 tmux('kill-session','-t','retired');time.sleep(1)
 for label in ('red','green'):
  print('Running '+label+' scanner against retired session',flush=True)
  start=time.monotonic();r=subprocess.run([str(base/'gascity-runtime-diagnosis/build'/('scan-'+label)),retired],capture_output=True,text=True,timeout=90)
  report[label]={'exit':r.returncode,'seconds':time.monotonic()-start,'rows':json.loads(r.stdout),'stderr':r.stderr}
  assert r.returncode==0
 assert server in [r['PID'] for r in report['red']['rows']],report
 assert not report['green']['rows'],report
 tmux('has-session','-t','peer');report['peer_survived']=True;report['status']='passed'
finally:
 r=subprocess.run([*prefix,'kill-server'],capture_output=True,text=True,timeout=30);report['cleanup_exit']=r.returncode
 (out/'live-probe-result.json').write_text(json.dumps(report,indent=2)+'\n')
 shutil.copy2(__file__,out/'live_probe.py')
print(json.dumps(report,indent=2))

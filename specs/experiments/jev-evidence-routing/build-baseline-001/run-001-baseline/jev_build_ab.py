#!/usr/bin/env python3
"""Run isolated build-basic A/B arms through Gas City with subscription Claude.

Retains cities, evidence, logs and transcript usage. Full build timing includes
city initialization, execution, independent verification and city shutdown.
No success is inferred from dispatch. A Jev arm without a completed Jev report
is a treatment failure, even if the fallback build passes.
"""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import tempfile
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inference_gate', ROOT/'scripts/gascity_pack_inference_gate.py')
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)
usage_spec = importlib.util.spec_from_file_location('jev_claude_usage', ROOT/'scripts/jev_claude_usage.py')
usage = importlib.util.module_from_spec(usage_spec)
usage_spec.loader.exec_module(usage)


def save(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def transcript_usage(projects, workspace, out):
    # Read only project directories whose encoded path includes this unique run.
    # Deduplicate repeated assistant chunks by message id, taking maximal counters.
    encoded = re.sub(r'[^a-zA-Z0-9]', '-', str(workspace.resolve()))
    messages, files = {}, []
    keys = ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')
    for directory in projects.iterdir():
        if directory.name != encoded and not directory.name.startswith(encoded + '-'):
            continue
        for path in directory.rglob('*.jsonl'):
            selected = []
            for line in path.read_text().splitlines():
                row = json.loads(line)
                msg = row.get('message', {})
                if row.get('type') != 'assistant' or not isinstance(msg, dict) or 'usage' not in msg:
                    continue
                identity = (row.get('sessionId'), msg.get('id'))
                if not all(identity):
                    raise ValueError('Transcript usage lacks stable session/message identity')
                u = msg['usage']
                if any(type(u.get(k)) is not int or u[k] < 0 for k in keys):
                    raise ValueError('Incomplete transcript usage; do not replace missing counters with zero')
                old = messages.setdefault(identity, {'model': msg.get('model'), **dict.fromkeys(keys, 0)})
                for k in keys: old[k] = max(old[k], u[k])
                selected.append({'session_id': identity[0], 'message_id': identity[1], 'model': msg.get('model'), 'usage': u})
            if selected:
                files.append({'source': str(path), 'records': selected})
    save(out/'transcript-usage-records.json', files)
    return {'status': 'observed' if messages else 'missing',
            'coverage': 'Recorded assistant messages only; auxiliary CLI calls may not appear in transcripts.',
            'message_count': len(messages), 'models': sorted({m['model'] for m in messages.values() if m['model']}),
            'totals': {k: sum(m[k] for m in messages.values()) for k in keys} if messages else None}



def stop_disposable_dolt(city):
    """Stop leftover server only when its exact config is inside this run's city."""
    config = city.resolve()/'.gc/runtime/packs/dolt/dolt-config.yaml'
    result = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True)
    if result.returncode:
        return {'status': 'unverified', 'error': result.stderr.strip()}
    signalled = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        command = re.fullmatch(r'(?:\S*/)?dolt sql-server --config (.+)', fields[1]) if len(fields) == 2 else None
        if command and Path(command.group(1)).resolve() == config:
            pid = int(fields[0])
            try:
                os.kill(pid, signal.SIGTERM)
                signalled.append(pid)
            except ProcessLookupError:
                pass
    return {'status': 'termination_requested' if signalled else 'no_leftover_server', 'pids': signalled}


def configure_experiment_env(env, workspace, *, real_home):
    env = dict(env)
    env['HOME'] = str(real_home)
    env['GIT_CONFIG_GLOBAL'] = str(workspace.gc_home/'gitconfig')
    env['DOLT_ROOT_PATH'] = str(workspace.gc_home)
    env.pop('BD_ALLOW_REMOTE_MIGRATE', None)
    return env


def new_runtime_workspace(pack, name):
    # macOS sockaddr_un cannot hold paths under the artifact directory.
    root = Path(tempfile.mkdtemp(prefix='gcja-', dir='/tmp'))/'w'
    workspace = gate.write_gate_workspace(root, pack_source=pack.source,
        roles_source=pack.roles_source, city_name='jev-ab-'+name, rig_name='fixture')
    if len(str(workspace.gc_home/'supervisor.sock').encode()) >= 100:
        raise ValueError('Runtime path is too long for a portable Unix socket')
    return workspace


def run(args, arm, out):
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'arm': arm, 'scope': 'full-build-basic', 'started_at': datetime.now(timezone.utc).isoformat(),
              'model': args.model, 'jev_model': args.jev_model, 'status': 'starting'}
    pack = gate.PACK_SPECS['gascity']
    workspace = new_runtime_workspace(pack, out.name)
    save(out/'runtime-path.json', {'root': str(workspace.root), 'retained': True})
    # A nested city must not inherit the parent repository's remote during bd init.
    subprocess.run(['git', 'init', '-q', str(workspace.city_dir)], check=True)
    env = gate.build_gate_env(args.gc_bin, workspace, bd_bin=args.bd_bin)
    # Isolate the controller's state. Workers use the existing subscription login.
    real_home = Path.home()
    real_claude = Path(os.environ.get('CLAUDE_CONFIG_DIR', real_home/'.claude')).resolve()
    env = configure_experiment_env(env, workspace, real_home=real_home)
    env['CLAUDE_CONFIG_DIR'] = str(real_claude)
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env['PATH']
    for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'OLLAMA_API_KEY',
                'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
        env.pop(key, None)
    if arm == 'jev' and not args.setup_only:
        env['TYPESAFE_API_KEY'] = os.environ['TYPESAFE_API_KEY']
    config = workspace.city_dir/'city.toml'
    text = config.read_text().replace('HOME = '+gate.toml_string(workspace.gc_home),
        'HOME = '+gate.toml_string(real_home)+'\nCLAUDE_CONFIG_DIR = '+gate.toml_string(real_claude))
    text = text.replace('base = "builtin:claude"', 'base = "builtin:claude"\nargs_append = '+
        json.dumps(['--model', args.model, '--effort', 'low', '--setting-sources', 'project,local']))
    config.write_text(text)
    versions = {name: subprocess.check_output(cmd, text=True).strip() for name,cmd in
                [('gc',[args.gc_bin,'version']),('bd',[args.bd_bin,'version']),('claude',['claude','--version']),('bash',['bash','--version'])]}
    save(out/'manifest.json', {'argv': sys.argv, 'versions': versions, 'model': args.model,
         'jev_model': args.jev_model, 'arm': arm, 'core_source': os.environ.get('GASCITY_SOURCE_ROOT'),
         'pack_git_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         'pack_diff': subprocess.check_output(['git','diff','--','gascity'],cwd=ROOT,text=True)})
    (out/'jev_build_ab.py').write_bytes(Path(__file__).read_bytes())
    save(out/'source-hashes.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), ROOT/'scripts/gascity_pack_inference_gate.py', ROOT/'scripts/jev_claude_usage.py',
                  *sorted((ROOT/'gascity').rglob('*'))] if p.is_file() and '__pycache__' not in p.parts})
    # Snapshot all current pack assets, including untracked new files.
    shutil.copytree(ROOT/'gascity', out/'pack-snapshot', ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    collector = usage.Collector(out/'otel-usage.jsonl')
    env.pop('CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC', None)
    env.update(collector.env)
    config.write_text(config.read_text().replace('[workspace.env]', '[workspace.env]\n' +
        '\n'.join(f'{k} = {gate.toml_string(v)}' for k,v in collector.env.items())))
    with (out/'run.log').open('x', buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
        try:
            gate.initialize_city(args.gc_bin, workspace, pack_spec=pack, gates=['build-basic'], env=env,
                seed_claude_state=False, init_timeout=args.setup_timeout)
            report['setup_seconds'] = time.monotonic() - started
            if args.setup_only:
                report['status'] = 'setup_only'
            else:
                gate.start_city(args.gc_bin, workspace, env=env)
                cmd = [args.gc_bin,'--city',str(workspace.city_dir),'--rig','fixture',
                       'sling','gc.run-operator','--stdin','--force','--on','build-basic',
                       '--title',gate.BUILD_TITLE,'--nudge','--json']
                variables = {'artifact_root':str(gate.BUILD_ARTIFACT_ROOT),'interaction_mode':'headless',
                    'review_mode':'agent','drain_policy':'separate','push':'false','open_pr':'false',
                    'max_iterations':'2','jev_mode':'assist' if arm=='jev' else 'off',
                    'jev_model':args.jev_model,'jev_threshold':'0.85'}
                for k,v in variables.items(): cmd += ['--var',f'{k}={v}']
                save(out/'launch.json', {'command':cmd,'task':gate.build_basic_work_item()})
                dispatched = gate.run_checked(cmd,cwd=workspace.rig_dir,env=env,timeout=120,
                                              input_text=gate.build_basic_work_item(),log_output=True)
                root_id = gate.resolve_workflow_root_id(args.gc_bin,workspace,env=env,
                    candidate_id=gate.extract_sling_root_id(dispatched),title=gate.BUILD_TITLE,
                    source_title=gate.BUILD_SOURCE_TITLE,timeout=30)
                report['root_id'] = root_id
                root = gate.wait_for_workflow_pass(args.gc_bin,workspace,root_id,env=env,
                                                  timeout=args.timeout,poll_interval=15)
                beads = gate.list_beads(args.gc_bin,workspace,env=env)
                save(out/'beads.json',beads)
                gate.validate_build_basic_artifacts(root,rig_dir=workspace.rig_dir,env=env,validator_source=pack.source)
                result_path = gate.validate_build_basic_result(workspace.rig_dir,[root,*beads],env=env,timeout=120)
                report.update(status='completed',fixture_tests_pass=True,result_path=str(result_path))
                # Hidden checks evaluate the produced function without trusting edited tests.
                hidden = "import importlib.util; s=importlib.util.spec_from_file_location('subject','slugger.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); cases=[('  Hello, World!  ','hello-world'),('a---b___c','a-b-c'),('123 ABC','123-abc'),('!@#','')]; assert all(m.slugify(x)==y for x,y in cases)"
                gate.run_checked([sys.executable,'-c',hidden],cwd=result_path,env=env,timeout=30,log_output=True)
                report['hidden_tests_pass'] = True
                jev_reports=[]
                for p in workspace.rig_dir.rglob('report.json'):
                    d=json.loads(p.read_text())
                    if d.get('schema')=='gc.evidence-assessment.v1': jev_reports.append({'path':str(p),**d})
                save(out/'jev-reports.json',jev_reports)
                if arm=='jev' and not any(r.get('status')=='completed' for r in jev_reports):
                    raise ValueError('Treatment not delivered: no completed Jev assessment; fallback is not a Jev result')
        except Exception as e:
            report.update(status='failed',error=f'{type(e).__name__}: {e}')
            print(report['error'],flush=True)
        finally:
            try:
                gate.stop_city(args.gc_bin,workspace,env=env)
                report['cleanup'] = stop_disposable_dolt(workspace.city_dir)
            finally:
                report['otel_usage'] = collector.close()
                report['otel_usage']['coverage'] = 'Local Claude API-request events; validate delivery and auxiliary coverage before comparing totals.'
    report['elapsed_seconds'] = time.monotonic()-started
    projects=real_claude/'projects'
    try:
        report['llm_usage'] = transcript_usage(projects,workspace.root,out) if projects.exists() else {'status':'missing'}
    except Exception as e:
        report['llm_usage'] = {'status':'failed','error':str(e)}
    save(out/'result.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--arms',choices=['baseline','jev','both'],default='both')
    p.add_argument('--repetitions',type=int,default=2)
    p.add_argument('--model',default='claude-sonnet-5')
    p.add_argument('--jev-model',default='jev-1.13.0')
    p.add_argument('--gc-bin',default='/opt/homebrew/bin/gc')
    p.add_argument('--bd-bin',default='/opt/homebrew/bin/bd')
    p.add_argument('--timeout',type=float,default=1200)
    p.add_argument('--setup-timeout',type=float,default=900)
    p.add_argument('--setup-only',action='store_true')
    args=p.parse_args()
    if args.arms!='baseline' and not args.setup_only and not os.environ.get('TYPESAFE_API_KEY'):
        p.error('Live Jev requires TYPESAFE_API_KEY')
    if args.repetitions<1:p.error('repetitions must be positive')
    args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    schedule=[]
    for r in range(args.repetitions):
        arms=(['baseline','jev'] if r%2==0 else ['jev','baseline']) if args.arms=='both' else [args.arms]
        schedule.extend((r,a) for a in arms)
    save(args.out/'schedule.json',[{'repetition':r,'arm':a} for r,a in schedule])
    for i,(r,a) in enumerate(schedule,1):
        name=f'run-{i:03d}-{a}'
        print(f'[{i}/{len(schedule)}] {name} starting; log: {args.out/name/"run.log"}',flush=True)
        try:
            result=run(args,a,args.out/name)
        except Exception as e:
            result={'status':'failed','arm':a,'scope':'full-build-basic','error':f'{type(e).__name__}: {e}'}
            save(args.out/(name+'-setup-failure.json'),result)
        print(f'[{i}/{len(schedule)}] {result["status"]}: {result.get("error", "")}',flush=True)
        if result['status']=='failed':sys.exit(1)


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Run isolated build-basic A/B arms through Gas City with subscription Claude.

Each arm follows the documented operator path in a disposable standalone city:
`gc init`, `gc import add`, `gc rig add` on a cloned fixture with an origin,
`gc bd create`, then `gc sling <bead> --on build-basic`. Gas City defaults are
kept (patrol interval, provider readiness, startup-dialog handling). Only the
supervisor is isolated under a private GC_HOME so the user's own cities are
never touched.

Retains cities, evidence, logs and transcript usage. Full build timing includes
city initialization, execution, independent verification and city shutdown.
No success is inferred from dispatch. A Jev arm without a completed Jev report
is a treatment failure, even if the fallback build passes.
"""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shlex
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
sys.path.insert(0, str(ROOT/'scripts'))
import jev_ab_workloads as workloads  # noqa: E402
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



def stop_disposable_dolt(city, rig=None):
    """Stop leftover servers only when their exact paths are inside this run's city or rig.

    Gas City 1.4 runs Dolt from the dolt pack's runtime directory. Gas City 1.5
    runs city and rig stores under `.beads/dolt` behind `bd db-proxy-child`
    processes that `gc stop` leaves running; proxies are stopped before servers.
    """
    city = city.resolve()
    stores = [city/'.beads/dolt'] + ([rig.resolve()/'.beads/dolt'] if rig else [])
    configs = {city/'.gc/runtime/packs/dolt/dolt-config.yaml', *(root/'config.yaml' for root in stores)}
    proxy_roots = set(stores)
    result = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True)
    if result.returncode:
        return {'status': 'unverified', 'error': result.stderr.strip()}
    proxies, servers = [], []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2:
            continue
        proxy = re.match(r'(?:\S*/)?bd db-proxy-child --root (\S+)', fields[1])
        server = re.fullmatch(r'(?:\S*/)?dolt sql-server --config (.+)', fields[1])
        if proxy and Path(proxy.group(1)).resolve() in proxy_roots:
            proxies.append(int(fields[0]))
        elif server and Path(server.group(1)).resolve() in configs:
            servers.append(int(fields[0]))
    signalled = []
    for pid in proxies + servers:
        try:
            os.kill(pid, signal.SIGTERM)
            signalled.append(pid)
        except ProcessLookupError:
            pass
    return {'status': 'termination_requested' if signalled else 'no_leftover_server', 'pids': signalled}


def configure_experiment_env(env, workspace, *, real_home, claude_config_dir=None):
    env = dict(env)
    env['HOME'] = str(real_home)
    env['GIT_CONFIG_GLOBAL'] = str(workspace.gc_home/'gitconfig')
    env['DOLT_ROOT_PATH'] = str(workspace.gc_home)
    env.pop('BD_ALLOW_REMOTE_MIGRATE', None)
    # An explicit default directory changes Claude's config/auth namespace.
    if claude_config_dir:
        env['CLAUDE_CONFIG_DIR'] = str(claude_config_dir)
    else:
        env.pop('CLAUDE_CONFIG_DIR', None)
    return env


def new_runtime_workspace(pack, name):
    """Lay out a standalone city and a fixture cloned from its own origin.

    Nothing is registered here: `gc init` and `gc rig add` do that later, the
    same way an operator would.
    """
    # macOS sockaddr_un cannot hold paths under the artifact directory.
    root = Path(tempfile.mkdtemp(prefix='gcja-', dir='/tmp'))/'w'
    workspace = gate.GateWorkspace(root=root.resolve(), city_dir=root.resolve()/'city',
        rig_dir=root.resolve()/'fixture', gc_home=root.resolve()/'gc-home',
        runtime_dir=root.resolve()/'runtime', claude_config_dir=root.resolve()/'gc-home/.claude',
        city_name='jev-'+root.parent.name+'-'+name, rig_name='fixture')
    for path in (workspace.gc_home, workspace.runtime_dir):
        path.mkdir(parents=True)
    if len(str(workspace.gc_home/'supervisor.sock').encode()) >= 100:
        raise ValueError('Runtime path is too long for a portable Unix socket')
    return workspace


def write_city_config(workspace, *, model, collector_env, claude_config_dir=None, claude_command=None):
    """The city.toml handed to `gc init --file`; only provider and env choices."""
    env = {'CLAUDE_CODE_EFFORT_LEVEL': 'low',
           # Expanded at session launch; the value is never written to disk.
           # An empty baseline environment leaves it unset.
           'TYPESAFE_API_KEY': '$TYPESAFE_API_KEY', **collector_env}
    if claude_config_dir:
        env['CLAUDE_CONFIG_DIR'] = str(claude_config_dir)
    lines = ['[workspace]', 'provider = "claude"', '', '[workspace.env]',
             *(f'{k} = {gate.toml_string(v)}' for k, v in env.items()), '',
             '[providers.claude]', 'base = "builtin:claude"',
             *([f'command = {gate.toml_string(claude_command)}'] if claude_command else []),
             'args_append = '+json.dumps(['--model', model, '--effort', 'low',
                                          '--setting-sources', 'project,local']), '',
             '[session]', '# Claude CLI cold starts can exceed the 60s default on a loaded host.',
             'startup_timeout = "3m"', '']
    path = workspace.root/'city.toml.in'
    path.write_text('\n'.join(lines))
    return path


def prepare_fixture_repo(workspace, pack, env, workload=workloads.SLUGIFY):
    """Clone the rig from a local origin, as the documented path clones a repo.

    do-work's worktree stage requires origin/HEAD; a clone provides it without
    any network remote.
    """
    seed, origin = workspace.root/'fixture-seed', workspace.root/'fixture-origin.git'
    if workspace.rig_dir.exists() or origin.exists():
        raise ValueError('Refusing to reuse an existing experiment fixture')
    seed.mkdir()
    gate.materialize_pack_check_scripts(pack.validator_source, seed)
    workload.seed(seed)
    gate.initialize_rig_git(seed, env=env)
    def git(*arguments, cwd=workspace.root):
        return gate.run_checked(['git', *arguments], cwd=cwd, env=env, timeout=60).strip()
    git('clone', '--bare', '--no-hardlinks', str(seed), str(origin))
    git('clone', str(origin), str(workspace.rig_dir))
    for key, value in (('user.name', 'Gas City Pack Gate'), ('user.email', 'gascity-pack-gate@example.invalid')):
        git('config', key, value, cwd=workspace.rig_dir)
    branch = git('symbolic-ref', '--short', 'refs/remotes/origin/HEAD', cwd=workspace.rig_dir)
    head = git('rev-parse', 'HEAD', cwd=workspace.rig_dir)
    remote_head = git('rev-parse', 'origin/HEAD', cwd=workspace.rig_dir)
    if not branch.startswith('origin/') or remote_head != head:
        raise ValueError('Experiment origin does not resolve to the initial fixture commit')
    return {'status':'passed', 'remote':str(origin), 'default_branch':branch,
            'initial_head':head, 'remote_head':remote_head, 'network_remote':False}


def add_rig_roles_import(config, rig_name, roles_source):
    """Bind the pack's rig roles as `gc`, per the pack README's city.toml step."""
    text = config.read_text()
    header = f'name = {gate.toml_string(rig_name)}'
    if text.count(header) != 1:
        raise ValueError(f'Expected exactly one [[rigs]] entry for {rig_name} after gc rig add')
    lines = text.splitlines()
    index = lines.index(header)
    # Insert after the rig's own scalar keys, before any following table.
    end = index + 1
    while end < len(lines) and not lines[end].startswith('['):
        end += 1
    block = ['', '[rigs.imports.gc]', f'source = {gate.toml_string(roles_source)}', '']
    config.write_text('\n'.join(lines[:end] + block + lines[end:]).rstrip('\n') + '\n')


def initialize_operator_city(gc_bin, workspace, pack, env, *, config_file, setup_timeout,
                             skip_provider_readiness=False):
    """Create the city exactly as the gascity README quick start describes.

    skip_provider_readiness passes gc's documented override when gc's own probe
    cannot verify a wrapped Claude CLI; the harness verifies the login itself."""
    city = ['--city', str(workspace.city_dir)]
    gate.write_supervisor_config(workspace.gc_home)
    gate.run_checked([gc_bin, 'init', '--file', str(config_file), '--name', workspace.city_name,
                      '--yes', *(['--skip-provider-readiness'] if skip_provider_readiness else []),
                      str(workspace.city_dir)], env=env, timeout=setup_timeout, log_output=True)
    gate.run_checked([gc_bin, *city, 'import', 'add', '--name', 'gc', str(pack.source)],
                     env=env, timeout=300, log_output=True)
    gate.run_checked([gc_bin, *city, 'rig', 'add', str(workspace.rig_dir), '--name', workspace.rig_name],
                     env=env, timeout=setup_timeout, log_output=True)
    add_rig_roles_import(workspace.city_dir/'city.toml', workspace.rig_name, pack.roles_source)
    for command in (['import', 'install'], ['import', 'check'], ['config', 'show'],
                    ['--rig', workspace.rig_name, 'formula', 'show', 'build-basic']):
        gate.run_checked([gc_bin, *city, *command], env=env, timeout=300, log_output=True)


def host_load(max_load):
    """Refuse to time a build on a host that is already saturated."""
    one, five, fifteen = os.getloadavg()
    cpus = os.cpu_count() or 1
    limit = cpus if max_load is None else max_load
    return {'status': 'passed' if one <= limit else 'failed', 'load_average': [one, five, fifteen],
            'logical_cpus': cpus, 'max_load': limit}


def unwrap_bd(path):
    """Check gates run with HOME set to the city, so a small wrapper that execs
    `$HOME/...` would break there; resolve it to the real binary."""
    path = Path(path).resolve()
    if path.stat().st_size < 4096:
        found = re.search(r'exec "\$HOME(/[^"]+)"', path.read_text(errors='ignore'))
        if found:
            return str(Path.home()) + found.group(1)
    return str(path)


def install_gate_toolchain(env, workspace, *, python_bin, bd_bin):
    """Keep the selected Python available in the SDK's restricted gate PATH."""
    directory = workspace.gc_home/'bin'
    directory.mkdir(parents=True, exist_ok=True)
    bd_target = shutil.which(bd_bin, path=env.get('PATH'))
    if not bd_target:
        raise ValueError(f'Beads executable not found: {bd_bin}')
    bd_target = unwrap_bd(bd_target)
    (directory/'bd').symlink_to(Path(bd_target).resolve())
    # Do not resolve the Python symlink: that would discard virtualenv identity.
    python = directory/'python3'
    with python.open('x') as f:
        f.write('#!/bin/sh\nexec '+shlex.quote(os.path.abspath(python_bin))+' "$@"\n')
    python.chmod(0o755)
    return {**env, 'PATH':str(directory)+os.pathsep+env.get('PATH','')}


def check_gate_python(env, workspace):
    # Replay v1.4.2 conditionPATH/ConditionEnv. The real RunCondition boundary
    # is separately verified in diagnosis/gate-python, including red and green.
    directories=[]
    for name in ('bd','gc','dolt','jq'):
        path=shutil.which(name,path=env['PATH'])
        if path and str(Path(path).parent) not in directories:
            directories.append(str(Path(path).parent))
    directories += ['/usr/local/bin','/usr/bin','/bin']
    restricted={'PATH':os.pathsep.join(directories),'HOME':str(workspace.city_dir),
                'TMPDIR':tempfile.gettempdir()}
    command=['python3','-c','import json,sys,yaml; print(json.dumps({"executable":sys.executable,"prefix":sys.prefix,"yaml":yaml.__file__}))']
    result=subprocess.run(command,env=restricted,capture_output=True,text=True,timeout=30)
    return {'status':'passed' if result.returncode==0 else 'failed',
        'policy':'Gas City v1.4.2 restricted gate PATH replay; real SDK boundary verified separately',
        'command':command,'path':restricted['PATH'],'exit':result.returncode,
        'stdout':result.stdout,'stderr':result.stderr}


def pack_for_arm(arm):
    """Compare separate base and Jev packs through compatible gc role bindings."""
    baseline = gate.PACK_SPECS['gascity']
    if arm == 'baseline':
        return baseline
    if arm != 'jev':
        raise ValueError(f'Unknown experiment arm: {arm}')
    source = ROOT / 'gascity-jev'
    return replace(baseline, name='gascity-jev', source=source,
                   roles_source=source/'roles', validator_source=source)


def snapshot_pack(pack, out):
    """Retain the selected pack's actual bytes, including uncommitted additions."""
    paths = [Path(__file__), ROOT/'scripts/gascity_pack_inference_gate.py',
             ROOT/'scripts/jev_claude_usage.py',
             *sorted(pack.source.rglob('*'))]
    save(out/'source-hashes.json', {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths if p.is_file() and not {'__pycache__', '.pytest_cache'}.intersection(p.parts)})
    shutil.copytree(pack.source, out/'pack-snapshot',
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    return {
        'pack_name': pack.name, 'pack_source': str(pack.source),
        'roles_source': str(pack.roles_source), 'validator_source': str(pack.validator_source),
        'pack_git_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'pack_diff': subprocess.check_output(['git','diff','HEAD','--',str(pack.source.relative_to(ROOT))],cwd=ROOT,text=True),
    }


def jev_variables(arm, model, state_dir=None, test_command=None):
    """Jev-arm launch variables. The gate state (bands, breaker, ledger) is shared
    across the experiment's Jev arms so audit counts accumulate over pairs."""
    if arm == 'baseline':
        return {}
    if arm != 'jev':
        raise ValueError(f'Unknown experiment arm: {arm}')
    variables = {'jev_mode': 'auto', 'jev_model': model}
    if state_dir:
        variables['jev_state_dir'] = str(state_dir)
    if test_command:
        variables['jev_test_command'] = test_command
    return variables


def launch_command(rig, arm, source_id, variables):
    """Baseline slings build-basic; the Jev arm goes through the pack's intake router,
    which slings jev-build-compact or jev-build."""
    if arm == 'jev':
        cmd = [*rig, 'gc', 'jev-route', source_id]
    else:
        cmd = [*rig, 'sling', 'gc.run-operator', source_id, '--on', 'build-basic',
               '--title', gate.BUILD_TITLE, '--nudge', '--json']
    for key, value in variables.items():
        cmd += ['--var', f'{key}={value}']
    return cmd


def require_committed_pack(pack):
    """`gc import add` pins a local path to its git HEAD, so uncommitted pack edits
    would silently not be tested. Refuse to run with a dirty pack tree."""
    paths = [str(pack.source.relative_to(ROOT))]
    if pack.roles_source and pack.roles_source != pack.source / 'roles':
        paths.append(str(pack.roles_source.relative_to(ROOT)))
    if pack.name == 'gascity-jev':
        paths.append('gascity')
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--', *paths], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError('Commit the pack before an A/B: gc import add pins the committed HEAD and would '
                         'not test these changes:\n' + dirty)


def sweep_run_processes(root):
    """Last-resort cleanup: SIGTERM any process whose command line holds this run's
    own root path (Beads proxies and Dolt servers can respawn after gc stop)."""
    root = str(Path(root).resolve())
    result = subprocess.run(['ps', '-eo', 'pid=,args='], capture_output=True, text=True)
    signalled = []
    for line in result.stdout.splitlines():
        pid, _, args = line.strip().partition(' ')
        if root in args and pid.isdigit() and int(pid) != os.getpid():
            try:
                os.kill(int(pid), signal.SIGTERM)
                signalled.append({'pid': int(pid), 'args': args[:160]})
            except ProcessLookupError:
                pass
    return signalled


def gate_delivery(beads):
    """Jev-arm treatment evidence: the review gate's item and summary per workflow."""
    rows = []
    for bead in beads:
        meta = bead.get('metadata') or {}
        if meta.get('jev.role') == 'review-gate' and meta.get('jev.item'):
            item = json.loads(meta['jev.item'])
            rows.append({'bead': bead['id'], 'root': meta.get('gc.root_bead_id'), 'item': item,
                         'summary': json.loads(meta.get('jev.summary') or '{}'),
                         'jev_answered': item.get('gate') == 'jev', 'reason': meta.get('jev.review_error', '')})
    return rows


COMPACT_SKIPS = {'gc.build.requirements_path', 'gc.build.plan_path', 'gc.build.decomposition_path',
                 'gc.build.implementation_summary_path'}


def validate_artifacts(root, workspace, env, pack, formula):
    """Validate every build artifact the formula produces; the compact route has no
    requirements, plan, decomposition or canonical summary stage."""
    validator = ROOT/'gascity/assets/scripts/validate_build_artifact.py'
    checked = []
    for key, schema in gate.BUILD_BASIC_ARTIFACT_CONTRACTS:
        if formula == 'jev-build-compact' and key in COMPACT_SKIPS:
            continue
        raw = (root.get('metadata') or {}).get(key)
        if not raw:
            raise ValueError(f'workflow root is missing {key}')
        path = gate.resolve_artifact_path(raw, base=workspace.rig_dir)
        gate.run_checked([sys.executable, str(validator), '--schema', schema, '--path', str(path)],
                         env=env, timeout=60, log_output=True)
        checked.append({'key': key, 'schema': schema, 'path': str(path)})
    return checked


def result_candidates(workspace, beads, workload):
    return [c for c in gate.build_result_candidates(workspace.rig_dir, beads) if (c/workload.module).is_file()]


def validate_result(workspace, beads, workload, env):
    """The first candidate whose module no longer holds the stub and whose visible tests pass."""
    failures = []
    for candidate in result_candidates(workspace, beads, workload):
        if workload.stub_marker in (candidate/workload.module).read_text(errors='replace') and workload.kind == 'planted':
            failures.append(f'{candidate}: {workload.module} still contains the stub')
            continue
        proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *workload.test_paths],
                              cwd=candidate, env=env, capture_output=True, text=True, timeout=300)
        if proc.returncode:
            failures.append(f'{candidate}: visible tests exit {proc.returncode}')
            continue
        if workload.kind == 'backlog':
            base = subprocess.run(['git', 'diff', '--quiet', 'origin/HEAD', '--', workload.module], cwd=candidate)
            if base.returncode == 0:
                failures.append(f'{candidate}: {workload.module} unchanged')
                continue
        return candidate
    raise ValueError('No passing implementation result:\n' + '\n'.join(failures or ['no candidates']))


def final_quality(workspace, beads, out, env, original_test_hashes, workload=workloads.SLUGIFY):
    """Evaluate unfinished runs too; never substitute a successful stage for proof."""
    rows = []
    for index, candidate in enumerate(result_candidates(workspace, beads, workload)):
        directory = out/f'quality-{index:03d}'
        directory.mkdir()
        row = {'worktree': str(candidate)}
        shutil.copy(candidate/workload.module, directory/Path(workload.module).name)
        if original_test_hashes:
            row['original_tests_unchanged'] = all(
                (candidate/path).is_file() and hashlib.sha256((candidate/path).read_bytes()).hexdigest() == digest
                for path, digest in original_test_hashes.items())
        try:
            proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *workload.test_paths],
                                  cwd=candidate, env=env, capture_output=True, text=True, timeout=300)
            (directory/'pytest.txt').write_text(proc.stdout + proc.stderr)
            row['pytest_exit'] = proc.returncode
        except subprocess.TimeoutExpired:
            row['pytest_timeout'] = True
        try:
            row['hidden'] = workload.hidden(candidate, directory, env)
            row['hidden_exit'] = 0 if row['hidden']['pass'] else 1
        except Exception as error:  # noqa: BLE001
            row['hidden_error'] = f'{type(error).__name__}: {error}'
        rows.append(row)
    return rows


def run(args, arm, out, workload=workloads.SLUGIFY):
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'arm': arm, 'scope': 'full-build', 'workload': workload.name, 'workload_kind': workload.kind,
              'started_at': datetime.now(timezone.utc).isoformat(),
              'model': args.model, 'jev_model': args.jev_model, 'status': 'starting'}
    pack = pack_for_arm(arm)
    report['pack_name'] = pack.name
    if not args.setup_only:
        require_committed_pack(pack)
    load = host_load(args.max_load)
    save(out/'host-load-preflight.json', load)
    if load['status'] != 'passed':
        raise ValueError(f"Host load {load['load_average'][0]:.1f} exceeds {load['max_load']}; "
                         'timings from a saturated host are not comparable')
    workspace = new_runtime_workspace(pack, out.name)
    save(out/'runtime-path.json', {'root': str(workspace.root), 'retained': True})
    env = gate.build_gate_env(args.gc_bin, workspace, bd_bin=args.bd_bin)
    # Isolate the supervisor's state. Workers use the existing subscription login.
    real_home = Path.home()
    custom_claude = os.environ.get('CLAUDE_CONFIG_DIR') or None
    real_claude = Path(custom_claude or real_home/'.claude').expanduser().resolve()
    env = configure_experiment_env(env, workspace, real_home=real_home,
        claude_config_dir=real_claude if custom_claude else None)
    env['CLAUDE_CODE_EFFORT_LEVEL'] = 'low'
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env['PATH']
    env = install_gate_toolchain(env,workspace,python_bin=sys.executable,bd_bin=args.bd_bin)
    python_preflight = check_gate_python(env,workspace)
    save(out/'gate-python-preflight.json',python_preflight)
    if python_preflight['status'] != 'passed':
        raise ValueError('Gate Python dependency preflight failed: '+python_preflight['stderr'])
    for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'OLLAMA_API_KEY',
                'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY',
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC'):
        env.pop(key, None)
    env.pop('TYPESAFE_API_KEY', None)
    if arm == 'jev' and not args.setup_only:
        env['TYPESAFE_API_KEY'] = os.environ['TYPESAFE_API_KEY']
    if not args.setup_only:
        auth = subprocess.run([args.claude_command,'auth','status','--json'],env=env,capture_output=True,text=True,timeout=120)
        status = json.loads(auth.stdout[auth.stdout.index('{'):]) if '{' in auth.stdout else {}
        safe_status = {k:status.get(k) for k in ('loggedIn','authMethod','apiProvider','subscriptionType')}
        save(out/'subscription-preflight.json',safe_status)
        if auth.returncode or not status.get('loggedIn') or status.get('authMethod') not in args.claude_auth.split(','):
            raise ValueError(f"Claude login {safe_status} is not one of the accepted methods {args.claude_auth}")
    versions = {name: subprocess.check_output(cmd, text=True).strip() for name,cmd in
                [('gc',[args.gc_bin,'version','--long']),('bd',[args.bd_bin,'version']),('claude',[args.claude_command,'--version']),('bash',['bash','--version'])]}
    save(out/'manifest.json', {'argv': sys.argv, 'versions': versions, 'model': args.model,
         'workload': {'name': workload.name, 'kind': workload.kind, 'task': workload.task(), **workload.notes},
         'jev_model': args.jev_model, 'arm': arm, 'setup': 'operator-path',
         **snapshot_pack(pack, out)})
    (out/'jev_build_ab.py').write_bytes(Path(__file__).read_bytes())
    collector = usage.Collector(out/'otel-usage.jsonl')
    env.update(collector.env)
    config_file = write_city_config(workspace, model=args.model, collector_env=collector.env,
                                    claude_config_dir=real_claude if custom_claude else None,
                                    claude_command=args.claude_command)
    final_beads, original_test_hash = [], None
    with (out/'run.log').open('x', buffering=1) as log, redirect_stdout(log), redirect_stderr(log):
        try:
            save(out/'fixture-origin-preflight.json', prepare_fixture_repo(workspace, pack, env, workload))
            original_test_hash = {p: hashlib.sha256((workspace.rig_dir/p).read_bytes()).hexdigest()
                                  for p in workload.protected_tests}
            save(out/'original-test-hash.json', original_test_hash)
            initialize_operator_city(args.gc_bin, workspace, pack, env,
                                     config_file=config_file, setup_timeout=args.setup_timeout,
                                     skip_provider_readiness=getattr(args, 'skip_provider_readiness', False))
            report['setup_seconds'] = time.monotonic() - started
            if args.setup_only:
                report['status'] = 'setup_only'
            else:
                gate.start_city(args.gc_bin, workspace, env=env)
                rig = [args.gc_bin,'--city',str(workspace.city_dir),'--rig',workspace.rig_name]
                task = workload.task()
                title, description = task.split('\n', 1)
                created = gate.run_checked([*rig,'bd','create',title,'--description',description.strip(),'--json'],
                                           cwd=workspace.rig_dir,env=env,timeout=120,log_output=True)
                source_id = gate.find_first_key(gate.extract_json_payload(created), ('id',))
                if not source_id:
                    raise ValueError('gc bd create did not report the task bead id')
                report['source_bead_id'] = source_id
                variables = {'artifact_root':str(gate.BUILD_ARTIFACT_ROOT),'interaction_mode':'headless',
                    'review_mode':'agent','drain_policy':'separate','push':'false','open_pr':'false',
                    'max_iterations':'2', **jev_variables(arm, args.jev_model, args.out/'jev-state', workload.test_command('python3'))}
                cmd = launch_command(rig, arm, source_id, variables)
                save(out/'launch.json', {'command':cmd,'task':task,'source_bead_id':source_id})
                dispatched = gate.run_checked(cmd,cwd=workspace.rig_dir,env=env,timeout=args.dispatch_timeout,
                                              log_output=True)
                if arm == 'jev':
                    routed = json.loads(dispatched.strip().splitlines()[-1])
                    save(out/'intake-route.json', routed)
                    report['formula'] = routed['formula']
                    candidate = routed.get('workflow_id')
                else:
                    report['formula'] = 'build-basic'
                    candidate = gate.extract_sling_root_id(dispatched)
                root_id = gate.resolve_workflow_root_id(args.gc_bin,workspace,env=env,
                    candidate_id=candidate,title=gate.BUILD_TITLE,
                    source_title=gate.BUILD_SOURCE_TITLE,timeout=30)
                report['root_id'] = root_id
                root = gate.wait_for_workflow_pass(args.gc_bin,workspace,root_id,env=env,
                                                  timeout=args.timeout,poll_interval=15)
                beads = gate.list_beads(args.gc_bin,workspace,env=env)
                save(out/'beads.json',beads)
                report['artifacts'] = validate_artifacts(root, workspace, env, pack, report['formula'])
                result_path = validate_result(workspace, [root, *beads], workload, env)
                report.update(status='completed', fixture_tests_pass=True, result_path=str(result_path))
                # Hidden checks evaluate the produced code without trusting edited tests.
                hidden_dir = out/'hidden-result'
                hidden_dir.mkdir()
                hidden = workload.hidden(result_path, hidden_dir, env)
                report['hidden'] = hidden
                report['hidden_tests_pass'] = hidden['pass']
                delivery = gate_delivery(beads)
                save(out/'jev-gate-delivery.json', delivery)
                if arm=='jev' and not any(row['jev_answered'] for row in delivery):
                    raise ValueError('Treatment not delivered: the review gate failed open; fallback is not a Jev result')
        except (Exception, KeyboardInterrupt) as e:
            if isinstance(e, subprocess.TimeoutExpired):
                for label, value in [('stdout', e.stdout), ('stderr', e.stderr)]:
                    (out/f'timeout-{label}.txt').write_bytes(value.encode() if isinstance(value, str) else value or b'')
            report.update(status='aborted' if isinstance(e,KeyboardInterrupt) else 'failed',
                          error=f'{type(e).__name__}: {e}')
            print(report['error'],flush=True)
        finally:
            if not args.setup_only:
                try:
                    final_beads = gate.list_beads(args.gc_bin, workspace, env=env)
                    save(out/'final-beads.json', final_beads)
                except Exception as error:
                    report['final_bead_collection_error'] = f'{type(error).__name__}: {error}'
            try:
                gate.stop_city(args.gc_bin,workspace,env=env)
                report['cleanup'] = stop_disposable_dolt(workspace.city_dir, workspace.rig_dir)
                # A late bd call from a stopping worker can respawn the 1.5
                # Beads proxy seconds after the first sweep; sweep once more,
                # then sweep anything else still holding this run's own paths.
                time.sleep(20)
                report['cleanup_resweep'] = stop_disposable_dolt(workspace.city_dir, workspace.rig_dir)
                time.sleep(25)
                report['cleanup_path_sweep'] = sweep_run_processes(workspace.root)
            finally:
                report['otel_usage'] = collector.close()
                report['otel_usage']['coverage'] = 'Local Claude API-request events; validate delivery and auxiliary coverage before comparing totals.'
    if not args.setup_only:
        try:
            report['independent_quality'] = final_quality(workspace, final_beads, out, env, original_test_hash, workload)
        except Exception as error:
            report['independent_quality_error'] = f'{type(error).__name__}: {error}'
        report['jev_gate_delivery'] = gate_delivery(final_beads)
        logs = sorted(str(p) for p in workspace.rig_dir.rglob('jev/decisions.jsonl'))
        for index, path in enumerate(logs):
            shutil.copy(path, out/f'decisions-{index:02d}.jsonl')
        report['jev_decision_logs'] = logs
    report['elapsed_seconds'] = time.monotonic()-started
    projects=Path(args.claude_projects_dir) if args.claude_projects_dir else real_claude/'projects'
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
    p.add_argument('--gc-bin',default=shutil.which('gc') or 'gc')
    p.add_argument('--bd-bin',default=shutil.which('bd') or 'bd')
    # Baseline 005 needed ~46 minutes just to reach implementation; upstream's
    # inference gate allows 75.
    p.add_argument('--timeout',type=float,default=4500)
    p.add_argument('--setup-timeout',type=float,default=900)
    p.add_argument('--dispatch-timeout',type=float,default=600)
    p.add_argument('--max-load',type=float,default=None,
                   help='Refuse to start an arm above this 1-minute load average (default: logical CPU count).')
    p.add_argument('--setup-only',action='store_true')
    p.add_argument('--workloads',default='slugify',
                   help='Comma-separated workloads from scripts/jev_ab_workloads.py; repetition r uses workload r mod n.')
    p.add_argument('--claude-command',default='claude',help='Claude CLI the city launches for every role.')
    p.add_argument('--claude-auth',default='claude.ai',
                   help='Comma-separated accepted `auth status` methods (claude.ai = subscription).')
    p.add_argument('--skip-provider-readiness',action='store_true',
                   help="Pass gc init's documented override when gc cannot probe a wrapped Claude CLI.")
    p.add_argument('--claude-projects-dir',default='',
                   help='Transcript projects directory (default: <claude config>/projects).')
    p.add_argument('--continue-on-failure', action='store_true',
                   help='Retain failed arms and still run the predeclared paired schedule.')
    args=p.parse_args()
    if args.arms!='baseline' and not args.setup_only and not os.environ.get('TYPESAFE_API_KEY'):
        p.error('Live Jev requires TYPESAFE_API_KEY')
    if args.repetitions<1:p.error('repetitions must be positive')
    args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=False)
    selected=[workloads.WORKLOADS[name] for name in args.workloads.split(',')]
    schedule=[]
    for r in range(args.repetitions):
        arms=(['baseline','jev'] if r%2==0 else ['jev','baseline']) if args.arms=='both' else [args.arms]
        schedule.extend((r,a,selected[r%len(selected)]) for a in arms)
    save(args.out/'schedule.json',[{'repetition':r,'arm':a,'workload':w.name} for r,a,w in schedule])
    failed = False
    for i,(r,a,w) in enumerate(schedule,1):
        name=f'run-{i:03d}-{a}-{w.name}'
        print(f'[{i}/{len(schedule)}] {name} starting; log: {args.out/name/"run.log"}',flush=True)
        try:
            result=run(args,a,args.out/name,w)
        except Exception as e:
            result={'status':'failed','arm':a,'scope':'full-build-basic','error':f'{type(e).__name__}: {e}'}
            save(args.out/(name+'-setup-failure.json'),result)
        finally:
            # Nothing from this arm may outlive it into the next arm's timing.
            runtime = args.out/name/'runtime-path.json'
            if runtime.exists():
                swept = sweep_run_processes(Path(json.loads(runtime.read_text())['root']).parent)
                if swept:
                    save(args.out/(name+'-final-sweep.json'), swept)
        error_summary = result.get('error','').splitlines()[0][:500] if result.get('error') else ''
        print(f'[{i}/{len(schedule)}] {result["status"]}: {error_summary}',flush=True)
        failed = failed or result['status']=='failed'
        if result['status']=='failed' and not args.continue_on_failure:sys.exit(1)
        if result['status']=='aborted':sys.exit(130)
    if failed:sys.exit(1)


if __name__=='__main__':main()

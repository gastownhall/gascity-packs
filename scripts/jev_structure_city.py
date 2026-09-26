#!/usr/bin/env python3
"""No-LLM structural test of the gascity-jev overlay in a disposable Gas City.

Runs the real `jev-build` formula end to end. Every Claude role (gc.*) is
patched to scripts/jev_stub_worker.py, a one-shot script that does what the
step's prompt asks with fixed output; the gc.jev-gate agent runs the real gate.
Jev answers come from a loopback stub server, so no network call and no API
key are used. No model session starts.

Scenarios (run in order in one city, then a no-key phase after a restart):

- some    one criterion above the act band: acceptance (scoped) + simplicity
- none    every lane cleared (design skip enabled in bands.json): loop dropped
- audit   every act decision audited; the acceptance lane contradicts one, so
          the review.criterion breaker trips
- tripped after the trip: every criterion is folded into confirm
- nokey   TYPESAFE_API_KEY removed: the gate fails open to every lane

Evidence lands in --out. The city lives under a short /tmp path and is torn
down (gc stop, supervisor stop, two scoped process sweeps) at the end.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inference_gate', ROOT / 'scripts/gascity_pack_inference_gate.py')
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)

ROLES = ['design-author', 'design-implementation-reviewer', 'design-test-risk-reviewer', 'gap-analyst',
         'implementation-reviewer', 'implementation-worker', 'publisher', 'requirements-planner',
         'review-synthesizer', 'run-operator', 'task-decomposer', 'issue-triager', 'feature-refiner',
         'quality-judge']
CRITERIA_IDS = ['AC-1', 'AC-2', 'AC-3', 'AC-4']
SCENARIOS = {
    'some': {'p': {'AC-1': 0.4}, 'audit_rate': '0'},
    'none': {'p': {}, 'audit_rate': '0', 'bands': {'simplicity.design': {'skip_when_screen_clean': True}}},
    'audit': {'p': {}, 'audit_rate': '1', 'violated': ['AC-2']},
    'tripped': {'p': {}, 'audit_rate': '0'},
    'compact': {'p': {}, 'audit_rate': '0', 'route': True, 'size': 0},
    'nokey': {'p': {}, 'audit_rate': '0', 'nokey': True},
}


def now() -> str:
    return datetime.now(timezone.utc).strftime('%H:%M:%S')


class JevStub:
    """Loopback Jev: violate_i answers from the scenario, smell answers 0.05."""

    def __init__(self, scenario_path: Path, log_path: Path):
        stub = self
        self.scenario_path = scenario_path

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                scenario = json.loads(stub.scenario_path.read_text())
                ids = list((payload.get('state') or {}).get('criteria', {}))
                answers = {}
                intake = {'needs_design': 'no', 'risky_surface': 'none',
                          'well_specified': 'clear_acceptance_criteria', **scenario.get('intake', {})}
                for qid, question in payload['questions'].items():
                    if question['type'] == 'score':
                        level = str(scenario.get('size', 0))
                        answers[qid] = {'type': 'score', 'score': float(level), 'confidence': 0.95,
                                        'probabilities': {str(i): 0.95 if str(i) == level else 0.025
                                                          for i in range(len(question['criteria']))}}
                        continue
                    if question['type'] == 'choice':
                        choice = intake.get(qid, next(iter(question['criteria'])))
                        answers[qid] = {'type': 'choice', 'choice': choice, 'confidence': 0.95,
                                        'probabilities': {c: 0.95 if c == choice else 0.05 / (len(question['criteria']) - 1)
                                                          for c in question['criteria']}}
                        continue
                    p = 0.05
                    if qid.startswith('violate_'):
                        cid = ids[int(qid.split('_')[1])] if ids else ''
                        p = scenario.get('p', {}).get(cid, 0.05)
                    answers[qid] = {'type': 'noul', 'noul': p}
                body = json.dumps({'model': payload['model'], 'answers': answers,
                                   'usage': {'input_tokens': len(json.dumps(payload)) // 4, 'output_tokens': 3}}).encode()
                with log_path.open('a') as handle:
                    handle.write(json.dumps({'at': now(), 'questions': len(payload['questions']),
                                             'criteria': ids, 'answers': answers}) + '\n')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/v1/systemone'


class City:
    def __init__(self, base: Path, out: Path, gc_bin: str, python_bin: str):
        self.base, self.out, self.gc_bin = base, out, gc_bin
        self.city, self.rig = base / 'city', base / 'fixture'
        self.gc_home, self.stub_dir = base / 'gc-home', base / 'stub'
        self.state_dir = base / 'jev-state'
        for path in (self.gc_home, base / 'runtime', self.stub_dir, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)
        shims = gate.install_service_manager_shims(self.gc_home)
        # Check gates run with HOME set to the city; a bd wrapper that execs
        # $HOME/... would break there, so put the real binary first on PATH.
        real_bd = Path(os.environ.get('JEV_STRUCTURE_BD') or shutil.which('bd') or 'bd').resolve()
        wrapped = re.search(r'exec "\$HOME(/[^"]+)"', real_bd.read_text(errors='ignore')) if real_bd.stat().st_size < 4096 else None
        if wrapped:
            real_bd = Path(os.environ['HOME'] + wrapped.group(1))
        (shims / 'bd').symlink_to(real_bd)
        gate.write_supervisor_config(self.gc_home)
        gate.write_dolt_global_config(self.gc_home)
        (self.gc_home / 'gitconfig').write_text('[user]\n\tname = Jev Structure\n\temail = jev@example.invalid\n')
        py_dir = str(Path(python_bin).parent)
        keep = {k: os.environ[k] for k in ('HOME', 'USER', 'LANG', 'TERM', 'SHELL', 'TMPDIR') if k in os.environ}
        self.env = {**keep, 'GC_HOME': str(self.gc_home), 'XDG_RUNTIME_DIR': str(base / 'runtime'),
                    'DOLT_ROOT_PATH': str(self.gc_home), 'GIT_CONFIG_GLOBAL': str(self.gc_home / 'gitconfig'),
                    'PATH': os.pathsep.join([str(shims), py_dir, str(Path(gc_bin).resolve().parent),
                                             os.environ.get('PATH', '')])}

    def run(self, *args, cwd=None, timeout=600, check=True):
        proc = subprocess.run(args, cwd=cwd or self.city, env=self.env, capture_output=True, text=True, timeout=timeout)
        with (self.out / 'commands.log').open('a') as handle:
            handle.write(f'$ {" ".join(map(str, args))}\n[{proc.returncode}] {proc.stdout[-2000:]}{proc.stderr[-2000:]}\n')
        if check and proc.returncode:
            raise RuntimeError(f'{" ".join(map(str, args[:4]))} failed: {proc.stderr[-800:]}')
        return proc.stdout

    def gc(self, *args, **kw):
        return self.run(self.gc_bin, *args, **kw)

    def fixture(self):
        seed, origin = self.base / 'seed', self.base / 'origin.git'
        seed.mkdir()
        gate.materialize_pack_check_scripts(ROOT / 'gascity', seed)
        gate.write_build_basic_fixture(seed)
        gate.initialize_rig_git(seed, env=self.env)
        self.run('git', 'clone', '-q', '--bare', str(seed), str(origin), cwd=self.base)
        self.run('git', 'clone', '-q', str(origin), str(self.rig), cwd=self.base)

    def city_toml(self, stub_url: str, key: bool):
        stub = f'python3 {ROOT / "scripts/jev_stub_worker.py"}'
        env = {'JEV_STUB_DIR': str(self.stub_dir), 'JEV_API_URL': stub_url}
        if key:
            env['TYPESAFE_API_KEY'] = 'structural-stub-not-a-secret'
        lines = ['[workspace]', 'provider = "claude"', '', '[workspace.env]']
        lines += [f'{k} = {json.dumps(v)}' for k, v in env.items()]
        lines += ['', '[providers.claude]', 'base = "builtin:claude"', 'ready_delay_ms = 0', '',
                  '[daemon]', 'formula_v2 = true', 'patrol_interval = "1s"', '',
                  '[orders]', 'skip = ["mol-dog-stale-db"]', '']
        for name in ('bd.dog', 'claude'):
            lines += ['[[patches.agent]]', f'name = "{name}"', 'suspended = true', '']
        return '\n'.join(lines)

    def rig_patches(self):
        stub = f'python3 {ROOT / "scripts/jev_stub_worker.py"}'
        lines = ['', '[[patches.agent]]', 'rig = "fixture"', 'name = "claude"', 'suspended = true', '']
        for role in ROLES:
            lines += ['[[patches.agent]]', 'rig = "fixture"', f'name = "gc.{role}"', f'start_command = {json.dumps(stub)}',
                      'lifecycle = "one_shot"', 'max_active_sessions = 3', '']
        return '\n'.join(lines)

    stub_url = ''
    route_key = True

    def init(self, stub_url: str):
        self.stub_url = stub_url
        (self.base / 'city.toml.in').write_text(self.city_toml(stub_url, key=True))
        self.gc('init', '--file', str(self.base / 'city.toml.in'), '--name', 'jevstruct', '--yes',
                '--skip-provider-readiness', str(self.city), cwd=self.base, timeout=900)
        # A plain path import reads the working tree; `gc import add` would pin
        # the path's git HEAD and hide uncommitted pack changes.
        pack = self.city / 'pack.toml'
        pack.write_text(pack.read_text().rstrip('\n') + '\n\n[imports.gc]\nsource = '
                        + json.dumps(str(ROOT / 'gascity-jev')) + '\n')
        self.gc('--city', str(self.city), 'rig', 'add', str(self.rig), '--name', 'fixture', timeout=900)
        text = (self.city / 'city.toml').read_text()
        text = text.replace('name = "fixture"', 'name = "fixture"\n\n[rigs.imports.gc]\nsource = '
                            + json.dumps(str(ROOT / 'gascity-jev/roles')), 1)
        (self.city / 'city.toml').write_text(text + self.rig_patches())
        for cmd in (('import', 'install'), ('import', 'check'), ('agent', 'list'),
                    ('--rig', 'fixture', 'formula', 'show', 'jev-build'),
                    ('--rig', 'fixture', 'formula', 'show', 'jev-review-tail')):
            (self.out / ('setup-' + '-'.join(c for c in cmd if not c.startswith('-')) + '.txt')).write_text(
                self.gc('--city', str(self.city), *cmd))

    def set_key(self, key: bool, stub_url: str):
        text = (self.city / 'city.toml').read_text()
        if not key:
            text = re.sub(r'(?m)^\s*TYPESAFE_API_KEY\s*=.*\n', '', text)
        (self.city / 'city.toml').write_text(text)
        self.gc('stop', str(self.city), '--force', timeout=300)
        time.sleep(3)
        self.gc('start', str(self.city), timeout=600)

    def beads(self):
        out = self.gc('--city', str(self.city), '--rig', 'fixture', 'bd', 'list', '--all', '--json', '--limit', '0',
                      cwd=self.rig, timeout=300)
        return gate.extract_json_payload(out) if hasattr(gate, 'extract_json_payload') else json.loads(out)

    def launch(self, label: str, variables: dict[str, str], route: bool = False) -> str:
        created = self.gc('--city', str(self.city), '--rig', 'fixture', 'bd', 'create', f'Structural {label}',
                          '--description', gate.build_basic_work_item(), '--json', cwd=self.rig)
        source = gate.find_first_key(gate.extract_json_payload(created), ('id',))
        if route:
            # Operator path for the compact route: the pack command asks the intake questions and slings.
            cmd = ['--city', str(self.city), '--rig', 'fixture', 'gc', 'jev-route', source, '--audit-rate', '0']
        else:
            cmd = ['--city', str(self.city), '--rig', 'fixture', 'sling', 'gc.run-operator', source, '--on', 'jev-build',
                   '--title', f'jev structure {label}', '--json']
        for key, value in variables.items():
            cmd += ['--var', f'{key}={value}']
        saved = dict(self.env)
        if route:
            # The router runs in the operator's shell, not in a session: give it the stub and key here.
            self.env.update(JEV_API_URL=self.stub_url)
            if self.route_key:
                self.env['TYPESAFE_API_KEY'] = 'structural-stub-not-a-secret'
        try:
            out = self.gc(*cmd, cwd=self.rig, timeout=600)
        finally:
            self.env = saved
        (self.out / f'{label}.sling.txt').write_text(out)
        ids = re.findall(r'"workflow_id"\s*:\s*"([^"]+)"', out)
        if not ids:
            raise RuntimeError(f'no workflow id in sling output: {out[-500:]}')
        return ids[-1]

    def wait(self, root: str, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                bead = gate.extract_json_payload(self.gc('--city', str(self.city), '--rig', 'fixture', 'bd', 'show',
                                                         root, '--json', cwd=self.rig, check=False))
                bead = bead[0] if isinstance(bead, list) else bead
                if isinstance(bead, dict) and bead.get('status') == 'closed':
                    return bead
            except Exception:  # noqa: BLE001
                pass
            time.sleep(5)
        raise TimeoutError(f'{root} did not close in {timeout}s')

    def teardown(self):
        for cmd in (('stop', str(self.city), '--force'), ('supervisor', 'stop', '--wait')):
            try:
                self.gc(*cmd, timeout=180, check=False)
            except Exception as error:  # noqa: BLE001
                print('teardown:', error)
        swept = []
        for attempt in range(2):
            time.sleep(3 if attempt == 0 else 25)
            ps = subprocess.run(['ps', '-eo', 'pid=,args='], capture_output=True, text=True).stdout
            for line in ps.splitlines():
                pid, _, args = line.strip().partition(' ')
                if str(self.base) in args and int(pid) != os.getpid():
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        swept.append(args[:120])
                    except ProcessLookupError:
                        pass
        return swept


def summarize(city: City, label: str, root: dict, beads: list[dict]) -> dict:
    members = [b for b in beads if (b.get('metadata') or {}).get('gc.root_bead_id') == root['id']]
    by_ref = {}
    for bead in members:
        ref = bead['metadata'].get('gc.step_ref', '')
        by_ref[ref] = bead
    gate_bead = next((b for b in members if b['metadata'].get('jev.role') == 'review-gate'), None)
    report_bead = next((b for b in members if b['metadata'].get('jev.role') == 'review-report'), None)
    lanes = sorted({(b['metadata'].get('jev.lane'), b['metadata'].get('gc.attempt', '1')) for b in members
                    if b['metadata'].get('jev.lane')})
    order = sorted((b for b in members if b.get('closed_at')), key=lambda b: b['closed_at'])
    publish = [b for b in members if b['metadata'].get('gc.step_ref', '').endswith('.publish')]
    gm = (gate_bead or {}).get('metadata', {})
    report_path = root['metadata'].get('gc.build.review_report_path', '')
    validity = subprocess.run([sys.executable, str(ROOT / 'gascity/assets/scripts/validate_build_artifact.py'),
                               '--schema', 'gc.build.review.v1', '--path', report_path],
                              capture_output=True, text=True) if report_path else None
    log_path = gm.get('jev.decision_log_path')
    records = [json.loads(l) for l in Path(log_path).read_text().splitlines()] if log_path and Path(log_path).is_file() else []
    result = {
        'label': label, 'root': root['id'], 'root_status': root.get('status'),
        'root_outcome': root['metadata'].get('gc.outcome'), 'root_closed_at': root.get('closed_at'),
        'publish_closed_at': [b.get('closed_at') for b in publish],
        'root_closed_after_publish': bool(publish) and all(b.get('closed_at') and b['closed_at'] <= root['closed_at'] for b in publish),
        'gate_item': json.loads(gm['jev.item']) if gm.get('jev.item') else None,
        'gate_summary': json.loads(gm['jev.summary']) if gm.get('jev.summary') else None,
        'gate_notes': {k: v for k, v in gm.items() if k.startswith('jev.') and k not in ('jev.item', 'jev.summary')},
        'lane_beads': lanes,
        'review_report_bead': (report_bead or {}).get('metadata', {}).get('gc.outcome'),
        'review_report_valid': validity.returncode == 0 if validity else None,
        'review_report_validator': (validity.stdout + validity.stderr).strip() if validity else None,
        'decision_records': len([r for r in records if r['record'] == 'decision']),
        'outcome_records': [{k: r[k] for k in ('type', 'label', 'audited', 'miss', 'band')} for r in records
                            if r['record'] == 'outcome'],
        'audited_decisions': [f"{r['type']}:{r['subject']}" for r in records if r['record'] == 'decision' and r['audit']],
        'closed_order': [(b['metadata'].get('gc.step_ref', '(root)'), b.get('closed_at'), b['metadata'].get('gc.outcome'))
                         for b in order],
        'open_members': [b['metadata'].get('gc.step_ref') for b in members if b.get('status') != 'closed'],
    }
    (city.out / f'{label}.summary.json').write_text(json.dumps(result, indent=2) + '\n')
    (city.out / f'{label}.beads.json').write_text(json.dumps([root] + members, indent=2) + '\n')
    if log_path and Path(log_path).is_file():
        shutil.copy(log_path, city.out / f'{label}.decisions.jsonl')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--gc-bin', default=shutil.which('gc') or 'gc')
    parser.add_argument('--python', default=sys.executable, help='python3 with PyYAML and pytest for gates/tests')
    parser.add_argument('--scenarios', default=','.join(SCENARIOS))
    parser.add_argument('--test-command', default='',
                        help='gate test command for the fixture (default: <python> -m pytest -q)')
    parser.add_argument('--timeout', type=float, default=900)
    parser.add_argument('--keep', action='store_true', help='leave the city running (debugging)')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    base = Path(tempfile.mkdtemp(prefix='jst-', dir='/tmp'))
    city = City(base, args.out, args.gc_bin, args.python)
    scenario_path = city.stub_dir / 'scenario.json'
    scenario_path.write_text('{}')
    stub = JevStub(scenario_path, args.out / 'jev-stub-calls.jsonl')
    results, status = [], 'completed'
    (args.out / 'manifest.json').write_text(json.dumps({
        'base': str(base), 'gc_version': subprocess.run([args.gc_bin, 'version'], capture_output=True, text=True).stdout.strip(),
        'python': args.python, 'scenarios': args.scenarios, 'started': datetime.now(timezone.utc).isoformat()}, indent=2) + '\n')
    try:
        city.fixture()
        city.init(stub.url)
        key = True
        for label in args.scenarios.split(','):
            scenario = SCENARIOS[label]
            if scenario.get('nokey') and key:
                city.set_key(False, stub.url)
                key = city.route_key = False
            bands = city.state_dir / 'bands.json'
            if 'bands' in scenario:
                stored = json.loads(bands.read_text()) if bands.is_file() else {'version': 1, 'types': {}}
                for kind, entry in scenario['bands'].items():
                    stored['types'].setdefault(kind, {}).update(entry)
                bands.write_text(json.dumps(stored, indent=2))
            scenario_path.write_text(json.dumps(scenario))
            print(f'[{now()}] {label}: launching', flush=True)
            root_id = city.launch(label, {'artifact_root': f'.gc/jev-structure/{label}', 'interaction_mode': 'headless',
                                          'review_mode': 'agent', 'push': 'false', 'open_pr': 'false',
                                          'jev_state_dir': str(city.state_dir), 'jev_audit_rate': scenario['audit_rate'],
                                          'jev_test_command': args.test_command or f'{args.python} -m pytest -q -p no:cacheprovider'},
                                  route=scenario.get('route', False))
            try:
                root = city.wait(root_id, args.timeout)
            except TimeoutError as error:
                root = {'id': root_id, 'status': 'timeout', 'metadata': {}, 'closed_at': None}
                status = 'failed'
                print(error, flush=True)
            time.sleep(8)
            result = summarize(city, label, root, city.beads())
            if 'bands' in scenario:
                stored = json.loads(bands.read_text())
                for kind in scenario['bands']:
                    stored['types'].pop(kind, None)
                bands.write_text(json.dumps(stored, indent=2))
            if bands.is_file():
                shutil.copy(bands, args.out / f'{label}.bands-after.json')
            results.append(result)
            print(f"[{now()}] {label}: root {result['root_status']}/{result['root_outcome']} item={result['gate_item']}",
                  flush=True)
    except KeyboardInterrupt:
        status = 'aborted'
    except Exception as error:  # noqa: BLE001
        status = f'failed: {type(error).__name__}: {error}'
        print(status, flush=True)
    finally:
        for name in ('stub-worker.log',):
            if (city.stub_dir / name).is_file():
                shutil.copy(city.stub_dir / name, args.out / name)
        for path in (city.city / '.gc/events.jsonl',):
            if path.is_file():
                shutil.copy(path, args.out / 'events.jsonl')
        if (city.state_dir / 'ledger.jsonl').is_file():
            shutil.copy(city.state_dir / 'ledger.jsonl', args.out / 'ledger.jsonl')
        swept = [] if args.keep else city.teardown()
        stub.server.shutdown()
        (args.out / 'result.json').write_text(json.dumps({'status': status, 'base': str(base), 'swept': swept,
                                                          'scenarios': [r['label'] for r in results]}, indent=2) + '\n')
    print(json.dumps({'status': status, 'out': str(args.out)}))
    return 0 if status == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())

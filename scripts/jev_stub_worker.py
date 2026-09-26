#!/usr/bin/env python3
"""No-LLM stand-in for the Claude roles in a jev-build structural test city.

Patched in as the start command of every gc.* role (one-shot). It claims one
routed step, does what that step's prompt asks with fixed, schema-valid output,
and closes it. Behavior that varies per scenario (the implementation variant
and the review lanes' verdicts) comes from `$JEV_STUB_DIR/scenario.json`.

This is test scaffolding for scripts/jev_structure_city.py, not a pack asset.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

GC = os.environ.get('GC_BIN') or 'gc'
STUB_DIR = Path(os.environ.get('JEV_STUB_DIR', '/nonexistent'))
LOG = STUB_DIR / 'stub-worker.log'
SLUG = {
    'correct': 'import re\n\n\ndef slugify(value: str) -> str:\n    """Return a URL slug for value."""\n'
               '    return "-".join(w.lower() for w in re.findall(r"[A-Za-z0-9]+", value))\n',
}
CRITERIA = [
    ('AC-1', 'slugify lowercases ASCII alphanumeric words.'),
    ('AC-2', 'Any run of non-alphanumeric characters acts as one separator.'),
    ('AC-3', 'Non-empty groups are joined with single hyphens, with no leading or trailing hyphen.'),
    ('AC-4', 'Input without alphanumeric characters returns an empty string.'),
]
SECTIONS = {
    'gc.build.requirements.v1': ['Problem Statement', 'W6H', 'User Stories', 'Technical Stories',
                                 'Behavior Requirements', 'Example Mapping', 'Acceptance Criteria',
                                 'Out Of Scope', 'Open Questions'],
    'gc.build.plan.v1': ['Summary', 'Current System', 'Proposed Implementation', 'Non-Goals', 'Verification'],
    'gc.build.decomposition.v1': ['Summary', 'Selected Downstream Formulas', 'Implementation Convoy', 'Work Items'],
    'gc.build.implementation-summary.v1': ['Summary', 'Intended Behavior', 'Changed Files', 'Verification',
                                           'Remaining Risks'],
    'gc.build.final-report.v1': ['Summary', 'Outcome', 'Artifacts', 'Remaining Risks'],
}


def log(message: str) -> None:
    with LOG.open('a') as handle:
        handle.write(f'{time.time():.3f} {os.getpid()} {message}\n')


def gc(*args: str, check: bool = True) -> str:
    proc = subprocess.run([GC, *args], capture_output=True, text=True, timeout=120)
    if check and proc.returncode:
        raise RuntimeError(f'gc {" ".join(args[:4])}: {proc.stderr.strip()[-300:]}')
    return proc.stdout


def as_json(text: str):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char in '[{':
            try:
                return decoder.raw_decode(text[index:])[0]
            except ValueError:
                continue
    raise ValueError('no JSON')


def show(bead_id: str) -> dict:
    data = as_json(gc('bd', 'show', bead_id, '--json'))
    return data[0] if isinstance(data, list) else data


def update(bead_id: str, **metadata: str) -> None:
    args = ['bd', 'update', bead_id]
    for key, value in metadata.items():
        args += ['--set-metadata', f'{key.replace("__", ".")}={value}']
    gc(*args)


def close(bead_id: str, reason: str, outcome: str = 'pass', **metadata: str) -> None:
    args = ['bd', 'update', bead_id, '--set-metadata', f'gc.outcome={outcome}',
            '--set-metadata', f'stub.close_reason={reason}']
    for key, value in metadata.items():
        args += ['--set-metadata', f'{key.replace("__", ".")}={value}']
    gc(*args, '--status', 'closed')


def scenario() -> dict:
    path = STUB_DIR / 'scenario.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def artifact(path: Path, schema: str, root: dict, stage: str, extra: dict[str, str] | None = None,
             upstream: list[dict] | None = None) -> None:
    ids = [cid for cid, _ in CRITERIA]
    front = [f'schema: {schema}',
             f'workflow: {{id: {root["id"]}, formula: {root["metadata"].get("gc.formula_name", "jev-build")}}}',
             'methodology: {pack: gascity-jev, name: jev-build}',
             f'producer: {{formula: jev-build, stage: {stage}, attempt: 1}}', 'status: approved', 'trace:',
             '  upstream:']
    for entry in upstream or [{'path': f'beads/{root["id"]}', 'hash': f'bead:{root["id"]}'}]:
        front.append(f'  - path: {entry["path"]}')
        front.append(f'    hash: {entry["hash"]}')
    front.append(f'    ids: [{", ".join(ids)}]')
    front.append('  coverage:')
    front += [f'  - {{id: {cid}, status: covered}}' for cid in ids]
    body = [f'# {stage} (stub)', '']
    for section in SECTIONS[schema]:
        body += [f'## {section}', '', (extra or {}).get(section, f'Stub {section.lower()}.'), '']
    body += ['## Coverage', '', '| ID | Status |', '| --- | --- |'] + [f'| {cid} | covered |' for cid in ids]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\n' + '\n'.join(front) + '\n---\n' + '\n'.join(body) + '\n')


def root_of(step: dict) -> dict:
    return show(step['metadata']['gc.root_bead_id'])


def rig_root() -> Path:
    return Path(os.environ.get('GC_RIG_ROOT') or os.environ.get('GC_STORE_PATH') or os.getcwd()).resolve()


def artifact_root(root: dict) -> Path:
    raw = root['metadata'].get('gc.var.artifact_root', '.gc/build')
    return Path(raw) if Path(raw).is_absolute() else rig_root() / raw


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True).stdout


# --- roles -------------------------------------------------------------------


def prepare(step, root):
    art = artifact_root(root)
    names = {'requirements': 'requirements.md', 'plan': 'implementation-plan.md',
             'decomposition': 'decomposition.md', 'implementation_summary': 'implementation-summary.md',
             'review_report': 'review-report.md', 'final_report': 'factory-run.md'}
    update(root['id'], gc__work_dir=str(rig_root()), gc__build__artifact_root=str(art),
           **{f'gc__build__{k}_path': str(art / v) for k, v in names.items()})
    close(step['id'], 'stub: prepared artifact paths')


def requirements(step, root):
    path = Path(root['metadata']['gc.build.requirements_path'])
    artifact(path, 'gc.build.requirements.v1', root, 'requirements', {
        'Problem Statement': 'Implement slugify in slugger.py so the existing tests pass.',
        'Acceptance Criteria': '\n'.join(f'- {cid}: {text}' for cid, text in CRITERIA)})
    close(step['id'], 'stub: requirements written')


def plan(step, root):
    artifact(Path(root['metadata']['gc.build.plan_path']), 'gc.build.plan.v1', root, 'plan')
    close(step['id'], 'stub: plan written')


def decompose(step, root):
    created = as_json(gc('bd', 'create', 'Implement slugify in slugger.py', '--description',
                         'Implement slugify per the approved requirements. Do not change tests/test_slugger.py.',
                         '--json'))
    task = created['id'] if isinstance(created, dict) else created[0]['id']
    update(task, gc__root_bead_id=root['id'])
    convoy = as_json(gc('convoy', 'create', f'jev-stub-{root["id"]}', task, '--json'))
    convoy_id = convoy.get('id') or convoy.get('convoy_id') or convoy.get('convoy', {}).get('id')
    artifact(Path(root['metadata']['gc.build.decomposition_path']), 'gc.build.decomposition.v1', root,
             'decompose', {'Implementation Convoy': f'`{convoy_id}` with task `{task}`.'})
    update(root['id'], gc__input_convoy_id=convoy_id, gc__build__implementation_convoy_id=convoy_id)
    close(step['id'], f'stub: convoy {convoy_id}')


def drain_anchor(step) -> tuple[dict, str]:
    root = root_of(step)
    convoy = show(root['metadata']['gc.input_convoy_id'])
    anchor = convoy.get('metadata', {}).get('gc.drain_member_id') or root['metadata'].get('gc.drain_member_id')
    return root, anchor


def prepare_worktree(step, _):
    root, anchor = drain_anchor(step)
    rig = rig_root()
    tree = rig / 'worktrees' / anchor
    if not tree.exists():
        git(rig, 'fetch', '-q', 'origin')
        git(rig, 'worktree', 'add', '-q', str(tree), '--detach', 'origin/HEAD')
    update(anchor, work_dir=str(tree))
    close(step['id'], f'stub: worktree {tree}')


def implement(step, _):
    root, anchor = drain_anchor(step)
    tree = Path(show(anchor)['metadata']['work_dir'])
    (tree / 'slugger.py').write_text(SLUG[scenario().get('implementation', 'correct')])
    git(tree, '-c', 'user.name=stub', '-c', 'user.email=stub@example.invalid', 'commit', '-qam', 'Implement slugify')
    build_root = show(root['metadata']['gc.root_bead_id']) if root['metadata'].get('gc.root_bead_id') else root
    summary = artifact_root(build_root) / f'task-{anchor}-summary.md'
    artifact(summary, 'gc.build.implementation-summary.v1', build_root, 'implement',
             upstream=[{'path': f'beads/{anchor}', 'hash': f'bead:{anchor}'}])
    update(root['id'], gc__implementation__summary_path=str(summary))
    close(step['id'], 'stub: implemented')


def close_anchor(step, _):
    _, anchor = drain_anchor(step)
    close(anchor, 'stub: source anchor done')
    close(step['id'], 'stub: source anchor closed')


def summarize(step, root):
    anchors = [m['id'] for m in as_json(gc('ready', '--metadata-field', f'gc.root_bead_id={root["id"]}',
                                            '--metadata-field', 'work_dir', '--status', 'closed',
                                            '--limit', '0', '--json'))]
    upstream = [{'path': f'beads/{a}', 'hash': f'bead:{a}'} for a in anchors] or None
    artifact(Path(root['metadata']['gc.build.implementation_summary_path']), 'gc.build.implementation-summary.v1',
             root, 'summarize-implementation', upstream=upstream)
    close(step['id'], 'stub: summary written')


def lane_report(root, name) -> str:
    path = artifact_root(root) / f'review/{name}-{int(time.time() * 1000)}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'# {name} (stub)\n')
    return str(path)


def acceptance(step, root):
    scope = step['metadata'].get('jev.scope', 'all')
    ids = [cid for cid, _ in CRITERIA] if scope in ('all', '') else [s.strip() for s in scope.split(',') if s.strip()]
    violated = set(scenario().get('violated', []))
    attempt = step['metadata'].get('gc.attempt', '1')
    verdicts = {cid: 'violated' if cid in violated and attempt == '1' else 'holds' for cid in ids}
    verdict = 'iterate' if 'violated' in verdicts.values() else 'approve'
    close(step['id'], f'stub: acceptance {verdict}', jev__criteria_verdicts=json.dumps(verdicts),
          code_review__acceptance_verdict=verdict, code_review__output_path=lane_report(root, 'acceptance'))


def test_evidence(step, root):
    close(step['id'], 'stub: test evidence approve', code_review__test_evidence_verdict='approve',
          code_review__output_path=lane_report(root, 'test-evidence'))


def simplicity(step, root):
    extra = {'jev__smell_verdicts': json.dumps({'screen': 'clean'})} if step['metadata'].get('jev.scope') == 'full' else {}
    close(step['id'], 'stub: simplicity approve', code_review__simplicity_verdict='approve',
          code_review__output_path=lane_report(root, 'simplicity'), **extra)


def synthesize(step, root):
    path = lane_report(root, 'synthesis')
    close(step['id'], 'stub: synthesized', code_review__synthesis_path=path, code_review__output_path=path)


def apply(step, root):
    path = lane_report(root, 'review-fix')
    close(step['id'], 'stub: review done', code_review__verdict='done', code_review__report_path=path,
          code_review__output_path=path)


def finalize(step, root):
    path = Path(root['metadata']['gc.build.final_report_path'])
    artifact(path, 'gc.build.final-report.v1', root, 'finalize')
    update(root['id'], gc__build__final_report_path=str(path), gc__build__factory_run_path=str(path))
    close(step['id'], 'stub: final report written')


def publish(step, root):
    close(step['id'], 'stub: publish disabled', gc__publish_outcome='noop', gc__publish_mode='disabled',
          gc__build_outcome='pass', gc__final_report=root['metadata'].get('gc.build.final_report_path', ''))


ROLES = [
    ('prepare-worktree', prepare_worktree), ('close-source-anchor', close_anchor),
    ('acceptance-review', acceptance), ('test-evidence-review', test_evidence),
    ('simplicity-review', simplicity), ('synthesize-review', synthesize),
    ('apply-review-findings', apply), ('summarize-implementation', summarize),
    ('requirements', requirements), ('plan-review', None), ('plan', plan), ('decompose', decompose),
    ('prepare', prepare), ('implement', implement), ('finalize', finalize), ('publish', publish),
]


def main() -> int:
    STUB_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        claimed = as_json(gc('hook', '--claim', '--drain-ack', '--json'))
        if not (isinstance(claimed, dict) and claimed.get('action') == 'work'):
            log(f'no work: {str(claimed)[:120]}')
            return 0
        step = show(claimed['bead_id'])
        kind = step.get('metadata', {}).get('gc.kind')
        if kind not in ('workflow', 'scope', 'spec'):
            break
        # Same rule as the base pack's claim command: never work a latch.
        gc('bd', 'release-if-current', step['id'], step.get('assignee') or claimed.get('assignee', ''), check=False)
        log(f'released latch {step["id"]} kind={kind}')
    else:
        return 0
    ref = step.get('metadata', {}).get('gc.step_ref', '')
    last = re.sub(r'\.iteration\.\d+$', '', ref).rsplit('.', 1)[-1]
    log(f'claim {step["id"]} {ref} agent={os.environ.get("GC_AGENT", "?")}')
    for name, handler in ROLES:
        if last == name:
            try:
                root = root_of(step)
                if handler is None:
                    close(step['id'], f'stub: {name} passed')
                else:
                    handler(step, root)
                log(f'done {step["id"]} {name}')
            except Exception as error:  # noqa: BLE001
                log(f'error {step["id"]} {name}: {type(error).__name__}: {error}')
                close(step['id'], f'stub error: {error}'[:200], outcome='fail')
            return 0
    log(f'unhandled {step["id"]} {ref}; closing pass')
    close(step['id'], f'stub: unhandled {ref}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

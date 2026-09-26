"""Unit tests for the Jev review gate, decision log and client.

Jev answers come from responses recorded in the gate spikes
(specs/experiments/jev-gate-spikes), replayed either directly or through a
loopback HTTP stub. No test calls the live API.
"""
import http.server
import json
from pathlib import Path
import random
import subprocess
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'gascity-jev/assets/scripts'
SPIKES = ROOT / 'specs/experiments/jev-gate-spikes'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / 'gascity/assets/scripts'))
import jev_client  # noqa: E402
import jev_decisions as jd  # noqa: E402
import jev_gate as gate  # noqa: E402
import validate_build_artifact  # noqa: E402

CRITERIA = [{'id': f'AC-{i}', 'text': t} for i, t in enumerate([
    'Lowercase ASCII alphanumeric words.', 'Treat any run of non-alphanumeric characters as a separator.',
    'Join non-empty groups with single hyphens.', 'No leading or trailing hyphens.',
    'Return an empty string when the input has no alphanumeric characters.'], 1)]


def recorded_review(name='V01-findall'):
    """A recorded spike response re-keyed to the gate's question ids."""
    data = json.loads((SPIKES / f'review-gate/calls/{name}-rep1.response.json').read_text())
    answers = {f'violate_{i}': data['answers'][f'C{i + 1}_violate'] for i in range(5)}
    return {'answers': answers, 'model': data['model'], 'usage': data['usage'], 'elapsed_seconds': 0.4}


def recorded_smell(diff_ids):
    data = json.loads((SPIKES / 'diff-screen/calls/screen-rep1.response.json').read_text())
    hunks = [{'id': f'h{i}', 'path': f'{d}.py', 'text': ''} for i, d in enumerate(diff_ids, 1)]
    answers = {f'h{i}__{rule}': data['answers'][f'{d}__{rule}']
               for i, d in enumerate(diff_ids, 1) for rule in gate.SMELL_RULES}
    return hunks, {'answers': answers, 'model': data['model'], 'usage': data['usage'], 'elapsed_seconds': 0.46}


def inputs(**overrides):
    hunks, smell = recorded_smell(['c1', 'c2'])
    base = dict(root_id='rig-root', step_id='rig-gate', criteria=CRITERIA, receipts_ok=True,
                receipt_problems=[], receipts={'a': {}}, review=recorded_review(), hunks=hunks, smell=smell)
    base.update(overrides)
    return gate.GateInputs(**base)


class Never(random.Random):
    def random(self):
        return 0.999


class Always(random.Random):
    def random(self):
        return 0.0


def bands(**changes):
    result = {k: {**v, 'tripped': False} for k, v in jd.DAY_ONE_BANDS.items()}
    for kind, entry in changes.items():
        result[kind.replace('__', '.')].update(entry)
    return result


BOND_KEYS = {'acceptance', 'test_evidence', 'simplicity', 'synth', 'loop', 'acceptance_scope',
             'simplicity_scope', 'forwarded_smells', 'gate'}


# --- parsing ---------------------------------------------------------------


def test_parse_criteria_lists_tables_nesting_and_generated_ids():
    text = """
- AC-1: Lowercase words.
  continued on the next line
  - nested detail folds into AC-1
- AC-2 (REQ-004): Empty input returns "".
- Plain criterion without an id.
"""
    got = gate.parse_criteria(text)
    assert [c['id'] for c in got] == ['AC-1', 'AC-2', 'C3']
    assert 'continued on the next line' in got[0]['text'] and 'nested detail' in got[0]['text']
    table = '| ID | Criterion |\n| --- | --- |\n| AC-7 | Tests stay unchanged |\n| AC-8 | Runs fast |\n'
    assert [c['id'] for c in gate.parse_criteria(table)] == ['AC-7', 'AC-8']
    assert gate.parse_criteria('### AC-3 Handles unicode\n\n### AC-4 Handles digits')[1]['id'] == 'AC-4'


def test_criteria_from_requirements_reads_only_the_acceptance_section():
    text = ('---\nschema: gc.build.requirements.v1\n---\n# Req\n\n## Behavior Requirements\n\n- REQ-1: x\n\n'
            '## Acceptance Criteria\n\n- AC-1: first\n- AC-2: second\n\n## Out Of Scope\n\n- nothing\n')
    assert gate.criteria_from_requirements(text) == [{'id': 'AC-1', 'text': 'first'}, {'id': 'AC-2', 'text': 'second'}]


def test_criteria_from_task_uses_expected_behavior_block():
    task = ('Implement slugify.\n\nExpected behavior:\n- Lowercase words.\n- Hyphen-join groups.\n\n'
            'Constraints:\n- Do not change tests.\n')
    assert [c['text'] for c in gate.criteria_from_task(task)] == ['Lowercase words.', 'Hyphen-join groups.']


def test_split_hunks_keeps_file_header_on_every_hunk():
    diff = ('diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n@@ -9 +9 @@\n-p\n+q\n'
            'diff --git a/b.py b/b.py\n--- /dev/null\n+++ b/b.py\n@@ -0,0 +1 @@\n+new\n')
    hunks = gate.split_hunks(diff)
    assert [(h['id'], h['path']) for h in hunks] == [('h1', 'a.py'), ('h2', 'a.py'), ('h3', 'b.py')]
    assert all(h['text'].startswith('--- a/') for h in hunks)


# --- band decisions with recorded answers -----------------------------------


def test_recorded_answers_scope_the_acceptance_lane_and_skip_test_evidence():
    item, records = gate.decide(inputs(), bands(), {}, Never())
    assert set(item) == BOND_KEYS
    # V01: C3 = 0.11 and C5 = 0.12 are in the act band; C1, C2, C4 need review.
    assert item['acceptance'] == 'run' and item['acceptance_scope'] == 'AC-1, AC-2, AC-4'
    assert item['test_evidence'] == 'skip'
    assert item['simplicity'] == 'run' and item['simplicity_scope'] == 'design'
    assert item['synth'] == 'run' and item['loop'] == 'run' and item['gate'] == 'jev'
    crit = {r['subject']: r for r in records if r['type'] == 'review.criterion'}
    assert crit['AC-3']['band'] == 'act' and crit['AC-3']['action'] == 'skip' and crit['AC-3']['p'] == 0.11
    assert crit['AC-1']['band'] == 'confirm' and crit['AC-1']['thresholds'] == {'act_max_p': 0.15}
    assert all(r['decision_id'].startswith('jd-') and r['workflow_root'] == 'rig-root' for r in records)


def test_all_criteria_cleared_leaves_one_lane_and_skips_synthesis():
    review = recorded_review()
    for answer in review['answers'].values():
        answer['noul'] = 0.05
    item, _ = gate.decide(inputs(review=review), bands(), {}, Never())
    assert (item['acceptance'], item['test_evidence'], item['simplicity']) == ('skip', 'skip', 'run')
    assert item['acceptance_scope'] == 'none' and item['synth'] == 'skip' and item['loop'] == 'run'


def test_design_skip_band_clears_every_lane_and_drops_the_loop():
    review = recorded_review()
    for answer in review['answers'].values():
        answer['noul'] = 0.05
    item, records = gate.decide(inputs(review=review), bands(simplicity__design={'skip_when_screen_clean': True}),
                                {}, Never())
    assert [item[k] for k in ('acceptance', 'test_evidence', 'simplicity', 'synth', 'loop')] == ['skip'] * 5
    assert any(r['type'] == 'simplicity.design' and r['action'] == 'skip' for r in records)


def test_confirmed_smell_is_forwarded_and_screen_is_not_clean():
    hunks, smell = recorded_smell(['c1', 'd1'])
    item, records = gate.decide(inputs(hunks=hunks, smell=smell), bands(), {}, Never())
    assert item['simplicity_scope'] == 'full'
    assert item['forwarded_smells'] == 'd1.py [h2] debug_output'
    forwarded = [r for r in records if r['type'] == 'smell.confirmed']
    assert forwarded[0]['p'] == 0.98 and forwarded[0]['action'] == 'forward'


def test_failed_receipts_escalate_every_lane_without_asking_jev():
    item, records = gate.decide(inputs(receipts_ok=False, receipt_problems=['a: tests exit 1'], review=None,
                                       smell=None), bands(), {}, Never())
    assert [item[k] for k in ('acceptance', 'test_evidence', 'simplicity', 'synth', 'loop')] == ['run'] * 5
    assert item['gate'] == 'escalate:receipts' and item['acceptance_scope'] == 'all'
    assert {r['band'] for r in records} == {'escalate'}


def test_jev_unavailable_fails_open_to_the_full_path_with_reason():
    item, records = gate.decide(inputs(review=None, review_error='no_key', smell=None), bands(), {}, Never())
    assert item == gate.full_item('fail-open:no_key')
    assert {r['band'] for r in records} == {'escalate'}
    assert all('no_key' in r['reason'] for r in records)


def test_audit_sample_runs_skipped_lanes_and_marks_decisions():
    item, records = gate.decide(inputs(), bands(), {}, Always())
    assert item['test_evidence'] == 'run' and item['simplicity_scope'] == 'full'
    assert item['acceptance_scope'] == 'AC-1, AC-2, AC-3, AC-4, AC-5'
    audited = {r['type'] + ':' + r['subject'] for r in records if r['audit']}
    assert audited == {'review.test_evidence:receipts', 'review.criterion:AC-3', 'review.criterion:AC-5',
                       'smell.clean:screen'}
    assert all(r['band'] == 'act' for r in records if r['audit'])


def test_tripped_breaker_folds_act_band_into_confirm_for_that_type_only():
    item, records = gate.decide(inputs(), bands(review__criterion={'tripped': True}), {}, Never())
    assert item['acceptance_scope'] == 'AC-1, AC-2, AC-3, AC-4, AC-5'
    assert all(r['band'] == 'confirm' for r in records if r['type'] == 'review.criterion')
    assert item['test_evidence'] == 'skip'  # other types keep acting


def test_audit_override_replaces_the_schedule():
    item, records = gate.decide(inputs(), bands(), {}, random.Random(7), audit_override=0.0)
    assert not any(r['audit'] for r in records) and item['test_evidence'] == 'skip'
    item, records = gate.decide(inputs(), bands(), {'review.criterion': 999}, random.Random(7), audit_override=1.0)
    assert all(r['audit'] for r in records if r['band'] == 'act')


def test_audit_rate_schedule():
    assert [jd.audit_rate(n) for n in (0, 59, 60, 299, 300, 5000)] == [0.3, 0.3, 0.1, 0.1, 0.05, 0.05]


# --- decision log, breaker and refit ----------------------------------------


def test_outcome_miss_trips_breaker_and_counts_only_accepted_audits(tmp_path):
    state = jd.StateDir(tmp_path / 'state')
    log = jd.DecisionLog(tmp_path / 'art/jev/decisions.jsonl', state)
    act = jd.decision('review.criterion', workflow_root='r', step_bead='s', subject='AC-1', band='act',
                      action='run', audit=True, p=0.1)
    ok = jd.decision('review.criterion', workflow_root='r', step_bead='s', subject='AC-2', band='act',
                     action='run', audit=True, p=0.12)
    log.write([act, ok])
    log.outcome(ok, label='holds', jev_correct=True, source='lane')
    assert state.accepted_audits() == {'review.criterion': 1}
    assert not state.bands()['review.criterion']['tripped']
    record = log.outcome(act, label='violated', jev_correct=False, source='acceptance lane')
    assert record['miss'] is True
    assert state.bands()['review.criterion']['tripped'] is True
    assert state.bands()['review.test_evidence']['tripped'] is False
    build = jd.read_jsonl(tmp_path / 'art/jev/decisions.jsonl')
    assert [r['record'] for r in build] == ['decision', 'decision', 'outcome', 'outcome']
    assert jd.summarize(state.records())['review.criterion']['misses'] == 1


def test_refit_narrows_below_a_contradiction_and_resets_breaker():
    records, bands_ = [], bands(review__criterion={'tripped': True})
    for p, label in ((0.05, 'holds'), (0.13, 'violated'), (0.3, 'holds')):
        d = jd.decision('review.criterion', workflow_root='r', step_bead='s', subject='x', band='act',
                        action='run', audit=True, p=p)
        records += [d, {'record': 'outcome', 'decision_id': d['decision_id'], 'type': d['type'],
                        'label': label, 'audited': True, 'miss': label == 'violated'}]
    new, notes = jd.refit(records, bands_)
    assert new['review.criterion']['act_max_p'] == pytest.approx(0.08)
    assert new['review.criterion']['tripped'] is False
    assert any('breaker reset' in n for n in notes)


def test_refit_widens_one_step_only_after_enough_clean_labels():
    records = []
    for i in range(60):
        d = jd.decision('review.criterion', workflow_root='r', step_bead='s', subject=str(i), band='confirm',
                        action='run', p=0.18)
        records += [d, {'record': 'outcome', 'decision_id': d['decision_id'], 'type': d['type'],
                        'label': 'holds', 'audited': False, 'miss': False}]
    new, _ = jd.refit(records, bands())
    assert new['review.criterion']['act_max_p'] == pytest.approx(0.2)
    new, _ = jd.refit(records[:20], bands())
    assert new['review.criterion']['act_max_p'] == pytest.approx(0.15)


def test_refit_disables_receipt_act_band_above_five_percent_misses():
    records = []
    for miss in (True, False, False):
        d = jd.decision('review.test_evidence', workflow_root='r', step_bead='s', subject='receipts', band='act',
                        action='run', audit=True)
        records += [d, {'record': 'outcome', 'decision_id': d['decision_id'], 'type': d['type'],
                        'label': 'iterate' if miss else 'approve', 'audited': True, 'miss': miss}]
    new, _ = jd.refit(records, bands())
    assert new['review.test_evidence']['act_enabled'] is False


def test_decisions_cli_status_and_aggregate(tmp_path):
    state = jd.StateDir(tmp_path / 's')
    d = jd.decision('smell.clean', workflow_root='r', step_bead='s', subject='screen', band='act', action='skip')
    state.append([d])
    out = tmp_path / 'agg.json'
    assert jd.main(['aggregate', str(state.ledger_path), '--out', str(out)]) == 0
    assert json.loads(out.read_text())['summary']['smell.clean']['actions'] == {'skip': 1}
    assert jd.main(['refit', '--state-dir', str(tmp_path / 's'), '--dry-run']) == 0
    assert not (tmp_path / 's/bands.json').exists()


# --- client ------------------------------------------------------------------


class StubJev:
    """Loopback Jev stand-in. `reply(payload)` returns (status, body)."""

    def __init__(self, reply):
        stub = self
        self.requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                stub.requests.append({'payload': payload, 'auth': self.headers.get('Authorization')})
                status, body = reply(payload)
                data = json.dumps(body).encode() if not isinstance(body, bytes) else body
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/v1/systemone'

    def close(self):
        self.server.shutdown()


def noul_reply(p):
    return lambda payload: (200, {'model': 'jev-1.13.0', 'usage': {'input_tokens': 10, 'output_tokens': 2},
                                  'answers': {q: {'type': 'noul', 'noul': p(q)} for q in payload['questions']}})


def test_client_requires_key_and_loopback_or_https(monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    with pytest.raises(jev_client.JevUnavailable, match='no_key'):
        jev_client.ask({}, {'q': {'type': 'noul'}})
    monkeypatch.setenv('JEV_API_URL', 'http://example.com/v1/systemone')
    with pytest.raises(jev_client.JevUnavailable, match='bad_endpoint'):
        jev_client.ask({}, {'q': {'type': 'noul'}}, key='k')


def test_client_validates_answers_and_maps_http_errors(monkeypatch):
    stub = StubJev(noul_reply(lambda q: 0.1))
    try:
        monkeypatch.setenv('JEV_API_URL', stub.url)
        result = jev_client.ask({'x': 1}, {'a': {'type': 'noul'}}, key='secret')
        assert result['answers']['a']['noul'] == 0.1 and result['usage']['input_tokens'] == 10
        assert stub.requests[0]['payload']['model'] == 'jev-1.13.0'
        assert stub.requests[0]['auth'] == 'Bearer secret'
    finally:
        stub.close()
    for reply, reason in ((lambda p: (500, {'error': 'x'}), 'http_error'),
                          (lambda p: (200, {'answers': {}}), 'invalid_response'),
                          (lambda p: (200, {'answers': {'a': {'noul': 7}}}), 'invalid_response'),
                          (lambda p: (200, b'not json'), 'invalid_response')):
        stub = StubJev(reply)
        try:
            monkeypatch.setenv('JEV_API_URL', stub.url)
            with pytest.raises(jev_client.JevUnavailable, match=reason):
                jev_client.ask({'x': 1}, {'a': {'type': 'noul'}}, key='k')
        finally:
            stub.close()
    with pytest.raises(jev_client.JevUnavailable, match='state_too_large'):
        jev_client.ask({'x': 'y' * 100_000}, {'a': {'type': 'noul'}}, key='k')


# --- end to end against a fake Gas City and a real git worktree ---------------


class FakeGc:
    def __init__(self, beads):
        self.beads = {b['id']: b for b in beads}
        self.closed = []

    def show(self, bead_id):
        return json.loads(json.dumps(self.beads[bead_id]))

    def update(self, bead_id, metadata):
        self.beads[bead_id].setdefault('metadata', {}).update(metadata)

    def close(self, bead_id, reason):
        self.beads[bead_id]['status'] = 'closed'
        self.closed.append((bead_id, reason))

    def claim(self):
        return 'rig-gate'

    def convoy_members(self, convoy_id):
        return []

    def list_root_members(self, root_id):
        return [self.show(i) for i, b in self.beads.items() if b.get('metadata', {}).get('gc.root_bead_id') == root_id]


def git(cwd, *args):
    subprocess.run(['git', '-C', str(cwd), '-c', 'user.name=t', '-c', 'user.email=t@example.test', *args],
                   check=True, capture_output=True)


SLUG_OK = 'import re\n\ndef slugify(value):\n    return "-".join(w.lower() for w in re.findall(r"[A-Za-z0-9]+", value))\n'
TESTS = 'from slugger import slugify\n\ndef test_basic():\n    assert slugify("Hello, World!") == "hello-world"\n'


def build_city(tmp_path, *, implementation=SLUG_OK, test_text=TESTS):
    origin, rig = tmp_path / 'origin', tmp_path / 'rig'
    origin.mkdir()
    (origin / 'tests').mkdir()
    (origin / 'slugger.py').write_text('def slugify(value):\n    raise NotImplementedError\n')
    (origin / 'tests/test_slugger.py').write_text(TESTS)
    (origin / 'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    git(origin, 'init', '-q', '-b', 'main')
    git(origin, 'add', '.')
    git(origin, 'commit', '-qm', 'fixture')
    subprocess.run(['git', 'clone', '-q', str(origin), str(rig)], check=True)
    tree = rig / 'worktrees/rig-task'
    git(rig, 'worktree', 'add', '-q', '--detach', str(tree), 'origin/main')
    (tree / 'slugger.py').write_text(implementation)
    (tree / 'tests/test_slugger.py').write_text(test_text)
    git(tree, 'commit', '-qam', 'implement')
    art = rig / '.gc/build'
    art.mkdir(parents=True)
    (art / 'requirements.md').write_text('---\nschema: x\n---\n## Problem Statement\n\nSlugs.\n\n## Acceptance Criteria\n\n'
                                        + '\n'.join(f"- {c['id']}: {c['text']}" for c in CRITERIA) + '\n')
    (art / 'implementation-summary.md').write_text('---\ntrace:\n  upstream:\n  - path: beads/rig-task\n---\n')
    root = {'id': 'rig-root', 'status': 'in_progress', 'metadata': {
        'gc.var.artifact_root': '.gc/build', 'gc.var.jev_state_dir': str(tmp_path / 'state'),
        'gc.var.jev_test_command': f'{sys.executable} -c "import sys; sys.exit(0)"',
        'gc.formula_name': 'jev-build', 'gc.work_dir': str(rig),
        'gc.build.requirements_path': str(art / 'requirements.md'),
        'gc.build.implementation_summary_path': str(art / 'implementation-summary.md')}}
    step = {'id': 'rig-gate', 'status': 'in_progress', 'metadata': {'gc.root_bead_id': 'rig-root', 'jev.role': 'review-gate'}}
    task = {'id': 'rig-task', 'status': 'closed', 'description': 'Implement slugify.',
            'metadata': {'gc.root_bead_id': 'rig-root', 'work_dir': str(tree)}}
    return FakeGc([root, step, task]), rig


def run_gate(fake, rng=None):
    ctx = gate.resolve_context(fake, fake.show('rig-gate'))
    return gate.review_gate(ctx, rng=rng or Never()), ctx


def test_gate_with_recorded_jev_emits_one_item_and_writes_log_and_context(tmp_path, monkeypatch):
    review = recorded_review()

    def reply(payload):
        if 'violate_0' in payload['questions']:
            return 200, {'model': 'jev-1.13.0', 'usage': review['usage'], 'answers': review['answers']}
        return noul_reply(lambda q: 0.05)(payload)

    stub = StubJev(reply)
    monkeypatch.setenv('JEV_API_URL', stub.url)
    monkeypatch.setenv('TYPESAFE_API_KEY', 'stub-key')
    try:
        fake, rig = build_city(tmp_path)
        item, ctx = run_gate(fake)
    finally:
        stub.close()
    step = fake.beads['rig-gate']['metadata']
    assert json.loads(step['gc.output_json']) == {'items': [item]}
    assert item['acceptance_scope'] == 'AC-1, AC-2, AC-4' and item['test_evidence'] == 'skip'
    assert step['gc.outcome'] == 'pass' and fake.beads['rig-gate']['status'] == 'closed'
    assert json.loads(step['jev.summary'])['skipped_lanes'] == ['test_evidence']
    state = stub.requests[0]['payload']['state']
    assert 'slugger.py' in state['implementation'] and 'tests/test_slugger.py' in state['tests']
    assert 'stub-key' not in json.dumps(stub.requests[0]['payload'])
    context = Path(fake.beads['rig-root']['metadata']['gc.build.code_review_context_path'])
    assert '## Implementation Worktrees' in context.read_text() and str(rig / 'worktrees/rig-task') in context.read_text()
    log = jd.read_jsonl(Path(step['jev.decision_log_path']))
    assert len(log) == 7 and log == jd.read_jsonl(tmp_path / 'state/ledger.jsonl')
    assert {r['type'] for r in log} == {'review.test_evidence', 'review.criterion', 'smell.clean'}


def test_gate_without_key_fails_open_to_every_lane(tmp_path, monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    fake, _ = build_city(tmp_path)
    item, _ = run_gate(fake)
    assert item == gate.full_item('fail-open:no_key')
    log = jd.read_jsonl(Path(fake.beads['rig-gate']['metadata']['jev.decision_log_path']))
    assert log and all(r['band'] == 'escalate' and 'no_key' in r['reason'] for r in log)


def test_gate_escalates_when_a_preexisting_test_changes(tmp_path, monkeypatch):
    monkeypatch.setenv('TYPESAFE_API_KEY', 'stub-key')
    monkeypatch.setenv('JEV_API_URL', 'http://127.0.0.1:9/unused')
    fake, _ = build_city(tmp_path, test_text=TESTS.replace('"hello-world"', 'slugify("Hello, World!")'))
    item, _ = run_gate(fake)
    assert item['gate'] == 'escalate:receipts' and item['test_evidence'] == 'run'
    problems = json.loads(fake.beads['rig-gate']['metadata']['jev.receipt_problems'])
    assert problems == ['rig-task: pre-existing test tests/test_slugger.py modified']


def test_gate_crash_still_emits_exactly_one_full_item(tmp_path, monkeypatch):
    fake, _ = build_city(tmp_path)
    monkeypatch.setattr(gate, 'source_anchors', lambda ctx: 1 / 0)
    item, _ = run_gate(fake)
    assert item == gate.full_item('fail-open:ZeroDivisionError')
    assert json.loads(fake.beads['rig-gate']['metadata']['gc.output_json'])['items'] == [item]


def test_review_report_is_valid_and_labels_an_audited_miss(tmp_path, monkeypatch):
    review = recorded_review()
    stub = StubJev(lambda p: (200, {'model': 'jev-1.13.0', 'usage': {}, 'answers': review['answers']})
                   if 'violate_0' in p['questions'] else noul_reply(lambda q: 0.05)(p))
    monkeypatch.setenv('JEV_API_URL', stub.url)
    monkeypatch.setenv('TYPESAFE_API_KEY', 'stub-key')
    try:
        fake, _ = build_city(tmp_path)
        item, ctx = run_gate(fake, Always())
    finally:
        stub.close()
    verdicts = {c['id']: 'holds' for c in CRITERIA}
    verdicts['AC-3'] = 'violated'  # AC-3 was an audited act-band skip
    fake.beads.update({
        'lane-a': {'id': 'lane-a', 'status': 'closed', 'metadata': {
            'gc.root_bead_id': 'rig-root', 'jev.lane': 'acceptance', 'gc.attempt': '1',
            'code_review.acceptance_verdict': 'iterate', 'jev.criteria_verdicts': json.dumps(verdicts)}},
        'lane-t': {'id': 'lane-t', 'status': 'closed', 'metadata': {
            'gc.root_bead_id': 'rig-root', 'jev.lane': 'test_evidence', 'gc.attempt': '1',
            'code_review.test_evidence_verdict': 'approve'}},
        'apply-1': {'id': 'apply-1', 'status': 'closed', 'metadata': {
            'gc.root_bead_id': 'rig-root', 'jev.lane': 'apply', 'gc.attempt': '1', 'code_review.verdict': 'iterate'}},
        'apply-2': {'id': 'apply-2', 'status': 'closed', 'metadata': {
            'gc.root_bead_id': 'rig-root', 'jev.lane': 'apply', 'gc.attempt': '2', 'code_review.verdict': 'done'}},
        'rig-report': {'id': 'rig-report', 'status': 'in_progress', 'metadata': {
            'gc.root_bead_id': 'rig-root', 'jev.role': 'review-report'}}})
    ctx = gate.resolve_context(fake, fake.show('rig-report'))
    result = gate.review_report(ctx)
    assert result['status'] == 'approved'
    report = Path(fake.beads['rig-root']['metadata']['gc.build.review_report_path'])
    artifact = validate_build_artifact.validate_artifact_text(report.read_text(), expected_schema='gc.build.review.v1')
    assert [c['id'] for c in artifact.coverage] == [c['id'] for c in CRITERIA]
    misses = [o for o in result['outcomes'] if o['miss']]
    assert [m['decision_id'] for m in misses] == json.loads(fake.beads['rig-report']['metadata']['jev.misses'])
    assert len(misses) == 1
    assert jd.StateDir(tmp_path / 'state').bands()['review.criterion']['tripped'] is True
    assert fake.beads['rig-report']['metadata']['gc.outcome'] == 'pass'


# --- intake router ---------------------------------------------------------

import jev_route  # noqa: E402


def recorded_intake(pr):
    data = json.loads((SPIKES / f'intake-router/calls/eval/{pr}.response.json').read_text())
    return data['attempts'][-1]['body']['answers']


def test_router_sends_recorded_compact_pr_to_compact_formula():
    formula, audited, facts = jev_route.route(recorded_intake(6411), bands()['intake.compact'], 0, Never())
    assert (formula, audited) == ('jev-build-compact', False)
    assert facts['size'] == 'compact' and facts['risky_surface'] == 'none' and facts['needs_design'] == 'no'


def test_router_keeps_the_near_miss_on_the_full_path():
    # #6460: size compact at P 0.89 / confidence 0.82, stopped only by security_or_auth.
    formula, audited, facts = jev_route.route(recorded_intake(6460), bands()['intake.compact'], 0, Never())
    assert formula == 'jev-build' and facts['risky_surface'] != 'none'


def test_router_audits_tripped_and_unavailable_paths():
    answers = recorded_intake(6411)
    assert jev_route.route(answers, bands()['intake.compact'], 0, Always())[:2] == ('jev-build', True)
    tripped = {**bands()['intake.compact'], 'tripped': True}
    assert jev_route.route(answers, tripped, 0, Never())[:2] == ('jev-build', False)
    assert jev_route.route(None, bands()['intake.compact'], 0, Never()) == ('jev-build', False, {})


def test_compact_proxy_matches_the_spike_ground_truth():
    small = {'a': {'files': [{'path': 'x.py'}, {'path': 'tests/test_x.py'}], 'diff_lines': 40}}
    assert gate.compact_proxy(small) is True
    assert gate.compact_proxy({'a': {'files': [{'path': 'x.py'}], 'diff_lines': 81}}) is False
    assert gate.compact_proxy({'a': {'files': [{'path': 'internal/api/h.go'}], 'diff_lines': 5}}) is False

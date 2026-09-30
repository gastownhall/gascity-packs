import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('jev_ab_report', ROOT/'scripts/jev_ab_report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_step_refs_normalize_to_stages():
    assert report.stage_of('jev-build.plan') == 'plan'
    assert report.stage_of('plan.iteration.1') == 'plan'
    assert report.stage_of('jev-build.plan-review') == 'plan-review'
    assert report.stage_of('do-work.prepare-worktree') == 'implement'
    assert report.stage_of('jev-review-tail.jev-build.review.item.1.finalize') == 'review'
    assert report.stage_of('summarize-implementation.iteration.1') == 'summarize'
    assert report.stage_of('finalize.iteration.1') == 'review'
    assert report.stage_of('build-basic.publish') == 'publish'
    assert report.stage_of('') == 'other'


def write_run(run: Path, transcripts: Path):
    run.mkdir(parents=True)
    beads = [{'id': 'fi-abc', 'metadata': {'gc.step_ref': 'plan.iteration.1'}},
             {'id': 'fi-def', 'metadata': {'gc.step_ref': 'implement.iteration.1'}}]
    (run/'final-beads.json').write_text(json.dumps(beads))
    sessions = []
    for name, prompt, messages in (('plan', 'Work bead fi-abc now', ['m1', 'm1', 'm2']),
                                   ('impl', 'Claim fi-def', ['m3']), ('dog', 'Run your patrol', ['m4'])):
        path = transcripts/f'{name}.jsonl'
        path.write_text(json.dumps({'type': 'user', 'message': {'content': prompt}}) + '\n')
        sessions.append({'source': str(path), 'records': [
            {'session_id': name, 'message_id': m, 'usage': {'input_tokens': 1, 'output_tokens': 10 if m != 'm1' else i + 5,
                                                          'cache_read_input_tokens': 100, 'cache_creation_input_tokens': 0}}
            for i, m in enumerate(messages)]})
    (run/'transcript-usage-records.json').write_text(json.dumps(sessions))
    (run/'result.json').write_text(json.dumps({
        'arm': 'jev', 'workload': 'slugify', 'status': 'passed', 'formula': 'jev-build', 'elapsed_seconds': 600,
        'fixture_tests_pass': True, 'hidden_tests_pass': True,
        # A stray candidate passing hidden checks must not count.
        'independent_quality': [{'pytest_exit': 0, 'hidden_exit': 0, 'worktree': '/elsewhere'}],
        'jev_gate_delivery': [{'item': {'gate': 'jev'}, 'summary': {'skipped_lanes': ['test_evidence']}}]}))


def test_sessions_are_attributed_by_first_bead_and_chunks_deduplicated(tmp_path):
    transcripts = tmp_path/'transcripts'
    transcripts.mkdir()
    write_run(tmp_path/'exp/run-001-jev-slugify', transcripts)
    [run] = report.collect(tmp_path/'exp')
    # m1 appears twice: counted once with its largest counters.
    assert run['stages']['plan'] == {'requests': 2, 'sessions': 1, 'input_tokens': 2,
                                     'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 200,
                                     'output_tokens': 16}
    assert run['stages']['implement']['requests'] == 1
    assert run['stages']['helpers']['sessions'] == 1
    assert run['total']['requests'] == 4 and run['hidden_pass'] and run['skipped_lanes'] == ['test_evidence']
    text = report.render([run])
    assert '| run-001-jev-slugify | jev | slugify | completed | passed | jev | yes | 10.0 | 4 |' in text
    assert '| plan | 2.0 | 16 |' in text and 'per stage, - workloads' in text


def test_hidden_pass_is_the_harness_verdict_and_gate_escalations_show(tmp_path):
    transcripts = tmp_path/'transcripts'
    transcripts.mkdir()
    run_dir = tmp_path/'exp/run-006-jev-legacy'
    write_run(run_dir, transcripts)
    result = json.loads((run_dir/'result.json').read_text())
    result.update(status='failed', hidden_tests_pass=False,
                  jev_gate_delivery=[{'item': {'gate': 'escalate:receipts'}, 'jev_answered': False}])
    (run_dir/'result.json').write_text(json.dumps(result))
    [run] = report.collect(tmp_path/'exp')
    assert run['build_completed'] and not run['hidden_pass'] and run['gate'] == 'escalate:receipts'


def test_decision_logs_count_bands_and_labeled_accuracy(tmp_path):
    transcripts = tmp_path/'transcripts'
    transcripts.mkdir()
    run_dir = tmp_path/'exp/run-002-jev-slugify'
    write_run(run_dir, transcripts)
    rows = [{'record': 'decision', 'type': 'intake.direct', 'band': 'act'},
            {'record': 'outcome', 'type': 'intake.direct', 'jev_correct': True, 'miss': False},
            {'record': 'decision', 'type': 'review.criterion', 'band': 'act'},
            {'record': 'decision', 'type': 'review.criterion', 'band': 'confirm'},
            {'record': 'outcome', 'type': 'review.criterion', 'jev_correct': False, 'miss': True},
            {'record': 'outcome', 'type': 'review.criterion', 'jev_correct': None, 'miss': False}]
    (run_dir/'decisions-00.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    [run] = report.collect(tmp_path/'exp')
    assert run['decisions']['intake.direct'] == {'act': 1, 'labeled': 1, 'jev_right': 1, 'miss': 0}
    assert run['decisions']['review.criterion']['jev_wrong'] == 1 and run['decisions']['review.criterion']['miss'] == 1
    assert '| review.criterion | 1 | 1 | 0 | 2 | 0 | 1 | 1 |' in report.render([run])

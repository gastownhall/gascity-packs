#!/usr/bin/env python3
"""All-enabled combined work-packet regression; not a Gas City runtime benchmark."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import jev_ab as accounting
import jev_tasks_ab as decisions
import jev_rank_ab as ranking

ROOT = Path(__file__).resolve().parents[1]
save = accounting.save
evidence = accounting.jev
tasks = decisions.tasks


def prepare(case, fixture_dir):
    states, questions, expected = {}, {}, {}
    for task in ('kind', 'findings', 'failure'):
        state, qs = tasks.prepare(task, case[task]['state'])
        states[task] = state
        for key, question in qs.items():
            questions[f'{task}:{key}'] = {**question, 'instructions':
                f'For this question, use ONLY the nested state `{task}` as your input state. ' + question['instructions']}
            expected[f'{task}:{key}'] = case[task]['expected'][key]
    fixture_dir.mkdir()
    bundle = accounting.fixture(case['evidence'], fixture_dir)
    state = evidence.materialize(bundle)
    states['evidence'] = state
    for key, question in evidence.questions(state).items():
        questions[f'evidence:{key}'] = {**question, 'instructions':
            'For this question, use ONLY the nested state `evidence` as your input state. ' + question['instructions']}
        expected[f'evidence:{key}'] = case['evidence']['expected']
    return states, questions, expected, bundle


def invoke(script, arguments, directory):
    command = [sys.executable, str(ROOT/'gascity-jev/assets/scripts'/script), *arguments,
               '--output-dir', str(directory), '--mode', 'auto']
    save(directory.parent/(directory.name+'-command.json'), command)
    result = subprocess.run(command, capture_output=True, text=True, timeout=65)
    (directory.parent/(directory.name+'-stdout.txt')).write_text(result.stdout)
    (directory.parent/(directory.name+'-stderr.txt')).write_text(result.stderr)
    report = json.loads((directory/'report.json').read_text())
    if bool(result.returncode) != (report['status'] == 'failed'):
        raise ValueError('Helper status/exit mismatch')
    return report


def accepted(report, task):
    if report['status'] != 'completed':
        return {}
    if task == 'evidence':
        return {f'evidence:evidence_{i}': row['choice']
                for i, row in enumerate(report['decisions']) if row['route'] != 'llm_review'}
    decision = report['decision']
    return {f'{task}:{key}': value['choice'] for key, value in decision['answers'].items()
            if key not in decision['fallback_questions']}


def run(case, arm, directory, prepared):
    directory.mkdir()
    start = time.monotonic()
    states, questions, expected, bundle = prepared
    report = {'case_id': case['id'], 'arm': arm, 'status': 'starting',
              'started_at': accounting.stamp(), 'expected': expected, 'helpers': {},
              'state_sha256': evidence.digest(json.dumps(states, sort_keys=True).encode()),
              'ranking_top1': None, 'source_preserved': False}
    save(directory/'state.json', states)
    save(directory/'questions.json', questions)
    trusted = {}
    try:
        rank_state, rank_questions = ranking.rank.prepare(case['ranking']['state'])
        save(directory/'ranking-input.json', rank_state)
        if arm == 'jev':
            for task in ('kind', 'findings', 'failure', 'evidence'):
                if task == 'evidence':
                    source = directory/'bundle.json'
                    save(source, bundle)
                    r = invoke('jev_evidence.py', [str(source), '--threshold', '0.85'], directory/task)
                else:
                    source = directory/(task+'-input.json')
                    save(source, states[task])
                    threshold = '0.85' if task == 'kind' and '/issues/' in case['kind']['provenance'] else '0.90'
                    r = invoke('jev_tasks.py', [task, str(source), '--threshold', threshold], directory/task)
                report['helpers'][task] = r
                trusted.update(accepted(r, task))
            r = invoke('jev_rank.py', [str(directory/'ranking-input.json')], directory/'ranking')
            report['helpers']['ranking'] = r
            if r['status'] == 'completed':
                order = r['decision']['ranked_candidate_ids']
            else:
                (directory/'ranking-fallback').mkdir()
                order, _ = ranking.claude(rank_state, rank_questions, directory/'ranking-fallback')
        else:
            (directory/'ranking-baseline').mkdir()
            order, _ = ranking.claude(rank_state, rank_questions, directory/'ranking-baseline')
        packet = ranking.rank.render(rank_state, order)
        (directory/'candidates.md').write_text(packet)
        report.update(ranked_candidate_ids=order,
                      ranking_top1=order[0] in case['ranking']['gold_top_ids'] if case['ranking']['gold_top_ids'] else None,
                      source_preserved=all(c['title'] in packet and c['body'] in packet for c in rank_state['candidates']))
        # Both arms generate one joint, source-quoted report. Trusted decisions
        # are only the treatment's accepted values; fallbacks are fresh calls.
        save(directory/'accepted-decisions.json', trusted)
        report_state = {**states, 'duplicate_investigation_packet': packet}
        labels, _ = decisions.claude(report_state, questions, trusted, directory/'claude', 'claude-opus-5', 'max', 'report')
        report.update(status='completed', answers=labels, correct=sum(labels[k] == v for k, v in expected.items()),
                      questions=len(expected), report_contract_pass=True,
                      quality_pass=labels == expected and report['ranking_top1'] is not False and report['source_preserved'])
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
    report['elapsed_seconds'] = time.monotonic()-start
    # Reconcile raw call telemetry even if parsing or quality checks failed.
    telemetry = [json.loads(p.read_text()) for p in directory.rglob('telemetry.json')]
    report['claude_calls'] = len(telemetry)
    report['llm_tokens'] = {key: sum(r['totals'][key] for r in telemetry)
                            for key in (*accounting.TOKEN_FIELDS, 'totalTokens')}
    report['llm_usage_unknown'] = sum(not (p.parent/'telemetry.json').exists() for p in directory.rglob('command.json'))
    report['jev_tokens'] = {key: sum((r.get('usage') or {}).get(key, 0) for r in report['helpers'].values())
                            for key in ('input_tokens', 'output_tokens')}
    report['jev_usage_unknown'] = sum(r.get('usage') is None for r in report['helpers'].values())
    report['fallback_questions'] = list(set(questions) - set(trusted)) if arm == 'jev' else []
    save(directory/'result.json', report)
    return report


def summarize(root):
    schedule = json.loads((root/'schedule.json').read_text())
    rows, pairs = [], {}
    for index, item in enumerate(schedule, 1):
        path = root/f'run-{index:03d}-{item["arm"]}'/'result.json'
        if path.exists():
            row = json.loads(path.read_text()); rows.append(row)
            pairs.setdefault((item['case_id'], item['repetition']), {})[item['arm']] = row
    arms = {}
    for arm in ('baseline', 'jev'):
        group = [r for r in rows if r['arm'] == arm]
        arms[arm] = {key: sum(r.get(key, 0) for r in group) for key in ('elapsed_seconds', 'claude_calls', 'correct', 'questions', 'report_contract_pass', 'quality_pass', 'source_preserved', 'llm_usage_unknown', 'jev_usage_unknown')}
        arms[arm].update(attempts=len(group), failed=sum(r['status'] != 'completed' for r in group),
                         ranking_top1_correct=sum(r['ranking_top1'] is True for r in group),
                         ranking_positive_cases=sum(r['ranking_top1'] is not None for r in group))
        for usage, keys in [('llm_tokens', (*accounting.TOKEN_FIELDS, 'totalTokens')), ('jev_tokens', ('input_tokens', 'output_tokens'))]:
            arms[arm][usage] = {k: sum(r[usage][k] for r in group) for k in keys}
        arms[arm]['features'] = {task: {'correct': sum(sum(v == r.get('answers', {}).get(k) for k,v in r['expected'].items() if k.startswith(task+':')) for r in group),
            'questions': sum(sum(k.startswith(task+':') for k in r['expected']) for r in group)} for task in ('kind','findings','failure','evidence')}
    mismatches = []
    for (case, rep), pair in pairs.items():
        if set(pair) != {'baseline', 'jev'}: continue
        b, j = pair['baseline'], pair['jev']
        assert b['state_sha256'] == j['state_sha256']
        for key, gold in b['expected'].items():
            bv, jv = b.get('answers', {}).get(key), j.get('answers', {}).get(key)
            if bv != gold or jv != gold:
                mismatches.append({'case_id': case, 'repetition': rep, 'question': key,
                                   'expected': gold, 'baseline': bv, 'jev': jv,
                                   'regression': bv == gold and jv != gold,
                                   'improvement': jv == gold and bv != gold})
    return {'planned_attempts':len(schedule), 'finished_attempts':len(rows), 'arms':arms,
            'mismatches':mismatches, 'regressions':sum(m['regression'] for m in mismatches),
            'improvements':sum(m['improvement'] for m in mismatches),
            'scope':'Combined independent work packets with generated reports, not a full runtime workflow'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=2)
    args = parser.parse_args()
    if not os.environ.get('TYPESAFE_API_KEY'): parser.error('Jev key required')
    suite = json.loads(args.suite.read_text()); cases = suite['cases']
    if args.repetitions < 1 or not cases: parser.error('Empty schedule')
    args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=False)
    save(args.out/'suite.json', suite)
    source_hashes = {}
    for module in [sys.modules[__name__], accounting, decisions, ranking, evidence, tasks, tasks.kind, ranking.rank]:
        path = Path(module.__file__); data = path.read_bytes()
        (args.out/path.name).write_bytes(data); source_hashes[path.name] = hashlib.sha256(data).hexdigest()
    save(args.out/'manifest.json', {'started_at':accounting.stamp(), 'pack_head': evidence.git_head(ROOT),
         'sources':source_hashes, 'suite_sha256':evidence.digest(args.suite.read_bytes()),
         'claude_model':'claude-opus-5', 'effort':'max', 'jev_model':'jev-1.13.0',
         'repetitions':args.repetitions, 'load_average':os.getloadavg(),
         'claude_version':subprocess.check_output(['claude','--version'],text=True).strip(),
         'thresholds':{'issue_kind':.85, 'pr_kind':.90, 'evidence':.85, 'findings_failure':.90, 'pairs':.95},
         'fixture_proof_in_timing':False, 'policy':'retain failures, continue predeclared schedule, no retries or tuning'})
    prepared = {c['id']:prepare(c, args.out/('input-'+c['id'])) for c in cases}
    schedule = [(c, arm, rep+1) for rep in range(args.repetitions) for i,c in enumerate(cases)
                for arm in (['baseline','jev'] if (rep+i)%2 == 0 else ['jev','baseline'])]
    save(args.out/'schedule.json', [{'case_id':c['id'], 'arm':arm, 'repetition':rep} for c,arm,rep in schedule])
    for index, (case, arm, rep) in enumerate(schedule, 1):
        print(f'[{index}/{len(schedule)}] {case["id"]} {arm} rep={rep} starting', flush=True)
        accounting.event(args.out/'ledger.jsonl', {'event':'started', 'index':index, 'case_id':case['id'], 'arm':arm, 'repetition':rep})
        result = run(case, arm, args.out/f'run-{index:03d}-{arm}', prepared[case['id']])
        accounting.event(args.out/'ledger.jsonl', {'event':'finished','index':index,'repetition':rep,**result})
        print(f'[{index}/{len(schedule)}] {result["status"]}; quality={result.get("quality_pass")}; {result["elapsed_seconds"]:.2f}s', flush=True)
    summary = summarize(args.out); save(args.out/'summary.json', summary)
    return int(any(a['failed'] for a in summary['arms'].values()))


if __name__ == '__main__':
    raise SystemExit(main())

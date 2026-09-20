#!/usr/bin/env python3
"""Audit retained kind cohorts; needs the live key only to check for leakage."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    key = os.environ['TYPESAFE_API_KEY'].encode()
    assert len(key) > 10
    sources = {
        'jev_kind_ab.py': REPO / 'scripts/jev_kind_ab.py',
        'jev_ab.py': REPO / 'scripts/jev_ab.py',
        'jev_kind.py': REPO / 'gascity/assets/scripts/jev_kind.py',
        'jev_evidence.py': REPO / 'gascity/assets/scripts/jev_evidence.py',
    }
    suite_path = ROOT / 'kind-real-dataset-001/suite.json'
    suite = read(suite_path)
    cases = {c['id']: c for c in suite['cases']}
    assert len(cases) == len(suite['cases']) == 36
    counts = {'attempts': 0, 'claude_calls': 0, 'jev_calls': 0, 'fallbacks': 0}
    fields = ['inputTokens', 'outputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens']
    for name in ['kind-pilot-paired-001', 'kind-evaluation-paired-001']:
        cohort = ROOT / name
        manifest = read(cohort / 'manifest.json')
        assert manifest['suite_sha256'] == digest(suite_path)
        assert read(cohort / 'suite.json') == suite
        for filename, path in sources.items():
            assert digest(path) == digest(cohort / filename) == manifest['sources'][filename]
        schedule = read(cohort / 'schedule.json')
        assert len(schedule) == (8 if manifest['split'] == 'pilot' else 64)
        for i, item in enumerate(schedule, 1):
            run = cohort / f'run-{i:03d}-{item["arm"]}'
            result = read(run / 'result.json')
            assert result['status'] == 'completed'
            assert result['case_id'] == item['id'] and result['arm'] == item['arm']
            case = cases[item['id']]
            assert case['split'] == manifest['split']
            state = read(run / 'state.json')
            assert state == {k: case['snapshot'][k] for k in ('title', 'body')}
            assert result['state_sha256'] == hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
            if item['arm'] == 'jev':
                request = read(run / 'request.json')
                response = read(run / 'response.json')
                assert request == {'model': manifest['jev_model'], 'state': state, 'questions': manifest['questions']}
                assert response['model'] == manifest['jev_model']
                assert result['jev_usage'] == response['usage']
                assert result['raw_choice'] == response['answers']['kind']['choice']
                assert result['confidence'] == response['answers']['kind']['confidence']
                assert result['fallback'] == (result['raw_choice'] == 'unclear' or result['confidence'] < manifest['threshold'])
                counts['jev_calls'] += 1
            if item['arm'] == 'baseline' or result['fallback']:
                call = run / 'fallback' if result['fallback'] else run
                prompt = json.loads((call / 'prompt.txt').read_text().split('\n', 1)[1])
                assert prompt == {'state': state, 'questions': manifest['questions']}
                raw = read(call / 'stdout.json')
                telemetry = read(call / 'telemetry.json')
                assert not raw['is_error'] and telemetry['returncode'] == 0
                assert set(raw['modelUsage']) == {'claude-opus-5'}
                totals = {f: sum(m[f] for m in raw['modelUsage'].values()) for f in fields}
                totals['totalTokens'] = sum(totals.values())
                assert result['llm_usage']['totals'] == telemetry['totals'] == totals
                assert result['llm_usage']['models'] == telemetry['models'] == raw['modelUsage']
                answer = raw['result'].strip()
                if answer.startswith('```'):
                    answer = answer.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                assert result['choice'] == json.loads(answer)['choice']
                command = read(call / 'command.json')
                assert command[command.index('--effort') + 1] == 'max'
                assert command[command.index('--model') + 1] == manifest['model']
                assert command[command.index('--tools') + 1] == '' and '--safe-mode' in command
                counts['claude_calls'] += 1
            else:
                assert result['choice'] == result['raw_choice']
                assert result['llm_usage']['totals']['totalTokens'] == 0
            counts['attempts'] += 1
            counts['fallbacks'] += result['fallback']
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and
                   ('kind-' in str(p.relative_to(ROOT)) or p.name in ['ledger.jsonl', 'summarize-kind.py', 'verify-kind.py']))
    files += list(sources.values())
    for path in files:
        if key in path.read_bytes():
            raise SystemExit('Credential leak detected; values suppressed')
    report = {
        'at': datetime.now(timezone.utc).isoformat(), 'status': 'passed', **counts,
        'raw_usage_reconciled': True, 'state_and_rubric_identical_across_arms': True,
        'input_only_title_body': True, 'frozen_sources_unchanged': True,
        'known_credential_absent': True, 'credential_scan_files': len(files),
        'suite_sha256': digest(suite_path), 'host_load_average_after_run': os.getloadavg(),
        'artifact_sha256': {str(p.relative_to(REPO)): digest(p) for p in files},
    }
    with (ROOT / 'kind-verification-001.json').open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'artifact_sha256'}))


if __name__ == '__main__':
    main()

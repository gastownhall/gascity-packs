"""Reconcile all-enabled artifacts without displaying credentials."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
import jev_combined_ab as runner


def main():
    root = Path(__file__).parent
    cohort = root/'combined-001'
    summary = json.loads((cohort/'summary.json').read_text())
    assert summary == runner.summarize(cohort)
    manifest = json.loads((cohort/'manifest.json').read_text())
    assert manifest['suite_sha256'] == hashlib.sha256((root/'suite.json').read_bytes()).hexdigest()
    for name, sha in manifest['sources'].items():
        assert hashlib.sha256((cohort/name).read_bytes()).hexdigest() == sha
    schedule = json.loads((cohort/'schedule.json').read_text())
    claude_calls = jev_calls = failures = 0
    pairs = {}
    for index, scheduled in enumerate(schedule, 1):
        directory = cohort/f'run-{index:03d}-{scheduled["arm"]}'
        result = json.loads((directory/'result.json').read_text())
        pairs.setdefault((scheduled['case_id'],scheduled['repetition']),{})[scheduled['arm']] = directory
        failures += result['status'] != 'completed'
        totals = dict.fromkeys((*runner.accounting.TOKEN_FIELDS,'totalTokens'),0)
        for path in directory.rglob('telemetry.json'):
            telemetry = json.loads(path.read_text())
            raw = json.loads((path.parent/'stdout.json').read_text())
            measured = runner.accounting.usage(raw)
            assert telemetry['totals'] == measured['totals']
            assert set(measured['models']) == {'claude-opus-5'}
            for key,value in measured['totals'].items(): totals[key] += value
            claude_calls += 1
        assert totals == result['llm_tokens']
        jev_tokens = {'input_tokens':0,'output_tokens':0}
        for name, report in result['helpers'].items():
            path = directory/name/'response.json'
            if path.exists():
                raw = json.loads(path.read_text())
                assert raw['usage'] == report['usage']
                assert raw['model'] == 'jev-1.13.0'
                for key in jev_tokens: jev_tokens[key] += raw['usage'][key]
                jev_calls += 1
            request_path = directory/name/'request.json'
            if request_path.exists():
                request = json.loads(request_path.read_text())
                assert set(request) == {'model','state','questions'}
                if name in ('kind','findings','failure','evidence'):
                    source = json.loads((directory/'state.json').read_text())[name]
                    assert request['state'] == source
        assert jev_tokens == result['jev_tokens']
        if scheduled['arm'] == 'baseline': assert not result['helpers']
        if result['status'] == 'completed':
            prompt = (directory/'claude/prompt.txt').read_text()
            payload = json.loads(prompt.split('\n',1)[1])
            assert set(payload) == {'state','questions','accepted_decisions'}
            assert payload['accepted_decisions'] == json.loads((directory/'accepted-decisions.json').read_text())
            assert 'expected' not in payload['state']
            parsed = json.loads((directory/'claude/parsed.json').read_text())
            assert parsed['answers'] == result['answers']
            assert all(parsed['answers'][k] == v for k,v in payload['accepted_decisions'].items())
    for pair in pairs.values():
        assert set(pair) == {'baseline','jev'}
        for name in ('state.json','questions.json','ranking-input.json'):
            assert (pair['baseline']/name).read_bytes() == (pair['jev']/name).read_bytes()
    secret = os.environ['TYPESAFE_API_KEY'].encode()
    count = 0
    for path in root.rglob('*'):
        if path.is_file() and not any(part in ('fixture','pack-snapshot','raw-transcripts','__pycache__') for part in path.parts):
            assert secret not in path.read_bytes(), f'Credential found in {path}; contents suppressed'
            count += 1
    result = {'at':runner.accounting.stamp(), 'status':'passed', 'attempts':len(schedule),
              'claude_calls':claude_calls, 'jev_calls':jev_calls, 'operational_failures':failures,
              'raw_usage_reconciled':True, 'paired_source_equal':True, 'accepted_answers_preserved':True,
              'credential_absent':True, 'files_scanned':count}
    runner.save(root/'audit-001.json', result)
    print(json.dumps(result))


if __name__ == '__main__': main()

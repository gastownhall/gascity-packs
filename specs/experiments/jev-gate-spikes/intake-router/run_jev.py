#!/usr/bin/env python3
"""Ask Jev the intake questions for each PR in a set. One call per PR, no hidden retries.

Usage: TYPESAFE_API_KEY=... run_jev.py --set pilot|eval --state request|issue_only \
           --questions questions/v1.json --out calls/pilot-1
The key is read from the environment only and never written anywhere.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
URL = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-1.13.0'
MAX_ATTEMPTS = 2


def save(path: Path, value) -> None:
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def post(payload: dict, key: str, timeout: float = 60):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), method='POST',
                                 headers={'Authorization': 'Bearer ' + key,
                                          'Content-Type': 'application/json'})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {'ok': True, 'status': r.status, 'body': json.load(r),
                    'latency_s': time.monotonic() - started}
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', 'replace')[:4000]
        return {'ok': False, 'status': e.code, 'error': text, 'latency_s': time.monotonic() - started}
    except Exception as e:  # transport failure; recorded, not hidden
        return {'ok': False, 'status': None, 'error': f'{type(e).__name__}: {e}',
                'latency_s': time.monotonic() - started}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True, choices=['pilot', 'eval'])
    ap.add_argument('--state', default='request', choices=['request', 'issue_only'])
    ap.add_argument('--questions', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--only', type=int, nargs='*', help='limit to these PR numbers (format checks)')
    args = ap.parse_args()
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key:
        raise SystemExit('TYPESAFE_API_KEY is required')
    questions = json.loads((HERE / args.questions).read_text())
    prs = json.loads((HERE / 'prs.json').read_text())['prs']
    out = HERE / args.out
    out.mkdir(parents=True, exist_ok=False)
    field = 'request' if args.state == 'request' else 'issue_only_request'
    index = []
    for pr in prs:
        if pr['set'] != args.set or (args.only and pr['number'] not in args.only):
            continue
        text = pr[field]
        if not text:
            continue
        payload = {'model': MODEL, 'state': {'request': text}, 'questions': questions}
        n = pr['number']
        save(out / f'{n}.request.json', payload)
        attempts = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            res = post(payload, key)
            res['attempt'] = attempt
            res['at'] = datetime.now(timezone.utc).isoformat()
            attempts.append(res)
            if res['ok'] or (res['status'] is not None and 400 <= res['status'] < 500):
                break  # success, or a client error that a retry would not fix
        save(out / f'{n}.response.json', {'attempts': attempts})
        final = attempts[-1]
        index.append({'number': n, 'ok': final['ok'], 'status': final['status'],
                      'attempts': len(attempts), 'latency_s': final['latency_s']})
        print(n, final['status'], f"{final['latency_s']:.2f}s", flush=True)
        if not final['ok'] and final['status'] == 422:
            print(final['error'][:1000])
            break
    save(out / 'index.json', {'set': args.set, 'state': args.state, 'model': MODEL,
                              'questions_file': str(args.questions), 'calls': index})


if __name__ == '__main__':
    main()

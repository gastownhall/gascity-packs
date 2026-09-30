#!/usr/bin/env python3
"""Ask Jev one question set for every record in a set file. One call per record, no hidden retries.

Usage: TYPESAFE_API_KEY=... run.py --set dev.json --questions questions/v4.json --out calls/dev-v4
The key is read from the environment only and never written anywhere. Calls run
in parallel; each response is saved as <out>/<id>.json.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'jev-gate-spikes/intake-router'))
import run_jev as spike  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True, type=Path)
    ap.add_argument('--questions', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key:
        raise SystemExit('TYPESAFE_API_KEY is required')
    questions = json.loads((HERE / args.questions).read_text())
    records = json.loads((HERE / args.set).read_text())['records']
    out = HERE / args.out
    out.mkdir(parents=True, exist_ok=False)

    def one(record):
        payload = {'model': spike.MODEL, 'state': {'request': record['request']}, 'questions': questions}
        reply = spike.post(payload, key)
        spike.save(out / f"{record['id']}.json", {'id': record['id'], 'questions': str(args.questions), **reply})
        return reply['ok']

    with ThreadPoolExecutor(args.workers) as pool:
        ok = list(pool.map(one, records))
    print(f'{sum(ok)}/{len(ok)} calls ok -> {out}')


if __name__ == '__main__':
    main()

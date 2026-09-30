#!/usr/bin/env python3
"""Collect a fresh held-out PR set for the intake-v4 routing study (no Jev calls).

Reuses the intake-router spike's selection and ground-truth rules unchanged
(../jev-gate-spikes/intake-router/collect.py) and takes the newest eligible PRs
merged after that spike's snapshot, so no PR here was seen while designing
questions. Writes fresh.json next to this script.

Usage: collect_fresh.py [--limit 100]
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SPIKE = HERE.parent / 'jev-gate-spikes/intake-router'
sys.path.insert(0, str(SPIKE))
import collect as spike  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=100)
    args = ap.parse_args()
    old = json.loads((SPIKE / 'prs.json').read_text())
    seen, snapshot = {p['number'] for p in old['prs']}, old['snapshot_at']
    listing = spike.gh_json('pr', 'list', '-R', spike.REPO, '--state', 'merged', '--limit', '400', '--json',
                            'number,title,author,mergedAt,baseRefName')
    listing.sort(key=lambda x: x['mergedAt'], reverse=True)
    picked = []
    for pr in listing:
        a = pr['author']
        if (pr['mergedAt'] <= snapshot[:19] or pr['number'] in seen or pr['baseRefName'] != 'main'
                or spike.is_bot(a.get('login'), a.get('is_bot', False)) or spike.TITLE_SKIP.search(pr['title'])):
            continue
        picked.append(pr['number'])
        if len(picked) >= args.limit:
            break
    records = []
    for n in picked:
        v = spike.gh_json('pr', 'view', str(n), '-R', spike.REPO, '--json',
                          'number,title,body,mergedAt,additions,deletions,changedFiles,closingIssuesReferences,url')
        files = [f['filename'] for f in spike.gh_paged(f'repos/{spike.REPO}/pulls/{n}/files')]
        issues = []
        for ref in (v.get('closingIssuesReferences') or [])[:2]:
            owner, name = ref['repository']['owner']['login'], ref['repository']['name']
            iss = spike.gh_json('api', f"repos/{owner}/{name}/issues/{ref['number']}")
            issues.append({'number': ref['number'], 'title': iss['title'], 'body': iss.get('body') or ''})
        cls = set()
        for f in files:
            cls |= spike.classes(f)
        lines = v['additions'] + v['deletions']
        records.append({'id': f"pr{n}", 'number': n, 'url': v['url'], 'title': v['title'],
                        'merged_at': v['mergedAt'], 'request': spike.request_text(v['title'], v['body'], issues),
                        'ground_truth': {'lines': lines, 'changed_files': v['changedFiles'],
                                         'path_classes': sorted(cls),
                                         'depth': spike.depth(v['changedFiles'], lines, cls)}})
        print(n, records[-1]['ground_truth']['depth'], flush=True)
    out = {'repo': spike.REPO, 'snapshot_at': datetime.now(timezone.utc).isoformat(),
           'after': snapshot, 'rules': str(SPIKE / 'PROTOCOL.md'), 'records': records}
    (HERE / 'fresh.json').write_text(json.dumps(out, indent=2) + '\n')


if __name__ == '__main__':
    main()

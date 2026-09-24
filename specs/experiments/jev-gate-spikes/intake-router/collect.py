#!/usr/bin/env python3
"""Collect PR inputs and ground truth for the intake-router spike (no Jev calls).

Writes prs.json next to this script. Rules are frozen in PROTOCOL.md.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

REPO = 'gastownhall/gascity'
HERE = Path(__file__).resolve().parent
N_EVAL, N_PILOT = 60, 10
REQ_CAP, PR_BODY_CAP_WITH_ISSUE = 6000, 3000
BOT_LOGINS = {'renovate', 'dependabot', 'github-actions', 'copilot-pull-request-reviewer',
              'copilot', 'coderabbitai', 'claude'}
TITLE_SKIP = re.compile(r'^(chore|build|fix)\(deps\)|^bump |^(chore\()?release|^release|'
                        r'^merge .* into |^merge branch', re.I)
SECURITY_DIRS = ('cliauth', 'clientauth', 'clientgrant', 'citywriteauth', 'credentialprovider',
                 'doltauth', 'gitcred', 'ssrf', 'webhookverify', 'promptsafe')


def gh_json(*args):
    return json.loads(subprocess.check_output(['gh', *args], text=True))


def gh_paged(path):
    out = subprocess.check_output(['gh', 'api', '--paginate', '--slurp', path], text=True)
    return [x for page in json.loads(out) for x in page]


def is_bot(login: str, flagged: bool = False) -> bool:
    login = (login or '').lower()
    return flagged or login.endswith('[bot]') or login in BOT_LOGINS


def classes(path: str) -> set[str]:
    p = path.lower()
    c = set()
    if p.startswith(('engdocs/', 'specs/', 'plans/', 'design/')) or '/design/' in p:
        c.add('design_docs')
    if p.startswith('internal/api/') or 'openapi' in p:
        c.add('api_contract')
    if p.startswith('schemas/') or p == 'schemas_embed.go' or p.endswith(('.schema.json', '.proto')):
        c.add('schema')
    if p.startswith('internal/migrate/') or any('migration' in seg for seg in p.split('/')):
        c.add('migration')
    if (any(p.startswith(f'internal/{d}/') for d in SECURITY_DIRS) or p == 'security.md'
            or p.startswith('.trivyignore') or 'secret' in p or 'credential' in p):
        c.add('security')
    return c


def depth(files: int, lines: int, cls: set[str]) -> str:
    risky = bool(cls)
    deep_trigger = bool(cls & {'design_docs', 'api_contract', 'schema', 'migration'})
    if files > 15 or lines > 600 or deep_trigger:
        return 'deep'
    if files <= 3 and lines <= 80 and not risky:
        return 'compact'
    return 'standard'


def strip_comments(s: str) -> str:
    return re.sub(r'<!--.*?-->', '', s or '', flags=re.S).strip()


def cap(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 12].rstrip() + ' [truncated]'


def request_text(title: str, body: str, issues: list[dict]) -> str:
    body = strip_comments(body)
    if issues:
        body = cap(body, PR_BODY_CAP_WITH_ISSUE)
    parts = [f'PR title: {title}', '', 'PR description:', body or '(empty)']
    for iss in issues:
        parts += ['', f"Linked issue #{iss['number']}: {iss['title']}",
                  strip_comments(iss['body']) or '(empty)']
    return cap('\n'.join(parts), REQ_CAP)


def issue_only_text(issues: list[dict]) -> str | None:
    if not issues:
        return None
    parts = []
    for iss in issues:
        parts += [f"Issue title: {iss['title']}", '', strip_comments(iss['body']) or '(empty)', '']
    return cap('\n'.join(parts).strip(), REQ_CAP)


def main() -> None:
    snapshot = datetime.now(timezone.utc).isoformat()
    listing = gh_json('pr', 'list', '-R', REPO, '--state', 'merged', '--limit', '300', '--json',
                      'number,title,author,mergedAt,baseRefName')
    listing.sort(key=lambda x: x['mergedAt'], reverse=True)
    excluded, eligible = [], []
    for pr in listing:
        a = pr['author']
        reason = None
        if pr['baseRefName'] != 'main':
            reason = f"base {pr['baseRefName']}"
        elif is_bot(a.get('login'), a.get('is_bot', False)):
            reason = 'bot author'
        elif TITLE_SKIP.search(pr['title']):
            reason = 'deps/release/sync title'
        if reason:
            excluded.append({'number': pr['number'], 'title': pr['title'], 'reason': reason})
        else:
            eligible.append(pr)
        if len(eligible) >= N_EVAL + N_PILOT:
            break
    records = []
    for rank, pr in enumerate(eligible):
        n = pr['number']
        v = gh_json('pr', 'view', str(n), '-R', REPO, '--json',
                    'number,title,body,author,mergedAt,additions,deletions,changedFiles,'
                    'closingIssuesReferences,comments,url')
        files = [f['filename'] for f in gh_paged(f'repos/{REPO}/pulls/{n}/files')]
        reviews = gh_paged(f'repos/{REPO}/pulls/{n}/reviews')
        rcomments = gh_paged(f'repos/{REPO}/pulls/{n}/comments')
        author = v['author']['login']
        human_reviews = [r for r in reviews if r.get('user') and not is_bot(
            r['user']['login'], r['user'].get('type') == 'Bot') and r['user']['login'] != author]
        issues = []
        for ref in (v.get('closingIssuesReferences') or [])[:2]:
            owner, name = ref['repository']['owner']['login'], ref['repository']['name']
            iss = gh_json('api', f"repos/{owner}/{name}/issues/{ref['number']}")
            issues.append({'number': ref['number'], 'repo': f'{owner}/{name}',
                           'title': iss['title'], 'body': iss.get('body') or ''})
        cls = set()
        per_class = {}
        for f in files:
            for c in classes(f):
                cls.add(c)
                per_class.setdefault(c, []).append(f)
        lines = v['additions'] + v['deletions']
        records.append({
            'number': n, 'url': v['url'], 'title': v['title'], 'author': author,
            'merged_at': v['mergedAt'], 'set': 'eval' if rank < N_EVAL else 'pilot',
            'request': request_text(v['title'], v['body'], issues),
            'issue_only_request': issue_only_text(issues),
            'linked_issues': [{k: i[k] for k in ('number', 'repo', 'title')} for i in issues],
            'ground_truth': {
                'additions': v['additions'], 'deletions': v['deletions'], 'lines': lines,
                'changed_files': v['changedFiles'], 'files_listed': len(files),
                'path_classes': sorted(cls), 'class_paths': per_class,
                'human_reviews': len(human_reviews),
                # non-approving human reviews ~ rounds of feedback before merge
                'human_review_rounds': sum(r['state'] in ('COMMENTED', 'CHANGES_REQUESTED')
                                           for r in human_reviews),
                'changes_requested': sum(r['state'] == 'CHANGES_REQUESTED' for r in human_reviews),
                'bot_reviews': len(reviews) - len(human_reviews),
                'review_comments': len(rcomments),
                'conversation_comments': len(v.get('comments') or []),
                'depth': depth(v['changedFiles'], lines, cls),
            },
            'files': files,
        })
        print(n, records[-1]['set'], records[-1]['ground_truth']['depth'], flush=True)
    out = {'repo': REPO, 'snapshot_at': snapshot, 'protocol': 'PROTOCOL.md',
           'n_eval': sum(r['set'] == 'eval' for r in records),
           'n_pilot': sum(r['set'] == 'pilot' for r in records),
           'excluded': excluded, 'prs': records}
    (HERE / 'prs.json').write_text(json.dumps(out, indent=2) + '\n')


if __name__ == '__main__':
    main()

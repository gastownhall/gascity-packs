#!/usr/bin/env python3
"""Read-only repository search producing an auditable Jev candidate input."""
import argparse,json,re,sys
from pathlib import Path
from urllib.parse import urlencode
# github_api lives in the imported base pack; resolve it from the sibling checkout.
sys.path.append(str(Path(__file__).resolve().parents[3]/'gascity/assets/scripts'))
import github_api
import jev_kind
import jev_evidence


def collect(snapshot, terms):
    issue=jev_kind.materialize(snapshot)
    ref=github_api.parse_github_url(snapshot['canonical_url'],expected_kind='issue')
    if not re.fullmatch(r'[A-Za-z0-9_ -]{1,100}',terms) or not terms.strip():
        raise ValueError('query must be plain search words, not GitHub operators')
    query=f'repo:{ref.repo_slug} is:issue in:title,body {terms.strip()}'
    endpoint='search/issues?'+urlencode({'q':query,'per_page':20})
    raw=github_api.gh_api([endpoint])
    if not isinstance(raw,dict) or not isinstance(raw.get('items'),list):
        raise ValueError('invalid search response; cannot infer absence of duplicates')
    candidates=[];seen=set()
    for row in raw['items']:
        candidate=github_api.parse_github_url(row['html_url'])
        if candidate.kind!='issue' or candidate.repo_slug!=ref.repo_slug or candidate.number==ref.number:
            continue
        if candidate.canonical_url in seen:continue
        seen.add(candidate.canonical_url)
        candidates.append({'id':candidate.canonical_url,**jev_kind.materialize(row)})
    return {'query':query,'endpoint':endpoint,'total_count':raw.get('total_count'),
            'incomplete_results':raw.get('incomplete_results'),'raw':raw,
            'input':{'issue':issue,'candidates':candidates}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot',type=Path)
    p.add_argument('--query',required=True,help='plain words selected for the issue, same query as ordinary investigation')
    p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=False)
    try:
        record=collect(json.loads(a.snapshot.read_text()),a.query)
        jev_evidence.save(a.output_dir/'search.json',record)
        jev_evidence.save(a.output_dir/'input.json',record['input'])
        print(json.dumps({'status':'completed','candidates':len(record['input']['candidates']),'input':str(a.output_dir/'input.json')}))
        return 0
    except Exception as e:
        jev_evidence.save(a.output_dir/'error.json',{'status':'failed','error':f'{type(e).__name__}: {e}'})
        return 1


if __name__=='__main__':raise SystemExit(main())

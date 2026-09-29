import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'assets/scripts'))
import github_duplicate_candidates as candidates


def test_search_excludes_self_prs_and_wrong_repository(monkeypatch):
    rows=[{'html_url':url,'title':'x','body':'body'} for url in [
        'https://github.com/acme/app/issues/1','https://github.com/acme/app/issues/2',
        'https://github.com/acme/other/issues/3','https://github.com/acme/app/pull/4']]
    calls=[]
    def api(args):calls.append(args);return {'items':rows,'total_count':4,'incomplete_results':False}
    monkeypatch.setattr(candidates.github_api,'gh_api',api)
    result=candidates.collect({'title':'config panic','body':'','canonical_url':'https://github.com/acme/app/issues/1'},'config panic')
    assert [c['id'] for c in result['input']['candidates']]==['https://github.com/acme/app/issues/2']
    assert 'repo%3Aacme%2Fapp' in calls[0][0]


def test_retrieval_error_and_invalid_query_are_not_empty_candidates(monkeypatch):
    def fail(args):raise RuntimeError('HTTP 503')
    monkeypatch.setattr(candidates.github_api,'gh_api',fail)
    snapshot={'title':'x','body':'','canonical_url':'https://github.com/acme/app/issues/1'}
    with pytest.raises(ValueError):candidates.collect(snapshot,'repo:other/private')
    with pytest.raises(RuntimeError):candidates.collect(snapshot,'config')

"""Benchmark accounting and cleanup must not misattribute work or stop other cities."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('jev_build_ab', ROOT/'scripts/jev_build_ab.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_transcript_usage_deduplicates_chunks_and_excludes_adjacent_city(tmp_path):
    workspace = tmp_path/'city'
    projects = tmp_path/'projects'
    encoded = build.re.sub(r'[^a-zA-Z0-9]', '-', str(workspace))
    selected = projects/(encoded+'-rig')
    unrelated = projects/(encoded+'other')
    selected.mkdir(parents=True)
    unrelated.mkdir()
    def row(output):
        return {'type':'assistant','sessionId':'session','message':{
            'id':'message','model':'sonnet','usage':{'input_tokens':2,
            'output_tokens':output,'cache_read_input_tokens':100,'cache_creation_input_tokens':5}}}
    (selected/'session.jsonl').write_text('\n'.join(json.dumps(row(n)) for n in [3,7,7]))
    (unrelated/'session.jsonl').write_text(json.dumps(row(99)))
    result = build.transcript_usage(projects,workspace,tmp_path)
    assert result['message_count']==1
    assert result['totals']=={'input_tokens':2,'output_tokens':7,
                             'cache_read_input_tokens':100,'cache_creation_input_tokens':5}


def test_missing_transcript_usage_remains_unknown(tmp_path):
    projects=tmp_path/'projects'; projects.mkdir()
    result=build.transcript_usage(projects,tmp_path/'workspace',tmp_path)
    assert result['status']=='missing' and result['totals'] is None


def test_cleanup_only_signals_exact_disposable_server(tmp_path, monkeypatch):
    city=tmp_path/'city'
    config=city/'.gc/runtime/packs/dolt/dolt-config.yaml'
    listing=f'1 dolt sql-server --config /another/city/config.yaml\n2 dolt sql-server --config {config}\n3 /bin/sh -c dolt sql-server --config {config}\n'
    monkeypatch.setattr(build.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=listing,stderr=''))
    signals=[]
    monkeypatch.setattr(build.os,'kill',lambda pid,sig:signals.append((pid,sig)))
    result=build.stop_disposable_dolt(city)
    assert result['pids']==[2]
    assert signals==[(2,build.signal.SIGTERM)]


def test_cleanup_reports_when_process_inspection_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(build.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout='',stderr='denied'))
    monkeypatch.setattr(build.os,'kill',lambda *a:pytest.fail('must not signal without ownership evidence'))
    assert build.stop_disposable_dolt(tmp_path)['status']=='unverified'


def test_cleanup_resolves_config_path_aliases(tmp_path, monkeypatch):
    actual=tmp_path/'actual'; actual.mkdir()
    alias=tmp_path/'alias'; alias.symlink_to(actual, target_is_directory=True)
    config=alias/'city/.gc/runtime/packs/dolt/dolt-config.yaml'
    listing=f'12 dolt sql-server --config {config}\n'
    monkeypatch.setattr(build.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=listing,stderr=''))
    signals=[]
    monkeypatch.setattr(build.os,'kill',lambda pid,sig:signals.append(pid))
    assert build.stop_disposable_dolt(actual/'city')['pids']==[12]


def test_experiment_env_retains_home_and_separates_mutable_config(tmp_path):
    workspace=SimpleNamespace(gc_home=tmp_path/'h')
    env={'HOME':str(tmp_path/'wrong'),'PATH':'/bin','BD_ALLOW_REMOTE_MIGRATE':'1'}
    result=build.configure_experiment_env(env,workspace,real_home=Path('/Users/example'))
    assert result['HOME']=='/Users/example'
    assert result['GIT_CONFIG_GLOBAL']==str(workspace.gc_home/'gitconfig')
    assert result['DOLT_ROOT_PATH']==str(workspace.gc_home)
    assert 'BD_ALLOW_REMOTE_MIGRATE' not in result


def test_workspace_socket_path_fits_even_with_deep_artifact_directory(tmp_path):
    from contextlib import ExitStack
    from unittest.mock import patch
    captured={}
    def workspace(root,**kwargs):
        captured['root']=root
        return SimpleNamespace(root=root,gc_home=root/'gc-home')
    with ExitStack() as stack:
        stack.enter_context(patch.object(build.gate,'write_gate_workspace',workspace))
        result=build.new_runtime_workspace(SimpleNamespace(source=tmp_path,roles_source=tmp_path),'unit')
        stack.callback(build.shutil.rmtree,result.root.parent)
        assert len(str(result.gc_home/'supervisor.sock').encode())<100

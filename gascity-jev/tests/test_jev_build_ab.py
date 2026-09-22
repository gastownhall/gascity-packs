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


def test_build_arms_explicitly_set_every_applicable_jev_mode():
    # The restored baseline has no Jev variables; even off would be unknown.
    assert build.jev_variables('baseline', 'jev-1.13.0') == {}
    variables = build.jev_variables('jev', 'jev-1.13.0')
    assert {key: variables[key] for key in ('jev_mode', 'jev_findings_mode', 'jev_failure_mode')} == {
        key: 'auto' for key in ('jev_mode', 'jev_findings_mode', 'jev_failure_mode')}
    assert variables['jev_model'] == variables['jev_decision_model'] == 'jev-1.13.0'


@pytest.mark.parametrize('arm, name', [('baseline', 'gascity'), ('jev', 'gascity-jev')])
def test_build_arm_installs_its_own_pack_roles_and_preserves_source_provenance(tmp_path, arm, name):
    import tomllib
    pack = build.pack_for_arm(arm)
    assert pack.name == name
    assert pack.source == ROOT / name
    assert pack.roles_source == pack.source / 'roles'
    assert pack.validator_source == pack.source
    assert pack.binding == 'gc'
    workspace = build.new_runtime_workspace(pack, 'pack-selection-test')
    try:
        config = tomllib.loads((workspace.city_dir / 'city.toml').read_text())
        city_pack = tomllib.loads((workspace.city_dir / 'pack.toml').read_text())
        assert city_pack['imports']['gc']['source'] == str(pack.source)
        assert city_pack['pack']['name'] == f'{name}-pack-inference-gate'
        assert config['rigs'][0]['imports']['gc']['source'] == str(pack.roles_source)
        out = tmp_path / 'provenance'
        out.mkdir()
        provenance = build.snapshot_pack(pack, out)
        assert provenance['pack_name'] == name
        assert provenance['pack_source'] == str(pack.source)
        assert provenance['roles_source'] == str(pack.roles_source)
        assert provenance['validator_source'] == str(pack.validator_source)
        hashes = json.loads((out / 'source-hashes.json').read_text())
        assert f'{name}/pack.toml' in hashes
        other = 'gascity-jev' if name == 'gascity' else 'gascity'
        assert not any(path.startswith(other + '/') for path in hashes)
        snapshot = out / 'pack-snapshot'
        assert (snapshot / 'pack.toml').read_bytes() == (pack.source / 'pack.toml').read_bytes()
        assert (snapshot / 'assets/scripts/jev_evidence.py').exists() == (arm == 'jev')
        assert hashes[f'{name}/pack.toml'] == build.hashlib.sha256((snapshot / 'pack.toml').read_bytes()).hexdigest()
    finally:
        build.shutil.rmtree(workspace.root.parent)


def test_independent_quality_rejects_stub_even_when_edited_tests_pass(tmp_path, monkeypatch):
    import os
    rig=tmp_path/'fixture'; (rig/'tests').mkdir(parents=True)
    (rig/'slugger.py').write_text('def slugify(value):\n    raise NotImplementedError\n')
    original=b'def test_original():\n    assert False\n'
    (rig/'tests/test_slugger.py').write_text('def test_placeholder():\n    assert True\n')
    monkeypatch.setattr(build.gate,'build_result_candidates',lambda *a:[rig])
    out=tmp_path/'out';out.mkdir()
    rows=build.final_quality(SimpleNamespace(rig_dir=rig),[],out,dict(os.environ),build.hashlib.sha256(original).hexdigest())
    assert len(rows)==1
    assert rows[0]['original_tests_unchanged'] is False
    assert rows[0]['pytest_exit']==0
    assert rows[0]['hidden_exit']==1
    assert all(not row['pass'] for row in json.loads((out/'quality-000/hidden.txt').read_text()))


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
        result=build.new_runtime_workspace(SimpleNamespace(source=tmp_path,roles_source=tmp_path,
            validator_source=tmp_path,name='test',binding='gc'),'unit')
        stack.callback(build.shutil.rmtree,result.root.parent)
        assert len(str(result.gc_home/'supervisor.sock').encode())<100


def test_default_claude_login_does_not_set_config_override(tmp_path):
    workspace=SimpleNamespace(gc_home=tmp_path/'h')
    result=build.configure_experiment_env({'CLAUDE_CONFIG_DIR':str(tmp_path/'scratch')},workspace,real_home=Path('/Users/example'))
    assert 'CLAUDE_CONFIG_DIR' not in result


def test_explicit_claude_profile_is_preserved(tmp_path):
    workspace=SimpleNamespace(gc_home=tmp_path/'h')
    result=build.configure_experiment_env({},workspace,real_home=Path('/Users/example'),claude_config_dir='/profiles/benchmark')
    assert result['CLAUDE_CONFIG_DIR']=='/profiles/benchmark'


def test_gate_toolchain_preserves_virtualenv_python(tmp_path):
    import os
    import subprocess
    import venv
    venv.EnvBuilder(with_pip=False).create(tmp_path/'venv')
    python = tmp_path/'venv/bin/python'
    bd = tmp_path/'real-bd'
    bd.write_text('#!/bin/sh\nexit 0\n')
    bd.chmod(0o755)
    workspace = SimpleNamespace(gc_home=tmp_path/'home')
    env = build.install_gate_toolchain({'PATH':os.defpath}, workspace,
        python_bin=str(python), bd_bin=str(bd))
    # Model the SDK's narrowed PATH using only the directory of its selected bd.
    safe_path = str(Path(build.shutil.which('bd', path=env['PATH'])).parent) + ':' + os.defpath
    actual = subprocess.check_output(['python3','-c','import sys; print(sys.prefix)'],
        env={'PATH':safe_path,'HOME':str(tmp_path)},text=True).strip()
    assert Path(actual) == tmp_path/'venv'


@pytest.mark.parametrize('arm', ['baseline', 'jev'])
def test_interrupt_retains_terminal_report_and_cleanup(tmp_path, monkeypatch, arm):
    events=[]
    selected_pack=build.pack_for_arm(arm)
    workspace=build.new_runtime_workspace(selected_pack,'interrupt-test')
    monkeypatch.setattr(build,'new_runtime_workspace',lambda *a:workspace)
    real_output=build.subprocess.check_output
    def output(cmd,**kw):
        return real_output(cmd,**kw) if cmd[0]=='git' else 'test-version\n'
    monkeypatch.setattr(build.subprocess,'check_output',output)
    def interrupt(*a,**kw):
        assert kw['pack_spec'] == selected_pack
        raise KeyboardInterrupt()
    monkeypatch.setattr(build.gate,'initialize_city',interrupt)
    monkeypatch.setattr(build.gate,'stop_city',lambda *a,**kw:events.append('stop'))
    monkeypatch.setattr(build,'stop_disposable_dolt',lambda *a:{'status':'not_started'})
    monkeypatch.setattr(build,'transcript_usage',lambda *a:{'status':'missing'})
    class Collector:
        env={}
        def __init__(self,*a):pass
        def close(self):events.append('collector_close');return {'status':'missing'}
    monkeypatch.setattr(build.usage,'Collector',Collector)
    args=SimpleNamespace(gc_bin=build.shutil.which('true'),bd_bin=build.shutil.which('true'),model='unused',
        jev_model='unused',setup_only=True,setup_timeout=1)
    try:
        try:result=build.run(args,arm,tmp_path/'run')
        except KeyboardInterrupt:pytest.fail('Interrupt escaped before saving terminal result')
        assert result['status']=='aborted'
        assert result['pack_name']==selected_pack.name
        manifest=json.loads((tmp_path/'run/manifest.json').read_text())
        assert manifest['pack_name']==selected_pack.name
        assert manifest['pack_source']==str(selected_pack.source)
        assert manifest['roles_source']==str(selected_pack.roles_source)
        assert manifest['validator_source']==str(selected_pack.validator_source)
        assert json.loads((tmp_path/'run/result.json').read_text())['status']=='aborted'
        assert events==['stop','collector_close']
    finally:
        build.shutil.rmtree(workspace.root.parent)


def test_local_origin_supports_workflow_default_branch_and_worktree(tmp_path):
    import os
    import subprocess
    env={**os.environ,'GIT_CONFIG_GLOBAL':os.devnull,'GIT_CONFIG_NOSYSTEM':'1'}
    rig=tmp_path/'fixture'; rig.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-C',str(rig),*args],env=env,text=True).strip()
    git('init','-b','release-line')
    (rig/'fixture.txt').write_text('original fixture\n')
    git('add','.')
    git('-c','user.name=Experiment','-c','user.email=experiment@example.invalid','commit','-m','fixture')
    original=git('rev-parse','HEAD')
    result=build.prepare_local_origin(SimpleNamespace(root=tmp_path,rig_dir=rig),env)
    assert result['default_branch']=='origin/release-line'
    assert git('rev-parse','origin/HEAD')==original
    assert Path(git('remote','get-url','origin')).is_relative_to(tmp_path)
    worktree=tmp_path/'implementation'
    git('fetch','--prune','origin','release-line')
    git('worktree','add',str(worktree),'--detach',result['default_branch'])
    assert (worktree/'fixture.txt').read_text()=='original fixture\n'

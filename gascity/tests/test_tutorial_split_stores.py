"""Actual split-store tutorial retry: source/convoy in work, root in graph."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'assets/scripts'
FIXTURE=Path(__file__).with_name('fixtures')/'tutorial-native-split-7d.json'

@pytest.mark.parametrize('extra_rows',[False,True],ids=['graph-only','federated-native'])
def test_immediate_start_observes_native_graph_binding_without_second_sling(tmp_path,monkeypatch,capsys,extra_rows):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec=importlib.util.spec_from_file_location('tutorial_split',SCRIPTS/'tutorial.py')
    tutorial=importlib.util.module_from_spec(spec);spec.loader.exec_module(tutorial)
    import source_delivery
    fixture=json.loads(FIXTURE.read_text())
    source,root,convoys=fixture['source'],fixture['workflow'],fixture['convoys']
    work_rows=[source,*convoys]
    all_rows=[*work_rows,root]
    calls=[]
    def observe(*argv,**kwargs):
        args=argv[1:];calls.append(args)
        if args[:2]==('rig','list'):return {'rigs':[{'name':'practice','path':str(tmp_path/'projects/practice')}]}
        if args==('beads','list','--all','--fresh','--strict','--format=json'):
            return copy.deepcopy(all_rows if extra_rows else root)
        if args[:4]==('--rig','practice','bd','list'):
            selector=args[args.index('--metadata-field')+1];key,value=selector.split('=',1)
            return [copy.deepcopy(row) for row in work_rows if row.get('metadata',{}).get(key)==value]
        if args[:4]==('--rig','practice','bd','dep'):return copy.deepcopy(convoys)
        if args[:3]==('--rig','practice','sling'):
            raise source_delivery.InfrastructureError('native source already has live workflow(s): '+root['id'])
        raise AssertionError('unexpected/mutating command: '+repr(args))
    monkeypatch.setattr(source_delivery,'gc',observe)
    monkeypatch.setattr(tutorial,'scaffold',lambda path:path)
    monkeypatch.setenv('GC_CITY_PATH',str(tmp_path))
    monkeypatch.setattr('sys.argv',['tutorial','start','--lesson','greeting'])
    tutorial.main()
    assert 'Existing workflow: '+root['id'] in capsys.readouterr().out
    assert not any('sling' in args or 'update' in args or '--force' in args for args in calls)


@pytest.fixture
def delivery(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import source_delivery
    return source_delivery


@pytest.mark.parametrize('payload', [
    None, {}, {'beads': [], '_cache_age_s': 0},
    {'beads': [], 'partial': True}, {'beads': [], 'next_cursor': 'more'},
    ['not a bead'], [{'id': 'root', 'status': 'open', 'metadata': []}],
    [{'id': 'root', 'status': 'open', 'metadata': {'gc.kind': None}}],
    [{'id': '', 'status': 'open'}], [{'id': 'root'}],
    [{'id': 'root', 'status': 'open', 'labels': 'gc:session'}],
])
def test_uncertain_native_listing_never_proves_no_workflow(delivery, payload):
    calls=[]
    def observe(*args, **kwargs):
        calls.append(args)
        assert args == ('gc', 'beads', 'list', '--all', '--fresh', '--strict', '--format=json')
        return payload
    with pytest.raises(delivery.InfrastructureError, match='native workflow observation'):
        delivery.attached_workflow(observe, {'id': 'pr-4ob'}, 'practice')
    assert len(calls) == 1


def test_root_identity_keeps_logical_source_scope_across_physical_binding(delivery):
    fixture=json.loads(FIXTURE.read_text())
    root=fixture['workflow']
    foreign_source=copy.deepcopy(root)
    foreign_source['id']='other-source'
    foreign_source['metadata']['gc.source_store_ref']='rig:other'
    foreign_root=copy.deepcopy(root)
    foreign_root['id']=root['id']  # same native ID, different logical scope
    foreign_root['metadata']['gc.root_store_ref']='rig:other'
    def observe(*args, **kwargs):
        if args[1:3] == ('beads', 'list'):
            return [foreign_source, foreign_root, root]
        assert args[1:5] == ('--rig', 'practice', 'bd', 'dep')
        return fixture['convoys']
    assert delivery.attached_workflow(observe, fixture['source'], 'practice') == root['id']


def test_same_id_different_matching_native_rows_are_ambiguous(delivery):
    root={'id':'same', 'status':'open', 'metadata':{
        'gc.kind':'workflow', 'gc.source_bead_id':'source', 'gc.source_store_ref':'rig:practice'}}
    different=copy.deepcopy(root)
    different['status']='closed'
    def observe(*args, **kwargs):
        if args[1:3] == ('beads', 'list'):
            return [root, different]
        return []
    with pytest.raises(ValueError, match='ambiguous workflow identity'):
        delivery.attached_workflow(observe, {'id':'source'}, 'practice')


def test_strict_read_failure_preserves_native_diagnostic_without_mutation(delivery):
    calls=[]
    def observe(*args, **kwargs):
        calls.append(args)
        raise delivery.InfrastructureError('configured practice store is unavailable')
    with pytest.raises(delivery.InfrastructureError, match='configured practice store is unavailable'):
        delivery.attached_workflow(observe, {'id':'source'}, 'practice')
    assert calls == [('gc', 'beads', 'list', '--all', '--fresh', '--strict', '--format=json')]


@pytest.mark.parametrize('binding', ['gc.source_bead_id', 'gc.input_convoy_id'])
def test_matching_unscoped_root_requires_inspection_not_inference(delivery, binding):
    root={'id':'legacy-root', 'status':'open', 'metadata':{
        'gc.kind':'workflow', 'gc.formula_name':'quick-start',
        binding:'source' if binding == 'gc.source_bead_id' else 'input'}}
    calls=[]
    def observe(*args, **kwargs):
        calls.append(args)
        if args[1:3] == ('beads', 'list'):
            return root
        assert args == ('gc', '--rig', 'practice', 'bd', 'dep', 'list', 'source',
                        '--direction', 'up', '--type', 'tracks', '--json')
        return [{'id':'input', 'issue_type':'convoy', 'metadata':{'gc.synthetic':'true'}}]
    with pytest.raises(ValueError, match='workflow scope is unavailable'):
        delivery.attached_workflow(observe, {'id':'source'}, 'practice')
    assert all('sling' not in args and 'update' not in args for args in calls)


def test_explicit_source_scope_can_differ_from_root_execution_scope(delivery):
    root={'id':'root', 'status':'open', 'metadata':{
        'gc.kind':'workflow', 'gc.source_bead_id':'source',
        'gc.source_store_ref':'rig:practice', 'gc.root_store_ref':'city:example'}}
    def observe(*args, **kwargs):
        return root if args[1:3] == ('beads', 'list') else []
    assert delivery.attached_workflow(observe, {'id':'source'}, 'practice') == 'root'


def test_unrelated_formula_does_not_require_a_scope_for_this_lesson(delivery):
    other={'id':'review', 'status':'open', 'metadata':{
        'gc.kind':'workflow', 'gc.formula_name':'review', 'gc.input_convoy_id':'input'}}
    def observe(*args, **kwargs):
        if args[1:3] == ('beads', 'list'):
            return other
        return [{'id':'input', 'issue_type':'convoy', 'metadata':{'gc.synthetic':'true'}}]
    assert delivery.attached_workflow(observe, {'id':'source'}, 'practice') is None

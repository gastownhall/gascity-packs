"""Durable seat bindings work after a session restart without a rebind."""
from __future__ import annotations

import pathlib
import sys
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))


@pytest.fixture
def common(monkeypatch):
    sys.modules.pop('slack_intake_common', None)
    import slack_intake_common
    monkeypatch.setenv('GC_SESSION_ID', 'local-session')
    monkeypatch.setenv('GC_ALIAS', 'local/seat')
    monkeypatch.setenv('GC_AGENT', 'local/seat')
    monkeypatch.setenv('GC_CITY_NAME', 'test-city')
    return slack_intake_common


def binding(agent='helios/canola', channel='CFOREMAN', **meta):
    return {
        'status': 'open',
        'metadata': {
            'agent_name': agent, 'session_id': '', 'provider': 'slack',
            'scope_id': 'test-city', 'account_id': 'TWORKSPACE',
            'conversation_id': channel, 'conversation_kind': 'room',
            'bound_at': '2026-09-13T16:13:07Z', 'expires_at': '', **meta,
        },
    }


def fake_api(common, monkeypatch, *, beads=None, sessions=None, session_bindings=None):
    calls = []

    def get(path):
        calls.append(path)
        parsed = urlsplit(path)
        query = parse_qs(parsed.query)
        if parsed.path == '/extmsg/bindings':
            return {'items': session_bindings or []}
        if parsed.path == '/sessions':
            return {'items': sessions if sessions is not None else [
                {'id': 'new-session', 'alias': 'helios/canola'}]}
        assert parsed.path == '/beads'
        assert query['label'][0].startswith('extmsg:binding:agent:v1:')
        assert query['status'] == ['open']
        return {'items': beads or [], 'total': len(beads or [])}

    monkeypatch.setattr(common, 'gc_get', get)
    return calls


def test_restarted_session_resolves_agent_binding(common, monkeypatch):
    calls = fake_api(common, monkeypatch, beads=[binding()])
    result = common.look_up_binding('new-session')
    assert result == {
        'scope_id': 'test-city', 'provider': 'slack', 'account_id': 'TWORKSPACE',
        'conversation_id': 'CFOREMAN', 'parent_conversation_id': '', 'kind': 'room',
    }
    assert parse_qs(urlsplit(calls[-1]).query)['label'] == [
        'extmsg:binding:agent:v1:helios/canola']


def test_current_alias_avoids_session_list(common, monkeypatch):
    calls = fake_api(common, monkeypatch, beads=[binding('local/seat')])
    assert common.look_up_binding('local-session')['conversation_id'] == 'CFOREMAN'
    assert '/sessions' not in calls


def test_explicit_other_session_does_not_borrow_current_alias(common, monkeypatch):
    fake_api(common, monkeypatch, beads=[binding('local/seat')])
    assert common.look_up_binding('new-session') is None


def test_session_binding_wins_without_agent_lookup(common, monkeypatch):
    conversation = {'provider': 'slack', 'conversation_id': 'CSESSION'}
    calls = fake_api(common, monkeypatch, session_bindings=[
        {'Status': 'active', 'Conversation': conversation}])
    assert common.look_up_binding('session?&other=1') == conversation
    assert len(calls) == 1
    assert parse_qs(urlsplit(calls[0]).query)['session_id'] == ['session?&other=1']


def test_newest_unexpired_slack_binding_wins(common, monkeypatch):
    rows = [binding(channel='CNEW', bound_at='2026-09-15T00:00:00Z'), binding()]
    rows += [binding(channel='CEXPIRED', expires_at='2000-01-01T00:00:00Z'),
             binding(channel='CDISCORD', provider='discord'),
             binding(channel='COTHER', agent='other/seat'),
             binding(channel='CSESSION', session_id='old-session')]
    closed = binding(channel='CCLOSED', bound_at='2099-01-01T00:00:00Z')
    closed['status'] = 'closed'
    rows.append(closed)
    fake_api(common, monkeypatch, beads=rows)
    assert common.look_up_binding('new-session')['conversation_id'] == 'CNEW'


def test_unknown_session_returns_no_binding(common, monkeypatch):
    calls = fake_api(common, monkeypatch, sessions=[])
    assert common.look_up_binding('unknown') is None
    assert len(calls) == 2


def test_agent_binding_pagination(common, monkeypatch):
    calls = fake_api(common, monkeypatch)
    original = common.gc_get

    def get(path):
        if path.startswith('/beads?'):
            cursor = parse_qs(urlsplit(path).query).get('cursor', [''])[0]
            calls.append(path)
            return {'items': [binding(channel='COLD' if not cursor else 'CNEW',
                                     bound_at='2026-09-13T00:00:00Z' if not cursor
                                     else '2026-09-15T00:00:00Z')], 'total': 2,
                    'next_cursor': 'page-2' if not cursor else ''}
        return original(path)

    monkeypatch.setattr(common, 'gc_get', get)
    assert common.look_up_binding('new-session')['conversation_id'] == 'CNEW'
    assert len([p for p in calls if p.startswith('/beads?')]) == 2


def test_lookup_failure_is_not_reported_as_missing_binding(common, monkeypatch):
    def get(path):
        raise common.GCAPIError('binding store unavailable')
    monkeypatch.setattr(common, 'gc_get', get)
    with pytest.raises(common.GCAPIError, match='store unavailable'):
        common.look_up_binding('new-session')


@pytest.mark.parametrize('verb', ['publish', 'upload', 'reply_current'])
def test_commands_use_agent_binding(common, monkeypatch, tmp_path, verb):
    import importlib
    name = 'slack_chat_' + verb
    sys.modules.pop(name, None)
    command = importlib.import_module(name)
    # Import the command against this fixture's common module.
    assert command.common is common
    fake_api(common, monkeypatch, beads=[binding()])
    monkeypatch.setattr(common, 'find_latest_inbound_for_session', lambda _: None)
    monkeypatch.setattr(common, 'find_latest_inbound_thread_for_session', lambda _: None)
    sent = {}

    def publish(**kwargs):
        sent.update(kwargs)
        return {'Receipt': {'Delivered': True}}

    helper = 'upload_via_gc_outbound_file' if verb == 'upload' else 'publish_via_gc_outbound'
    monkeypatch.setattr(common, helper, publish)
    if verb == 'upload':
        file = tmp_path / 'report.txt'
        file.write_text('report')
        args = ['--file', str(file)]
    else:
        args = ['--body', 'hello']
    assert command.main(['--session', 'new-session', *args]) == 0
    assert sent['conversation_id'] == 'CFOREMAN'
    assert sent['session_id'] == 'new-session'


@pytest.mark.parametrize('result', [
    {'items': [binding()], 'partial': True},
    {'items': [], 'next_cursor': 'stuck'},
])
def test_incomplete_binding_list_fails_closed(common, monkeypatch, result):
    fake_api(common, monkeypatch)
    get = common.gc_get
    monkeypatch.setattr(common, 'gc_get', lambda path: result if path.startswith('/beads?') else get(path))
    with pytest.raises(common.GCAPIError):
        common.look_up_binding('new-session')

import json
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from full_e2e_browser_cases import permission_provider, require_pending_gate, require_native_denial, await_gate
from live_assertions import AcceptanceFailure


class BrowserCaseGuards(unittest.TestCase):
    def test_failed_startup_ends_gate_wait_and_preserves_actual_pending_evidence(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            runner = SimpleNamespace(timeout=240, private=root,
                manifest={'bbUrl': 'http://bb', 'gcUrl': 'http://gc'}, progress=lambda _: None)
            failure = {'type': 'provider/error', 'data': {'message': 'Startup needs a response. No prompt was sent.'}}
            native = {'supported': True, 'pending': {'request_id': 'startup-ls', 'kind': 'approval'}}
            def read(url):
                if url.endswith('/interactions'): return []
                if url.endswith('/threads/thread'): return {'status': 'error'}
                if '/events?' in url: return [failure]
                if url.endswith('/pending'): return native
                raise AssertionError(url)
            value = {'target': {'city': 'city'}, 'sessionId': 'session'}
            with patch('full_e2e_browser_cases.read_json', side_effect=read), \
                    patch('full_e2e_browser_cases.receipt', return_value=value), \
                    patch('full_e2e_browser_cases.gc_frame', return_value={'history': {}}), \
                    patch('full_e2e_browser_cases.time.sleep', side_effect=AssertionError('must not wait after failure')):
                with self.assertRaisesRegex(AcceptanceFailure, 'failed before.*permission interaction'):
                    await_gate(runner, 'thread', root / 'proof', 'case')
            evidence = json.loads((root / 'case-pending-failed.json').read_text())
            self.assertEqual(evidence['events'], [failure])
            self.assertEqual(evidence['native_pending'], native)
            self.assertFalse((root / 'proof').exists())

    def denial(self):
        prompt = 'Remember secret. Run write proof once.'
        turn = {'baselineMessageIds': ['startup'], 'messageDigest': hashlib.sha256(prompt.encode()).hexdigest()}
        tool = {'arguments': {'command': 'write proof'}, 'result': {'error': {'category': 'user_rejection'}}}
        frame = {'schema_version': 'session.structured.v1', 'history': {'tail_state': {'activity': 'idle'}},
                 'structured_messages': [
                     {'id': 'input', 'role': 'user', 'status': 'final', 'user_prompt': {'text': prompt}, 'blocks': []},
                     {'id': 'tool', 'role': 'assistant', 'status': 'final', 'blocks': [
                         {'type': 'tool_use', 'id': 'native-tool', 'input': {'command': 'write proof'}}]},
                     {'id': 'rejected', 'role': 'user', 'status': 'final', 'blocks': [
                         {'type': 'tool_result', 'tool_call_id': 'native-tool', 'is_error': True,
                          'structured': {'error': {'category': 'user_rejection'}}}]}]}
        return frame, turn, prompt, 'write proof', tool

    def test_denial_needs_matching_native_rejected_tool_and_full_prompt_but_no_assistant_answer(self):
        self.assertEqual(require_native_denial(*self.denial())['gc_tool_call_id'], 'native-tool')
        for corrupt in ('unrelated_tool', 'different_command', 'command_failure', 'retry', 'degraded', 'truncated_prompt'):
            args = copy.deepcopy(self.denial()); frame, turn, _, _, tool = args
            blocks = frame['structured_messages']
            if corrupt == 'unrelated_tool': blocks[2]['blocks'][0]['tool_call_id'] = 'other'
            elif corrupt == 'different_command': tool['arguments']['command'] = 'different proof'
            elif corrupt == 'command_failure': blocks[2]['blocks'][0]['structured']['error']['category'] = 'command_failure'
            elif corrupt == 'retry': blocks.append(copy.deepcopy(blocks[1]))
            elif corrupt == 'degraded': frame['history']['tail_state']['degraded'] = True
            elif corrupt == 'truncated_prompt': turn['messageDigest'] = 'other'
            with self.subTest(corrupt=corrupt), self.assertRaises(AcceptanceFailure): require_native_denial(*args)

    def test_claude_permission_fixture_explicitly_requests_manual_approval(self):
        value = tomllib.loads(permission_provider('claude', 'case-runtime', '/test/claude'))['providers']['case-runtime']
        self.assertEqual(value['base'], 'builtin:claude')
        self.assertEqual(value['session_id_flag'], '--session-id')
        self.assertEqual(value['permission_modes']['auto-edit'], '--permission-mode manual')
        self.assertEqual(value['options_schema'][0]['choices'][0]['flag_args'], ['--permission-mode', 'manual'])
        self.assertEqual(value['option_defaults']['permission_mode'], 'auto-edit')

    def test_codex_permission_fixture_never_uses_unrestricted_mode(self):
        value = tomllib.loads(permission_provider('codex', 'case-runtime', '/test/codex'))['providers']['case-runtime']
        self.assertEqual(value['base'], 'builtin:codex')
        self.assertNotIn('session_id_flag', value)
        self.assertEqual(value['option_defaults']['permission_mode'], 'suggest')
        self.assertEqual(value['permission_modes']['suggest'], '--ask-for-approval on-request --sandbox read-only')
        self.assertEqual(value['options_schema_merge'], 'by_key')
        self.assertEqual(value['options_schema'][0]['choices'][0]['flag_args'],
                         ['--ask-for-approval', 'on-request', '--sandbox', 'read-only'])
        self.assertNotIn('unrestricted', json.dumps(value))

    def test_executed_artifact_or_unrelated_question_is_not_an_approval_gate(self):
        pending = [{'id': 'bb-question', 'payload': {'kind': 'user_question', 'questions': [{'id': 'gc-request', 'options': [{'value': 'approve'}, {'value': 'deny'}]}]}}]
        frame = {'supported': True, 'pending': {'kind': 'approval', 'request_id': 'gc-request', 'metadata': {'source': 'tmux'}}}
        with tempfile.TemporaryDirectory() as scratch:
            proof = Path(scratch) / 'proof'
            self.assertEqual(require_pending_gate(pending, frame, proof)['id'], 'bb-question')
            unrelated = {'supported': True, 'pending': {'kind': 'approval', 'request_id': 'other-request', 'metadata': {'source': 'tmux'}}}
            with self.assertRaises(AcceptanceFailure): require_pending_gate(pending, unrelated, proof)
            proof.write_text('already ran')
            with self.assertRaises(AcceptanceFailure): require_pending_gate(pending, frame, proof)


if __name__ == '__main__': unittest.main()

"""Busy follow-ups and interruption through the released BB composer."""
import hashlib
import json
from pathlib import Path
import secrets
import shlex

from full_e2e_browser_cases import fixture, await_gate, receipt, gc_frame, read_json, save_json
from full_e2e_fault_cases import FaultCases
from live_assertions import AcceptanceFailure, verify_prompt_frame, verify_resume_identity


def events(runner, thread, after=0):
    rows, cursor = [], after
    page_size = 100
    while True:
        page = read_json(runner.manifest['bbUrl'] + f'/api/v1/threads/{thread}/events?afterSeq={cursor}&limit={page_size}&order=asc')
        fresh = [row for row in page if row['seq'] > cursor]
        rows.extend(fresh)
        if len(page) < page_size: return rows
        if not fresh: raise AcceptanceFailure('BB event pagination did not advance')
        cursor = max(row['seq'] for row in fresh)


def require_interrupted(rows):
    completed = [row for row in rows if row['type'] == 'turn/completed']
    if not completed: return None
    if len(completed) != 1 or completed[0]['data'].get('status') != 'interrupted':
        raise AcceptanceFailure('Stop must interrupt exactly one turn, without a successful completion')
    requests = [row for row in rows if row['type'] == 'client/turn/requested']
    accepted = [row for row in rows if row['type'] == 'turn/input/accepted']
    if (len(requests) != 1 or len(accepted) != 1 or
            accepted[0]['data']['clientRequestId'] != requests[0]['data']['requestId']):
        raise AcceptanceFailure('Interrupted turn did not correlate to exactly one submitted input')
    return completed[0]


class InteractionCases:
    def __init__(self, runner):
        self.runner, self.waiter = runner, FaultCases(runner)

    def busy(self, label):
        r = self.runner
        agent, workspace = r.agent('global'), r.manifest['workspaces']['global']
        nonce = secrets.token_hex(8)
        proof = Path(workspace) / ('busy-' + nonce + '.txt')
        marker = 'BUSY_FINISHED_' + nonce
        command = 'python3 -c ' + shlex.quote(
            f'from pathlib import Path; import time; p=Path({str(proof)!r}); '
            "f=p.open('x'); f.write('started\\n'); f.close(); time.sleep(90)")
        prompt = ('Remember the private word ' + nonce + '. Run exactly this shell command once and wait for it. '
                  'Do not run any other tools.\n' + command + '\nThen reply exactly ' + marker + '.')
        start = r.browser(label + '-start', agent, 'proj_personal', workspace, prompt, until='submitted')
        thread = start['threadId']
        def running():
            try: value = receipt(r, thread)
            except FileNotFoundError: return None
            if not value.get('sessionId') or not value.get('turn'): return None
            frame = gc_frame(r, value)
            tail = frame.get('history', {}).get('tail_state', {})
            if (proof.is_file() and proof.read_bytes() == b'started\n' and tail.get('activity') == 'in_turn'
                    and tail.get('open_tool_call_ids') and not tail.get('degraded')):
                return value, frame
        value, frame = self.waiter.poll(label + ' busy tool', running)
        save_json(r.private / (label + '-busy.json'), {'receipt': value, 'frame': frame})
        return {'agent': agent, 'project': 'proj_personal', 'workspace': workspace, 'reasoning': 'medium',
                'thread': thread, 'start': start, 'prompt': prompt, 'marker': marker,
                'receipt': value, 'frame': frame, 'memory': nonce}

    def interrupt(self, *, at_approval=False):
        r = self.runner
        label = 'approvals.interrupt' if at_approval else 'lifecycle.interrupt'
        proof = None
        if at_approval:
            f, nonce = fixture(r), secrets.token_hex(8)
            proof = Path(f['workspace']) / ('interrupted-approval-' + nonce)
            command = 'python3 -c ' + shlex.quote(f'from pathlib import Path; Path({str(proof)!r}).open("x").write("fixture")')
            prompt = (f'Remember the private test word {nonce} for our next turn. '
                      f'Run only this exact shell command once. Do not use alternatives.\n{command}')
            start = r.browser(label + '-start', f['agent'], f['project'], f['workspace'], prompt, reasoning='none', until='submitted')
            await_gate(r, start['threadId'], proof, label)
            value = receipt(r, start['threadId'])
            c = {**f, 'thread': start['threadId'], 'start': start, 'prompt': prompt, 'receipt': value,
                 'frame': gc_frame(r, value), 'memory': nonce}
        else:
            c = self.busy(label)
        r.browser(label + '-stop', c['agent'], c['project'], c['workspace'], thread=c['thread'],
                  action='interrupt', until='submitted', reasoning=c['reasoning'])
        terminal = self.waiter.poll(label + ' interrupted BB turn', lambda: require_interrupted(events(r, c['thread'], c['start']['afterSeq'])))
        def settled():
            frame = gc_frame(r, c['receipt'])
            tail = frame.get('history', {}).get('tail_state', {})
            if (tail.get('activity') == 'idle' and not tail.get('degraded')
                    and not tail.get('pending_interaction_ids') and not tail.get('open_tool_call_ids')):
                return frame
        frame = self.waiter.poll(label + ' reliable native idle', settled)
        verify_prompt_frame(frame, c['receipt']['turn'], c['prompt'])
        verify_resume_identity(c['frame'], frame)
        if proof and proof.exists(): raise AcceptanceFailure('Interrupted approval executed its tool')
        if read_json(r.manifest['bbUrl'] + f'/api/v1/threads/{c["thread"]}/interactions'):
            raise AcceptanceFailure('Interrupted approval remains actionable in BB')
        save_json(r.private / (label + '-interrupted.json'), {'terminal': terminal, 'frame': frame})
        marker = 'AFTER_STOP_' + secrets.token_hex(6)
        prompt = (f'This is a new request: do not run or retry any tools. '
                  f'Reply exactly {marker}, one space, then the private test word I asked you to remember in my first request.')
        result = r.browser(label + '-resume', c['agent'], c['project'], c['workspace'], prompt,
                           thread=c['thread'], expected=marker + ' ' + c['memory'], reasoning=c['reasoning'])
        harness = r.new_harness(label, c['agent'], c['project'], c['workspace'], c['thread'])
        r.verify_turn(harness, result, prompt, marker + ' ' + c['memory'], no_tools=True)
        verify_resume_identity(frame, harness.last_gc_frame)
        if proof and proof.exists(): raise AcceptanceFailure('Denied tool ran later after interruption')
        return {'thread_id': c['thread'], 'interrupted_turn': terminal['scope']['turnId'],
                'same_conversation_resumed': True, 'approval_tool_absent': at_approval}

    def followup(self):
        r, label = self.runner, 'lifecycle.busy_followup'
        c = self.busy(label)
        marker = 'QUEUED_' + secrets.token_hex(6)
        prompt = f'Without tools, reply exactly {marker}, one space, then the private word from the previous request.'
        queued = r.browser(label + '-queue', c['agent'], c['project'], c['workspace'], prompt,
                           thread=c['thread'], action='queue', until='submitted')
        def first_done():
            rows = events(r, c['thread'], c['start']['afterSeq'])
            terminals = [row for row in rows if row['type'] == 'turn/completed']
            if not terminals: return None
            if terminals[0]['data'].get('status') != 'completed': raise AcceptanceFailure('Busy turn was interrupted by queueing')
            return terminals[0]
        first = self.waiter.poll(label + ' original completion', first_done)
        result = r.browser(label + '-completed', c['agent'], c['project'], c['workspace'], thread=c['thread'],
                           action='wait', after=first['seq'], expected=marker + ' ' + c['memory'])
        harness = r.new_harness(label, c['agent'], c['project'], c['workspace'], c['thread'])
        r.verify_turn(harness, result, prompt, marker + ' ' + c['memory'], no_tools=True)
        verify_prompt_frame(harness.last_gc_frame, c['receipt']['turn'], c['prompt'])
        verify_resume_identity(c['frame'], harness.last_gc_frame)
        rows = events(r, c['thread'], c['start']['afterSeq'])
        terminals = [row for row in rows if row['type'] == 'turn/completed']
        if len(terminals) != 2 or any(row['data'].get('status') != 'completed' for row in terminals):
            raise AcceptanceFailure('Queued follow-up did not produce exactly two successful turns')
        answers = [row for row in result['visibleRows'] if '|turn:' + first['scope']['turnId'] + '|' in row['id']]
        if not any(row['text'].strip().splitlines()[-1:] == [c['marker']] for row in answers):
            raise AcceptanceFailure('The original busy turn has no rendered final answer')
        save_json(r.private / (label + '-events.json'), rows)
        return {'thread_id': c['thread'], 'queue': queued.get('queuedMessage'), 'completed_turns': 2,
                'first_completed_before_followup': True, 'same_native_conversation': True}


def case_functions(runner):
    cases = InteractionCases(runner)
    return {'lifecycle.busy_followup': cases.followup,
            'lifecycle.interrupt': cases.interrupt,
            'approvals.interrupt': lambda: cases.interrupt(at_approval=True)}

import test from 'node:test';
import assert from 'node:assert/strict';
import { assessCompletion, assessDenial, revealDeniedTurn, assessRejection, assessLauncherRejection, submitQueuedPrompt, assertPersistedQueuedPrompt, eventsAfter } from './browser_driver.mjs';

test('event pagination obeys the BB 100-row limit and retains every event across sparse cursors', async () => {
  const expected = Array.from({ length: 237 }, (_, index) => ({ seq: 15 + index * 2, data: { value: index } }));
  const cursors = [];
  const page = { request: { async get(address) {
    const url = new URL(address);
    assert.equal(url.pathname, '/api/v1/threads/thread%2Fone/events');
    assert.equal(url.searchParams.get('order'), 'asc');
    const limit = Number(url.searchParams.get('limit'));
    const after = Number(url.searchParams.get('afterSeq'));
    cursors.push(after);
    return { ok: () => limit <= 100, status: () => limit <= 100 ? 200 : 400,
      json: async () => expected.filter(row => row.seq > after).slice(0, limit) };
  } } };
  assert.deepEqual(await eventsAfter(page, 'http://127.0.0.1:54321', 'thread/one', 13), expected);
  assert.deepEqual(cursors, [13, 213, 413]);
});

test('an exact full event page requires another fetch and stalled pagination fails closed', async () => {
  const expected = Array.from({ length: 100 }, (_, index) => ({ seq: index + 1 }));
  let calls = 0;
  const page = { request: { async get() {
    calls++;
    return { ok: () => true, status: () => 200, json: async () => calls === 1 ? expected : [] };
  } } };
  assert.deepEqual(await eventsAfter(page, 'http://127.0.0.1:54321', 'thread'), expected);
  assert.equal(calls, 2);
  page.request.get = async () => ({ ok: () => true, status: () => 200, json: async () => expected });
  await assert.rejects(eventsAfter(page, 'http://127.0.0.1:54321', 'thread', 100), /did not advance/);
});

const events = () => [
  { seq: 11, type: 'client/turn/requested', data: { requestId: 'request-1', execution: { model: 'agent-1', reasoningLevel: 'medium' } } },
  { seq: 12, type: 'turn/started', scope: { kind: 'turn', turnId: 'turn-1' }, data: {} },
  { seq: 13, type: 'turn/input/accepted', scope: { kind: 'turn', turnId: 'turn-1' }, data: { clientRequestId: 'request-1' } },
  { seq: 14, type: 'turn/completed', scope: { kind: 'turn', turnId: 'turn-1' }, data: { status: 'completed', providerThreadId: 'gc-session-1' } },
  { seq: 13, type: 'item/completed', scope: { kind: 'turn', turnId: 'turn-1' }, data: { item: { id: 'answer-1', type: 'agentMessage', text: 'Finished.\nDONE 123' } } },
];
const valid = () => ({ events: events(), afterSeq: 10, model: 'agent-1', reasoning: 'medium', expectedResponse: 'DONE 123', visibleRows: [{ id: 'thread:assistant:kind:assistant|turn:turn-1|item:answer-1', text: 'Finished.\nDONE 123' }] });

test('a rendered answer needs a successful correlated fresh provider turn', () => {
  assert.equal(assessCompletion(valid()).providerThreadId, 'gc-session-1');
  assert.equal(assessCompletion({ ...valid(), events: [] }), null);
  assert.equal(assessCompletion({ ...valid(), afterSeq: 14 }), null);
});

test('user echoes and old assistant answers cannot satisfy completion', () => {
  assert.equal(assessCompletion({ ...valid(), visibleRows: [{ id: 'thread:user-seed:1', text: 'DONE 123' }] }), null);
  assert.equal(assessCompletion({ ...valid(), visibleRows: [{ id: 'thread:assistant:kind:assistant|turn:old-turn|item:old', text: 'DONE 123' }] }), null);
});

test('errors, unsupported reasoning and duplicate or mismatched completions fail', () => {
  let input = valid(); input.events.push({seq:15,type:'system/error',data:{message:'provider unavailable'}});
  assert.throws(() => assessCompletion(input), /system\/error/);
  input = valid(); input.events[3].data.status = 'failed';
  assert.throws(() => assessCompletion(input), /failed/);
  input = valid(); input.events.push({...input.events[3],seq:15});
  assert.throws(() => assessCompletion(input), /exactly one/);
  input = valid(); input.events[2].data.clientRequestId = 'another-request';
  assert.throws(() => assessCompletion(input), /correlate/);
  assert.throws(() => assessCompletion({ ...valid(), reasoning: 'high' }), /reasoning/);
});

test('an echoed marker elsewhere in the answer does not satisfy the final line', () => {
  assert.throws(() => assessCompletion({ ...valid(), visibleRows: [{ id: valid().visibleRows[0].id, text: 'DONE 123\nProvider failed.' }] }), /final line/);
});

test('Markdown soft line breaks may collapse while the exact raw final line remains visible in the same item', () => {
  const input = valid();
  input.visibleRows[0].text = 'Finished. DONE 123';
  assert.equal(assessCompletion(input).renderedRowId, input.visibleRows[0].id);
  input.visibleRows[0].text = 'Finished.\nDONE\t123';
  assert.ok(assessCompletion(input));
});

test('rendered marker text cannot conceal a wrong or absent raw final line', () => {
  for (const text of ['DONE 123\nDifferent final line', 'Prefix DONE 123', '', undefined]) {
    const input = valid();
    input.events.at(-1).data.item.text = text;
    assert.throws(() => assessCompletion(input), /raw final line/i);
  }
  const input = valid(); input.visibleRows[0].text = 'Finished. XDONE 123';
  assert.throws(() => assessCompletion(input), /final line/);
});

test('completion waits for the final item to render instead of accepting a workspace notice', () => {
  assert.equal(assessCompletion({ ...valid(), visibleRows: [{ id: 'thread:assistant:kind:assistant|turn:turn-1|item:warning-1', text: 'Gas City works elsewhere.' }] }), null);
});

const denied = () => {
  const input = valid();
  input.events = input.events.filter(row => row.type !== 'item/completed');
  for (const row of input.events.filter(row => ['turn/started', 'turn/input/accepted'].includes(row.type)))
    row.data.providerThreadId = 'gc-session-1';
  input.events.push(
    { seq: 13, type: 'system/interaction/lifecycle', scope: { kind: 'turn', turnId: 'turn-1' }, data: {
      interaction: { id: 'question-1', status: 'resolved', payload: { kind: 'user_question', questions: [{ id: 'native-question' }] },
        resolution: { kind: 'user_answer', answers: { 'native-question': { selected: ['deny'] } } } } } },
    { seq: 13, type: 'item/completed', scope: { kind: 'turn', turnId: 'turn-1' }, data: {
      providerThreadId: 'gc-session-1', item: { type: 'toolCall', id: 'tool-1', tool: 'Bash', status: 'failed',
        arguments: { command: 'write proof' }, result: { error: { category: 'user_rejection' } } } } });
  input.visibleRows = [
    { id: 'thread:question:question-1', visible: true, aria: '- button "Answered Bash: write proof — Deny"' },
    { id: 'thread:tool:tool-1', visible: true, aria: '- button "Bash error"' },
  ];
  return input;
};

test('a native permission denial completes through the visible denied tool without an assistant marker', () => {
  assert.equal(assessDenial(denied()).toolItem.id, 'tool-1');
  assert.equal(assessDenial(denied()).interactionId, 'question-1');
  assert.throws(() => assessCompletion(denied()), /no final assistant/);
  assert.equal(assessDenial({ ...denied(), visibleRows: [] }), null);
  const input = denied(); input.visibleRows[0].aria = '- button "Answered Bash — Approve once"';
  assert.equal(assessDenial(input), null);
});

test('denied tool labels allow the rendered elapsed duration while requiring the same tool and error', () => {
  for (const label of ['Bash error', 'Bash 8s error', 'Bash 1m 8s error']) {
    const input = denied(); input.visibleRows[1].aria = `- button "${label}"`;
    assert.ok(assessDenial(input));
  }
  for (const label of ['Write 8s error', 'Bash 8s completed', 'Bash unknown error']) {
    const input = denied(); input.visibleRows[1].aria = `- button "${label}"`;
    assert.equal(assessDenial(input), null);
  }
});

test('denial reveals only its correlated completed turn and never collapses an open disclosure', async () => {
  const input = denied();
  const terminal = input.events.find(event => event.type === 'turn/completed');
  let expanded = false, clicks = 0;
  const page = { locator(selector) {
    assert.equal(selector, `[data-timeline-row-id="thread-1:${terminal.scope.turnId}:turn"]`);
    return { getByRole(role, options) {
      assert.equal(role, 'button');
      assert.ok(options.name.test('Worked for 12s'));
      return { count: async () => 1, getAttribute: async name => {
        assert.equal(name, 'aria-expanded'); return String(expanded);
      }, click: async () => { expanded = true; clicks++; } };
    } };
  } };
  await revealDeniedTurn(page, 'thread-1', input);
  await revealDeniedTurn(page, 'thread-1', input);
  assert.equal(clicks, 1);
  await revealDeniedTurn({ locator() { assert.fail('unfinished turn must not be expanded'); } }, 'thread-1',
    { ...input, events: input.events.filter(event => event.type !== 'turn/completed') });
  await assert.rejects(revealDeniedTurn(page, 'thread-1', {
    ...input, events: input.events.map(event => event === terminal ? { ...event, data: { ...event.data, status: 'failed' } } : event),
  }), /failed/);
});

test('denial cannot hide failed turns, mismatched questions, unrelated tool errors or a retried tool', () => {
  let input = denied(); input.events[2].data.clientRequestId = 'wrong-request';
  assert.throws(() => assessDenial(input), /correlate/);
  input = denied(); input.events[3].data.status = 'failed';
  assert.throws(() => assessDenial(input), /failed/);
  input = denied(); input.events[4].data.interaction.resolution.answers = { 'wrong-question': { selected: ['deny'] } };
  assert.throws(() => assessDenial(input), /matching.*denial/);
  input = denied(); input.events[5].data.item.result.error.category = 'command_failure';
  assert.throws(() => assessDenial(input), /user rejection/);
  input = denied(); input.events.push({ ...input.events[5], seq: 15 });
  assert.throws(() => assessDenial(input), /exactly one.*tool/);
  input = denied(); input.events[5].data.providerThreadId = 'other-gc-session';
  assert.throws(() => assessDenial(input), /conversation/);
  input = denied(); input.visibleRows[1].visible = false;
  assert.equal(assessDenial(input), null);
});

test('negative cases need a fresh matching error both in BB events and visibly rendered', () => {
  const input = { events: [{ seq: 20, type: 'system/error', data: { message: 'reasoning is fixed at Medium' } }], afterSeq: 19, visibleText: 'reasoning is fixed at Medium', expectedError: 'reasoning is fixed' };
  assert.equal(assessRejection(input).seq, 20);
  assert.equal(assessRejection({ ...input, afterSeq: 20 }), null);
  assert.equal(assessRejection({ ...input, visibleText: '' }), null);
  assert.throws(() => assessRejection({ ...input, events: [...input.events, { seq: 21, type: 'turn/completed', data: { status: 'completed' } }] }), /unexpectedly completed/);
});

test('negative errors match decoded message fields with quotes and newlines, never unrelated metadata', () => {
  const expectedError = 'Provider "gas-city" exited unexpectedly\nwith signal SIGKILL';
  for (const data of [{ message: expectedError }, { detail: expectedError }, { error: { message: expectedError } }]) {
    const input = { events: [{ seq: 20, type: 'system/error', data }], afterSeq: 19, visibleText: expectedError, expectedError };
    assert.equal(assessRejection(input).seq, 20);
    assert.equal(assessRejection({ ...input, visibleText: '' }), null);
    assert.equal(assessRejection({ ...input, afterSeq: 20 }), null);
  }
  for (const data of [{ providerId: expectedError }, { error: { unrelated: expectedError } }, { metadata: { message: expectedError } }]) {
    assert.equal(assessRejection({ events: [{ seq: 20, type: 'system/error', data }], afterSeq: 19, visibleText: expectedError, expectedError }), null);
  }
});

test('launcher rejection needs one real error response, visible error and no new thread', () => {
  const input = { requests: [{ method: 'POST', url: 'http://127.0.0.1:54321/api/v1/plugins/gas-city/rpc/launch',
    response: { ok: true, result: { error: 'Workspace unavailable', uncertain: false } } }],
    currentUrl: 'http://127.0.0.1:54321/plugins/gas-city/launch', visibleText: 'Workspace unavailable', expectedError: 'Workspace unavailable' };
  assert.ok(assessLauncherRejection(input));
  assert.equal(assessLauncherRejection({ ...input, requests: [] }), null);
  assert.equal(assessLauncherRejection({ ...input, visibleText: '' }), null);
  assert.throws(() => assessLauncherRejection({ ...input, currentUrl: 'http://127.0.0.1:54321/threads/new' }), /unexpectedly/);
  assert.throws(() => assessLauncherRejection({ ...input, requests: [...input.requests, ...input.requests] }), /exactly one/);
  for (const result of [{ threadId: 'new' }, { error: 'Workspace unavailable', uncertain: true }, { error: 'Another failure', uncertain: false }])
    assert.throws(() => assessLauncherRejection({ ...input, requests: [{ ...input.requests[0], response: { ok: true, result } }] }));
});

// Portable guards for the driver's action/response boundary. Live E2E still
// verifies the released frontend, persisted queue and native prompt count.
function queuePage(label, expectedAction, platform = 'MacIntel') {
  const actions = [];
  let accept;
  const response = (path, method = 'POST') => ({
    url: () => `http://127.0.0.1:59340${path}`, request: () => ({ method: () => method }),
    ok: () => true, status: () => 200, json: async () => ({ id: 'queue-1' }),
  });
  const perform = async action => {
    actions.push(action);
    assert.equal(action, expectedAction, 'Driver steered or resubmitted instead of queueing');
    accept(response('/api/v1/threads/thread-1/queued-messages'));
  };
  const page = {
    evaluate: async () => platform,
    getByRole: (role, { name } = {}) => {
      if (role === 'textbox') return { filter: () => ({ press: key => perform(key) }) };
      assert.equal(role, 'button');
      const present = typeof name === 'string' ? name === label : name.test(label);
      return {
        waitFor: async () => { assert.ok(present, 'Requested queue control is not rendered'); },
        getAttribute: async key => { assert.equal(key, 'aria-label'); return label; },
        click: async () => { assert.ok(present, 'Requested queue control is not rendered'); await perform('click'); },
      };
    },
    waitForResponse: predicate => {
      assert.equal(predicate(response('/api/v1/threads/another-thread/queued-messages')), false);
      assert.equal(predicate(response('/api/v1/threads/thread-1/queued-messages', 'GET')), false);
      assert.equal(predicate(response('/api/v1/threads/thread-1/messages')), false);
      return new Promise(resolve => { accept = value => { assert.ok(predicate(value)); resolve(value); }; });
    },
  };
  return { page, actions };
}

for (const [label, action, platform] of [
  ['Queue follow-up (Enter)', 'click'],
  ['Steer current run (Enter)', 'Meta+Enter'],
  ['Steer when ready (Enter)', 'Meta+Enter'],
  ['Steer current run (Enter)', 'Control+Enter', 'Linux x86_64'],
  ['Steer when ready (Enter)', 'Control+Enter', 'Win32'],
  ['Steer current run (Enter), Ctrl + Enter to queue', 'Control+Enter', 'Linux x86_64'],
  ['Steer when ready (Enter), Meta + Enter to queue', 'Meta+Enter'],
  ['Steer current run (Enter), ⌘ + Enter to queue', 'Meta+Enter'],
]) test(`queue uses the rendered ${label} mode exactly once`, async () => {
  const { page, actions } = queuePage(label, action, platform);
  assert.equal((await submitQueuedPrompt(page, 'thread-1')).id, 'queue-1');
  assert.deepEqual(actions, [action]);
});

test('queue fails closed for unknown labels, shortcuts, or unhinted platforms', async () => {
  for (const [label, platform] of [
    ['Send now (Enter)', 'Linux x86_64'],
    ['Steer current run (Enter), Alt + Enter to queue', 'Linux x86_64'],
    ['Steer when ready (Enter)', 'unknown-platform'],
  ]) {
    const { page, actions } = queuePage(label, 'must-not-act', platform);
    await assert.rejects(submitQueuedPrompt(page, 'thread-1'));
    assert.deepEqual(actions, []);
  }
});

test('a response timeout is caught even while the queue interaction is still pending', async () => {
  const { page } = queuePage('Queue follow-up (Enter)', 'click');
  page.waitForResponse = () => new Promise((_, reject) => setTimeout(() => reject(new Error('queue response timeout')), 1));
  const original = page.getByRole;
  page.getByRole = (...args) => ({ ...original(...args),
    click: () => new Promise((_, reject) => setTimeout(() => reject(new Error('late click failure')), 30)),
  });
  await assert.rejects(submitQueuedPrompt(page, 'thread-1'), /queue response timeout/);
  // Both promises must have handlers, including the later losing rejection.
  await new Promise(resolve => setTimeout(resolve, 50));
});

// Sanitized BB 0.42.1 GET /queued-messages capture from the live busy-followup
// trace: the persisted response uses content, although the request uses input.
const capturedQueue = () => [{ id: 'qmsg-1', threadId: 'thread-1',
  content: [{ type: 'text', text: 'Recall the private word.', mentions: [] }],
  model: 'gc-model', reasoningLevel: 'medium', permissionMode: 'full', serviceTier: 'default',
  groupWithNext: false, sendAt: null, waitingOn: { kind: 'thread-busy' }, failureReason: null,
  payload: { kind: 'inline' }, editable: true, createdAt: 1788822057050, updatedAt: 1788822057050 }];

test('the captured persisted queue needs exactly one full prompt with the accepted identity', () => {
  const accepted = capturedQueue()[0], prompt = accepted.content[0].text;
  assert.equal(assertPersistedQueuedPrompt(capturedQueue(), accepted, prompt).id, accepted.id);
  for (const rows of [[], [...capturedQueue(), ...capturedQueue()],
    [{ ...accepted, id: 'different' }], [{ ...accepted, threadId: 'another-thread' }],
    [{ ...accepted, content: [{ type: 'text', text: prompt.slice(0, -1) }] }],
    [{ ...accepted, content: [...accepted.content, { type: 'image', url: 'extra' }] }],
    [{ ...accepted, content: undefined, input: accepted.content }],
  ]) assert.throws(() => assertPersistedQueuedPrompt(rows, accepted, prompt));
});

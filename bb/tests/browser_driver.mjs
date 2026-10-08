// Real BB frontend driver. Every mutation below is a rendered UI interaction.
// GET requests provide independent identities/correlation, never synthetic replies.
// Evidence contains private prompts/model output: retain it locally, do not upload it.
import { parseArgs } from 'node:util';
import { mkdir, mkdtemp, writeFile, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const exactIgnoringCase = value => new RegExp(`^${value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`, 'i');
const threadPath = (project, threadId) => project === 'proj_personal' ? `/threads/${threadId}` : `/projects/${project}/threads/${threadId}`;
const bounded = async (promise, milliseconds, label) => {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} exceeded ${milliseconds}ms`)), milliseconds);
    })]);
  } finally { clearTimeout(timer); }
};

function correlatedCompletion({ events, afterSeq, model, reasoning }) {
  const fresh = events.filter(event => event.seq > afterSeq);
  const failure = fresh.find(event => ['system/error', 'client/turn/rejected', 'provider/modelFallback'].includes(event.type));
  if (failure) throw new Error(`BB reported ${failure.type}; see private events`);
  const completed = fresh.filter(event => event.type === 'turn/completed');
  if (!completed.length) return null;
  assert.equal(completed.length, 1, 'Expected exactly one fresh completed turn');
  const terminal = completed[0];
  assert.equal(terminal.data?.status, 'completed', `BB turn ended ${terminal.data?.status}`);
  assert.ok(!terminal.data.error, 'BB completion includes a provider error');
  const turnId = terminal.scope?.turnId;
  assert.ok(turnId && terminal.scope.kind === 'turn', 'Missing BB turn identity');
  assert.ok(terminal.data.providerThreadId, 'Missing GC provider conversation identity');
  const scoped = fresh.filter(event => event.scope?.kind === 'turn' && event.scope.turnId === turnId);
  assert.equal(scoped.filter(event => event.type === 'turn/started').length, 1, 'Expected exactly one turn start');
  const requests = fresh.filter(event => event.type === 'client/turn/requested');
  assert.equal(requests.length, 1, 'Expected exactly one submitted request');
  const accepted = scoped.filter(event => event.type === 'turn/input/accepted');
  assert.equal(accepted.length, 1, 'Expected exactly one accepted input');
  const request = requests[0].data;
  assert.ok(request.requestId && accepted[0].data.clientRequestId === request.requestId, 'Completion does not correlate to the submitted request');
  if (model) assert.equal(request.execution?.model, model, 'BB selected another model');
  if (reasoning) assert.equal(request.execution?.reasoningLevel, reasoning, 'BB selected another reasoning level');
  return { terminal, turnId, scoped, request };
}

export function assessCompletion(input) {
  const correlated = correlatedCompletion(input);
  if (!correlated) return null;
  const { terminal, turnId, scoped, request } = correlated;
  const { visibleRows, expectedResponse } = input;
  const finalItem = scoped.filter(event => event.type === 'item/completed' && event.data?.item?.type === 'agentMessage').at(-1)?.data.item;
  assert.ok(finalItem?.id, 'Completed turn has no final assistant item');
  const answers = visibleRows.filter(row => row.id.includes(':assistant:') && row.id.includes(`|turn:${turnId}|`) && row.id.endsWith(`|item:${finalItem.id}`) && row.text.trim());
  if (!answers.length) return null; // The event exists, but the user still has no answer.
  const answer = answers.at(-1).text.trim();
  if (expectedResponse) {
    assert.equal(finalItem.text?.trim().split(/\r?\n/).at(-1), expectedResponse, 'Raw final line does not match the expected response');
    // Markdown soft line breaks render as spaces. Keep the exact raw contract,
    // then require that ending in this same rendered item with only whitespace
    // normalized. A user echo, earlier item, or suffix inside another word fails.
    const rendered = answer.replace(/\s+/gu, ' ');
    const ending = expectedResponse.replace(/\s+/gu, ' ');
    assert.ok(rendered === ending || rendered.endsWith(' ' + ending), 'Rendered final line does not match the expected response');
  }
  return { turnId, requestId: request.requestId, providerThreadId: terminal.data.providerThreadId,
    completedSeq: terminal.seq, answer, renderedRowId: answers.at(-1).id };
}

// A native denial may intentionally stop without another assistant message.
// Its success condition is the resolved Deny question and rejected tool, not
// a workspace notice or an invented assistant completion marker.
export function assessDenial(input) {
  const correlated = correlatedCompletion(input);
  if (!correlated) return null;
  const { terminal, turnId, scoped, request } = correlated;
  for (const event of scoped.filter(event => ['turn/started', 'turn/input/accepted'].includes(event.type)))
    assert.equal(event.data.providerThreadId, terminal.data.providerThreadId, 'Denied turn changed provider conversation identity');
  const resolved = scoped.filter(event => event.type === 'system/interaction/lifecycle'
    && event.data?.interaction?.status === 'resolved').map(event => event.data.interaction);
  assert.equal(resolved.length, 1, 'Expected exactly one resolved permission question');
  const question = resolved[0];
  const questions = question.payload?.questions;
  assert.ok(question.id && question.payload?.kind === 'user_question' && questions?.length === 1, 'Missing permission question identity');
  const answers = question.resolution?.answers;
  assert.ok(question.resolution?.kind === 'user_answer' && Object.keys(answers ?? {}).length === 1
    && JSON.stringify(answers[questions[0].id]?.selected) === '["deny"]', 'Expected matching explicit denial answer');
  const tools = scoped.filter(event => event.type === 'item/completed'
    && ['toolCall', 'commandExecution'].includes(event.data?.item?.type));
  assert.equal(tools.length, 1, 'Denial requires exactly one completed tool without retry');
  const tool = tools[0].data.item;
  assert.equal(tools[0].data.providerThreadId, terminal.data.providerThreadId, 'Denied tool belongs to another conversation');
  assert.ok(tool.id && tool.status === 'failed'
    && ['user_rejection', 'user_rejection_with_reason'].includes(tool.result?.error?.category), 'Tool did not report a native user rejection');
  const questionRow = input.visibleRows.find(row => row.id.endsWith(`:question:${question.id}`));
  const toolRow = input.visibleRows.find(row => row.id.endsWith(`:tool:${tool.id}`));
  const escapedTool = tool.tool.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const failedToolLabel = new RegExp(`button "${escapedTool}(?: \\d+(?:\\.\\d+)?(?:ms|s|m|h)(?: \\d+(?:\\.\\d+)?(?:ms|s|m|h))*)? error"`);
  if (!questionRow?.visible || !questionRow.aria?.includes('Answered ')
    || !questionRow.aria.includes(' — Deny') || !toolRow?.visible
    || !failedToolLabel.test(toolRow.aria ?? "")) return null;
  return { turnId, requestId: request.requestId, providerThreadId: terminal.data.providerThreadId,
    completedSeq: terminal.seq, interactionId: question.id, nativeQuestionId: questions[0].id,
    toolItem: tool, renderedQuestionRowId: questionRow.id, renderedToolRowId: toolRow.id };
}

// Completed turns collapse their answered questions. Reveal only the exact
// correlated turn so denial assertions inspect the real rendered answer.
export async function revealDeniedTurn(page, threadId, input) {
  const correlated = correlatedCompletion(input);
  if (!correlated) return;
  const rowId = `${threadId}:${correlated.turnId}:turn`;
  const turn = page.locator(`[data-timeline-row-id=${JSON.stringify(rowId)}]`);
  const disclosure = turn.getByRole('button', { name: /^Worked for / });
  if (await disclosure.count() === 0) return;
  assert.equal(await disclosure.count(), 1, 'Completed denial turn has ambiguous disclosures');
  if (await disclosure.getAttribute('aria-expanded') !== 'true') await disclosure.click();
}

export function assessRejection({ events, afterSeq, visibleText, expectedError }) {
  const fresh = events.filter(event => event.seq > afterSeq);
  assert.ok(!fresh.some(event => event.type === 'turn/completed' && event.data?.status === 'completed'), 'Negative case unexpectedly completed successfully');
  const failure = fresh.find(event => ['system/error', 'client/turn/rejected', 'turn/completed'].includes(event.type)
    && [event.data?.error?.message, event.data?.message, event.data?.detail]
      .some(message => typeof message === 'string' && message.includes(expectedError)));
  return failure && visibleText.includes(expectedError) ? failure : null;
}

export function assessLauncherRejection({ requests, currentUrl, visibleText, expectedError }) {
  assert.ok(!/\/threads\/[^/]+/.test(new URL(currentUrl).pathname), 'Negative launcher unexpectedly created/navigated to a thread');
  const launches = requests.filter(row => row.method === 'POST' && new URL(row.url).pathname === '/api/v1/plugins/gas-city/rpc/launch');
  if (!launches.length) return null;
  assert.equal(launches.length, 1, 'Expected exactly one actual launcher request');
  const response = launches[0].response;
  if (!response) return null;
  assert.equal(response.ok, true, 'Launcher did not return its real RPC result');
  assert.ok(!response.result?.threadId, 'Negative launcher unexpectedly created a BB thread');
  assert.equal(response.result?.uncertain, false, 'Creation may have happened; cannot certify rejection before creation');
  assert.ok(typeof response.result?.error === 'string' && response.result.error.includes(expectedError), 'Launcher returned another error');
  return visibleText.includes(expectedError) ? launches[0] : null;
}

export async function interruptControl(page) {
  const running = page.getByRole('button', { name: 'Stop run', exact: true });
  // BB replaces the composer while a provider question is pending. Its
  // approval form's Cancel invokes the same threads.stop action. Scope it to
  // this exact approval form so unrelated Cancel buttons cannot stop a test.
  const approval = page.getByRole('region', { name: 'Question', exact: true })
    .filter({ has: page.getByRole('button', { name: 'Approve once', exact: true }) })
    .filter({ has: page.getByRole('button', { name: 'Deny', exact: true }) });
  const cancel = approval.getByRole('button', { name: 'Cancel', exact: true });
  await running.or(cancel).first().waitFor({ state: 'visible' });
  if (await running.isVisible()) return { locator: running, kind: 'Stop run' };
  assert.equal(await approval.count(), 1, 'Pending interruption requires exactly one approval form');
  return { locator: cancel, kind: 'approval Cancel' };
}

export async function submitQueuedPrompt(page, threadId) {
  const control = page.getByRole('button', { name: /^(Queue follow-up|Steer current run|Steer when ready) \(Enter\)(?:, .* to queue)?$/ });
  await control.waitFor({ state: 'visible' });
  const label = await control.getAttribute('aria-label');
  let shortcut;
  if (label !== 'Queue follow-up (Enter)') {
    const mode = /^(Steer current run|Steer when ready) \(Enter\)(?:, (Ctrl|Meta|⌘) \+ Enter to queue)?$/.exec(label ?? '');
    assert.ok(mode, `Unsupported queue control: ${label}`);
    if (mode[2]) shortcut = mode[2] === 'Ctrl' ? 'Control+Enter' : 'Meta+Enter';
    else {
      const platform = await page.evaluate(() => navigator.platform);
      assert.match(platform, /^(Mac|Linux|Win)/, 'Unknown browser platform for queue shortcut');
      shortcut = platform.startsWith('Mac') ? 'Meta+Enter' : 'Control+Enter';
    }
  }
  const endpoint = `/api/v1/threads/${encodeURIComponent(threadId)}/queued-messages`;
  // BB's default swaps Enter to steer. Use the rendered queue shortcut, or
  // the browser platform for older labels; clicking would interrupt the run.
  // Await both promises together so a response timeout cannot escape while
  // Playwright is still waiting for the interaction and discard artifacts.
  const [response] = await Promise.all([
    page.waitForResponse(response => new URL(response.url()).pathname === endpoint && response.request().method() === 'POST'),
    label === 'Queue follow-up (Enter)' ? control.click()
      : page.getByRole('textbox').filter({ visible: true }).press(shortcut),
  ]);
  assert.ok(response.ok(), `Queue submission failed: ${response.status()}`);
  const message = await response.json();
  assert.ok(message.id, 'BB queue response has no message identity');
  return message;
}

export function assertPersistedQueuedPrompt(queued, accepted, prompt) {
  assert.ok(Array.isArray(queued), 'BB persisted queue is not a message list');
  const exact = queued.filter(message => message.content?.length === 1
    && message.content[0].type === 'text' && message.content[0].text === prompt);
  assert.equal(exact.length, 1, 'Expected exactly one independently persisted queued prompt');
  assert.equal(exact[0].id, accepted.id, 'Visible queue is not the accepted queued message');
  assert.equal(exact[0].threadId, accepted.threadId, 'Queued prompt belongs to another thread');
  return exact[0];
}

async function getJson(page, base, path) {
  const response = await page.request.get(new URL(path, base).href);
  assert.ok(response.ok(), `GET ${path} failed: ${response.status()}`);
  return response.json();
}

export async function eventsAfter(page, base, threadId, afterSeq = 0) {
  const result = [];
  const pageSize = 100;
  let cursor = afterSeq;
  for (;;) {
    const rows = await getJson(page, base, `/api/v1/threads/${encodeURIComponent(threadId)}/events?afterSeq=${cursor}&limit=${pageSize}&order=asc`);
    assert.ok(Array.isArray(rows), 'Unexpected BB events response');
    const fresh = rows.filter(row => Number.isInteger(row.seq) && row.seq > cursor);
    result.push(...fresh);
    if (rows.length < pageSize) return result;
    assert.ok(fresh.length, 'BB events pagination did not advance');
    cursor = Math.max(...fresh.map(row => row.seq));
  }
}

function options(argv) {
  const strings = ['url', 'host', 'project', 'model', 'workspace', 'reasoning', 'prompt', 'artifacts',
    'route', 'existing-thread-id', 'action', 'until', 'expected-response', 'expected-error', 'timeout-ms', 'after-seq', 'channel', 'switch-from-provider'];
  const { values } = parseArgs({ args: argv, options: { ...Object.fromEntries(strings.map(key => [key, { type: 'string' }])), headed: { type: 'boolean', default: false } } });
  for (const key of ['url', 'host']) assert.ok(values[key], `Missing --${key}`);
  values.route ??= 'native'; values.action ??= 'send'; values.until ??= 'completed';
  values.project ??= 'proj_personal'; values.reasoning ??= 'none';
  assert.ok(['native', 'launcher'].includes(values.route), 'Unsupported route');
  assert.ok(['send', 'queue', 'wait', 'approve', 'deny', 'interrupt'].includes(values.action), 'Unsupported action');
  assert.ok(['ready', 'submitted', 'completed', 'rejected'].includes(values.until), 'Unsupported --until');
  assert.ok(['none', 'low', 'medium', 'high', 'xhigh', 'max'].includes(values.reasoning), 'Unsupported reasoning');
  values.timeout = Number(values['timeout-ms'] ?? 240000);
  assert.ok(Number.isFinite(values.timeout) && values.timeout > 0, 'Invalid --timeout-ms');
  if (values.action !== 'send') assert.ok(values['existing-thread-id'], `${values.action} needs --existing-thread-id`);
  if (values.action === 'send') {
    assert.ok(values.model, 'Missing --model');
    if (values.until !== 'ready') assert.ok(values.prompt?.trim(), 'Missing --prompt');
  }
  if (values.action === 'queue') {
    assert.ok(values.prompt?.trim(), 'Queue requires --prompt');
    assert.ok(['ready', 'submitted'].includes(values.until), 'Queue submission and its later turn need separate correlated assertions');
  }
  if (values.action === 'deny') assert.ok(!values['expected-response'], 'Denial validates the rejected tool, not an assistant response');
  if (values.until === 'rejected') {
    assert.ok(values.route === 'launcher' && values.action === 'send' && !values['existing-thread-id'] && values['expected-error'], 'Rejected launch requires a new launcher request with --expected-error');
  } else if (values['expected-error']) assert.ok(values['existing-thread-id'], 'A negative send case requires an existing test thread');
  if (values['switch-from-provider']) assert.ok(!values['existing-thread-id'], 'Provider switching is a New thread control; an existing BB conversation keeps its provider');
  if (!values['existing-thread-id'] && (values.route === 'launcher' || values.project !== 'proj_personal')) assert.ok(values.workspace, 'This route requires --workspace');
  if (!values['existing-thread-id'] && values.route === 'launcher') assert.notEqual(values.project, 'proj_personal', 'The Gas City launcher requires a standard BB project; use native New thread for personal conversations');
  return values;
}

export async function runBrowser(argv = process.argv.slice(2), surface = null) {
  const args = options(argv);
  // The parent must identify an isolated installation. This driver never creates,
  // resets, starts, stops, or cleans BB/GC installations or their state.
  process.umask(0o077);
  const artifacts = args.artifacts ? resolve(args.artifacts) : await mkdtemp(join(tmpdir(), 'bb-browser-'));
  if (args.artifacts) await mkdir(artifacts, { recursive: false, mode: 0o700 });
  const result = { status: 'running', startedAt: new Date().toISOString(), route: args.route, action: args.action,
    until: args.until, artifacts, selection: { host: args.host, project: args.project, model: args.model,
      workspace: args.workspace, reasoning: args.reasoning }, steps: [], requests: [], consoleErrors: [] };
  const step = (name, details = {}) => { const row = { at: new Date().toISOString(), name, ...details }; result.steps.push(row); console.error(JSON.stringify({ progress: row })); };
  let browser, context, page;
  let tracingStarted = false;
  const listeners = [];
  const listen = (event, listener) => { page.on(event, listener); listeners.push([event, listener]); };
  const pendingEvidence = new Set();
  const catalogs = [];
  try {
    if (surface) {
      ({ context, page } = surface);
      assert.ok(context && page && page.context() === context, 'Supplied page/context do not belong together');
    } else {
      const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
      browser = await chromium.launch({ ...(args.channel ? { channel: args.channel } : {}), headless: !args.headed });
      context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
      page = await context.newPage();
    }
    await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
    tracingStarted = true;
    page.setDefaultTimeout(Math.min(args.timeout, 30000));
    listen('console', message => { if (message.type() === 'error') result.consoleErrors.push(message.text()); });
    listen('pageerror', error => result.consoleErrors.push(String(error)));
    listen('response', response => {
      const request = response.request(), url = new URL(response.url());
      if (url.origin !== new URL(args.url).origin || !url.pathname.startsWith('/api/v1/') || /\/assets\//.test(url.pathname)) return;
      if (request.method() === 'GET' && !url.pathname.includes('execution-options')) return;
      const operation = (async () => {
        const row = { at: new Date().toISOString(), method: request.method(), url: response.url(), status: response.status(), request: request.postData() };
        result.requests.push(row);
        try { row.response = await bounded(response.json(), 10000, 'Response evidence capture'); } catch (error) { row.responseReadError = String(error); }
        if (request.method() === 'GET' && row.response?.models) catalogs.push(row.response);
      })();
      pendingEvidence.add(operation); operation.finally(() => pendingEvidence.delete(operation));
    });

    await page.goto(new URL('/', args.url).href);
    result.bbVersion = await getJson(page, args.url, '/api/v1/system/version');
    const hosts = await getJson(page, args.url, '/api/v1/hosts');
    assert.ok(hosts.some(host => host.id === args.host && host.status === 'connected'), 'Requested BB host is not connected');
    step('loaded released BB frontend', { version: result.bbVersion.currentVersion });
    let afterSeq = 0;
    if (args['existing-thread-id']) {
      result.threadId = args['existing-thread-id'];
      const thread = await getJson(page, args.url, `/api/v1/threads/${result.threadId}`);
      assert.equal(thread.providerId, 'gas-city', 'Existing thread is not a Gas City conversation');
      assert.equal(thread.projectId, args.project, 'Existing thread belongs to another project');
      await page.goto(new URL(threadPath(thread.projectId, result.threadId), args.url).href);
      await page.locator('[data-timeline-row-list]').first().waitFor();
      const oldEvents = await eventsAfter(page, args.url, result.threadId);
      if (args['after-seq'] !== undefined) {
        afterSeq = Number(args['after-seq']);
        assert.ok(Number.isInteger(afterSeq) && afterSeq >= 0, 'Invalid --after-seq');
      } else if (['send', 'queue'].includes(args.action)) afterSeq = Math.max(0, ...oldEvents.map(event => event.seq));
      else {
        const activeRequest = oldEvents.filter(event => event.type === 'client/turn/requested').at(-1);
        assert.ok(activeRequest, 'Existing thread has no submitted turn');
        afterSeq = activeRequest.seq - 1;
      }
      step('opened existing conversation', { threadId: result.threadId, afterSeq });
    } else if (args.route === 'launcher') {
      await page.getByRole('button', { name: 'Gas City', exact: true }).click();
      await page.getByLabel('Host', { exact: true }).selectOption(args.host);
      await page.getByLabel('Project', { exact: true }).selectOption(args.project === 'proj_personal' ? 'globals' : args.project);
      await page.getByLabel('Agent', { exact: true }).selectOption(args.model);
      await page.getByLabel('Reasoning', { exact: true }).selectOption(args.reasoning);
      await page.getByLabel('Existing workspace', { exact: true }).fill(args.workspace);
      if (args.prompt) await page.getByLabel('First message', { exact: true }).fill(args.prompt);
      step('selected launcher host, scope, agent, effort and workspace');
    } else {
      await page.getByRole('button', { name: /^New thread \(/ }).click();
      if (args.project !== 'proj_personal') {
        const project = await getJson(page, args.url, `/api/v1/projects/${args.project}`);
        const source = project.sources.find(source => source.isDefault && source.type === 'local_path');
        assert.ok(source && source.hostId === args.host, 'Native project must have its default local source on the requested host');
        assert.equal(await realpath(source.path), await realpath(args.workspace), 'Native Work locally source does not match the requested GC workspace');
        await page.getByRole('button', { name: /^Project: / }).click();
        await page.getByRole('dialog', { name: 'Project', exact: true }).getByRole('option', { name: project.name, exact: true }).click();
        await page.getByRole('button', { name: 'Environment', exact: true }).click();
        await page.getByRole('dialog', { name: 'Environment', exact: true })
          .getByRole('option', { name: 'Project checkout', exact: true }).click();
      }
      step('selected native New thread and project', { project: args.project });
    }

    if (args.action === 'send' && (args.route === 'native' || args['existing-thread-id'])) {
      await page.getByRole('button', { name: /^Provider, model and reasoning/ }).click();
      const picker = page.getByRole('dialog');
      if (args['switch-from-provider']) {
        await picker.getByTitle(args['switch-from-provider'], { exact: true }).click();
        step('switched to the requested prior provider', { provider: args['switch-from-provider'] });
      }
      if (!args['existing-thread-id']) await picker.getByTitle('Gas City', { exact: true }).click();
      const deadline = Date.now() + Math.min(args.timeout, 30000);
      let model;
      while (Date.now() < deadline) {
        model = catalogs.flatMap(catalog => catalog.models).find(row => row.id === args.model || row.model === args.model);
        if (model) break;
        if (await picker.getByText('Could not load models for Gas City.', { exact: true }).isVisible()) throw new Error('Native Gas City model catalog failed to load');
        await page.waitForTimeout(100);
      }
      assert.ok(model, 'Requested model is absent from the actual BB catalog');
      // BB title-cases model display names; the chosen event must still carry the exact ID.
      const selectedModel = { name: exactIgnoringCase(model.displayName) };
      // BB uses a searchable list for larger catalogs and direct buttons for
      // smaller ones, such as the globals on an existing personal thread.
      await picker.getByRole('option', selectedModel).or(picker.getByRole('button', selectedModel)).click();
      if (!await picker.isVisible()) await page.getByRole('button', { name: /^Provider, model and reasoning/ }).click();
      const reasoningLabels = { none: 'Agent default', low: 'Low', medium: 'Medium', high: 'High', xhigh: 'Extra High', max: 'Max' };
      await page.getByRole('dialog').getByRole('radio', { name: reasoningLabels[args.reasoning], exact: true }).check();
      await page.keyboard.press('Escape');
      step('selected native Gas City model and reasoning', { modelLabel: model.displayName, reasoning: args.reasoning });
    }
    await page.screenshot({ path: join(artifacts, 'selection.png'), fullPage: true });
    if (args.until === 'ready') result.status = 'ready';
    else if (args.until === 'rejected') {
      await page.getByRole('button', { name: 'Start conversation', exact: true }).click();
      const deadline = Date.now() + args.timeout;
      while (Date.now() < deadline) {
        const rejection = assessLauncherRejection({ requests: result.requests, currentUrl: page.url(),
          visibleText: await page.locator('body').innerText(), expectedError: args['expected-error'] });
        if (rejection) { result.rejection = rejection; result.status = 'rejected'; break; }
        await page.waitForTimeout(100);
      }
      assert.equal(result.status, 'rejected', 'Expected pre-creation launcher error was not visible');
      step('rendered launcher rejection before thread creation');
      await page.screenshot({ path: join(artifacts, 'result.png'), fullPage: true });
    }
    else {
      if (args.action === 'send' || args.action === 'queue') {
        if (args.route === 'launcher' && !args['existing-thread-id']) await page.getByRole('button', { name: 'Start conversation', exact: true }).click();
        else {
          await page.getByRole('textbox').filter({ visible: true }).fill(args.prompt);
          if (args.action === 'queue') {
            result.queuedMessage = await submitQueuedPrompt(page, result.threadId);
          } else await page.locator('[data-promptbox-submit-action]').click();
        }
        await page.waitForURL(url => /\/threads\/[^/]+/.test(url.pathname), { timeout: args.timeout });
        result.threadId = new URL(page.url()).pathname.match(/\/threads\/([^/]+)/)[1];
        step('submitted prompt through BB UI', { threadId: result.threadId });
      } else if (args.action === 'approve' || args.action === 'deny') {
        const option = page.getByRole('button', { name: args.action === 'approve' ? 'Approve once' : 'Deny', exact: true });
        await option.click();
        assert.equal(await option.getAttribute('aria-pressed'), 'true', 'Approval answer was not selected');
        await page.getByRole('button', { name: 'Submit answer', exact: true }).click();
        step(`${args.action} through BB UI`);
      } else if (args.action === 'interrupt') {
        const control = await interruptControl(page);
        await control.locator.click();
        step('interrupted through BB UI', { control: control.kind });
      }
      result.threadUrl = new URL(threadPath(args.project, result.threadId), args.url).href;
      result.afterSeq = afterSeq;
      let thread = await getJson(page, args.url, `/api/v1/threads/${result.threadId}`);
      assert.equal(thread.providerId, 'gas-city', 'Submitted thread uses another provider');
      assert.equal(thread.projectId, args.project, 'Submitted thread uses another project');
      // New personal threads navigate before asynchronous workspace provisioning
      // attaches their environment. Wait for that real association before
      // validating the execution host; /environments/null is never meaningful.
      const provisioningDeadline = Date.now() + args.timeout;
      while (!thread.environmentId && Date.now() < provisioningDeadline) {
        await page.waitForTimeout(100);
        thread = await getJson(page, args.url, `/api/v1/threads/${result.threadId}`);
      }
      assert.ok(thread.environmentId, 'BB did not provision a thread environment before the deadline');
      result.thread = thread;
      const environment = await getJson(page, args.url, `/api/v1/environments/${thread.environmentId}`);
      assert.equal(environment.hostId, args.host, 'Submitted thread uses another host');
      result.environment = environment;
      if (args.until === 'submitted') {
        if (args.action === 'queue') {
          const queued = await getJson(page, args.url, `/api/v1/threads/${encodeURIComponent(result.threadId)}/queued-messages`);
          assertPersistedQueuedPrompt(queued, result.queuedMessage, args.prompt);
          await page.getByText(args.prompt, { exact: true }).first().waitFor({ state: 'visible' });
          result.queue = queued;
          result.events = await eventsAfter(page, args.url, result.threadId, afterSeq);
        } else if (args.action === 'send') {
          const deadline = Date.now() + args.timeout;
          do {
            result.events = await eventsAfter(page, args.url, result.threadId, afterSeq);
            if (result.events.some(event => event.type === 'client/turn/requested')) break;
            await page.waitForTimeout(100);
          } while (Date.now() < deadline);
          assert.equal(result.events.filter(event => event.type === 'client/turn/requested').length, 1, 'Expected exactly one UI-submitted request');
        }
        result.status = 'submitted';
      }
      else {
        const deadline = Date.now() + args.timeout;
        let lastProgress = 0;
        while (Date.now() < deadline) {
          const events = await eventsAfter(page, args.url, result.threadId, afterSeq);
          if (args.action === 'deny') await revealDeniedTurn(page, result.threadId,
            { events, afterSeq, model: args.model, reasoning: args.reasoning });
          const visibleRows = await page.locator('[data-timeline-row-id]').evaluateAll(rows => rows.map(row => ({
            id: row.getAttribute('data-timeline-row-id'), text: [...row.querySelectorAll('[data-markdown-preview]')].map(node => node.innerText).join('\n'),
          })));
          if (args.action === 'deny') {
            for (const row of await page.locator('[data-timeline-row-id]').all()) {
              const id = await row.getAttribute('data-timeline-row-id');
              if (!id.includes(':question:') && !id.includes(':tool:')) continue;
              const evidence = visibleRows.find(value => value.id === id);
              if (evidence) { evidence.visible = await row.isVisible(); evidence.aria = await row.ariaSnapshot(); }
            }
          }
          result.events = events;
          result.visibleRows = visibleRows;
          if (args['expected-error']) {
            const rejection = assessRejection({ events, afterSeq, visibleText: await page.locator('body').innerText(), expectedError: args['expected-error'] });
            if (rejection) { result.rejection = rejection; result.status = 'passed'; step('rendered the expected rejection', { seq: rejection.seq }); break; }
          }
          const assess = args.action === 'deny' ? assessDenial : assessCompletion;
          const completion = args['expected-error'] ? null : assess({ events, visibleRows, afterSeq, model: args.model, reasoning: args.reasoning, expectedResponse: args['expected-response'] });
          if (completion) { result.completion = completion; result.status = 'passed'; step('rendered correlated model completion', { turnId: completion.turnId }); break; }
          if (Date.now() - lastProgress > 15000) { step('waiting for rendered model completion', { events: events.length, assistantRows: visibleRows.filter(row => row.id.includes(':assistant:')).length }); lastProgress = Date.now(); }
          await page.waitForTimeout(500);
        }
        assert.equal(result.status, 'passed', 'Timed out waiting for a rendered correlated model completion');
      }
      await page.screenshot({ path: join(artifacts, 'result.png'), fullPage: true });
    }
  } catch (error) {
    result.status = 'failed'; result.error = String(error.stack || error);
    if (page) {
      try { await page.screenshot({ path: join(artifacts, 'failure.png'), fullPage: true }); result.failureUi = await page.locator('body').ariaSnapshot(); }
      catch (captureError) { result.captureError = String(captureError); }
    }
  } finally {
    for (const [event, listener] of listeners) page.off(event, listener);
    step('saving browser evidence');
    const evidence = await Promise.allSettled(pendingEvidence);
    const failedEvidence = evidence.filter(entry => entry.status === 'rejected');
    if (failedEvidence.length) { result.evidenceErrors = failedEvidence.map(entry => String(entry.reason)); result.status = 'failed'; }
    if (tracingStarted) {
      try { await bounded(context.tracing.stop({ path: join(artifacts, 'trace.zip') }), 20000, 'Trace capture'); }
      catch (error) { result.traceError = String(error); result.status = 'failed'; }
    }
    if (browser) {
      try { await bounded(browser.close(), 15000, 'Browser close'); }
      catch (error) { result.browserCloseError = String(error); result.status = 'failed'; }
    }
    result.finishedAt = new Date().toISOString();
    await writeFile(join(artifacts, 'result.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  }
  console.log(JSON.stringify({ status: result.status, threadId: result.threadId, threadUrl: result.threadUrl, artifacts, result: join(artifacts, 'result.json') }));
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { const result = await runBrowser(); if (result.status === 'failed') process.exitCode = 1; }
  catch (error) { console.error(String(error.stack || error)); process.exitCode = 1; }
}

import test from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { experimental_assembleCapturedThreadEvents, experimental_runBridgeConformance, experimental_formatConformanceReport } from "@get-bb/plugin-sdk/provider-bridge/testing";
import { GasCityProvider } from "../src/provider.js";
import { Journal, type Receipt } from "../src/journal.js";
import { GasCityClient } from "../src/client.js";
import { targetId } from "../src/catalog.js";
import { fixture, options, until } from "./fixture.js";

const target = { v: 1 as const, connection: "local", city: "alpha", agent: "gc.mayor" };

test("async create, first prompt once, transcript replay, completed resume, and release", async () => {
  const f = await fixture();
  const messages: any[] = [];
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, serviceTier: "default" as const, model: targetId(target), providerOptions: { projectId: "proj_personal" } };
    const start = await provider.dispatch("thread/start", { threadId: "bb-thread", cwd: f.cwd, instructionMode: "append", options: execution }) as { providerThreadId: string };
    assert.match(start.providerThreadId, /^gcs1_/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/sessions") && c.method === "POST").length, 1);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    await provider.dispatch("turn/start", { threadId: "bb-thread", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "Hello" }], clientRequestId: "creq_23456789ab", options: execution });
    await until(() => messages.some(m => m.params?.deltas?.some((d: any) => d.kind === "turn.boundary" && d.status === "completed")));
    const submissions = f.calls.filter(c => c.path.endsWith("/submit"));
    assert.equal(submissions.length, 1);
    assert.equal(submissions[0]!.headers["x-gc-request"], "bb-provider");
    const text = messages.flatMap(m => m.params?.deltas ?? []).filter(d => d.kind === "item.textDelta").map(d => d.text).join("");
    assert.equal(text, "Hello from Gas City");
    const events = experimental_assembleCapturedThreadEvents(messages, "gas-city");
    assert.ok(events.length > 0);
    await provider.dispatch("thread/stop", { threadId: "bb-thread", providerThreadId: start.providerThreadId, intent: "release", activeTurnId: null });
    assert.equal(f.calls.filter(c => c.path.endsWith("/stop")).length, 0);
    const restored = await provider.dispatch("thread/resume", { threadId: "bb-thread", providerThreadId: start.providerThreadId, cwd: f.cwd, instructionMode: "append", options: execution }) as any;
    assert.equal(restored.providerThreadId, start.providerThreadId);
    assert.equal(f.calls.filter(c => c.path.endsWith("/sessions") && c.method === "POST").length, 1);
    await assert.rejects(provider.dispatch("turn/start", { threadId: "bb-thread", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "Hello" }], clientRequestId: "creq_23456789ab", options: execution }), /already journaled/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await provider.close(); await f.close(); }
});

test("wrong rig is rejected before GC creation; existing thread cannot switch agents", async () => {
  const f = await fixture(); const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    await assert.rejects(provider.dispatch("thread/start", { threadId: "wrong", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId({ ...target, agent: "api/review.reviewer" }), providerOptions: { projectId: "project-web" } } }), /outside/);
    assert.equal(f.sessions.size, 0);
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "fixed", cwd: f.cwd, instructionMode: "append", options: execution });
    await assert.rejects(provider.dispatch("turn/start", { threadId: "fixed", providerThreadId: start.providerThreadId, clientRequestId: "creq_23456789af", input: [{ type: "text", text: "Hello" }], options: { ...execution, model: targetId({ ...target, city: "beta" }) } }), /cannot switch agents/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
  } finally { await provider.close(); await f.close(); }
});

test("release preserves the remote turn and uncertain resume blocks", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "held", cwd: f.cwd, instructionMode: "append", options: execution });
    await provider.dispatch("turn/start", { threadId: "held", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "hold" }], clientRequestId: "creq_23456789ac", options: execution });
    await provider.dispatch("thread/stop", { threadId: "held", providerThreadId: start.providerThreadId, intent: "release", activeTurnId: null });
    assert.equal(f.calls.filter(c => c.path.endsWith("/stop")).length, 0);
    await assert.rejects(provider.dispatch("thread/resume", { threadId: "held", providerThreadId: start.providerThreadId, cwd: f.cwd, instructionMode: "append", options: execution }), /interrupted or its delivery is uncertain/);
    assert.equal((await journal.get("held"))?.turn?.state, "accepted");
  } finally { await provider.close(); await f.close(); }
});

test("release during preflight prevents a later prompt submission", async () => {
  const f = await fixture(); let reached = false; let release!: () => void;
  const paused = new Promise<void>(resolve => { release = resolve; });
  class PausingClient extends GasCityClient {
    override async get<T = any>(path: string, signal?: AbortSignal): Promise<T> {
      if (path.includes("/transcript?")) { reached = true; await paused; }
      return super.get<T>(path, signal);
    }
  }
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, client: c => new PausingClient(c), journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "preflight", cwd: f.cwd, instructionMode: "append", options: execution });
    const pending = assert.rejects(provider.dispatch("turn/start", { threadId: "preflight", providerThreadId: start.providerThreadId, clientRequestId: "creq_23456789ag", input: [{ type: "text", text: "Hello" }], options: execution }), /abort/i);
    await until(() => reached);
    await provider.dispatch("thread/stop", { threadId: "preflight", providerThreadId: start.providerThreadId, intent: "release", activeTurnId: null });
    release(); await pending;
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit") || c.path.endsWith("/stop")).length, 0);
  } finally { release(); await provider.close(); await f.close(); }
});

for (const intent of ["interrupt", "release"] as const) {
  test(`${intent} during completion preserves one terminal outcome`, async () => {
    const f = await fixture(); const messages: any[] = [];
    let writingCompletion = false; let finishWrite!: () => void; let didWrite!: () => void;
    const paused = new Promise<void>(resolve => { finishWrite = resolve; });
    const written = new Promise<void>(resolve => { didWrite = resolve; });
    class PausingJournal extends Journal {
      override async put(threadId: string, receipt: Receipt) {
        if (receipt.turn?.state === "completed") { writingCompletion = true; await paused; }
        await super.put(threadId, receipt);
        if (receipt.turn?.state === "completed") didWrite();
      }
    }
    const journal = new PausingJournal(join(f.cwd, "journal"));
    const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal });
    try {
      const execution = { ...options, model: targetId(target) };
      const start: any = await provider.dispatch("thread/start", { threadId: "completion-race", cwd: f.cwd, instructionMode: "append", options: execution });
      await provider.dispatch("turn/start", { threadId: "completion-race", providerThreadId: start.providerThreadId, clientRequestId: "creq_23456789ai", input: [{ type: "text", text: "Hello" }], options: execution });
      await until(() => writingCompletion);
      const stopping = provider.dispatch("thread/stop", { threadId: "completion-race", providerThreadId: start.providerThreadId, intent, activeTurnId: null });
      finishWrite(); await written; await stopping;
      const boundaries = messages.flatMap(m => m.params?.deltas ?? []).filter(d => d.kind === "turn.boundary");
      assert.deepEqual(boundaries.map(d => d.status), intent === "interrupt" ? ["interrupted"] : []);
      assert.equal((await journal.get("completion-race"))?.turn?.state, intent === "interrupt" ? "failed" : "accepted");
      if (intent === "release") {
        await assert.rejects(provider.dispatch("thread/resume", { threadId: "completion-race", providerThreadId: start.providerThreadId, cwd: f.cwd, instructionMode: "append", options: execution }), /interrupted or its delivery is uncertain/);
      } else {
        await provider.dispatch("turn/start", { threadId: "completion-race", providerThreadId: start.providerThreadId, clientRequestId: "creq_23456789aj", input: [{ type: "text", text: "Next" }], options: execution });
        await until(() => messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "turn.boundary" && d.status === "completed"));
        assert.equal((await journal.get("completion-race"))?.turn?.clientRequestId, "creq_23456789aj");
      }
    } finally { finishWrite(); await provider.close(); await f.close(); }
  });
}

test("published BB bridge conformance against the GC 1.4 fixture", async () => {
  const f = await fixture(); let messages: any[] = [];
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "conformance")) });
  try {
    const report = await experimental_runBridgeConformance({
      providerId: "gas-city", timeoutMs: 2000,
      transport: { send: line => provider.handleLine(line), takeMessages: () => { const out = messages; messages = []; return out; }, close: () => provider.close() },
      session: { cwd: f.cwd, promptInput: [{ type: "text", text: "Hello", mentions: [] }], interruptiblePromptInput: [{ type: "text", text: "hold", mentions: [] }], options: { ...options, model: targetId(target) } },
    });
    assert.equal(report.passed, true, experimental_formatConformanceReport(report));
  } finally { await provider.close(); await f.close(); }
});

test("lost submit response is journaled and never automatically resent", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "uncertain", cwd: f.cwd, instructionMode: "append", options: execution });
    f.faults.dropSubmitReply = true;
    const turn = { threadId: "uncertain", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "Hello" }], clientRequestId: "creq_23456789ad", options: execution };
    await assert.rejects(provider.dispatch("turn/start", turn), /fetch failed/);
    assert.equal((await journal.get("uncertain"))?.turn?.state, "submitting");
    await assert.rejects(provider.dispatch("turn/start", turn), /already journaled/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await provider.close(); await f.close(); }
});

test("checkout mismatch blocks before any prompt and initial-input start submits once", async () => {
  const f = await fixture(); const output: any[] = [];
  const provider = new GasCityProvider({ send: m => output.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, model: targetId(target) };
    f.faults.workDir = "/tmp";
    await assert.rejects(provider.dispatch("thread/start", { threadId: "mismatch", cwd: f.cwd, instructionMode: "append", options: execution, input: [{ type: "text", text: "Hello" }] }), /Select a matching unmanaged/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    f.faults.workDir = "";
    await provider.dispatch("thread/start", { threadId: "initial", cwd: f.cwd, instructionMode: "append", options: execution, input: [{ type: "text", text: "Hello" }] });
    await until(() => output.some(m => m.params?.deltas?.some((d: any) => d.kind === "turn.boundary")));
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
    experimental_assembleCapturedThreadEvents(output, "gas-city");
  } finally { await provider.close(); await f.close(); }
});

test("GC tmux approval remains an explicit user decision in BB full mode", async () => {
  const f = await fixture(); const messages: any[] = [];
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "approval", cwd: f.cwd, instructionMode: "append", options: execution });
    await provider.dispatch("turn/start", { threadId: "approval", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "approval" }], clientRequestId: "creq_23456789ae", options: execution });
    await until(() => messages.some(m => m.method === "interaction/request"));
    const request = messages.find(m => m.method === "interaction/request");
    assert.equal(f.calls.filter(c => c.path.endsWith("/respond")).length, 0);
    assert.equal(request.params.payload.kind, "user_question");
    provider.handleLine(JSON.stringify({ jsonrpc: "2.0", id: request.id, result: { kind: "user_answer", answers: { "gc-approval-1": { selected: ["approve"] } } } }));
    await until(() => messages.some(m => m.params?.deltas?.some((d: any) => d.kind === "turn.boundary" && d.status === "completed")));
    assert.deepEqual(f.calls.find(c => c.path.endsWith("/respond"))?.body, { request_id: "gc-approval-1", action: "approve" });
  } finally { await provider.close(); await f.close(); }
});

test("a fresh session can bootstrap from GC terminal fallback into structured history", async () => {
  const f = await fixture(); const messages: any[] = [];
  f.faults.freshHistoryFallback = true;
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "fresh", cwd: f.cwd, instructionMode: "append", options: execution });
    await provider.dispatch("turn/start", { threadId: "fresh", providerThreadId: start.providerThreadId, clientRequestId: "creq_23456789ah", input: [{ type: "text", text: "Hello" }], options: execution });
    await until(() => messages.some(m => m.params?.deltas?.some((d: any) => d.kind === "turn.boundary" && d.status === "completed")));
    const text = messages.flatMap(m => m.params?.deltas ?? []).filter(d => d.kind === "item.textDelta").map(d => d.text).join("");
    assert.equal(text, "Hello from Gas City");
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
    assert.equal(f.calls.filter(c => c.path.endsWith("/pending")).length, 1);
  } finally { await provider.close(); await f.close(); }
});

test("the same GC approval ID prompts again on later turns and forwards deny", async () => {
  const f = await fixture(); const messages: any[] = [];
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "repeat", cwd: f.cwd, instructionMode: "append", options: execution });
    for (const [index, action] of ["approve", "deny"].entries()) {
      await provider.dispatch("turn/start", { threadId: "repeat", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "approval" }], clientRequestId: `creq_23456789a${index ? "f" : "e"}`, options: execution });
      await until(() => messages.filter(m => m.method === "interaction/request").length === index + 1);
      const request = messages.filter(m => m.method === "interaction/request").at(-1);
      provider.handleLine(JSON.stringify({ jsonrpc: "2.0", id: request.id, result: { kind: "user_answer", answers: { "gc-approval-1": { selected: [action] } } } }));
      await until(() => messages.flatMap(m => m.params?.deltas ?? []).filter(d => d.kind === "turn.boundary" && d.status === "completed").length === index + 1);
    }
    assert.deepEqual(f.calls.filter(c => c.path.endsWith("/respond")).map(c => c.body.action), ["approve", "deny"]);
  } finally { await provider.close(); await f.close(); }
});

test("unsupported steering preserves a live turn and never submits the follow-up", async () => {
  const f = await fixture(); const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await provider.dispatch("thread/start", { threadId: "steer", cwd: f.cwd, instructionMode: "append", options: execution });
    const turn = { threadId: "steer", providerThreadId: start.providerThreadId, input: [{ type: "text", text: "hold" }], clientRequestId: "creq_23456789ae", options: execution };
    await provider.dispatch("turn/start", turn);
    await assert.rejects(provider.dispatch("turn/steer", { ...turn, expectedTurnId: "turn-active" }), (error: any) => error.code === -32601);
    assert.equal(provider.sessions.get("steer")?.busy, true);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await provider.close(); await f.close(); }
});

test("a second bridge cannot resume or recover an owned thread even while idle", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const first = new GasCityProvider({ send: () => {}, config: async () => f.config, journal });
  const second = new GasCityProvider({ send: () => {}, config: async () => f.config, journal: new Journal(journal.directory) });
  try {
    const execution = { ...options, model: targetId(target) };
    const start: any = await first.dispatch("thread/start", { threadId: "owned", cwd: f.cwd, instructionMode: "append", options: execution });
    const resume = { threadId: "owned", providerThreadId: start.providerThreadId, cwd: f.cwd, instructionMode: "append", options: execution };
    await assert.rejects(second.dispatch("thread/resume", resume), /owned by/);
    await assert.rejects(journal.locked("owned", async () => {}), /owned by/);
    await first.dispatch("thread/stop", { threadId: "owned", providerThreadId: start.providerThreadId, intent: "release", activeTurnId: null });
    await second.dispatch("thread/resume", resume);
  } finally { await first.close(); await second.close(); await f.close(); }
});


test("a lost create response recovers the deterministic alias without creating twice", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal });
  try {
    f.faults.dropCreateReply = true;
    const execution = { ...options, model: targetId(target) };
    const args = { threadId: "lost-create", cwd: f.cwd, instructionMode: "append", options: execution };
    await assert.rejects(provider.dispatch("thread/start", args), /fetch failed/);
    const start: any = await provider.dispatch("thread/start", args);
    assert.match(start.providerThreadId, /^gcs1_/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/sessions") && c.method === "POST").length, 1);
    assert.equal((await journal.get("lost-create"))?.sessionId, "s1");
  } finally { await provider.close(); await f.close(); }
});


test("failed initial preflight relinquishes ownership so the same BB thread can retry", async () => {
  const f = await fixture(); let fail = true;
  class PreflightClient extends GasCityClient {
    override async get<T = any>(path: string, signal?: AbortSignal): Promise<T> {
      if (path.includes("/transcript?") && fail) { fail = false; throw new Error("transient preflight failure"); }
      return super.get<T>(path, signal);
    }
  }
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, client: c => new PreflightClient(c), journal: new Journal(join(f.cwd, "journal")) });
  try {
    const args = { threadId: "retry-preflight", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId(target) }, input: [{ type: "text", text: "Hello" }] };
    await assert.rejects(provider.dispatch("thread/start", args), /transient preflight/);
    assert.equal(provider.sessions.size, 0);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    await provider.dispatch("thread/start", args);
    assert.equal(f.calls.filter(c => c.path.endsWith("/sessions") && c.method === "POST").length, 1);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await provider.close(); await f.close(); }
});


test("unsupported tier and unverifiable working directory fail before prompt submission", async () => {
  const f = await fixture();
  class MissingDirectoryClient extends GasCityClient {
    override async get<T = any>(path: string, signal?: AbortSignal): Promise<T> {
      const result = await super.get<any>(path, signal);
      if (result.template) delete result.work_dir;
      return result;
    }
  }
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, client: c => new MissingDirectoryClient(c), journal: new Journal(join(f.cwd, "journal")) });
  try {
    f.config.workspacePolicy = "require-match";
    const args = { threadId: "no-directory", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId(target) }, input: [{ type: "text", text: "Hello" }] };
    await assert.rejects(provider.dispatch("thread/start", { ...args, options: { ...args.options, serviceTier: "fast" } }), /does not override/);
    assert.equal(f.sessions.size, 0);
    await assert.rejects(provider.dispatch("thread/start", args), /cannot verify workspace ownership/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
  } finally { await provider.close(); await f.close(); }
});

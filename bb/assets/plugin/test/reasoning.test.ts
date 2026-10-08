import test from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { discover, modelRow, targetId } from "../src/catalog.js";
import { GasCityProvider } from "../src/provider.js";
import { Journal } from "../src/journal.js";
import plugin from "../server.js";
import { fixture, options } from "./fixture.js";

test("BB catalogs expose nonempty native effort choices, including an explicit agent default", async () => {
  const f = await fixture();
  try {
    const catalog = await discover(f.config, { projectId: "project-web" });
    const rows = catalog.agents.map(modelRow);
    assert.deepEqual(rows.find(r => r.displayName.includes("gc.mayor"))!.supportedReasoningEfforts.map((r: any) => r.reasoningEffort), ["none", "low", "medium", "high", "xhigh", "max"]);
    assert.deepEqual(rows.find(r => r.displayName.includes("review.reviewer"))!.supportedReasoningEfforts.map((r: any) => r.reasoningEffort), ["none", "low", "medium", "high", "xhigh"]);
    f.providers[0]!.options_schema = [];
    const unsupported = (await discover(f.config)).agents.map(modelRow);
    assert.deepEqual(unsupported[0]!.supportedReasoningEfforts.map((r: any) => r.reasoningEffort), ["none"]);
    let registered: any;
    plugin({ rpc: { register() {} }, hosts: { experimental_client() { return {}; } }, onDispose() {}, providers: { register(value: any) { registered = value; } } } as any);
    for (const row of rows) for (const effort of row.supportedReasoningEfforts as any[]) assert.ok(registered.capabilities.reasoningLevels.includes(effort.reasoningEffort));
    assert.equal(registered.reasoningLevels.find((r: any) => r.id === "none").label, "Agent default");
  } finally { await f.close(); }
});

test("medium is forwarded at GC creation and cannot be silently changed on a turn or resume", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send() {}, config: async () => f.config, journal });
  try {
    const target = (await discover(f.config)).agents[0]!;
    const execution = { ...options, model: targetId(target), reasoningLevel: "medium" };
    const args = { threadId: "reasoning", cwd: f.cwd, instructionMode: "append", options: execution };
    const started: any = await provider.dispatch("thread/start", args);
    assert.deepEqual(f.calls.find(c => c.method === "POST" && c.path.endsWith("/sessions"))!.body.options, { effort: "medium" });
    assert.equal((await journal.get(args.threadId) as any).reasoningLevel, "medium");
    await assert.rejects(provider.dispatch("turn/start", { threadId: args.threadId, providerThreadId: started.providerThreadId, options: { ...execution, reasoningLevel: "high" }, clientRequestId: "creq_23456789ab", input: [{ type: "text", text: "Do not send" }] }), /reasoning.*new BB thread/i);
    await provider.dispatch("thread/stop", { threadId: args.threadId, providerThreadId: started.providerThreadId, intent: "release", activeTurnId: null });
    await assert.rejects(provider.dispatch("thread/resume", { ...args, providerThreadId: started.providerThreadId, options: { ...execution, reasoningLevel: "none" } }), /reasoning.*new BB thread/i);
    await assert.rejects(provider.dispatch("thread/start", { ...args, options: { ...execution, reasoningLevel: "high" } }), /reasoning.*new BB thread/i);
    await provider.dispatch("thread/resume", { ...args, providerThreadId: started.providerThreadId });
    assert.equal(f.calls.filter(c => c.method === "POST").length, 1);
  } finally { await provider.close(); await f.close(); }
});

test("agent default omits the GC effort override and older receipts still resume", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send() {}, config: async () => f.config, journal });
  try {
    const target = (await discover(f.config)).agents[0]!;
    const args = { threadId: "default", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId(target) } };
    const started: any = await provider.dispatch("thread/start", args);
    assert.equal(f.calls.find(c => c.method === "POST")!.body.options, undefined);
    await provider.dispatch("thread/stop", { threadId: args.threadId, providerThreadId: started.providerThreadId, intent: "release", activeTurnId: null });
    const receipt: any = await journal.get(args.threadId);
    delete receipt.reasoningLevel;
    await journal.put(args.threadId, receipt);
    await provider.dispatch("thread/resume", { ...args, providerThreadId: started.providerThreadId });
    assert.equal(f.calls.filter(c => c.method === "POST").length, 1);
  } finally { await provider.close(); await f.close(); }
});

test("unsupported native effort is rejected before GC creation", async () => {
  const f = await fixture(); const provider = new GasCityProvider({ send() {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const target = (await discover(f.config, { projectId: "project-web" })).agents.find(a => a.provider === "codex")!;
    await assert.rejects(provider.dispatch("thread/start", { threadId: "invalid", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId(target), reasoningLevel: "max", providerOptions: { projectId: "project-web" } } }), /does not support.*max/i);
    assert.equal(f.calls.filter(c => c.method === "POST").length, 0);
  } finally { await provider.close(); await f.close(); }
});

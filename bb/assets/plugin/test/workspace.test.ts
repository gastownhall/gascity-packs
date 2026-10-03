import test from "node:test";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { GasCityProvider } from "../src/provider.js";
import { GasCityClient } from "../src/client.js";
import { Journal } from "../src/journal.js";
import { targetId } from "../src/catalog.js";
import { fixture, options, until } from "./fixture.js";

const target = { v: 1 as const, connection: "local", city: "alpha", agent: "gc.mayor" };

test("personal global conversations work from BB's separate workspace and resume the same GC session", async () => {
  const f = await fixture();
  const bbCwd = join(f.cwd, "bb-personal-workspace"), gcCwd = join(f.cwd, "gc-city");
  await mkdir(bbCwd); await mkdir(gcCwd); f.faults.workDir = gcCwd;
  const messages: any[] = [];
  let noticeBeforeSubmit = false;
  const provider = new GasCityProvider({
    send: m => messages.push(m), config: async () => f.config, journal: new Journal(join(f.cwd, "journal")),
    client: connection => new GasCityClient(connection, async (input, init) => {
      if (String(input).endsWith("/submit")) noticeBeforeSubmit = messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "item.textClose" && d.text?.includes(gcCwd));
      return fetch(input, init);
    }),
  });
  try {
    const args = { threadId: "personal-global", cwd: bbCwd, instructionMode: "append", options: { ...options, model: targetId(target), reasoningLevel: "medium", instructions: `BB workspace: ${bbCwd}`, providerOptions: { projectId: "proj_personal" } } };
    const started: any = await provider.dispatch("thread/start", { ...args, input: [{ type: "text", text: "hello?" }] });
    await until(() => messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "turn.boundary" && d.status === "completed"));
    const creation = f.calls.filter(c => c.method === "POST" && c.path.endsWith("/sessions"));
    assert.equal(creation.length, 1);
    assert.deepEqual(creation[0]!.body.options, { effort: "medium" });
    const submissions = f.calls.filter(c => c.path.endsWith("/submit")); assert.equal(submissions.length, 1);
    assert.equal(submissions[0]!.body.message.split("hello?").length - 1, 1);
    assert.ok(submissions[0]!.body.message.endsWith("hello?"));
    assert.ok(submissions[0]!.body.message.includes(gcCwd), "GC receives its actual working directory alongside BB context");
    assert.equal(noticeBeforeSubmit, true, "the workspace notice is visible before GC receives the prompt");
    const notice = messages.flatMap(m => m.params?.deltas ?? []).find(d => d.kind === "item.textClose" && d.text?.includes(gcCwd));
    assert.ok(notice, "the conversation names the GC working directory");
    assert.ok(notice.text.includes(bbCwd));
    assert.match(notice.text, /file and diff views.*not synchronized/i);
    await provider.dispatch("thread/stop", { threadId: args.threadId, providerThreadId: started.providerThreadId, intent: "release", activeTurnId: null });
    const resumed: any = await provider.dispatch("thread/resume", { ...args, providerThreadId: started.providerThreadId });
    assert.equal(resumed.providerThreadId, started.providerThreadId);
    assert.equal(f.calls.filter(c => c.method === "POST" && c.path.endsWith("/sessions")).length, 1);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await provider.close(); await f.close(); }
});

for (const agent of ["gc.mayor", "web/review.reviewer"]) {
  test(`mapped project ${agent} rejects a different GC checkout before sending a prompt`, async () => {
    const f = await fixture(); const otherCheckout = join(f.cwd, "other-checkout");
    await mkdir(otherCheckout); f.faults.workDir = otherCheckout;
    const provider = new GasCityProvider({ send() {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
    try {
      await assert.rejects(provider.dispatch("thread/start", { threadId: "mapped-mismatch", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId({ ...target, agent }), providerOptions: { projectId: "project-web" } }, input: [{ type: "text", text: "Do not send" }] }), /Select a matching unmanaged/);
      assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    } finally { await provider.close(); await f.close(); }
  });
}

test("personal conversations cannot select rig agents without a project binding", async () => {
  const f = await fixture();
  const provider = new GasCityProvider({ send() {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    await assert.rejects(provider.dispatch("thread/start", { threadId: "personal-rig", cwd: f.cwd, instructionMode: "append", options: { ...options, model: targetId({ ...target, agent: "web/review.reviewer" }), providerOptions: { projectId: "proj_personal" } }, input: [{ type: "text", text: "Do not send" }] }), /outside the project's city\/rig/);
    assert.equal(f.calls.filter(c => c.method === "POST").length, 0);
  } finally { await provider.close(); await f.close(); }
});

test("personal startup without a GC directory blocks, then explicit retry reuses its unsent session", async () => {
  const f = await fixture(); const bbCwd = join(f.cwd, "bb-personal-workspace"); await mkdir(bbCwd);
  let reportDirectory = false;
  class DirectoryClient extends GasCityClient {
    override async get<T = any>(path: string, signal?: AbortSignal): Promise<T> {
      const result = await super.get<any>(path, signal);
      if (result.template && !reportDirectory) delete result.work_dir;
      return result;
    }
  }
  const messages: any[] = []; const journal = new Journal(join(f.cwd, "journal"));
  const provider = new GasCityProvider({ send: m => messages.push(m), config: async () => f.config, client: c => new DirectoryClient(c), journal });
  try {
    const args = { threadId: "retry-workspace", cwd: bbCwd, instructionMode: "append", options: { ...options, model: targetId(target), providerOptions: { projectId: "proj_personal" } }, input: [{ type: "text", text: "hello?" }] };
    await assert.rejects(provider.dispatch("thread/start", args), /cannot verify workspace ownership/);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
    const receipt = await journal.get(args.threadId); assert.ok(receipt?.sessionId);
    assert.equal(receipt.turn, undefined);
    reportDirectory = true;
    const started: any = await provider.dispatch("thread/start", args);
    await until(() => messages.flatMap(m => m.params?.deltas ?? []).some(d => d.kind === "turn.boundary" && d.status === "completed"));
    assert.equal((await journal.get(args.threadId))?.sessionId, receipt.sessionId);
    assert.ok(started.providerThreadId);
    assert.equal(f.calls.filter(c => c.method === "POST" && c.path.endsWith("/sessions")).length, 1);
    const submissions = f.calls.filter(c => c.path.endsWith("/submit")); assert.equal(submissions.length, 1);
    assert.equal(submissions[0]!.body.message.split("hello?").length - 1, 1);
    assert.ok(submissions[0]!.body.message.endsWith("hello?"));
  } finally { await provider.close(); await f.close(); }
});

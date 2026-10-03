import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { GasCityClient } from "../src/client.js";
import { Journal } from "../src/journal.js";
import { recoverThread } from "../src/recovery.js";
import { fixture } from "./fixture.js";

const target = { v: 1 as const, connection: "local", city: "alpha", agent: "gc.mayor" };

test("lost submit acceptance can be reconciled using inspected request evidence without resending", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal")); const client = new GasCityClient(f.config.connections[0]!);
  try {
    const create = await client.post(client.city("alpha", "/sessions"), { kind: "agent", name: target.agent, alias: "bb-evidence" });
    const created = await client.result("alpha", create, "create");
    const accepted = await client.post(client.session("alpha", created.session.id, "/submit"), { message: "Hello" });
    await journal.put("lost", { target, sessionId: created.session.id, turn: { clientRequestId: "creq_23456789ab", digest: createHash("sha256").update("Hello").digest("hex"), state: "submitting", baselineMessageIds: [], messageDigest: createHash("sha256").update("Hello").digest("hex") } });
    await assert.rejects(recoverThread(f.config, journal, "lost"), /response was lost/);
    const recovered = await recoverThread(f.config, journal, "lost", { requestId: accepted.request_id, eventCursor: accepted.event_cursor });
    assert.equal(recovered.turn?.state, "completed");
    assert.equal(recovered.turn?.request_id, accepted.request_id);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await f.close(); }
});

test("recovery waits for the exact async request before considering an idle transcript", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal"));
  const client = new GasCityClient(f.config.connections[0]!);
  try {
    const create = await client.post(client.city("alpha", "/sessions"), { kind: "agent", name: target.agent, alias: "bb-recovery" });
    const created = await client.result("alpha", create, "create");
    await journal.put("recovery", { target, sessionId: created.session.id, turn: { clientRequestId: "creq_23456789ab", digest: "digest", state: "accepted", request_id: "not-yet-delivered", event_cursor: "1" } });
    await assert.rejects(recoverThread(f.config, journal, "recovery", { signal: AbortSignal.timeout(40) }), /not confirmed|abort/i);
    assert.equal((await journal.get("recovery"))?.turn?.state, "accepted");
    assert.equal(f.calls.filter(c => c.path.endsWith("/transcript")).length, 0);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 0);
  } finally { await f.close(); }
});

test("a confirmed delivery cannot recover an old idle snapshot before the prompt is consumed", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal")); const client = new GasCityClient(f.config.connections[0]!);
  try {
    const create = await client.post(client.city("alpha", "/sessions"), { kind: "agent", name: target.agent, alias: "bb-delayed" });
    const created = await client.result("alpha", create, "create");
    const accepted = await client.post(client.session("alpha", created.session.id, "/submit"), { message: "Hello" });
    const remote = f.sessions.get(created.session.id); const finished = [...remote.messages]; remote.messages = [];
    await journal.put("delayed", { target, sessionId: created.session.id, turn: { clientRequestId: "creq_23456789ab", digest: createHash("sha256").update("Hello").digest("hex"), state: "accepted", baselineMessageIds: [], messageDigest: createHash("sha256").update("Hello").digest("hex"), ...accepted } });
    await assert.rejects(recoverThread(f.config, journal, "delayed"), /prompt.*history|history.*prompt/i);
    assert.equal((await journal.get("delayed"))?.turn?.state, "accepted");
    remote.messages = finished;
    assert.equal((await recoverThread(f.config, journal, "delayed")).turn?.state, "completed");
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await f.close(); }
});

test("reviewed recovery settles a correlated native failure without mistaking planning for success", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal")); const client = new GasCityClient(f.config.connections[0]!);
  try {
    const create = await client.post(client.city("alpha", "/sessions"), { kind: "agent", name: target.agent, alias: "bb-native-error" });
    const created = await client.result("alpha", create, "create");
    const accepted = await client.post(client.session("alpha", created.session.id, "/submit"), { message: "Hello" });
    const remote = f.sessions.get(created.session.id);
    remote.messages.push({ id: "error", role: "system", status: "final", system_event: { kind: "error", category: "provider_error", message: "Provider failed" }, blocks: [{ type: "text", text: "Provider failed" }] });
    await journal.put("native-error", { target, sessionId: created.session.id, turn: { clientRequestId: "creq_23456789ab", digest: "digest", state: "accepted", baselineMessageIds: [], messageDigest: createHash("sha256").update("Hello").digest("hex"), ...accepted } });
    const recovered = await recoverThread(f.config, journal, "native-error");
    assert.equal(recovered.turn?.state, "failed");
    assert.equal((await journal.get("native-error"))?.turn?.state, "failed");
    assert.equal(recovered.turn?.request_id, accepted.request_id);
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await f.close(); }
});

test("recovery leaves unfinished native outcomes uncertain and ignores baseline errors", async () => {
  const f = await fixture(); const journal = new Journal(join(f.cwd, "journal")); const client = new GasCityClient(f.config.connections[0]!);
  try {
    const create = await client.post(client.city("alpha", "/sessions"), { kind: "agent", name: target.agent, alias: "bb-recovery-guards" });
    const created = await client.result("alpha", create, "create");
    const accepted = await client.post(client.session("alpha", created.session.id, "/submit"), { message: "Hello" });
    const remote = f.sessions.get(created.session.id);
    const [prompt, answer] = remote.messages;
    const error = { id: "error", role: "system", status: "final", system_event: { kind: "error", category: "provider_error", message: "Native failure" }, blocks: [] };
    const receipt: any = { target, sessionId: created.session.id, turn: { clientRequestId: "creq_23456789ab", digest: "digest", state: "accepted", baselineMessageIds: [], messageDigest: createHash("sha256").update("Hello").digest("hex"), ...accepted } };
    for (const messages of [
      [prompt, answer, { ...error, status: "partial" }],
      [prompt, answer, { ...error, system_event: { kind: "retry", category: "provider_retry" } }],
      [prompt, { ...answer, status: "partial" }, error],
      [prompt, { ...answer, blocks: [{ type: "tool_use", id: "unclosed", name: "Bash" }] }, error],
    ]) {
      remote.messages = messages;
      await journal.put("guards", receipt);
      await assert.rejects(recoverThread(f.config, journal, "guards"), /no settled outcome/);
      assert.equal((await journal.get("guards"))?.turn?.state, "accepted");
    }
    remote.messages = [error, prompt, answer];
    await journal.put("guards", { ...receipt, turn: { ...receipt.turn, baselineMessageIds: [error.id] } });
    assert.equal((await recoverThread(f.config, journal, "guards")).turn?.state, "completed");
    remote.messages = [prompt, error, answer];
    await journal.put("guards", receipt);
    assert.equal((await recoverThread(f.config, journal, "guards")).turn?.state, "completed", "later real success wins over an earlier native error");
    assert.equal(f.calls.filter(c => c.path.endsWith("/submit")).length, 1);
  } finally { await f.close(); }
});

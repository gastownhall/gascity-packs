import test from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { GasCityProvider } from "../src/provider.js";
import { Journal } from "../src/journal.js";
import { targetId } from "../src/catalog.js";
import { fixture, options } from "./fixture.js";

test("native New thread lists mapped rigs before BB has provisioned its cwd", async () => {
  const f = await fixture();
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  try {
    const catalog: any = await provider.dispatch("model/list", {});
    const ids = catalog.models.map((row: any) => row.id);
    const target = { v: 1 as const, connection: "local", city: "alpha", agent: "web/review.reviewer" };
    assert.ok(ids.includes(targetId(target)), "Mapped rig must be selectable before a native thread exists");
    assert.ok(!ids.includes(targetId({ ...target, agent: "api/review.reviewer" })), "Unmapped rigs stay unavailable");
    const scoped: any = await provider.dispatch("model/list", { cwd: f.cwd });
    assert.equal(scoped.models.length, 2, "Actual workspace still narrows the catalog");
  } finally { await provider.close(); await f.close(); }
});

test("native project creation and restore resolve scope from BB's actual cwd", async () => {
  const f = await fixture();
  const provider = new GasCityProvider({ send: () => {}, config: async () => f.config, journal: new Journal(join(f.cwd, "journal")) });
  const target = { v: 1 as const, connection: "local", city: "alpha", agent: "web/review.reviewer" };
  const execution = { ...options, model: targetId(target) };
  try {
    const start: any = await provider.dispatch("thread/start", { threadId: "native-rig", cwd: f.cwd, instructionMode: "append", options: execution });
    assert.equal(f.calls.find(c => c.path.endsWith("/sessions") && c.method === "POST")?.body.project_id, "project-web");
    await provider.dispatch("thread/stop", { threadId: "native-rig", providerThreadId: start.providerThreadId, intent: "release", activeTurnId: null });
    const resumed: any = await provider.dispatch("thread/resume", { threadId: "native-rig", providerThreadId: start.providerThreadId, cwd: f.cwd, instructionMode: "append", options: execution });
    assert.equal(resumed.providerThreadId, start.providerThreadId);
    await assert.rejects(provider.dispatch("thread/start", { threadId: "wrong-rig", cwd: f.cwd, instructionMode: "append", options: { ...execution, model: targetId({ ...target, agent: "api/review.reviewer" }) } }), /outside/);
    assert.equal(f.sessions.size, 1, "Another rig must be rejected before creation");
  } finally { await provider.close(); await f.close(); }
});

import test from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./fixture.js";
import { createLauncherHostHandlers } from "../src/launcher-host.js";

test("launcher validates the exact mapped agent and existing workspace before launch", async () => {
  const f = await fixture();
  try {
    const host = createLauncherHostHandlers(async () => f.config);
    const context = { signal: new AbortController().signal };
    const catalog = await host.catalog({ projectId: "project-web" }, context);
    const agent = catalog.agents.find(a => a.name === "web/review.reviewer")!;
    assert.ok(agent);
    assert.equal(agent.workspacePath, await (await import("node:fs/promises")).realpath(f.cwd));
    assert.deepEqual(await host.validate({ projectId: "project-web", model: agent.id, workspacePath: f.cwd }, context), { model: agent.id, workspacePath: agent.workspacePath });
    await assert.rejects(host.validate({ projectId: null, model: agent.id, workspacePath: f.cwd }, context), /unavailable|outside/);
    assert.equal(f.calls.filter(c => c.method === "POST").length, 0);
  } finally { await f.close(); }
});

test("server launch pins explicit Gas City selection and revalidates on the chosen host", async () => {
  const { registerLauncher } = await import("../src/launcher-server.js");
  let handlers: any, spawned: any;
  const calls: any[] = [];
  const bb: any = {
    rpc: { register(_contract: unknown, value: unknown) { handlers = value; } },
    hosts: { experimental_client: () => ({ async call(method: string, input: any, options: any) { calls.push({ method, input, options }); return { model: input.model, workspacePath: "/existing/rig" }; } }) },
    sdk: { hosts: { list: async () => [{ id: "host-a", name: "A", status: "connected", maxPermissionMode: "full" }] }, projects: { list: async () => [{ id: "project-web", name: "Web", kind: "standard" }] }, threads: { spawn: async (args: unknown) => { spawned = args; return { id: "thread-created" }; } } },
    onDispose() {},
  };
  registerLauncher(bb);
  assert.deepEqual(await handlers.launch({ hostId: "host-a", projectId: "project-web", model: "exact-agent", workspacePath: "/existing/rig", prompt: "Review this" }), { threadId: "thread-created" });
  assert.equal(calls[0].options.hostId, "host-a");
  assert.deepEqual(calls[0].input, { projectId: "project-web", model: "exact-agent", workspacePath: "/existing/rig" });
  assert.equal(spawned.providerId, "gas-city");
  assert.equal(spawned.model, "exact-agent");
  assert.deepEqual(spawned.executionInputSources, { providerId: "explicit", model: "explicit", permissionMode: "explicit", reasoningLevel: "explicit" });
  assert.deepEqual(spawned.environment, { type: "host", hostId: "host-a", workspace: { type: "unmanaged", path: "/existing/rig" } });
  spawned = undefined;
  const failure = await handlers.launch({ hostId: "missing", projectId: "project-web", model: "exact-agent", workspacePath: "/existing/rig", prompt: "Review this" });
  assert.equal(failure.uncertain, false);
  assert.match(failure.error, /host.*unavailable/i);
  const personal = await handlers.launch({ hostId: "host-a", projectId: null, model: "exact-agent", workspacePath: "/existing/rig", prompt: "Review this" });
  assert.equal(personal.uncertain, false);
  assert.match(personal.error, /standard BB project/);
  assert.equal(spawned, undefined);
  bb.sdk.threads.spawn = async () => { throw new Error("lost create response"); };
  const lost = await handlers.launch({ hostId: "host-a", projectId: "project-web", model: "exact-agent", workspacePath: "/existing/rig", prompt: "Review this" });
  assert.equal(lost.uncertain, true);
});

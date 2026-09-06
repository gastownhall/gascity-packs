import test from "node:test";
import assert from "node:assert/strict";
import { configSchema, bindingFor } from "../src/config.js";
import { discover, targetId, parseTarget } from "../src/catalog.js";
import { fixture } from "./fixture.js";

test("projectless globals, mapped rig plus its city's globals, scale-zero templates, unique IDs", async () => {
  const f = await fixture();
  try {
    const global = await discover(f.config, { projectId: null });
    assert.equal(global.agents.length, 2);
    assert.equal(new Set(global.agents.map(targetId)).size, 2);
    assert.ok(global.agents.every(a => !a.rig));
    const project = await discover(f.config, { projectId: "project-web" });
    assert.deepEqual(project.agents.map(a => a.agent).sort(), ["gc.mayor", "web/review.reviewer"]);
    assert.equal((await discover(f.config, { cwd: f.cwd })).agents.length, 2);
    assert.equal(global.agents[0]?.isPool, true);
    assert.ok(global.warnings.some(w => w.includes("generic rig")));
    await assert.rejects(discover(f.config, { projectId: "unmapped" }), /not mapped/);
    for (const a of global.agents) assert.equal(targetId(parseTarget(targetId(a))), targetId(a));
    assert.throws(() => parseTarget("gc.mayor"), /exact/);
  } finally { await f.close(); }
});

test("binding ambiguity and insecure/config-embedded credential URLs are rejected", async () => {
  const f = await fixture();
  try {
    await assert.rejects(bindingFor({ ...f.config, bindings: [...f.config.bindings, { ...f.config.bindings[0]!, projectId: "other" }] }, { cwd: f.cwd }), /multiple/);
    for (const url of ["http://example.org", "https://secret@example.org", "https://example.org?token=secret"]) assert.equal(configSchema.safeParse({ ...f.config, connections: [{ id: "local", url }] }).success, false);
  } finally { await f.close(); }
});

test("stale bindings warn without hiding valid projects or losing recreated paths", async () => {
  const f = await fixture();
  try {
    const { mkdir } = await import("node:fs/promises");
    const stale = { ...f.config.bindings[0]!, projectId: "old", paths: [`${f.cwd}/old-worktree`] };
    const config = { ...f.config, bindings: [stale, ...f.config.bindings] };
    const catalog = await discover(config, { cwd: f.cwd });
    assert.equal(catalog.binding?.projectId, "project-web");
    assert.ok(catalog.warnings.some(w => w.includes("old-worktree") && w.includes("gc bb bind")));
    assert.equal(config.bindings[0], stale);
    await mkdir(stale.paths[0]!);
    assert.equal((await bindingFor(config, { cwd: stale.paths[0]! }))?.projectId, "old");
  } finally { await f.close(); }
});

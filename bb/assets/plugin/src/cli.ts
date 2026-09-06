import { parseArgs } from "node:util";
import { realpath, readdir, readFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { join } from "node:path";
import { configPath, readConfig, saveConfig, statePath, type Config } from "./config.js";
import { discover, targetId } from "./catalog.js";
import { GasCityClient } from "./client.js";
import { Journal } from "./journal.js";
import { recoverThread } from "./recovery.js";

async function main() {
  const command = process.argv[2];
  const { values } = parseArgs({ args: process.argv.slice(3), strict: true, options: {
    id: { type: "string" }, url: { type: "string" }, project: { type: "string" },
    city: { type: "string" }, rig: { type: "string" }, path: { type: "string", multiple: true },
    cwd: { type: "string" }, json: { type: "boolean" }, thread: { type: "string" },
    "workspace-policy": { type: "string" }, "confirm-reviewed": { type: "boolean" },
    "request-id": { type: "string" }, "event-cursor": { type: "string" },
  } });
  if (command === "connect") {
    if (!values.url) throw new Error("Usage: gc bb connect --id local --url http://127.0.0.1:8372");
    const connection = { id: values.id ?? "local", url: values.url };
    let config: Config;
    try { config = await readConfig(); }
    catch (error) {
      if (!(error as Error).message.includes("is not configured")) throw error;
      config = { version: 1, workspacePolicy: "require-match", connections: [], bindings: [] };
    }
    config.connections = [...config.connections.filter(c => c.id !== connection.id), connection];
    if (values["workspace-policy"]) config.workspacePolicy = values["workspace-policy"] as Config["workspacePolicy"];
    // Validate the URL before contacting it; save only after the health probe succeeds.
    const { configSchema } = await import("./config.js");
    configSchema.parse(config);
    const health = await new GasCityClient(connection).health();
    await saveConfig(config);
    console.log(`Connected ${connection.id} to Gas City ${health.version}. Configuration: ${configPath()}`);
    return;
  }
  const config = await readConfig();
  if (command === "bind") {
    if (!values.project || !values.city || !values.rig || !values.path?.length) throw new Error("Usage: gc bb bind --project <BB-project-ID> --id local --city <city> --rig <rig> --path <checkout> [--path <worktree>]");
    if (values.project === "proj_personal") throw new Error("BB's personal project stays projectless; bind a standard BB project.");
    const connection = config.connections.find(c => c.id === (values.id ?? "local"));
    if (!connection) throw new Error("Unknown connection; run gc bb connect");
    const client = new GasCityClient(connection);
    const city = await client.get(client.city(values.city, "/config"));
    if (!city.rigs?.some((r: any) => r.name === values.rig && !r.suspended)) throw new Error("Rig is absent or suspended in that city");
    const binding = { projectId: values.project, connection: connection.id, city: values.city, rig: values.rig, paths: await Promise.all(values.path.map(p => realpath(p))) };
    config.bindings = [...config.bindings.filter(b => b.projectId !== binding.projectId), binding];
    await saveConfig(config);
    console.log(`Mapped ${binding.projectId} to ${binding.city}/${binding.rig} on ${binding.connection}. BB may cache this catalog for 10 minutes; restart the BB server for an immediate refresh. gc bb agents always discovers afresh.`);
    return;
  }
  if (command === "agents") {
    const context = values.project ? { projectId: values.project } : values.cwd ? { cwd: values.cwd } : { projectId: null };
    const catalog = await discover(config, context);
    const agents = catalog.agents.map(a => ({ ...a, id: targetId(a) }));
    if (values.json) console.log(JSON.stringify({ agents, warnings: catalog.warnings }, null, 2));
    else {
      for (const agent of agents) console.log(`${agent.displayName}\n  ${agent.id}`);
      for (const warning of catalog.warnings) console.error(warning);
    }
    return;
  }
  if (command === "status" || command === "doctor") {
    const checks = await Promise.all(config.connections.map(async c => {
      try { const health = await new GasCityClient(c).health(); return { id: c.id, ok: true, version: health.version }; }
      catch (error) { return { id: c.id, ok: false, error: (error as Error).message }; }
    }));
    const bindingChecks = await Promise.all(config.bindings.map(async binding => {
      try {
        await discover(config, { projectId: binding.projectId });
        await Promise.all(binding.paths.map(p => realpath(p)));
        return { projectId: binding.projectId, ok: true };
      } catch (error) { return { projectId: binding.projectId, ok: false, error: (error as Error).message }; }
    }));
    const directory = join(statePath(), "sessions");
    const names = await readdir(directory).catch(error => { if (error.code === "ENOENT") return []; throw error; });
    const receipts = await Promise.all(names.filter(n => /^[a-f0-9]{64}\.json$/.test(n)).map(async name => {
      const path = join(directory, name);
      try {
        const receipt = JSON.parse(await readFile(path, "utf8"));
        return { path, threadId: receipt.threadId ?? null, sessionId: receipt.sessionId ?? null, state: receipt.turn?.state ?? "created", needsRecovery: !receipt.sessionId || !!receipt.turn && !["completed", "failed"].includes(receipt.turn.state) };
      } catch (error) { return { path, needsRecovery: true, error: (error as Error).message }; }
    }));
    let registration;
    try {
      const { stdout } = await promisify(execFile)("bb", ["plugin", "list", "--json"], { timeout: 15_000 });
      const plugin = JSON.parse(stdout).plugins?.find((p: any) => p.id === "gas-city");
      registration = { ok: plugin?.status === "running", status: plugin?.status ?? "missing", detail: plugin?.statusDetail };
    } catch (error) { registration = { ok: false, status: "unavailable", detail: (error as Error).message }; }
    const healthy = checks.every(c => c.ok) && bindingChecks.every(c => c.ok) && registration.ok;
    if (values.json) console.log(JSON.stringify({ config: configPath(), workspacePolicy: config.workspacePolicy, connections: checks, bindings: config.bindings, bindingChecks, registration, journal: directory, receipts }, null, 2));
    else {
      console.log(healthy ? "BB provider is ready" : "BB provider needs attention");
      for (const check of checks) console.log(`${check.id}: ${check.ok ? `Gas City ${check.version}` : check.error}`);
      console.log(`Workspace policy: ${config.workspacePolicy}; ${config.bindings.length} project binding(s)`);
      console.log(`BB registration: ${registration.status}${registration.detail ? ` — ${registration.detail}` : ""}`);
      for (const check of bindingChecks) if (!check.ok) console.log(`Project ${check.projectId}: ${check.error}`);
      for (const receipt of receipts) if (receipt.needsRecovery) console.log(`Unsettled receipt (may still be active): ${receipt.path}. Release the BB thread and inspect it before recovery.`);
    }
    if (!healthy) process.exitCode = 1;
    return;
  }
  if (command === "recover") {
    if (!values.thread || !values["confirm-reviewed"]) throw new Error("Inspect the complete remote transcript first, then run gc bb recover --thread <BB-thread-ID> --confirm-reviewed. This acknowledges unseen output; it never resends a prompt.");
    const journal = new Journal(join(statePath(), "sessions"));
    const receipt = await recoverThread(config, journal, values.thread, { requestId: values["request-id"], eventCursor: values["event-cursor"] });
    console.log(`Recovered ${values.thread} → ${receipt.sessionId}. Resume the BB thread; no prompt was resent.`);
    return;
  }
  throw new Error("Commands: connect, bind, agents, status, recover");
}
main().catch(error => { console.error(`bb: ${(error as Error).message}`); process.exitCode = 1; });

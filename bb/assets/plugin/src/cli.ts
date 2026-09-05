import { parseArgs } from "node:util";
import { realpath } from "node:fs/promises";
import { join } from "node:path";
import { configPath, readConfig, saveConfig, statePath, type Config } from "./config.js";
import { discover, targetId } from "./catalog.js";
import { GasCityClient } from "./client.js";
import { Journal } from "./journal.js";

async function main() {
  const command = process.argv[2];
  const { values } = parseArgs({ args: process.argv.slice(3), strict: true, options: {
    id: { type: "string" }, url: { type: "string" }, project: { type: "string" },
    city: { type: "string" }, rig: { type: "string" }, path: { type: "string", multiple: true },
    cwd: { type: "string" }, json: { type: "boolean" }, thread: { type: "string" },
    "workspace-policy": { type: "string" }, "confirm-reviewed": { type: "boolean" },
  } });
  if (command === "connect") {
    if (!values.url) throw new Error("Usage: gc bb connect --id local --url http://localhost:7375");
    const connection = { id: values.id ?? "local", url: values.url };
    let config: Config;
    try { config = await readConfig(); }
    catch (error) {
      if (!(error as Error).message.includes("is not configured")) throw error;
      config = { version: 1, workspacePolicy: "conversation", connections: [], bindings: [] };
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
    if (values.json) console.log(JSON.stringify({ config: configPath(), workspacePolicy: config.workspacePolicy, connections: checks, bindings: config.bindings, journal: join(statePath(), "sessions") }, null, 2));
    else {
      console.log(checks.every(c => c.ok) ? "BB provider connections are healthy" : "One or more BB provider connections need attention");
      for (const check of checks) console.log(`${check.id}: ${check.ok ? `Gas City ${check.version}` : check.error}`);
      console.log(`Workspace policy: ${config.workspacePolicy}; ${config.bindings.length} project binding(s)`);
    }
    if (checks.some(c => !c.ok)) process.exitCode = 1;
    return;
  }
  if (command === "recover") {
    if (!values.thread || !values["confirm-reviewed"]) throw new Error("Inspect the complete remote transcript first, then run gc bb recover --thread <BB-thread-ID> --confirm-reviewed. This acknowledges unseen output; it never resends a prompt.");
    const journal = new Journal(join(statePath(), "sessions"));
    await journal.locked(values.thread, async () => {
      const receipt = await journal.get(values.thread!);
      if (!receipt?.sessionId || !receipt.turn) throw new Error("No existing remote turn is recorded for this thread");
      const connection = config.connections.find(c => c.id === receipt.target.connection);
      if (!connection) throw new Error("Restore this thread's original connection first");
      const client = new GasCityClient(connection);
      const snapshot = await client.get(client.session(receipt.target.city, receipt.sessionId, "/transcript?format=structured"));
      const pending = await client.get(client.session(receipt.target.city, receipt.sessionId, "/pending"));
      if (snapshot.history?.tail_state?.activity !== "idle" || snapshot.history.tail_state.degraded || snapshot.history.tail_state.open_tool_call_ids?.length || snapshot.history.tail_state.pending_interaction_ids?.length || pending.pending) throw new Error("The remote session is still active, degraded, or awaiting a response");
      receipt.turn.state = "completed";
      await journal.put(values.thread!, receipt);
      console.log(`Acknowledged reviewed remote output for ${values.thread}. Resume the BB thread; no prompt was resent.`);
    });
    return;
  }
  throw new Error("Commands: connect, bind, agents, status, recover");
}
main().catch(error => { console.error(`bb: ${(error as Error).message}`); process.exitCode = 1; });

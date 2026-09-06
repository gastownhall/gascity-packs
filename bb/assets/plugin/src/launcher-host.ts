import { realpath, stat } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { readConfig, type Config } from "./config.js";
import { discover, targetId } from "./catalog.js";
import { GasCityClient } from "./client.js";
import type { LaunchCatalog } from "./launcher-contract.js";

// All filesystem checks execute on the selected BB host, never the server.
export function createLauncherHostHandlers(loadConfig: () => Promise<Config> = readConfig) {
  async function catalog(input: { projectId: string | null }, context: { signal: AbortSignal }): Promise<LaunchCatalog> {
    context.signal.throwIfAborted();
    const config = await loadConfig();
    const found = await discover(config, input, connection => new GasCityClient(connection, (url, init) => fetch(url, { ...init, signal: init?.signal ? AbortSignal.any([init.signal, context.signal]) : context.signal })));
    const result: LaunchCatalog = { agents: [], warnings: found.warnings, workspacePolicy: config.workspacePolicy };
    const cities = new Map<string, { path: string; config: any }>();
    for (const agent of found.agents) {
      context.signal.throwIfAborted();
      const key = JSON.stringify([agent.connection, agent.city]);
      let city = cities.get(key);
      if (!city) {
        const client = new GasCityClient(config.connections.find(c => c.id === agent.connection)!);
        const rows = await client.get<{ items: { name: string; path?: string }[] }>("/v0/cities", context.signal);
        city = { path: rows.items.find(c => c.name === agent.city)?.path ?? "", config: await client.get(client.city(agent.city, "/config"), context.signal) };
        cities.set(key, city);
      }
      const rigPath = city.config.rigs?.find((r: any) => r.name === agent.rig)?.path;
      let workspacePath: string | null = null, unavailableReason: string | null = null;
      try {
        // GC 1.4 expanded config omits effective work_dir. This is a suggestion;
        // the provider compares the created session work_dir before sending input.
        const path = agent.rig ? rigPath : city.path;
        if (!path || path.includes("{{")) throw new Error("This agent needs a runtime-created workspace. Choose an agent with an existing, fixed work directory.");
        if (!isAbsolute(path) && !isAbsolute(city.path)) throw new Error("Gas City did not report an absolute city path.");
        workspacePath = await realpath(isAbsolute(path) ? path : resolve(city.path, path));
        if (!(await stat(workspacePath)).isDirectory()) throw new Error("The agent workspace is not a directory.");
      } catch (error) {
        workspacePath = null;
        unavailableReason = `Workspace unavailable on this BB host: ${(error as Error).message}`;
      }
      result.agents.push({ id: targetId(agent), name: agent.agent, group: `${agent.connection} · ${agent.city} · ${agent.rig || "Global"}`, provider: agent.provider, workspacePath, unavailableReason });
    }
    context.signal.throwIfAborted();
    return result;
  }
  return {
    catalog,
    async validate(input: { projectId: string | null; model: string; workspacePath: string }, context: { signal: AbortSignal }) {
      const fresh = await catalog({ projectId: input.projectId }, context);
      if (fresh.workspacePolicy !== "require-match") throw new Error("Enable require-match on this host before coding: gc bb connect --workspace-policy require-match (include your connection URL).");
      const agent = fresh.agents.find(a => a.id === input.model);
      if (!agent) throw new Error("The selected Gas City agent is unavailable or outside this project. Refresh and choose again.");
      if (!isAbsolute(input.workspacePath)) throw new Error("Choose an absolute existing workspace path on the selected host.");
      const workspacePath = await realpath(input.workspacePath);
      if (!(await stat(workspacePath)).isDirectory()) throw new Error("The selected workspace is not a directory.");
      return { model: agent.id, workspacePath };
    },
  };
}

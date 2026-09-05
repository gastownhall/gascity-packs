import { z } from "zod";
import { bindingFor, type Config, type Binding } from "./config.js";
import { GasCityClient } from "./client.js";

const identity = z.string().min(1).max(500);
const targetSchema = z.object({ v: z.literal(1), connection: identity, city: identity, agent: identity }).strict();
export type Target = z.infer<typeof targetSchema>;
export interface Agent extends Target { rig: string; displayName: string; provider: string; isPool: boolean }
export const targetId = (target: Target) => `gc1_${Buffer.from(JSON.stringify(targetSchema.parse({ v: target.v, connection: target.connection, city: target.city, agent: target.agent }))).toString("base64url")}`;
export function parseTarget(value: unknown): Target {
  if (typeof value !== "string" || !/^gc1_[A-Za-z0-9_-]+$/.test(value) || value.length > 3000) throw new Error("Choose an exact Gas City agent ID from gc bb agents; model names and aliases are not agent IDs.");
  const target = targetSchema.parse(JSON.parse(Buffer.from(value.slice(4), "base64url").toString("utf8")));
  if (targetId(target) !== value) throw new Error("Noncanonical Gas City agent ID");
  return target;
}
export function inScope(target: Target, binding?: Binding): boolean {
  const rig = target.agent.includes("/") ? target.agent.slice(0, target.agent.indexOf("/")) : "";
  return binding ? target.connection === binding.connection && target.city === binding.city && (!rig || rig === binding.rig) : !rig;
}
export async function discover(config: Config, context: { projectId?: string | null; cwd?: string } = {}, makeClient = (id: Config["connections"][number]) => new GasCityClient(id)) {
  const binding = await bindingFor(config, context);
  const agents: Agent[] = [], warnings: string[] = [];
  for (const connection of config.connections.filter(c => !binding || c.id === binding.connection)) {
    try {
      const client = makeClient(connection);
      await client.health();
      const cities = await client.get<{ items: { name: string; running: boolean }[] }>("/v0/cities");
      if (binding && !cities.items.some(c => c.name === binding.city && c.running)) throw new Error(`Mapped city ${binding.city} is not running`);
      for (const city of cities.items.filter(c => c.running && (!binding || c.name === binding.city))) {
        const cfg = await client.get(client.city(city.name, "/config"));
        if (cfg.workspace?.suspended) continue;
        if (binding && !cfg.rigs?.some((r: any) => r.name === binding.rig && !r.suspended)) throw new Error(`Mapped rig ${binding.rig} is absent or suspended`);
        for (const a of cfg.agents ?? []) {
          if (a.suspended) continue;
          if (a.scope === "rig" && !a.dir) { warnings.push(`${city.name}: generic rig template ${a.name} needs an expanded rig import in v1`); continue; }
          const rig = a.dir ?? "";
          if (rig && !cfg.rigs?.some((r: any) => r.name === rig && !r.suspended)) continue;
          const target: Target = { v: 1, connection: connection.id, city: city.name, agent: rig ? `${rig}/${a.name}` : a.name };
          if (!inScope(target, binding)) continue;
          agents.push({ ...target, rig, displayName: `${city.name} · ${rig || "Global"} · ${a.name} [${connection.id}]`, provider: a.provider || cfg.workspace?.provider || "configured", isPool: a.is_pool === true });
        }
      }
    } catch (error) {
      if (binding) throw error;
      warnings.push(`${connection.id}: ${(error as Error).message}`);
    }
  }
  agents.sort((a, b) => a.displayName.localeCompare(b.displayName));
  if (!agents.length && warnings.length) throw new Error(warnings.join("\n"));
  return { agents, warnings, binding };
}
export const modelRow = (agent: Agent, index: number) => ({
  id: targetId(agent), model: targetId(agent), displayName: agent.displayName,
  description: `Gas City agent ${agent.agent}; configured runtime ${agent.provider}`,
  supportedReasoningEfforts: [], defaultReasoningEffort: "none" as const, isDefault: index === 0,
});
export async function validateTarget(config: Config, target: Target, projectId?: string | null): Promise<Agent> {
  const catalog = await discover(config, { projectId: projectId ?? null });
  const found = catalog.agents.find(a => targetId(a) === targetId(target));
  if (!found) throw new Error("The selected Gas City agent is unavailable or outside the project's city/rig. Refresh and choose again.");
  return found;
}

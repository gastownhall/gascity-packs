import { mkdir, readFile, realpath, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { randomUUID } from "node:crypto";
import { z } from "zod";

const name = z.string().trim().min(1).max(200);
export const configSchema = z.object({
  version: z.literal(1),
  workspacePolicy: z.enum(["conversation", "require-match"]).default("require-match"),
  connections: z.array(z.object({ id: name, url: z.string().url() }).strict()).min(1),
  bindings: z.array(z.object({
    projectId: name, connection: name, city: name, rig: name,
    paths: z.array(z.string().refine(isAbsolute, "Expected an absolute checkout path")).min(1),
  }).strict()).default([]),
}).strict().superRefine((value, ctx) => {
  if (new Set(value.connections.map(c => c.id)).size !== value.connections.length)
    ctx.addIssue({ code: "custom", message: "Connection IDs must be unique" });
  const keys = value.bindings.map(b => b.projectId);
  if (new Set(keys).size !== keys.length)
    ctx.addIssue({ code: "custom", message: "One binding per BB project on this host is supported" });
  for (const c of value.connections) {
    const url = new URL(c.url);
    if (url.username || url.password || url.search || url.hash ||
      !["http:", "https:"].includes(url.protocol) ||
      (url.protocol === "http:" && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))
      ctx.addIssue({ code: "custom", message: "Use loopback HTTP or an authorized HTTPS proxy, without URL credentials/query/fragment" });
  }
  for (const b of value.bindings) if (!value.connections.some(c => c.id === b.connection))
    ctx.addIssue({ code: "custom", message: `Binding ${b.projectId} uses an unknown connection` });
});
export type Config = z.infer<typeof configSchema>;
export type Binding = Config["bindings"][number];
export type Connection = Config["connections"][number];
export const configPath = () => process.env.GC_BB_CONFIG ?? join(process.env.XDG_CONFIG_HOME ?? join(homedir(), ".config"), "gascity", "bb.json");
export const statePath = () => join(process.env.XDG_STATE_HOME ?? join(homedir(), ".local", "state"), "gascity", "bb");
export async function readConfig(path = configPath()): Promise<Config> {
  try { return configSchema.parse(JSON.parse(await readFile(path, "utf8"))); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT")
      throw new Error(`Gas City connection is not configured. Run gc bb connect first (${path}).`);
    throw error;
  }
}
export async function atomicJson(path: string, value: unknown): Promise<void> {
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  const temp = `${path}.${randomUUID()}.tmp`;
  await writeFile(temp, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600, flag: "wx" });
  await rename(temp, path);
}
export async function saveConfig(value: unknown, path = configPath()): Promise<void> {
  await atomicJson(path, configSchema.parse(value));
}
export async function bindingFor(config: Config, context: { projectId?: string | null; cwd?: string }, warn: (message: string) => void = console.warn): Promise<Binding | undefined> {
  if (context.projectId !== undefined) {
    if (context.projectId === null || context.projectId === "proj_personal") return undefined;
    const binding = config.bindings.find(b => b.projectId === context.projectId);
    if (!binding) throw new Error(`BB project ${context.projectId} is not mapped. Run gc bb bind.`);
    return binding;
  }
  if (!context.cwd) return undefined;
  const cwd = await realpath(context.cwd);
  const matches: { binding: Binding; length: number }[] = [];
  for (const binding of config.bindings) for (const path of binding.paths) {
    let root: string;
    try { root = await realpath(path); }
    catch (error) {
      if (!["ENOENT", "ENOTDIR"].includes((error as NodeJS.ErrnoException).code ?? "")) throw error;
      warn(`Binding ${binding.projectId}: checkout ${path} is missing. Restore it or update gc bb bind; the saved binding is preserved.`);
      continue;
    }
    const suffix = relative(root, cwd);
    if (suffix === "" || (suffix !== ".." && !suffix.startsWith(`..${sep}`) && !isAbsolute(suffix))) matches.push({ binding, length: root.length });
  }
  matches.sort((a, b) => b.length - a.length);
  if (matches[0] && matches.some(m => m.length === matches[0]!.length && m.binding !== matches[0]!.binding))
    throw new Error("The BB workspace matches multiple project bindings; fix gc bb bind configuration.");
  return matches[0]?.binding;
}

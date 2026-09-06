import { defineRpcContract } from "@get-bb/plugin-sdk";
import { z } from "zod";

const id = z.string().min(1).max(3000);
const scope = z.object({ projectId: id.nullable() }).strict();
const launchAgent = z.object({
  id, name: id, group: id, provider: id,
  workspacePath: z.string().nullable(), unavailableReason: z.string().nullable(),
});
const catalog = z.object({ agents: z.array(launchAgent), warnings: z.array(z.string()), workspacePolicy: z.enum(["conversation", "require-match"]) });
const selection = scope.extend({ model: id, workspacePath: z.string().min(1) }).strict();
export const launcherHostContract = defineRpcContract({
  catalog: { input: scope, output: catalog },
  validate: { input: selection, output: z.object({ model: id, workspacePath: z.string() }) },
});
export const launcherContract = defineRpcContract({
  choices: { input: z.object({}).strict(), output: z.object({
    hosts: z.array(z.object({ id, name: z.string(), connected: z.boolean() })),
    projects: z.array(z.object({ id, name: z.string(), personal: z.boolean() })),
  }) },
  catalog: { input: scope.extend({ hostId: id }).strict(), output: catalog },
  launch: { input: selection.extend({ hostId: id, prompt: z.string().trim().min(1).max(100_000) }).strict(), output: z.union([z.object({ threadId: id }), z.object({ error: z.string(), uncertain: z.boolean() })]) },
});
export type LaunchCatalog = z.infer<typeof catalog>;

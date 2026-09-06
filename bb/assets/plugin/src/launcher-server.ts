import type { BbPluginApi } from "@get-bb/plugin-sdk";
import { launcherContract, launcherHostContract } from "./launcher-contract.js";

export function registerLauncher(bb: BbPluginApi) {
  const lifetime = new AbortController();
  bb.onDispose(() => lifetime.abort());
  const host = bb.hosts.experimental_client({ contract: launcherHostContract });
  const signal = () => AbortSignal.any([lifetime.signal, AbortSignal.timeout(60_000)]);
  async function validateScope(hostId: string, projectId: string | null) {
    const [hosts, projects] = await Promise.all([bb.sdk.hosts.list(), bb.sdk.projects.list({ includePersonal: true })]);
    const selectedHost = hosts.find(h => h.id === hostId && h.status === "connected");
    if (!selectedHost) throw new Error("The selected BB host is unavailable. Refresh and choose a connected host.");
    if (selectedHost.maxPermissionMode !== "full") throw new Error("Gas City requires a BB host with full permission mode.");
    const project = projects.find(p => projectId === null ? p.kind === "personal" : p.id === projectId);
    if (!project || project.kind === "personal") throw new Error("Choose a standard BB project with an existing workspace; personal projects cannot adopt unmanaged workspaces.");
    return project;
  }
  bb.rpc.register(launcherContract, {
    async choices() {
      const [hosts, projects] = await Promise.all([bb.sdk.hosts.list(), bb.sdk.projects.list({ includePersonal: true })]);
      return {
        hosts: hosts.map(h => ({ id: h.id, name: h.name, connected: h.status === "connected" })),
        projects: projects.filter(p => p.kind !== "personal").map(p => ({ id: p.id, name: p.name, personal: p.kind === "personal" })),
      };
    },
    async catalog({ hostId, projectId }) {
      await validateScope(hostId, projectId);
      return host.call("catalog", { projectId }, { hostId, signal: signal() });
    },
    async launch({ hostId, projectId, model, workspacePath, prompt }) {
      let checked: { model: string; workspacePath: string }, project;
      try {
        project = await validateScope(hostId, projectId);
        checked = await host.call("validate", { projectId, model, workspacePath }, { hostId, signal: signal() });
      } catch (error) {
        return { error: (error as Error).message, uncertain: false };
      }
      try {
        const thread = await bb.sdk.threads.spawn({
          projectId: project.id, providerId: "gas-city", model: checked.model,
          input: [{ type: "text", text: prompt, mentions: [] }], permissionMode: "full", reasoningLevel: "none",
          executionInputSources: { providerId: "explicit", model: "explicit", permissionMode: "explicit", reasoningLevel: "explicit" },
          environment: { type: "host", hostId, workspace: { type: "unmanaged", path: checked.workspacePath } },
        });
        return { threadId: thread.id };
      } catch (error) {
        return { error: (error as Error).message, uncertain: true };
      }
    },
  });
}

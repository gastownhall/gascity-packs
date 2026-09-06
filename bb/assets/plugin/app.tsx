import { useEffect, useRef, useState } from "react";
import { definePluginApp, useBbNavigate, useRpc } from "@get-bb/plugin-sdk/app";
import type { PluginRpcResult } from "@get-bb/plugin-sdk/app";
import type { launcherContract, LaunchCatalog } from "./src/launcher-contract.js";

type Choices = PluginRpcResult<typeof launcherContract.choices>;

// Native controls share BB's font and theme, including dark mode and focus rings.
export function GasCityLauncher() {
  const rpc = useRpc<typeof launcherContract>();
  const navigate = useBbNavigate();
  const [choices, setChoices] = useState<Choices>();
  const [hostId, setHostId] = useState("");
  const [project, setProject] = useState("");
  const [model, setModel] = useState("");
  const [workspacePath, setWorkspacePath] = useState("");
  const [prompt, setPrompt] = useState("");
  const [catalog, setCatalog] = useState<LaunchCatalog>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current++; }; }, []);
  useEffect(() => {
    let current = true;
    rpc.call("choices", {}).then(value => { if (current) setChoices(value); }).catch(cause => { if (current) setError(String(cause.message ?? cause)); });
    return () => { current = false; };
  }, [rpc, revision]);
  useEffect(() => {
    const request = ++generation.current;
    setCatalog(undefined); setError("");
    if (!hostId || !project) { setLoading(false); return; }
    setLoading(true);
    rpc.call("catalog", { hostId, projectId: project === "globals" ? null : project }).then(value => {
      if (request === generation.current) setCatalog(value);
    }).catch(cause => {
      if (request === generation.current) setError(String(cause.message ?? cause));
    }).finally(() => { if (request === generation.current) setLoading(false); });
    return () => { generation.current++; };
  }, [rpc, hostId, project, revision]);
  const selected = catalog?.agents.find(a => a.id === model);
  const groups = [...new Set(catalog?.agents.map(a => a.group) ?? [])];
  const hostAvailable = choices?.hosts.some(h => h.id === hostId && h.connected);
  const projectAvailable = choices?.projects.some(p => project === "globals" ? p.personal : p.id === project);
  const canLaunch = selected && hostAvailable && projectAvailable && workspacePath.trim() && prompt.trim() && catalog?.workspacePolicy === "require-match" && !loading && !starting && !uncertain;
  function changeScope(change: () => void) { generation.current++; setCatalog(undefined); setModel(""); setWorkspacePath(""); change(); }
  async function launch() {
    if (!canLaunch) return;
    setStarting(true); setError("");
    try {
      const result = await rpc.call("launch", { hostId, projectId: project === "globals" ? null : project, model, workspacePath: workspacePath.trim(), prompt });
      if (mounted.current) {
        if ("threadId" in result) navigate.toThread(result.threadId);
        else {
          setError(result.error);
          setUncertain(result.uncertain);
        }
      }
    } catch (cause) {
      if (mounted.current) {
        setError(`${String((cause as Error).message ?? cause)} Check BB’s thread list before starting another conversation; creation may have reached the server.`);
        setUncertain(true);
      }
    } finally { if (mounted.current) setStarting(false); }
  }
  return <main className="gc-launcher">
    <style>{`
      .gc-launcher { font-family: inherit; color: var(--foreground); background: var(--background); overflow: auto; height: 100%; padding: clamp(20px, 4vw, 48px); }
      .gc-launcher * { box-sizing: border-box; }
      .gc-launcher .gc-content { max-width: 700px; margin: 0 auto; }
      .gc-launcher h1 { font-size: 24px; font-weight: 600; letter-spacing: -.025em; margin: 0 0 8px; }
      .gc-launcher p { color: var(--muted-foreground); font-size: 14px; line-height: 1.55; margin: 8px 0 18px; }
      .gc-launcher form { display: grid; gap: 20px; margin-top: 28px; }
      .gc-launcher .gc-row { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 16px; }
      .gc-launcher label { display: grid; gap: 8px; font-size: 13px; font-weight: 500; }
      .gc-launcher input, .gc-launcher select, .gc-launcher textarea { width: 100%; font: inherit; font-size: 14px; font-weight: 400; color: var(--foreground); background: var(--background); border: 1px solid var(--border); border-radius: 7px; padding: 10px 12px; }
      .gc-launcher textarea { resize: vertical; min-height: 128px; }
      .gc-launcher button { font: inherit; font-size: 13px; border-radius: 7px; padding: 9px 14px; cursor: pointer; border: 1px solid var(--border); color: var(--foreground); background: var(--background); }
      .gc-launcher button[type=submit] { background: var(--primary); color: var(--primary-foreground); border-color: var(--primary); }
      .gc-launcher :disabled { opacity: .5; cursor: not-allowed; }
      .gc-launcher :is(input,select,textarea,button,summary):focus-visible { outline: 2px solid var(--ring); outline-offset: 3px; }
      .gc-launcher .gc-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
      .gc-launcher .gc-note { font-size: 12px; color: var(--muted-foreground); font-weight: 400; line-height: 1.5; overflow-wrap: anywhere; }
      .gc-launcher .gc-error { border: 1px solid var(--destructive); border-radius: 7px; padding: 12px; margin-top: 18px; font-size: 13px; overflow-wrap: anywhere; white-space: pre-wrap; }
      .gc-launcher details { border-top: 1px solid var(--border); padding-top: 18px; margin-top: 28px; font-size: 13px; }
      .gc-launcher summary { cursor: pointer; }
      .gc-launcher code { font-family: var(--font-mono, monospace); font-size: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
      @media(max-width: 520px) { .gc-launcher .gc-row { grid-template-columns: 1fr; } }
    `}</style>
    <div className="gc-content">
      <h1>Gas City</h1>
      <p>Start a conversation with a configured agent. Choose its host and project, then use the workspace where the agent works.</p>
      <form onSubmit={event => { event.preventDefault(); void launch(); }}>
        <div className="gc-row">
          <label>Host<select aria-label="Host" value={hostId} disabled={starting || uncertain} onChange={e => changeScope(() => setHostId(e.target.value))}>
            <option value="">Choose a host</option>
            {hostId && !choices?.hosts.some(h => h.id === hostId) && <option value={hostId}>Selected host unavailable</option>}
            {choices?.hosts.map(h => <option key={h.id} value={h.id} disabled={!h.connected}>{h.name}{!h.connected ? " · offline" : ""}</option>)}
          </select></label>
          <label>Project<select aria-label="Project" value={project} disabled={!hostId || starting || uncertain} onChange={e => changeScope(() => setProject(e.target.value))}>
            <option value="">Choose a project</option>
            {project && !projectAvailable && <option value={project}>Selected project unavailable</option>}
            {choices?.projects.map(p => <option key={p.id} value={p.personal ? "globals" : p.id}>{p.personal ? "Global agents · Personal" : p.name}</option>)}
          </select></label>
        </div>
        <label>Agent<select aria-label="Agent" value={model} disabled={!catalog || starting || uncertain} onChange={e => { setModel(e.target.value); setWorkspacePath(catalog?.agents.find(a => a.id === e.target.value)?.workspacePath ?? ""); }}>
          <option value="">{loading ? "Loading agents…" : "Choose an exact agent"}</option>
          {model && !selected && <option value={model}>Selected agent unavailable · choose again</option>}
          {groups.map(group => <optgroup key={group} label={group}>{catalog?.agents.filter(a => a.group === group).map(a => <option key={a.id} value={a.id}>{a.name} · {a.provider}</option>)}</optgroup>)}
        </select><span className="gc-note">{selected ? `${selected.group} · ${selected.provider}` : catalog && !catalog.agents.length ? "No active agents in this scope. Check the host configuration below." : "Project agents are grouped with their city’s global agents."}</span></label>
        <label>Existing workspace<input aria-label="Existing workspace" value={workspacePath} placeholder="/absolute/path/on/selected/host" disabled={!selected || starting || uncertain} onChange={e => setWorkspacePath(e.target.value)} />
          <span className="gc-note">The suggested city or rig path may differ from the agent’s configured workspace. BB adopts this directory as an unmanaged workspace. Gas City’s actual session directory must match before your prompt is sent.</span>
          {selected?.unavailableReason && <span className="gc-note">{selected.unavailableReason} Enter an existing path on this host.</span>}
        </label>
        <label>First message<textarea aria-label="First message" value={prompt} disabled={starting || uncertain} onChange={e => setPrompt(e.target.value)} placeholder="What should this agent work on?" /></label>
        {catalog?.workspacePolicy === "conversation" && <div role="alert" className="gc-error">This host allows mismatched workspaces. Set its workspace policy to require-match to use this launcher.</div>}
        <div className="gc-actions">
          <button type="submit" disabled={!canLaunch}>{starting ? "Starting…" : "Start conversation"}</button>
          <button type="button" disabled={starting} onClick={() => setRevision(r => r + 1)}>Refresh</button>
          {loading && <button type="button" onClick={() => { generation.current++; setLoading(false); setCatalog(undefined); }}>Cancel loading</button>}
          <span role="status" className="gc-note">{loading ? "Checking the selected host…" : starting ? "Validating agent and workspace…" : ""}</span>
        </div>
      </form>
      {error && <div role="alert" className="gc-error">{error}</div>}
      {uncertain && <div className="gc-error"><p>Creation may have reached BB. Check its thread list before trying again.</p><button type="button" onClick={() => { setUncertain(false); setError(""); }}>I checked: no thread was created</button></div>}
      {catalog?.warnings.map((warning, i) => <p className="gc-note" key={i}>{warning}</p>)}
      <details><summary>Connection and project setup</summary>
        <p>Run these commands on the selected BB host. Use its Gas City supervisor URL and the BB project ID shown below. Configuration changes are picked up by Refresh.</p>
        <code>{`gc bb connect --url http://127.0.0.1:8372 --workspace-policy require-match\ngc bb bind --project ${project && project !== "globals" ? JSON.stringify(project) : "<BB-project-ID>"} --id <connection-ID> --city <city> --rig <rig> --path <checkout-path>`}</code>
        <p>Gas City controls the model, runtime, and tool approvals. This launcher sends text and requires a matching workspace. A disconnected host or missing agent must be selected again.</p>
      </details>
    </div>
  </main>;
}
export default definePluginApp(app => { app.slots.navPanel({ id: "gas-city", title: "Gas City", icon: "Building2", path: "launch", component: GasCityLauncher }); });

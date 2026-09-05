import { createHash, randomUUID } from "node:crypto";
import { realpath } from "node:fs/promises";
import { join } from "node:path";
import {
  BRIDGE_JSON_RPC_ERRORS, PROVIDER_BRIDGE_PROTOCOL_VERSION, THREAD_DELTA_GRAMMAR_V3,
  initializeParamsSchema, modelListParamsSchema, providerMaintenanceParamsSchema,
  threadStartParamsSchema, threadResumeParamsSchema, threadStopParamsSchema,
  threadDiscardParamsSchema, turnStartParamsSchema, turnSteerParamsSchema,
  type ThreadDelta, type BridgeExecutionOptions, type PromptInput,
} from "@get-bb/plugin-sdk/provider-bridge";
import { z } from "zod";
import { readConfig, statePath, type Config, type Connection } from "./config.js";
import { discover, modelRow, parseTarget, targetId, validateTarget, type Target } from "./catalog.js";
import { GasCityClient } from "./client.js";
import { Journal, type Receipt } from "./journal.js";
import { Transcript, type Frame } from "./transcript.js";

const remoteIdentity = z.object({ v: z.literal(1), target: z.object({ v: z.literal(1), connection: z.string(), city: z.string(), agent: z.string() }), sessionId: z.string().min(1) }).strict();
const encodeRemote = (target: Target, sessionId: string) => `gcs1_${Buffer.from(JSON.stringify({ v: 1, target, sessionId })).toString("base64url")}`;
function decodeRemote(value: string) {
  if (!/^gcs1_[A-Za-z0-9_-]+$/.test(value) || value.length > 5000) throw new Error("Invalid Gas City provider session ID");
  return remoteIdentity.parse(JSON.parse(Buffer.from(value.slice(5), "base64url").toString("utf8")));
}
interface LiveSession {
  threadId: string; providerThreadId: string; target: Target; sessionId: string;
  cwd: string; client: GasCityClient; projectId: string | null; warning?: string;
  controller?: AbortController; busy: boolean; turnOpen: boolean; pending: Set<string>;
}
interface Dependencies {
  send(message: any): void;
  config?: () => Promise<Config>;
  client?: (connection: Connection) => GasCityClient;
  journal?: Journal;
}
export class GasCityProvider {
  readonly sessions = new Map<string, LiveSession>();
  private readonly pendingResponses = new Map<string, { resolve(value: any): void; reject(error: Error): void }>();
  private readonly loadConfig: () => Promise<Config>;
  private readonly makeClient: (connection: Connection) => GasCityClient;
  private readonly journal: Journal;
  constructor(private readonly deps: Dependencies) {
    this.loadConfig = deps.config ?? readConfig;
    this.makeClient = deps.client ?? (connection => new GasCityClient(connection));
    this.journal = deps.journal ?? new Journal(join(statePath(), "sessions"));
  }
  private sendResult(id: string | number, result: unknown) { this.deps.send({ jsonrpc: "2.0", id, result }); }
  private emit(session: LiveSession, deltas: ThreadDelta[]) {
    if (deltas.length) this.deps.send({ jsonrpc: "2.0", method: "thread/delta", params: { threadId: session.threadId, deltas } });
  }
  handleLine(line: string): void {
    let message: any;
    try { message = JSON.parse(line); } catch { return; }
    if (!message || typeof message !== "object" || Array.isArray(message)) return;
    if (typeof message.method !== "string") {
      const pending = this.pendingResponses.get(String(message.id));
      if (pending) {
        this.pendingResponses.delete(String(message.id));
        if (message.error) pending.reject(new Error(message.error.message ?? "Interaction failed"));
        else pending.resolve(message.result);
      }
      return;
    }
    if (typeof message.id !== "string" && typeof message.id !== "number") return;
    void this.dispatch(message.method, message.params).then(
      result => this.sendResult(message.id, result),
      error => this.deps.send({ jsonrpc: "2.0", id: message.id, error: { code: error instanceof z.ZodError ? BRIDGE_JSON_RPC_ERRORS.INVALID_PARAMS : typeof error.code === "number" ? error.code : -32000, message: error.message ?? String(error) } }),
    );
  }
  private checkOptions(options: BridgeExecutionOptions, expected?: Target) {
    if (options.permissionMode !== "full") throw new Error("Gas City owns agent permissions. Select BB Full access; GC's configured permission prompts still require a response.");
    if (options.promptMode || (options.reasoningLevel && options.reasoningLevel !== "none") || options.serviceTier) throw new Error("Configure plan/model/reasoning/tier in the Gas City agent; this bridge does not override them.");
    const target = parseTarget(options.model);
    if (expected && targetId(target) !== targetId(expected)) throw new Error("An existing Gas City conversation cannot switch agents. Create a new BB thread.");
    return target;
  }
  private live(threadId: string, providerThreadId: string) {
    const live = this.sessions.get(threadId);
    if (!live || live.providerThreadId !== providerThreadId) throw new Error("Resume the matching Gas City session before sending a turn");
    return live;
  }
  async dispatch(method: string, input: unknown): Promise<unknown> {
    if (method === "initialize") {
      initializeParamsSchema.parse(input);
      return { protocolVersion: PROVIDER_BRIDGE_PROTOCOL_VERSION, capabilities: { grammarVersions: [THREAD_DELTA_GRAMMAR_V3, THREAD_DELTA_GRAMMAR_V3], sessionRestore: true, threadArchive: false, threadRename: false, threadGoalClear: false, fork: "none", approvalEnforcedBy: "provider", steerMode: "queue", skills: { configure: false } } };
    }
    if (method === "model/list") {
      const { cwd } = modelListParamsSchema.parse(input);
      const catalog = await discover(await this.loadConfig(), { cwd }, this.makeClient);
      for (const warning of catalog.warnings) process.stderr.write(`[gas-city] ${warning}\n`);
      return { models: catalog.agents.map(modelRow), selectedOnlyModels: [] };
    }
    if (method === "provider/health") {
      providerMaintenanceParamsSchema.parse(input);
      let version: string | null = null, problem: string | null = null;
      try {
        const config = await this.loadConfig();
        const results = await Promise.allSettled(config.connections.map(c => this.makeClient(c).health()));
        const ready = results.find(r => r.status === "fulfilled");
        if (ready?.status === "fulfilled") version = ready.value.version;
        else throw new Error("No configured Gas City supervisor is reachable; run gc bb status.");
      } catch (error) { problem = (error as Error).message; }
      return { supported: true, health: { status: problem ? "error" : "ready", statusMessage: problem, accountEmail: null, planLabel: null, installedVersion: version, minimumSupportedVersion: "1.4.0", canInstall: false, canUpdate: false, loginCommand: null } };
    }
    if (method === "thread/start") {
      const args = threadStartParamsSchema.parse(input);
      if (args.input?.length) this.text(args.input);
      return this.journal.locked(args.threadId, async () => {
        const config = await this.loadConfig();
        const target = this.checkOptions(args.options);
        const projectId = String(args.options.providerOptions?.projectId ?? "proj_personal");
        await validateTarget(config, target, projectId);
        const connection = config.connections.find(c => c.id === target.connection)!;
        const client = this.makeClient(connection);
        let receipt = await this.journal.get(args.threadId);
        if (receipt && targetId(receipt.target) !== targetId(target)) throw new Error("This BB thread already has a different Gas City target");
        if (receipt && !receipt.sessionId && !receipt.create) throw new Error("A prior session creation has uncertain delivery. Inspect Gas City for this BB thread's alias before retrying.");
        if (!receipt) {
          receipt = { target };
          await this.journal.put(args.threadId, receipt);
          const alias = `bb-${createHash("sha256").update(args.threadId).digest("hex").slice(0, 24)}`;
          receipt.create = await client.post(client.city(target.city, "/sessions"), { kind: "agent", name: target.agent, alias, title: `BB · ${target.agent}`, project_id: projectId });
          await this.journal.put(args.threadId, receipt);
        }
        if (!receipt.sessionId) {
          const result = await client.result(target.city, receipt.create!, "create");
          receipt.sessionId = result.session.id;
          await this.journal.put(args.threadId, receipt);
        }
        const session = await this.open(config, args.threadId, target, receipt.sessionId!, args.cwd, projectId);
        if (args.input?.length) await this.startTurn(session, args.input, args.options);
        return { providerThreadId: session.providerThreadId, sessionRestorable: true };
      });
    }
    if (method === "thread/resume") {
      const args = threadResumeParamsSchema.parse(input);
      const remote = decodeRemote(args.providerThreadId);
      this.checkOptions(args.options, remote.target);
      const receipt = await this.journal.get(args.threadId);
      if (!receipt || receipt.sessionId !== remote.sessionId || targetId(receipt.target) !== targetId(remote.target)) throw new Error("This host has no ownership receipt for that Gas City conversation; restore the original host journal.");
      if (receipt.turn && !["completed", "failed"].includes(receipt.turn.state)) throw new Error("A remote turn was interrupted or its delivery is uncertain. Inspect it in Gas City, then run gc bb recover --thread <BB-thread-id> after it is idle. No prompt has been resent.");
      const session = await this.open(await this.loadConfig(), args.threadId, remote.target, remote.sessionId, args.cwd, String(args.options.providerOptions?.projectId ?? "proj_personal"));
      return { providerThreadId: session.providerThreadId, sessionRestorable: true };
    }
    if (method === "turn/start") {
      const args = turnStartParamsSchema.parse(input);
      const session = this.live(args.threadId, args.providerThreadId);
      this.checkOptions(args.options, session.target);
      await this.startTurn(session, args.input, args.options, args.clientRequestId);
      return {};
    }
    if (method === "turn/steer") {
      turnSteerParamsSchema.parse(input);
      throw Object.assign(new Error("Gas City v1 accepts one BB turn at a time. Stop the turn or wait for it to finish before sending another prompt."), { code: BRIDGE_JSON_RPC_ERRORS.NO_ACTIVE_TURN });
    }
    if (method === "thread/stop") {
      const args = threadStopParamsSchema.parse(input);
      const session = this.live(args.threadId, args.providerThreadId);
      session.controller?.abort();
      if (args.intent === "interrupt" && session.busy) {
        await session.client.post(session.client.session(session.target.city, session.sessionId, "/stop"));
        const receipt = await this.journal.get(session.threadId);
        // If submit was still in flight, /stop cannot prove it will not arrive
        // later. Preserve that uncertain receipt for explicit recovery.
        if (session.turnOpen) {
          if (receipt?.turn) { receipt.turn.state = "failed"; await this.journal.put(session.threadId, receipt); }
          this.emit(session, [{ kind: "turn.boundary", status: "interrupted" }]);
        }
      }
      session.busy = false; session.turnOpen = false;
      if (args.intent === "release") this.sessions.delete(args.threadId);
      return {};
    }
    if (method === "thread/discard") {
      const args = threadDiscardParamsSchema.parse(input);
      const session = this.sessions.get(args.threadId);
      session?.controller?.abort(); this.sessions.delete(args.threadId);
      return {};
    }
    throw Object.assign(new Error(`Unsupported bridge method: ${method}`), { code: BRIDGE_JSON_RPC_ERRORS.METHOD_NOT_FOUND });
  }
  private async open(config: Config, threadId: string, target: Target, sessionId: string, cwd: string, projectId: string) {
    if (this.sessions.get(threadId)?.busy) throw new Error("This BB thread already has an active Gas City turn");
    const connection = config.connections.find(c => c.id === target.connection);
    if (!connection) throw new Error(`Gas City connection ${target.connection} is no longer configured`);
    const client = this.makeClient(connection);
    const remote = await client.get(client.session(target.city, sessionId));
    if (remote.template !== target.agent || remote.state === "closed") throw new Error("Gas City session template changed or the session is closed");
    let warning: string | undefined;
    if (remote.work_dir && await realpath(cwd) !== await realpath(remote.work_dir)) {
      if (config.workspacePolicy === "require-match") throw new Error(`GC works in ${remote.work_dir}; BB works in ${cwd}. Select a matching unmanaged environment before running.`);
      warning = `Gas City works in ${remote.work_dir}. This BB thread uses ${cwd}; its file and diff views are not synchronized with the agent's checkout.`;
    }
    const session: LiveSession = { threadId, target, sessionId, cwd, projectId, client, providerThreadId: encodeRemote(target, sessionId), warning, busy: false, turnOpen: false, pending: new Set() };
    this.sessions.set(threadId, session);
    this.deps.send({ jsonrpc: "2.0", method: "thread/identity", params: { threadId, providerThreadId: session.providerThreadId } });
    this.emit(session, [{ kind: "session.reset" }]);
    return session;
  }
  private text(input: readonly PromptInput[]) {
    if (input.some(i => i.type !== "text")) throw new Error("The GC 1.4 submit API accepts text. Use a same-host file path in your prompt; inline attachments and BB skill injection are not supported in v1.");
    const text = input.map(i => i.type === "text" ? i.text : "").join("\n");
    if (!text.trim()) throw new Error("A nonempty prompt is required");
    return text;
  }
  private async startTurn(session: LiveSession, input: readonly PromptInput[], options: BridgeExecutionOptions, requestId?: string) {
    if (session.busy) throw new Error("Wait for the active Gas City turn to finish");
    session.busy = true;
    session.turnOpen = false;
    const controller = new AbortController();
    session.controller = controller;
    try {
      const prompt = this.text(input);
      const operationId = requestId ?? `initial-${session.threadId}`;
      const snapshot = await session.client.get<Frame>(session.client.session(session.target.city, session.sessionId, "/transcript?format=structured"), controller.signal);
      controller.signal.throwIfAborted();
      const receipt = (await this.journal.get(session.threadId))!;
      controller.signal.throwIfAborted();
      if (receipt.turn?.clientRequestId === operationId) throw new Error("That BB prompt is already journaled; it has not been resent");
      if (receipt.turn && !["completed", "failed"].includes(receipt.turn.state)) throw new Error("The previous prompt has uncertain delivery. Inspect the remote session before retrying.");
      const message = options.instructions ? `BB session context (supplements your Gas City agent configuration):\n${options.instructions}\n\nUser request:\n${prompt}` : prompt;
      const bootstrap = !receipt.turn && (
        (snapshot.history?.tail_state.degraded && snapshot.history.transcript_stream_id === `fallback:${session.sessionId}`) ||
        (!snapshot.structured_messages?.length && snapshot.history?.tail_state.activity === "unknown"));
      const transcript = new Transcript(snapshot, bootstrap ? message : undefined);
      if ((!bootstrap && snapshot.history.tail_state.activity !== "idle") || snapshot.history.tail_state.pending_interaction_ids?.length || snapshot.history.tail_state.open_tool_call_ids?.length) throw new Error("The Gas City session is busy or needs a response; resolve it there before starting a BB turn");
      if (bootstrap) {
        const pending = await session.client.get(session.client.session(session.target.city, session.sessionId, "/pending"), controller.signal);
        if (pending.pending) throw new Error("The new Gas City session needs a response; resolve it before sending a prompt");
        controller.signal.throwIfAborted();
      }
      receipt.turn = { clientRequestId: operationId, digest: createHash("sha256").update(prompt).digest("hex"), state: "submitting" };
      await this.journal.put(session.threadId, receipt);
      controller.signal.throwIfAborted();
      const accepted = await session.client.post(session.client.session(session.target.city, session.sessionId, "/submit"), { message, intent: "default" }, controller.signal);
      receipt.turn = { ...receipt.turn, state: "accepted", request_id: accepted.request_id, event_cursor: accepted.event_cursor };
      await this.journal.put(session.threadId, receipt);
      const result = await session.client.result(session.target.city, accepted, "submit", controller.signal);
      controller.signal.throwIfAborted();
      if (result.session_id !== session.sessionId) throw new Error("Gas City submitted to an unexpected session");
      session.turnOpen = true;
      this.emit(session, [...(requestId ? [{ kind: "input.accepted" as const, clientRequestId: requestId }] : []), { kind: "turn.open" }]);
      if (session.warning) {
        const key = { providerItemId: `gc-workspace-${randomUUID()}` };
        this.emit(session, [{ kind: "item.open", key, item: { type: "agentMessage", text: session.warning } }, { kind: "item.textClose", key, channel: "agentMessage", text: session.warning }]);
        session.warning = undefined;
      }
      void this.observe(session, transcript, snapshot.history.cursor.resume_token).catch(error => this.failTurn(session, error));
    } catch (error) { session.busy = false; controller.abort(); throw error; }
  }
  private async observe(session: LiveSession, transcript: Transcript, cursor: string) {
    const controller = session.controller!;
    const startup = setTimeout(() => {
      if (transcript.waitingForPrompt) void this.failTurn(session, new Error("Gas City did not publish structured history containing the first prompt within 150 seconds. Inspect the session in Gas City."));
    }, 150_000);
    const path = session.client.session(session.target.city, session.sessionId, `/stream?format=structured&after_cursor=${encodeURIComponent(cursor)}`);
    try {
      for await (const event of session.client.events(path, controller.signal, cursor)) {
        if (controller.signal.aborted) return;
        if (event.event === "structured") {
          this.emit(session, transcript.apply(JSON.parse(event.data)));
          if (transcript.complete()) {
            const receipt = (await this.journal.get(session.threadId))!;
            receipt.turn!.state = "completed"; await this.journal.put(session.threadId, receipt);
            this.emit(session, [{ kind: "turn.boundary", status: "completed" }]);
            session.busy = false; session.turnOpen = false; controller.abort(); return;
          }
        } else if (event.event === "pending") {
          const pending = JSON.parse(event.data);
          if (!session.pending.has(pending.request_id)) {
            session.pending.add(pending.request_id);
            void this.respond(session, pending, controller.signal).catch(error => this.failTurn(session, error));
          }
        }
      }
    } finally { clearTimeout(startup); }
  }
  private async respond(session: LiveSession, pending: any, signal: AbortSignal) {
    if (pending.kind !== "approval" || pending.metadata?.source !== "tmux") throw new Error("This GC interaction type is not mapped in v1; respond in Gas City, then recover the BB thread.");
    const id = `gc-interaction-${randomUUID()}`;
    const response = new Promise<any>((resolve, reject) => {
      this.pendingResponses.set(id, { resolve, reject });
      signal.addEventListener("abort", () => { this.pendingResponses.delete(id); reject(new Error("Interaction interrupted")); }, { once: true });
    });
    this.deps.send({ jsonrpc: "2.0", id, method: "interaction/request", params: {
      threadId: session.threadId, providerThreadId: session.providerThreadId, turnId: null,
      payload: { kind: "user_question", questions: [{ id: pending.request_id, prompt: pending.prompt || "Gas City requests approval", shortLabel: "Gas City", multiSelect: false, allowFreeText: false, options: [{ value: "approve", label: "Approve once" }, { value: "deny", label: "Deny" }] }] },
    } });
    const result = await response;
    const action = result?.kind === "user_answer" ? result.answers?.[pending.request_id]?.selected?.[0] : undefined;
    if (!['approve', 'deny'].includes(action)) throw new Error("Gas City approval requires an explicit approve or deny response");
    if (!signal.aborted) await session.client.post(session.client.session(session.target.city, session.sessionId, "/respond"), { request_id: pending.request_id, action }, signal);
  }
  private async failTurn(session: LiveSession, error: Error) {
    if (session.controller?.signal.aborted) return;
    this.emit(session, [{ kind: "turn.boundary", status: "failed", error: { message: `${error.message} Remote execution may continue; no prompt will be resent automatically.` } }]);
    session.busy = false; session.turnOpen = false; session.controller?.abort();
  }
  close() { for (const session of this.sessions.values()) session.controller?.abort(); this.sessions.clear(); }
}

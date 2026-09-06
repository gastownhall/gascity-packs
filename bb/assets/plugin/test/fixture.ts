import { createServer, type ServerResponse } from "node:http";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Config } from "../src/config.js";
import type { Frame } from "../src/transcript.js";

export const options = { permissionMode: "full", permissionScope: "full", approvalReviewer: null, permissionEscalation: null, reasoningLevel: "none", serviceTier: "default" } as const;
export function frame(id: string, messages: any[] = [], activity = "idle", operation = "snapshot"): Frame {
  return { schema_version: "session.structured.v1", operation, structured_messages: messages,
    history: { transcript_stream_id: `stream-${id}`, generation: { id: "g1" }, cursor: { resume_token: `cursor-${id}-${messages.length}` }, tail_state: { activity } } };
}
export async function fixture() {
  const cwd = await mkdtemp(join(tmpdir(), "bb-gc-test-"));
  const calls: { method: string; path: string; body: any; headers: any }[] = [];
  const sessions = new Map<string, any>();
  const events: any[] = [];
  const held = new Set<ServerResponse>();
  const faults = { dropSubmitReply: false, dropCreateReply: false, workDir: "", freshHistoryFallback: false };
  let seq = 0;
  const server = createServer(async (req, res) => {
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : undefined;
    const path = decodeURIComponent(new URL(req.url!, "http://fixture").pathname);
    calls.push({ method: req.method!, path, body, headers: req.headers });
    const json = (value: unknown, status = 200) => { res.writeHead(status, { "Content-Type": "application/json" }); res.end(JSON.stringify(value)); };
    const sse = (event: string, value: unknown, id = "1") => res.write(`event: ${event}\nid: ${id}\ndata: ${JSON.stringify(value)}\n\n`);
    if (path === "/health") return json({ status: "ok", version: "1.4.0" });
    if (path === "/v0/cities") return json({ items: [{ name: "alpha", running: true }, { name: "beta", running: true }, { name: "off", running: false }], total: 3 });
    if (path.endsWith("/config")) return json({ workspace: { name: path.includes("alpha") ? "alpha" : "beta", suspended: false }, rigs: [{ name: "web", path: cwd }, { name: "api", path: cwd }], agents: [
      { name: "gc.mayor", dir: "", is_pool: true, scope: "city", provider: "claude" },
      { name: "review.reviewer", dir: "web", is_pool: true, scope: "rig", provider: "codex" },
      { name: "review.reviewer", dir: "api", is_pool: true, scope: "rig", provider: "codex" },
      { name: "disabled", dir: "", suspended: true },
      { name: "generic", dir: "", scope: "rig" },
    ] });
    if (path.endsWith("/sessions") && req.method === "POST") {
      const id = `s${sessions.size + 1}`;
      const session = { id, template: body.name, state: "running", work_dir: faults.workDir || cwd, messages: [] as any[], title: body.title, provider: "claude", session_name: body.alias, alias: body.alias, created_at: "2026-09-05T00:00:00Z", attached: false, running: true, streams: new Set<ServerResponse>() };
      sessions.set(id, session);
      const request_id = `req-${++seq}`;
      events.push({ seq, type: "request.result.session.create", payload: { request_id, session } });
      if (faults.dropCreateReply) { res.destroy(); return; }
      return json({ status: "accepted", request_id, event_cursor: String(seq - 1) }, 202);
    }
    if (path.endsWith("/events/stream")) {
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      sse("event", { type: "request.failed", payload: { request_id: "unrelated", message: "ignore me" } }, "0");
      for (const event of events) sse("event", event, String(event.seq));
      held.add(res); res.on("close", () => held.delete(res)); return;
    }
    const match = /\/session\/([^/]+)(.*)$/.exec(path);
    const session = match ? sessions.get(match[1]!) ?? [...sessions.values()].find(s => s.alias === match[1]) : undefined;
    if (!session) return json({ message: "not found" }, 404);
    const suffix = match![2];
    if (!suffix) return json(session);
    if (suffix === "/transcript") {
      if (faults.freshHistoryFallback && !session.messages.length) {
        const fallback = frame(session.id, [{ id: "terminal", role: "assistant", status: "partial", blocks: [{ type: "text", text: "Terminal startup screen" }] }], "in_turn");
        fallback.history.transcript_stream_id = `fallback:${session.id}`;
        fallback.history.tail_state.degraded = true;
        return json(fallback);
      }
      return json(frame(session.id, session.messages));
    }
    if (suffix === "/pending") return json({ supported: true });
    if (suffix === "/submit") {
      const request_id = `req-${++seq}`;
      session.hold = body.message.includes("hold");
      session.approval = body.message.includes("approval");
      session.messages.push({ id: `user-${seq}`, role: "user", status: "final", user_prompt: { text: body.message }, blocks: [{ type: "text", text: body.message }] });
      session.messages.push({ id: `m-${seq}`, role: "assistant", status: session.hold || session.approval ? "partial" : "final", blocks: [{ type: "text", text: "Hello from Gas City" }] });
      events.push({ seq, type: "request.result.session.submit", payload: { request_id, session_id: session.id, queued: false, intent: "default" } });
      if (faults.dropSubmitReply) { res.destroy(); return; }
      return json({ status: "accepted", request_id, event_cursor: String(seq - 1) }, 202);
    }
    if (suffix === "/stream") {
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      const last = session.messages.at(-1);
      if (last) sse("structured", frame(session.id, [...session.messages.slice(0, -1), { ...last, status: "partial", blocks: [{ type: "text", text: "Hello" }] }], "in_turn", "upsert"), "partial-cursor");
      if (session.approval) sse("pending", { request_id: "gc-approval-1", kind: "approval", prompt: "Run the command?", metadata: { source: "tmux" }, options: ["Yes", "No"] });
      if (!session.hold && !session.approval) {
        sse("structured", frame(session.id, session.messages, "idle", "upsert"), "final-cursor");
        sse("structured", frame(session.id, session.messages, "idle", "upsert"), "final-cursor");
      }
      held.add(res); session.streams.add(res); res.on("close", () => { held.delete(res); session.streams.delete(res); }); return;
    }
    if (suffix === "/respond") {
      session.messages.at(-1).status = "final";
      for (const stream of session.streams) stream.write(`event: structured\nid: approved\ndata: ${JSON.stringify(frame(session.id, session.messages, "idle", "upsert"))}\n\n`);
      return json({ status: "ok" });
    }
    if (suffix === "/stop") return json({ status: "ok" });
    return json({ message: "not found" }, 404);
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  const address = server.address() as { port: number };
  const config: Config = { version: 1, workspacePolicy: "require-match", connections: [{ id: "local", url: `http://127.0.0.1:${address.port}` }], bindings: [{ projectId: "project-web", connection: "local", city: "alpha", rig: "web", paths: [cwd] }] };
  return { cwd, calls, config, sessions, faults, async close() { for (const res of held) res.end(); server.closeAllConnections(); await new Promise<void>(resolve => server.close(() => resolve())); await rm(cwd, { recursive: true, force: true }); } };
}
export async function until(predicate: () => boolean, timeout = 3000) {
  const end = Date.now() + timeout;
  while (!predicate()) { if (Date.now() > end) throw new Error("Condition timed out"); await new Promise(resolve => setTimeout(resolve, 5)); }
}

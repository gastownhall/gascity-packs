import { setTimeout as delay } from "node:timers/promises";
import type { Connection } from "./config.js";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export interface SSE { event: string; id?: string; data: string }
export async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<SSE> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", event = "message", id: string | undefined, lines: string[] = [];
  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      if (buffer.length > 8 * 1024 * 1024) throw new Error("Gas City SSE frame exceeded 8 MiB");
      let end: number;
      while ((end = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, end).replace(/\r$/, ""); buffer = buffer.slice(end + 1);
        if (!line) {
          if (lines.length) yield { event, id, data: lines.join("\n") };
          event = "message"; id = undefined; lines = [];
        } else if (!line.startsWith(":")) {
          const colon = line.indexOf(":");
          const key = colon === -1 ? line : line.slice(0, colon);
          const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
          if (key === "event") event = value;
          if (key === "id" && !value.includes("\0")) id = value;
          if (key === "data") lines.push(value);
        }
      }
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
export class GasCityClient {
  constructor(readonly connection: Connection, private readonly transport: typeof fetch = fetch) {}
  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    if (init.method && init.method !== "GET") headers.set("X-GC-Request", "bb-provider");
    if (process.env.GC_BB_AUTH_TOKEN) headers.set("Authorization", `Bearer ${process.env.GC_BB_AUTH_TOKEN}`);
    const timeout = AbortSignal.timeout(20_000);
    const signal = headers.get("Accept") === "text/event-stream" ? init.signal : init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    const response = await this.transport(`${this.connection.url.replace(/\/$/, "")}${path}`, {
      ...init, headers, redirect: "error", signal,
    });
    if (!response.ok) {
      const body = (await response.text()).slice(0, 1200);
      throw new ApiError(response.status, `Gas City ${response.status} on ${path.split("?")[0]}: ${body}`);
    }
    return response;
  }
  async get<T = any>(path: string, signal?: AbortSignal): Promise<T> { return (await this.request(path, { signal })).json(); }
  async post<T = any>(path: string, body: unknown = {}, signal?: AbortSignal): Promise<T> {
    return (await this.request(path, { method: "POST", body: JSON.stringify(body), signal })).json();
  }
  city(city: string, suffix: string) { return `/v0/city/${encodeURIComponent(city)}${suffix}`; }
  session(city: string, id: string, suffix = "") { return this.city(city, `/session/${encodeURIComponent(id)}${suffix}`); }
  async health(): Promise<{ version: string }> {
    const health = await this.get<{ status: string; version: string }>("/health");
    const match = /^v?(\d+)\.(\d+)\.(\d+)(?:[+-].*)?$/.exec(health.version);
    if (health.status !== "ok" || !match || Number(match[1]) !== 1 || Number(match[2]) < 4)
      throw new Error(`Gas City 1.4+ is required; supervisor reported ${health.version ?? "unknown"}`);
    return health;
  }
  async *events(path: string, signal: AbortSignal, resume?: string): AsyncGenerator<SSE> {
    let last = resume, attempts = 0;
    while (!signal.aborted) {
      try {
        const headers = new Headers({ Accept: "text/event-stream" });
        if (last) headers.set("Last-Event-ID", last);
        const response = await this.request(path, { headers, signal });
        if (!response.body) throw new Error("Gas City returned no event stream");
        for await (const event of parseSSE(response.body)) {
          if (event.id) last = event.id;
          attempts = 0;
          yield event;
        }
      } catch (error) {
        if (signal.aborted) return;
        if (error instanceof ApiError && error.status < 500) throw error;
        if (++attempts > 6) throw error;
      }
      await delay(Math.min(250 * 2 ** attempts, 5000), undefined, { signal });
    }
  }
  async result(city: string, accepted: { request_id: string; event_cursor: string }, operation: "create" | "submit", signal?: AbortSignal): Promise<any> {
    if (!accepted.request_id || accepted.event_cursor === undefined) throw new Error("Invalid Gas City async acceptance response");
    const timeout = AbortSignal.timeout(150_000);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    const path = this.city(city, `/events/stream?after_seq=${encodeURIComponent(accepted.event_cursor)}`);
    for await (const event of this.events(path, combined)) {
      const envelope = JSON.parse(event.data);
      if (envelope.payload?.request_id !== accepted.request_id) continue;
      if (envelope.type === "request.failed") throw new Error(`Gas City ${operation} failed: ${envelope.payload.error_message ?? envelope.payload.message ?? envelope.message ?? "unknown failure"}`);
      if (envelope.type === `request.result.session.${operation}`) return envelope.payload;
    }
    throw new Error(`Gas City ${operation} result was not confirmed. Do not retry a prompt blindly.`);
  }
}

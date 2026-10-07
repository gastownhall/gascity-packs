import { setTimeout as delay } from "node:timers/promises";
import * as sdk from "./generated/gc/sdk.gen.js";
import { createClient, type Client } from "./generated/gc/client/index.js";
import type { AsyncAcceptedBody, CreateSessionData, SubmitSessionData, RespondSessionData, SessionCreateSucceededPayload, SessionSubmitSucceededPayload, TypedEventStreamEnvelope } from "./generated/gc/types.gen.js";
import type { Frame } from "./transcript.js";
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
  private readonly api: Client;
  constructor(readonly connection: Connection, private readonly transport: typeof fetch = fetch) {
    this.api = createClient({ baseUrl: connection.url.replace(/\/$/, ""), throwOnError: true,
      fetch: async request => this.request(request instanceof Request ? request : new Request(request)) });
    // Keep the bridge's bounded SSE parser/reconnect policy. The generated SDK
    // still owns the endpoint, parameter serialization and wire data types.
    this.api.sse.get = async options => ({ stream: this.streamData(options) });
  }
  private options(signal?: AbortSignal) {
    return { client: this.api, signal, headers: { "X-GC-Request": "bb-provider" } };
  }
  private async request(request: Request): Promise<Response> {
    const headers = new Headers(request.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (process.env.GC_BB_AUTH_TOKEN) headers.set("Authorization", `Bearer ${process.env.GC_BB_AUTH_TOKEN}`);
    const signal = headers.get("Accept") === "text/event-stream" ? request.signal : AbortSignal.any([request.signal, AbortSignal.timeout(20_000)]);
    const response = await this.transport(request.url, { method: request.method, headers,
      ...(request.body ? { body: await request.text() } : {}), redirect: "error", signal });
    if (!response.ok) {
      const body = (await response.text()).slice(0, 1200);
      throw new ApiError(response.status, `Gas City ${response.status} on ${new URL(request.url).pathname}: ${body}`);
    }
    return response;
  }
  cities(signal?: AbortSignal) { return sdk.getV0Cities(this.options(signal)); }
  config(city: string, signal?: AbortSignal) { return sdk.getV0CityByCityNameConfig({ ...this.options(signal), path: { cityName: city } }); }
  providers(city: string, signal?: AbortSignal) { return sdk.getV0CityByCityNameProvidersPublic({ ...this.options(signal), path: { cityName: city } }); }
  getSession(city: string, id: string, signal?: AbortSignal) { return sdk.getV0CityByCityNameSessionById({ ...this.options(signal), path: { cityName: city, id } }); }
  createSession(city: string, body: CreateSessionData["body"], signal?: AbortSignal) { return sdk.createSession({ ...this.options(signal), path: { cityName: city }, body }); }
  submit(city: string, id: string, body: SubmitSessionData["body"], signal?: AbortSignal) { return sdk.submitSession({ ...this.options(signal), path: { cityName: city, id }, body }); }
  stop(city: string, id: string, signal?: AbortSignal) { return sdk.postV0CityByCityNameSessionByIdStop({ ...this.options(signal), path: { cityName: city, id } }); }
  pending(city: string, id: string, signal?: AbortSignal) { return sdk.getV0CityByCityNameSessionByIdPending({ ...this.options(signal), path: { cityName: city, id } }); }
  respond(city: string, id: string, body: RespondSessionData["body"], signal?: AbortSignal) { return sdk.respondSession({ ...this.options(signal), path: { cityName: city, id }, body }); }
  async transcript(city: string, id: string, signal?: AbortSignal): Promise<Frame> {
    const frame = await sdk.getV0CityByCityNameSessionByIdTranscript({ ...this.options(signal), path: { cityName: city, id }, query: { format: "structured" } });
    if (!("schema_version" in frame) || frame.schema_version !== "session.structured.v1" || !frame.history || !Array.isArray(frame.structured_messages)) throw new Error("Gas City did not return its structured transcript contract");
    return frame;
  }
  async health() {
    const health = await sdk.getHealth(this.options());
    const match = /^v?(\d+)\.(\d+)\.(\d+)(?:[+-].*)?$/.exec(health.version);
    if (health.status !== "ok" || !match || Number(match[1]) !== 1 || Number(match[2]) < 5)
      throw new Error(`Gas City 1.5+ is required; supervisor reported ${health.version ?? "unknown"}`);
    if (health.startup && health.startup.ready !== true)
      throw new Error(`Gas City supervisor is not ready (${health.startup.phase ?? "initializing"}). Check gc supervisor status and logs.`);
    return health;
  }
  private async *streamData<T>(options: Omit<import("./generated/gc/client/index.js").RequestOptions<T, import("./generated/gc/client/index.js").ResponseStyle>, "method">) {
    const headers = new Headers(options.headers as HeadersInit);
    headers.set("Accept", "text/event-stream");
    const response = await this.request(new Request(this.api.buildUrl({ url: options.url, path: options.path, query: options.query }), { headers, signal: options.signal }));
    if (!response.body) throw new Error("Gas City returned no event stream");
    for await (const event of parseSSE(response.body)) {
      const data = JSON.parse(event.data);
      options.onSseEvent?.({ ...event, data });
      yield data;
    }
  }
  private async *events(open: (last: string | undefined, onEvent: (event: { data: unknown; event?: string; id?: string }) => void) => Promise<{ stream: AsyncGenerator<unknown> }>, signal: AbortSignal, resume?: string): AsyncGenerator<SSE> {
    let last = resume, attempts = 0;
    while (!signal.aborted) {
      try {
        let current: SSE | undefined;
        const { stream } = await open(last, event => { current = { event: event.event ?? "message", id: event.id, data: JSON.stringify(event.data) }; });
        for await (const _data of stream) {
          if (!current) throw new Error("Gas City stream did not publish event metadata");
          if (current.id) last = current.id;
          attempts = 0;
          yield current;
        }
      } catch (error) {
        if (signal.aborted) return;
        if (error instanceof ApiError && error.status < 500) throw error;
        if (++attempts > 6) throw error;
      }
      await delay(Math.min(250 * 2 ** attempts, 5000), undefined, { signal });
    }
  }
  sessionEvents(city: string, id: string, cursor: string, signal: AbortSignal) {
    return this.events((last, onSseEvent) => sdk.streamSession({ ...this.options(signal), path: { cityName: city, id }, query: { format: "structured", after_cursor: cursor }, headers: { "X-GC-Request": "bb-provider", ...(last ? { "Last-Event-ID": last } : {}) }, onSseEvent }), signal, cursor);
  }
  cityEvents(city: string, cursor: string, signal: AbortSignal) {
    return this.events((last, onSseEvent) => sdk.streamEvents({ ...this.options(signal), path: { cityName: city }, query: { after_seq: cursor }, headers: { "X-GC-Request": "bb-provider", ...(last ? { "Last-Event-ID": last } : {}) }, onSseEvent }), signal, cursor);
  }
  result(city: string, accepted: Pick<AsyncAcceptedBody, "request_id" | "event_cursor">, operation: "create", signal?: AbortSignal): Promise<SessionCreateSucceededPayload>;
  result(city: string, accepted: Pick<AsyncAcceptedBody, "request_id" | "event_cursor">, operation: "submit", signal?: AbortSignal): Promise<SessionSubmitSucceededPayload>;
  async result(city: string, accepted: Pick<AsyncAcceptedBody, "request_id" | "event_cursor">, operation: "create" | "submit", signal?: AbortSignal) {
    if (!accepted.request_id || accepted.event_cursor === undefined) throw new Error("Invalid Gas City async acceptance response");
    const timeout = AbortSignal.timeout(150_000);
    const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
    for await (const event of this.cityEvents(city, accepted.event_cursor, combined)) {
      if (event.event !== "event") continue;
      const envelope = JSON.parse(event.data) as TypedEventStreamEnvelope;
      if (!envelope.payload || typeof envelope.payload !== "object" || !("request_id" in envelope.payload) || envelope.payload.request_id !== accepted.request_id) continue;
      if (envelope.type === "request.failed") throw new Error(`Gas City ${operation} failed: ${envelope.payload.error_message}`);
      if (operation === "create" && envelope.type === "request.result.session.create") return envelope.payload;
      if (operation === "submit" && envelope.type === "request.result.session.submit") return envelope.payload;
    }
    throw new Error(`Gas City ${operation} result was not confirmed. Do not retry a prompt blindly.`);
  }
}

import test from "node:test";
import assert from "node:assert/strict";
import { GasCityClient } from "../src/client.js";

function clientReporting(version: string, startup?: { ready: boolean; phase: string }) {
  const transport = (async () => new Response(JSON.stringify({ status: "ok", version, startup }),
    { headers: { "Content-Type": "application/json" } })) as typeof fetch;
  return new GasCityClient({ id: "local", url: "http://127.0.0.1:1" }, transport);
}

test("health requires Gas City 1.5 or a later 1.x, including labeled prereleases", async () => {
  for (const version of ["1.5.0", "v1.5.0", "1.5.0-rc+750ee9020", "1.5.1", "1.6.0"])
    assert.equal((await clientReporting(version).health()).version, version);
  for (const version of ["1.4.2", "1.4.2-bb-runtime.4f41f8285070", "2.0.0", "dev", ""])
    await assert.rejects(clientReporting(version).health(), /Gas City 1\.5\+ is required/);
});

// A running HTTP listener does not mean the controller finished initialization.
test("health rejects a supervisor that reports failed or incomplete startup", async () => {
  for (const phase of ["init_failed", "loading_config"])
    await assert.rejects(
      clientReporting("1.6.0-dev.readiness", { ready: false, phase }).health(),
      /Gas City supervisor is not ready/);
  assert.equal((await clientReporting("1.6.0-dev.readiness", { ready: true, phase: "running" }).health()).version, "1.6.0-dev.readiness");
});

// Exercise transport behavior, including encoded identifiers and GC's required header.
test("generated submit operation preserves multiline input and encodes scope once", async () => {
  let seen: { url: string; init?: RequestInit } | undefined;
  const transport = (async (url: string, init?: RequestInit) => {
    seen = { url: String(url), init };
    return new Response(JSON.stringify({ request_id: "req-test", event_cursor: "42" }), { status: 202, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  const client = new GasCityClient({ id: "local", url: "http://127.0.0.1:1" }, transport);
  const result = await client.submit("city /α", "session/?#", { message: "first\nlast", intent: "default" });
  assert.equal(result.request_id, "req-test");
  assert.equal(seen?.url, "http://127.0.0.1:1/v0/city/city%20%2F%CE%B1/session/session%2F%3F%23/submit");
  assert.equal(seen?.init?.method, "POST");
  assert.equal(new Headers(seen?.init?.headers).get("X-GC-Request"), "bb-provider");
  assert.deepEqual(JSON.parse(String(seen?.init?.body)), { message: "first\nlast", intent: "default" });
});

for (const kind of ["session", "city"] as const) {
  test(`generated ${kind} stream resumes from the last delivered event and closes on return`, async () => {
    const requests: { url: URL; headers: Headers }[] = [];
    let canceled = 0;
    const transport = (async (url: string, init?: RequestInit) => {
      requests.push({ url: new URL(String(url)), headers: new Headers(init?.headers) });
      const n = requests.length;
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(`event: heartbeat\r\nid: next-${n}\r\ndata: {"value":"café"}\r\n\r\n`));
          if (n === 1) controller.close();
        },
        cancel() { canceled++; },
      });
      return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
    }) as typeof fetch;
    const client = new GasCityClient({ id: "local", url: "http://127.0.0.1:1" }, transport);
    const abort = new AbortController();
    const stream = kind === "session" ? client.sessionEvents("a/b", "c d", "start/+?", abort.signal) : client.cityEvents("a/b", "start/+?", abort.signal);
    try {
      assert.deepEqual((await stream.next()).value, { event: "heartbeat", id: "next-1", data: '{"value":"café"}' });
      assert.equal((await stream.next()).value?.id, "next-2");
      assert.equal(requests[0]?.url.pathname, kind === "session" ? "/v0/city/a%2Fb/session/c%20d/stream" : "/v0/city/a%2Fb/events/stream");
      assert.equal(requests[0]?.url.searchParams.get(kind === "session" ? "after_cursor" : "after_seq"), "start/+?");
      if (kind === "session") assert.equal(requests[0]?.url.searchParams.get("format"), "structured");
      assert.equal(requests[0]?.headers.get("Last-Event-ID"), "start/+?");
      assert.equal(requests[1]?.headers.get("Last-Event-ID"), "next-1");
      assert.equal(requests[0]?.headers.get("X-GC-Request"), "bb-provider");
    } finally { await stream.return(undefined); abort.abort(); }
    assert.equal(canceled, 1);
  });
}

test("generated stream does not retry rejected access", async () => {
  let requests = 0;
  const client = new GasCityClient({ id: "local", url: "http://127.0.0.1:1" }, (async () => {
    requests++; return new Response("denied", { status: 403 });
  }) as typeof fetch);
  const stream = client.sessionEvents("city", "session", "0", new AbortController().signal);
  await assert.rejects(stream.next(), /Gas City 403/);
  assert.equal(requests, 1);
});

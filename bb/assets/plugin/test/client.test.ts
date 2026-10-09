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
    if (String(url).endsWith("/turn-target")) return new Response(JSON.stringify({mode:"native_interrupt",state:"unknown"}), {headers:{"Content-Type":"application/json"}});
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


test("owned Stop uses a fresh turn target and never falls back to terminal interrupt", async () => {
  const calls: {path: string; body: unknown}[] = [];let target = "previous";
  const client = new GasCityClient({id:"stage",url:"http://127.0.0.1:1"}, (async (url:string, init?:RequestInit) => {
    const path = new URL(String(url)).pathname;calls.push({path,body:init?.body?JSON.parse(String(init.body)):null});
    const body = path.endsWith("/turn-target") ? {mode:"owned_commands",turn_id:target,state:"inProgress"} : path.endsWith("/submit") ? {request_id:"submitted",event_cursor:"0"} : {mode:"owned_commands",turn_id:target,state:"stopped"};
    return new Response(JSON.stringify(body),{status:path.endsWith("/submit")?202:200,headers:{"Content-Type":"application/json"}});
  }) as typeof fetch);
  await client.submit("city","session",{message:"work"});
  await assert.rejects(client.stop("city","session"),/ownership|current turn/);
  assert.equal(calls.filter(c=>c.path.endsWith("/stop")||c.path.endsWith("/stop-commands")).length,0);
  target="current";await client.stop("city","session");
  assert.deepEqual(calls.at(-1),{path:"/v0/city/city/session/session/stop-commands",body:{turn_id:"current"}});
  assert.equal(calls.filter(c=>c.path.endsWith("/stop")).length,0);
});

test("owned Stop retry retains its original turn after a lost reply", async () => {
  let target = "before", lost = true;const stopped: string[] = [];
  const client = new GasCityClient({id:"stage",url:"http://127.0.0.1:1"}, (async (url:string, init?:RequestInit) => {
    const path=new URL(String(url)).pathname;
    if(path.endsWith("/stop-commands")){stopped.push(JSON.parse(String(init?.body)).turn_id);if(lost){lost=false;throw new Error("lost reply");}}
    const body=path.endsWith("/turn-target")?{mode:"owned_commands",turn_id:target,state:"inProgress"}:path.endsWith("/submit")?{request_id:"req",event_cursor:"0"}:{mode:"owned_commands",turn_id:stopped.at(-1),state:"stopped"};
    return new Response(JSON.stringify(body),{headers:{"Content-Type":"application/json"}});
  }) as typeof fetch);
  await client.submit("city","session",{message:"work"});target="owned";
  await assert.rejects(client.stop("city","session"),/lost reply/);
  target="newer";await client.stop("city","session");assert.deepEqual(stopped,["owned","owned"]);
});

for (const outcome of ["ready", "denied", "aborted"] as const) {
 test(`sleeping conversation prepares its retained runtime before submission: ${outcome}`, async () => {
  const calls: string[]=[];let probes=0;
  const transport=(async (url:string,init?:RequestInit)=>{
   const path=new URL(String(url)).pathname;calls.push(path);
   if(path.endsWith('/wake'))return new Response(JSON.stringify({status:'ok'}),{status:outcome==='denied'?403:200,headers:{'Content-Type':'application/json'}});
   if(path.endsWith('/turn-target')){probes++;if(probes===1||outcome==='aborted')return new Response('runtime starting',{status:409});return new Response(JSON.stringify({mode:'owned_commands',state:'idle'}),{headers:{'Content-Type':'application/json'}});}
   return new Response(JSON.stringify({id:'session',running:false,state:'suspended'}),{headers:{'Content-Type':'application/json'}});
  }) as typeof fetch;
  const client=new GasCityClient({id:'local',url:'http://127.0.0.1:1'},transport);
  const result=client.prepareTurn('city','session',AbortSignal.timeout(outcome==='aborted'?50:5000));
  if(outcome==='ready')await result;else await assert.rejects(result,outcome==='denied'?/403/:/abort|timeout/i);
  assert.equal(calls.filter(p=>p.endsWith('/wake')).length,1);
  assert.equal(calls.some(p=>p.endsWith('/submit')),false);
  if(outcome==='ready')assert.equal(probes,2);
 });
}
test('preparing an already running conversation does not wake or reconfigure it', async()=>{
 const calls:string[]=[];const client=new GasCityClient({id:'local',url:'http://127.0.0.1:1'},(async(url:string)=>{calls.push(String(url));return new Response(JSON.stringify({id:'session',running:true,state:'active'}),{headers:{'Content-Type':'application/json'}});}) as typeof fetch);
 await client.prepareTurn('city','session');assert.equal(calls.length,1);assert(calls[0]?.endsWith('/session/session'));
});

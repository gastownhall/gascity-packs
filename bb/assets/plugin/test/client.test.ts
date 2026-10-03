import test from "node:test";
import assert from "node:assert/strict";
import { GasCityClient } from "../src/client.js";

function clientReporting(version: string) {
  const transport = (async () => new Response(JSON.stringify({ status: "ok", version }),
    { headers: { "Content-Type": "application/json" } })) as typeof fetch;
  return new GasCityClient({ id: "local", url: "http://127.0.0.1:1" }, transport);
}

test("health requires Gas City 1.5 or a later 1.x, including labeled prereleases", async () => {
  for (const version of ["1.5.0", "v1.5.0", "1.5.0-rc+750ee9020", "1.5.1", "1.6.0"])
    assert.equal((await clientReporting(version).health()).version, version);
  for (const version of ["1.4.2", "1.4.2-bb-runtime.4f41f8285070", "2.0.0", "dev", ""])
    await assert.rejects(clientReporting(version).health(), /Gas City 1\.5\+ is required/);
});

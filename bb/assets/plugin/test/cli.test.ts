import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fixture } from "./fixture.js";

const exec = promisify(execFile);
test("CLI connects with matching workspaces and diagnoses missing registration and stale paths", async () => {
  const f = await fixture();
  try {
    const cli = join(f.cwd, "cli.mjs"), config = join(f.cwd, "config.json"), bin = join(f.cwd, "bin");
    await exec(resolve("node_modules/.bin/esbuild"), [resolve("src/cli.ts"), "--bundle", "--platform=node", "--format=esm", `--outfile=${cli}`, "--log-level=silent"]);
    await mkdir(bin);
    await writeFile(join(bin, "bb"), '#!/bin/sh\nprintf \'%s\\n\' \'{"plugins":[]}\'\n', { mode: 0o700 });
    const env = { ...process.env, GC_BB_CONFIG: config, XDG_STATE_HOME: join(f.cwd, "state"), PATH: `${bin}:${process.env.PATH}` };
    await exec(process.execPath, [cli, "connect", "--url", f.config.connections[0]!.url], { env });
    const saved = JSON.parse(await readFile(config, "utf8"));
    assert.equal(saved.workspacePolicy, "require-match");
    saved.bindings = [{ ...f.config.bindings[0], paths: [join(f.cwd, "gone")] }];
    await writeFile(config, JSON.stringify(saved));
    await assert.rejects(exec(process.execPath, [cli, "status", "--json"], { env }), (error: any) => {
      assert.equal(error.code, 1);
      const status = JSON.parse(error.stdout);
      assert.equal(status.connections[0].ok, true);
      assert.equal(status.registration.status, "missing");
      assert.equal(status.bindingChecks[0].ok, false);
      assert.match(status.bindingChecks[0].error, /ENOENT/);
      return true;
    });
  } finally { await f.close(); }
});

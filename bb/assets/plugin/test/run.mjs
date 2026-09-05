import { build } from "esbuild";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

// Match BB's packages/plugin-build Node ESM require banner. The published SDK
// includes CJS dependencies and import.meta URLs, so both bindings matter.
const output = await mkdtemp(join(tmpdir(), "bb-gc-tests-"));
try {
  const tests = (await readdir("test")).filter(file => file.endsWith(".test.ts"));
  await build({ entryPoints: tests.map(file => `test/${file}`), bundle: true, platform: "node", format: "esm", outdir: output, outExtension: { ".js": ".mjs" }, banner: { js: 'import { createRequire as __nodeRequire } from "node:module"; const require = __nodeRequire(import.meta.url);' }, logLevel: "warning" });
  const result = spawnSync(process.execPath, ["--test", ...tests.map(file => join(output, file.replace(/\.ts$/, ".mjs")))], { stdio: "inherit" });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} finally { await rm(output, { recursive: true, force: true }); }

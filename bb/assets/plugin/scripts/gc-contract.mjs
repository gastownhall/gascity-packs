import { createClient } from "@hey-api/openapi-ts";
import ts from "typescript";
import { readFile, readdir, mkdtemp, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const schema = join(root, "contracts/gc/openapi.json");
const output = join(root, "src/generated/gc");
async function files(dir) {
  const result = [];
  try {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) result.push(...await files(path));
      else result.push(path);
    }
  } catch (error) { if (error.code !== "ENOENT") throw error; }
  return result.sort();
}
export async function compareTrees(actual, expected) {
  const a = new Map(await Promise.all((await files(actual)).map(async path => [relative(actual, path), await readFile(path)])));
  const b = new Map(await Promise.all((await files(expected)).map(async path => [relative(expected, path), await readFile(path)])));
  const changed = [...new Set([...a.keys(), ...b.keys()])].sort().filter(path => !a.has(path) || !b.has(path) || !a.get(path).equals(b.get(path)));
  if (changed.length) throw new Error(`Generated GC client differs: ${changed.join(", ")}. Run npm run gc:generate and review the diff.`);
}
export async function assertGeneratedBoundary(base = root) {
  const restricted = new Set(["client.ts", "provider.ts", "transcript.ts", "recovery.ts", "catalog.ts"]);
  for (const path of await files(join(base, "src"))) {
    const name = relative(join(base, "src"), path);
    if (name.startsWith("generated/") || !name.endsWith(".ts")) continue;
    const source = ts.createSourceFile(path, await readFile(path, "utf8"), ts.ScriptTarget.Latest, true);
    function visit(node) {
      if (ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) {
        if (/\/v0(?:\/|$)|^\/health$/.test(node.text)) throw new Error(`${name}: handwritten GC route; use the generated SDK`);
        if (restricted.has(name) && /^(?:node:)?child_process$|^execa(?:\/|$)|^node-pty$/.test(node.text)) throw new Error(`${name}: subprocess access cannot supply session truth`);
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
async function generate(path) {
  await createClient({
    input: schema,
    output: { path, importFileExtension: ".js" },
    plugins: ["@hey-api/typescript", { name: "@hey-api/client-fetch", throwOnError: true }, { name: "@hey-api/sdk", responseStyle: "data" }],
  });
}
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
async function main(mode, url) {
  const bytes = await readFile(schema);
  const provenance = JSON.parse(await readFile(join(root, "contracts/gc/provenance.json"), "utf8"));
  if (createHash("sha256").update(bytes).digest("hex") !== provenance.sha256) throw new Error("GC schema checksum differs from provenance; review and record the schema update first");
  if (mode === "generate") return generate(output);
  if (mode === "check-live") {
    if (!url) throw new Error("Usage: npm run gc:check-live -- <supervisor-url>");
    const headers = process.env.GC_BB_AUTH_TOKEN ? { Authorization: `Bearer ${process.env.GC_BB_AUTH_TOKEN}` } : {};
    const response = await fetch(new URL("openapi.json", url.replace(/\/$/, "") + "/"), { headers, redirect: "error", signal: AbortSignal.timeout(20_000) });
    if (!response.ok) throw new Error(`GC schema fetch failed: HTTP ${response.status}`);
    if (JSON.stringify(canonical(await response.json())) !== JSON.stringify(canonical(JSON.parse(bytes)))) throw new Error("Live GC OpenAPI differs from the pinned contract; review before changing the schema or deploying");
    console.log("Live supervisor OpenAPI matches the pinned contract");
    return;
  }
  if (mode !== "check") throw new Error("Expected generate, check, or check-live");
  await assertGeneratedBoundary();
  const temp = await mkdtemp(join(tmpdir(), "bb-gc-generated-"));
  try { await generate(join(temp, "gc")); await compareTrees(output, join(temp, "gc")); }
  finally { await rm(temp, { recursive: true, force: true }); }
  console.log("GC generated client and API boundary checks passed");
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv[2], process.argv[3]).catch(error => { console.error(error.message); process.exitCode = 1; });
}

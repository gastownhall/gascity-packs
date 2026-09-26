import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync,
  readlinkSync, realpathSync, renameSync, rmdirSync, symlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const root = resolve(process.env.GC_BB_INSTALL_DIR ?? join(process.env.XDG_DATA_HOME ?? join(homedir(), ".local/share"), "gascity/bb/plugin"));
const current = join(root, "current");
const versions = join(root, "versions");
const marker = ".gc-bb-install.json";
const exists = path => lstatSync(path, { throwIfNoEntry: false }) !== undefined;

function run(command, argv, cwd, capture = false) {
  const result = spawnSync(command, argv, { cwd, stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit", encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} ${argv.join(" ")} failed (${result.status ?? result.signal})${capture ? `: ${result.stderr.trim()}` : ""}`);
  return result.stdout;
}

function registered() {
  const response = JSON.parse(run("bb", ["plugin", "list", "--json"], undefined, true));
  if (!Array.isArray(response.plugins)) throw new Error("BB plugin list returned an invalid response");
  return response.plugins.find(plugin => plugin.id === "gas-city");
}

function checkPointer() {
  if (!exists(current)) return;
  if (!lstatSync(current).isSymbolicLink()) throw new Error(`Preserving unexpected ${current}; move it aside before installing`);
  const target = resolve(root, readlinkSync(current));
  if (dirname(target) !== versions || !existsSync(join(target, marker))) throw new Error(`Preserving unrecognized current link at ${current}; inspect it before installing`);
}

function restore(previous, stage) {
  if (!previous) {
    console.error("No prior BB registration exists to restore; any failed registration and its settings were retained for inspection.");
    return;
  }
  // BB path-source moves retain the plugin's settings, secrets, and schedules.
  // Never uninstall: removal would discard those independent pieces of state.
  const observed = registered();
  if (observed?.source === previous.source && observed.status === previous.status && observed.enabled === previous.enabled) return;
  if (observed && observed.source !== previous.source && realpathSync(observed.rootDir) !== realpathSync(stage)) throw new Error(`BB registration changed to ${observed.source}; refusing to overwrite a concurrent change`);
  run("bb", ["plugin", "install", previous.source, "--yes"]);
  const restored = registered();
  if (!restored || restored.source !== previous.source || restored.enabled !== previous.enabled || restored.status !== previous.status) throw new Error(`BB did not restore ${previous.source}; inspect bb plugin list`);
  console.error(`Restored previous BB registration: ${previous.source}`);
}

function main() {
  if (args.some(arg => arg !== "--yes")) throw new Error("Usage: gc bb install [--yes]");
  mkdirSync(root, { recursive: true, mode: 0o700 });
  checkPointer();
  const lock = join(root, ".install-lock");
  try { mkdirSync(lock, { mode: 0o700 }); }
  catch (error) { if (error.code === "EEXIST") throw new Error(`Installation is active or interrupted; inspect ${lock} before retrying`); throw error; }
  let stage, previous, registrationAttempted = false;
  try {
    previous = registered();
    if (previous && !previous.source?.startsWith("path:")) throw new Error(`Gas City is installed from ${previous.source}; preserving that registration. Use BB's update flow for that source.`);
    if (exists(versions) && (!lstatSync(versions).isDirectory() || lstatSync(versions).isSymbolicLink())) throw new Error(`Preserving unexpected ${versions}; inspect it before installing`);
    mkdirSync(versions, { recursive: true, mode: 0o700 });
    stage = mkdtempSync(join(versions, "install-"));
    writeFileSync(join(stage, marker), JSON.stringify({ format: 1, createdAt: new Date().toISOString(), previousSource: previous?.source ?? null }) + "\n", { mode: 0o600, flag: "wx" });
    const source = resolve(process.env.GC_PACK_DIR, "assets/plugin");
    cpSync(source, stage, { recursive: true, force: false, errorOnExist: true,
      filter: path => !["node_modules", "dist", ".git"].includes(relative(source, path).split("/")[0]) });
    console.log(`Preparing provider in ${stage}`);
    run("npm", ["ci", "--include=dev", "--ignore-scripts", "--no-audit", "--no-fund"], stage);
    run("npm", ["run", "build"], stage);
    if (!existsSync(join(stage, "dist/cli.js"))) throw new Error("Build did not produce dist/cli.js");
    registrationAttempted = true;
    run("bb", ["plugin", "install", `path:${stage}`, ...args]);
    const plugin = registered();
    if (!plugin || realpathSync(plugin.rootDir) !== realpathSync(stage) || !["running", "needs-configuration", "disabled"].includes(plugin.status)) throw new Error(`BB did not register a healthy Gas City plugin: ${plugin?.statusDetail ?? plugin?.status ?? "missing"}`);
    checkPointer();
    const next = join(stage, ".current-link");
    symlinkSync(stage, next);
    renameSync(next, current);
    console.log(`Provider installed at ${stage}. Previous sources were preserved. Run gc bb connect on each BB execution host.`);
  } catch (error) {
    if (registrationAttempted) {
      try { restore(previous, stage); }
      catch (rollbackError) { console.error(`Registration rollback failed: ${rollbackError.message}. Previous source: ${previous?.source ?? "none"}. Settings and files were retained.`); }
    }
    if (stage) console.error(`Installation files retained for inspection: ${stage}`);
    throw error;
  } finally { rmdirSync(lock); }
}

try { main(); } catch (error) { console.error(`bb install: ${error.message}`); process.exitCode = 1; }

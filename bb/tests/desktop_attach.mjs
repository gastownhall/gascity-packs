/** Actual released Electron shell, isolated from the normal app and BB store.
 * --user-data-dir is applied before app JS in Electron 41.7.0:
 * https://github.com/electron/electron/blob/v41.7.0/shell/app/electron_main_delegate.cc
 * No provider responses, permissions, dialogs or BB frontend code are mocked.
 */
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFile, realpath, stat, access, writeFile } from 'node:fs/promises';
import http from 'node:http';
import net from 'node:net';
import { homedir } from 'node:os';
import { join, relative, isAbsolute, resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

export function inside(root, target) {
  const suffix = relative(root, target);
  return suffix !== '' && suffix !== '..' && !suffix.startsWith('../') && !isAbsolute(suffix);
}

const digest = bytes => createHash('sha256').update(bytes).digest('hex');
async function exclusiveJson(path, value) {
  await writeFile(path, JSON.stringify(value, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
}
async function unusedPort() {
  const server = net.createServer();
  await new Promise((done, fail) => { server.once('error', fail); server.listen(0, '127.0.0.1', done); });
  const port = server.address().port;
  await new Promise(done => server.close(done));
  return port;
}

export function parseRuntimeProcess(text, spec, uid) {
  const found = text.trim().match(/^(\d+)\s+(\d+)\s+(\S+\s+\S+\s+\d+\s+\S+\s+\d+)\s+([\s\S]+)$/);
  assert.ok(found, 'BB process identity is unavailable');
  assert.equal(Number(found[1]), spec.appPid);
  assert.equal(Number(found[2]), uid);
  const command = found[4];
  assert.match(command, /\/bb-app(?:\.js)?(?:\s|$)/);
  const token = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  assert.match(command, new RegExp(`(?:^|\\s)--data-dir(?:=|\\s)${token(spec.bbDataDir)}(?:\\s|$)`));
  assert.match(command, new RegExp(`(?:^|\\s)--server-port(?:=|\\s)${new URL(spec.bbUrl).port}(?:\\s|$)`));
  return { pid: Number(found[1]), uid: Number(found[2]), birth: found[3], command_sha256: digest(command) };
}

async function runtimeIdentity(spec) {
  // A retained launcher started with explicit CLI flags can predate/lose its
  // advisory runtime record. Prove the actual process instead of recreating it.
  const text = execFileSync('ps', ['-ww', '-p', String(spec.appPid), '-o', 'pid=', '-o', 'uid=', '-o', 'lstart=', '-o', 'command='], { encoding: 'utf8' });
  const identity = parseRuntimeProcess(text, spec, process.getuid());
  try {
    const record = JSON.parse(await readFile(join(spec.bbDataDir, 'bb-app-runtime.json'), 'utf8'));
    assert.equal(record.pid, spec.appPid);
    assert.equal(record.serverUrl, spec.bbUrl);
  } catch (error) { if (error.code !== 'ENOENT') throw error; }
  return identity;
}

export async function validateDesktopSpec(spec, { launched = false } = {}) {
  assert.equal(process.platform, 'darwin', 'Native BB desktop requires macOS');
  assert.equal(spec.schema, 1);
  const root = await realpath(spec.root);
  assert.match(root, /^\/(?:private\/)?(?:var\/)?tmp\/bb-live-[^/]+$/);
  const marker = JSON.parse(await readFile(join(root, '.bb-full-e2e-owned.json'), 'utf8'));
  assert.equal(marker.root, root);
  const directory = await realpath(spec.directory);
  assert.ok(inside(root, directory), 'Desktop directory escapes the owned installation');
  for (const key of ['executablePath', 'appAsar', 'userDataDir', 'diskCacheDir', 'updaterCacheDir']) {
    assert.ok(inside(directory, await realpath(spec[key])), `${key} escapes the desktop clone`);
  }
  assert.ok(inside(root, await realpath(spec.envFile)));
  const environment = JSON.parse(await readFile(spec.envFile, 'utf8'));
  for (const key of ['BB_DATA_DIR', 'GC_HOME', 'GC_BB_CONFIG', 'XDG_STATE_HOME'])
    assert.ok(inside(root, await realpath(environment[key])), `${key} escapes the owned installation`);
  assert.equal(environment.BB_DATA_DIR, spec.bbDataDir);
  const url = new URL(spec.bbUrl);
  assert.equal(url.protocol, 'http:');
  assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname));
  assert.ok(url.port && !['38886', '8372'].includes(url.port));
  assert.ok(!url.username && !url.password && !url.search && !url.hash);
  assert.ok(url.pathname === '/');
  assert.equal(digest(await readFile(spec.appAsar)), spec.identity.app_asar_sha256);
  assert.equal(digest(await readFile(join(spec.sourceApp, 'Contents/Resources/app.asar'))), spec.identity.app_asar_sha256);
  const contents = dirname(dirname(spec.executablePath));
  const bundleId = execFileSync('/usr/bin/plutil', ['-extract', 'CFBundleIdentifier', 'raw', '-o', '-', join(contents, 'Info.plist')], { encoding: 'utf8' }).trim();
  assert.equal(bundleId, spec.bundleId);
  assert.match(bundleId, /^dev\.bb\.desktop\.e2e\.[0-9a-f]{16}$/);
  const cacheLine = (await readFile(join(contents, 'Resources/app-update.yml'), 'utf8')).match(/^updaterCacheDirName: (.+)$/m);
  assert.ok(cacheLine, 'The cloned updater cache configuration is missing');
  assert.equal(resolve(homedir(), 'Library/Caches', JSON.parse(cacheLine[1])), await realpath(spec.updaterCacheDir));
  const runtime = await runtimeIdentity(spec);
  const response = await fetch(spec.bbUrl + '/api/v1/system/version', { signal: AbortSignal.timeout(10000), redirect: 'error' });
  assert.equal(response.status, 200);
  assert.equal((await response.json()).currentVersion, spec.identity.version);
  // A second launch must never clear cache, recover a runtime or reuse state
  // from an earlier attempt. Prepare a new clone directory for a new attempt.
  if (!launched) {
    for (const name of ['desktop-started.json', 'desktop-ready.json']) {
      await assert.rejects(access(join(directory, name)), { code: 'ENOENT' });
    }
  }
  return { environment, directory, runtime };
}

export async function connectOwnedDesktop(spec) {
  const { directory } = await validateDesktopSpec(spec, { launched: true });
  const ready = JSON.parse(await readFile(join(directory, 'desktop-ready.json'), 'utf8'));
  assert.equal(ready.status, 'attached');
  assert.equal(ready.bbUrl, spec.bbUrl);
  assert.equal(ready.identity.app_asar_sha256, spec.identity.app_asar_sha256);
  const endpoint = new URL(ready.cdpEndpoint);
  assert.equal(endpoint.hostname, '127.0.0.1');
  assert.equal(endpoint.protocol, 'http:');
  const command = execFileSync('ps', ['-ww', '-p', String(ready.native.pid), '-o', 'command='], { encoding: 'utf8' }).trim();
  assert.ok(command.startsWith(spec.executablePath + ' '), 'CDP owner is not the exact copied app');
  assert.ok(command.split(' ').includes(`--user-data-dir=${spec.userDataDir}`), 'CDP owner uses another profile');
  const { chromium } = await import('playwright');
  const browser = await chromium.connectOverCDP(ready.cdpEndpoint, { timeout: 15000 });
  const pages = browser.contexts().flatMap(context => context.pages()).filter(page => new URL(page.url()).origin === new URL(spec.bbUrl).origin);
  assert.equal(pages.length, 1, 'Expected one actual BB desktop page');
  return { page: pages[0], context: pages[0].context(), evidence: ready,
    // connectOverCDP closes its transport here, not the independently launched
    // Electron process (Playwright's _connectOverCDPImpl close implementation).
    close: () => browser.close() };
}

export async function launchOwnedDesktop(spec) {
  const { environment, directory, runtime: initialRuntime } = await validateDesktopSpec(spec);
  process.umask(0o077);
  let denied = 0;
  // Electron-updater's real network executor uses Chromium's proxy. Deny
  // external downloads; BB's explicit loopback endpoint bypasses this proxy.
  // This changes updater network availability, never BB/GC response content.
  const proxy = http.createServer((_req, res) => { denied++; res.writeHead(502); res.end(); });
  proxy.on('connect', (_req, socket) => { denied++; socket.end('HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n'); });
  await new Promise((done, fail) => { proxy.once('error', fail); proxy.listen(0, '127.0.0.1', done); });
  const proxyPort = proxy.address().port;
  const cdpPort = await unusedPort();
  const args = [`--user-data-dir=${spec.userDataDir}`, `--disk-cache-dir=${spec.diskCacheDir}`, '--use-mock-keychain',
    `--proxy-server=http://127.0.0.1:${proxyPort}`, '--proxy-bypass-list=127.0.0.1;localhost;[::1]',
    `--remote-debugging-port=${cdpPort}`, '--remote-debugging-address=127.0.0.1'];
  const env = { ...environment, BB_DATA_DIR: spec.bbDataDir, BB_SERVER_PORT: new URL(spec.bbUrl).port,
    BB_SERVER_URL: spec.bbUrl, BB_DESKTOP_ATTACH_WITHOUT_PROMPT: '1' };
  delete env.BB_DESKTOP_APP_URL;
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.NODE_OPTIONS;
  await exclusiveJson(join(directory, 'desktop-started.json'), { at: new Date().toISOString(), args, identity: spec.identity });
  let electronApp;
  try {
    const { _electron } = await import('playwright');
    console.error('[desktop] Launching isolated copy; attaching to the retained BB server');
    electronApp = await _electron.launch({ executablePath: spec.executablePath, args, env,
      cwd: directory, artifactsDir: join(directory, 'playwright-artifacts'), timeout: 45000 });
    const page = await electronApp.firstWindow({ timeout: 30000 });
    await page.waitForURL(url => url.origin === new URL(spec.bbUrl).origin, { timeout: 45000 });
    await page.getByRole('button', { name: /New thread/i }).first().waitFor({ state: 'visible', timeout: 30000 });
    const native = await electronApp.evaluate(({ app, session }) => ({ pid: process.pid, version: app.getVersion(),
      electronVersion: process.versions.electron, packaged: app.isPackaged, appPath: app.getAppPath(),
      userData: app.getPath('userData'), sessionData: app.getPath('sessionData'), storagePath: session.defaultSession.storagePath,
      bbDataDir: process.env.BB_DATA_DIR, home: process.env.HOME }));
    assert.equal(native.version, spec.identity.version);
    assert.equal(native.packaged, true);
    assert.equal(await realpath(native.appPath), await realpath(spec.appAsar));
    assert.equal(await realpath(native.userData), await realpath(spec.userDataDir));
    assert.equal(await realpath(native.sessionData), await realpath(spec.userDataDir));
    assert.equal(await realpath(native.storagePath), await realpath(spec.userDataDir));
    assert.equal(native.bbDataDir, spec.bbDataDir);
    assert.equal(native.home, environment.HOME, 'The home environment must remain unchanged');
    await assert.rejects(access(join(spec.userDataDir, 'owned-runtime.json')), { code: 'ENOENT' });
    const runtime = await runtimeIdentity(spec);
    assert.deepEqual(runtime, initialRuntime, 'Desktop replaced the retained BB server');
    const cdp = await fetch(`http://127.0.0.1:${cdpPort}/json/version`, { signal: AbortSignal.timeout(10000) });
    assert.equal(cdp.status, 200);
    await page.screenshot({ path: join(directory, 'desktop-attached.png'), fullPage: true });
    const evidence = { status: 'attached', native, cdpEndpoint: `http://127.0.0.1:${cdpPort}`,
      bbUrl: spec.bbUrl, unchangedServerPid: runtime.pid, identity: spec.identity,
      instrumentation: spec.instrumentation, deniedExternalRequests: denied };
    await exclusiveJson(join(directory, 'desktop-ready.json'), evidence);
    console.error('[desktop] Actual packaged app attached; native profile and existing server verified');
    return { electronApp, page, context: electronApp.context(), evidence, async close() {
      await electronApp.close();
      await new Promise(done => proxy.close(done));
    } };
  } catch (error) {
    if (electronApp) await electronApp.close().catch(() => {});
    await new Promise(done => proxy.close(done));
    await exclusiveJson(join(directory, 'desktop-failure.json'), { status: 'failed', error: String(error) });
    throw error;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const index = process.argv.indexOf('--spec');
  assert.ok(index > 0 && process.argv[index + 1], 'Pass --spec <prepared desktop.json>');
  const desktop = await launchOwnedDesktop(JSON.parse(await readFile(process.argv[index + 1], 'utf8')));
  console.log(JSON.stringify({ status: 'attached', cdpEndpoint: desktop.evidence.cdpEndpoint }));
  // Keep this exact child alive for subsequent browser journeys. Closing this
  // helper only closes its own Electron child, never the separately owned BB.
  for (const name of ['SIGINT', 'SIGTERM']) process.once(name, async () => { await desktop.close(); process.exitCode = 0; });
}

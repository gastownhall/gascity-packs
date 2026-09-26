// Run against a disposable BB/GC installation. Requires Playwright and Chrome.
// This checks real UI/registration, not model completion; retain thread logs too.
import { parseArgs } from 'node:util';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
const { values: args } = parseArgs({ options: Object.fromEntries(
  ['url', 'host', 'project', 'model', 'workspace', 'prompt'].map(key => [key, { type: 'string' }])) });
for (const key of ['url', 'host', 'project', 'model', 'workspace']) {
  if (!args[key]) throw new Error(`Missing --${key}`);
}
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const artifacts = await mkdtemp(join(tmpdir(), 'bb-gc-launcher-'));
console.log(`Artifacts: ${artifacts}`);
const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
try {
  console.log('[1/3] Loading the actual installed launcher');
  await page.goto(new URL('/plugins/gas-city/launch', args.url).href);
  await page.getByLabel('Host', { exact: true }).selectOption(args.host);
  await page.getByLabel('Project', { exact: true }).selectOption(args.project);
  await page.getByLabel('Agent', { exact: true }).selectOption(args.model);
  await page.getByLabel('Existing workspace', { exact: true }).fill(args.workspace);
  await page.getByLabel('First message', { exact: true }).fill(args.prompt || 'Workspace validation check.');
  await page.screenshot({ path: join(artifacts, 'desktop.png') });
  console.log('[2/3] Checking missing-workspace validation and exact selection');
  await page.getByLabel('Existing workspace', { exact: true }).fill(`${args.workspace}/gc-bb-missing-${randomUUID()}`);
  await page.getByRole('button', { name: 'Start conversation', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'ENOENT' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Start conversation', exact: true }).isEnabled(), true);
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('select[aria-label="Agent"]').disabled);
  assert.equal(await page.getByLabel('Agent', { exact: true }).inputValue(), args.model);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: 'dark' });
  assert.equal(await page.evaluate(() => {
    const main = document.querySelector('.gc-launcher');
    return main.scrollWidth <= main.clientWidth;
  }), true);
  await page.screenshot({ path: join(artifacts, 'mobile.png') });
  if (args.prompt) {
    console.log('[3/3] Creating one thread with the explicit selection');
    await page.getByLabel('Existing workspace', { exact: true }).fill(args.workspace);
    await page.getByRole('button', { name: 'Start conversation', exact: true }).click();
    await page.waitForURL(url => /\/threads\//.test(url.pathname), { timeout: 60_000 });
    await writeFile(join(artifacts, 'thread-url.txt'), `${page.url()}\n`, { flag: 'wx' });
    console.log(`Created: ${page.url()}. Verify model completion separately.`);
  } else console.log('[3/3] Validation passed; no model thread requested.');
} catch (error) {
  await page.screenshot({ path: join(artifacts, 'failure.png') }).catch(() => {});
  await writeFile(join(artifacts, 'failure.txt'), String(error), { flag: 'wx' });
  throw error;
} finally { await browser.close(); }

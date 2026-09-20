// Reuse every normal browser journey assertion in the actual retained Electron
// page. The desktop helper owns its lifetime; this process only disconnects.
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { connectOwnedDesktop } from './desktop_attach.mjs';
import { runBrowser } from './browser_driver.mjs';

const separator = process.argv.indexOf('--');
assert.ok(separator === 4 && process.argv[2] === '--spec', 'Usage: desktop_journey.mjs --spec <desktop.json> -- <browser arguments>');
const spec = JSON.parse(await readFile(process.argv[3], 'utf8'));
const surface = await connectOwnedDesktop(spec);
try {
  const result = await runBrowser(process.argv.slice(separator + 1), surface);
  if (result.status === 'failed') process.exitCode = 1;
} finally { await surface.close(); }

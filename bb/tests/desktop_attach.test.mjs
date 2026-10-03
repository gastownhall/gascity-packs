import test from 'node:test';
import assert from 'node:assert/strict';
import { inside, parseRuntimeProcess } from './desktop_attach.mjs';

test('desktop path ownership distinguishes siblings and the root itself', () => {
  assert.equal(inside('/tmp/bb-live-one', '/tmp/bb-live-one/desktop/profile'), true);
  for (const path of ['/tmp/bb-live-one', '/tmp/bb-live-one-more/profile', '/tmp/profile', '/Users/person/.bb'])
    assert.equal(inside('/tmp/bb-live-one', path), false);
});

test('retained BB identity requires its exact PID, UID, data directory and port', () => {
  const spec = { appPid: 42, bbDataDir: '/tmp/bb-live-one/bb-data', bbUrl: 'http://127.0.0.1:54321' };
  const text = '42 501 Mon Sep 7 12:09:05 2026 /node /runtime/bb-app.js --data-dir /tmp/bb-live-one/bb-data --server-port 54321';
  assert.equal(parseRuntimeProcess(text, spec, 501).pid, 42);
  for (const altered of [text.replace('54321', '38886'), text.replace('bb-live-one/', 'bb-live-other/'), text.replace('42 501', '43 501'), text.replace('42 501', '42 502')])
    assert.throws(() => parseRuntimeProcess(altered, spec, 501));
});

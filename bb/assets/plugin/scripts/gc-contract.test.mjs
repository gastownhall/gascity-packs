import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { compareTrees, assertGeneratedBoundary } from './gc-contract.mjs';

test('stale, missing and extra generated files fail without overwriting the candidate', async () => {
  const root = await mkdtemp(join(tmpdir(), 'gc-contract-'));
  try {
    const actual = join(root, 'actual'), expected = join(root, 'expected');
    await mkdir(actual); await mkdir(expected);
    await writeFile(join(expected, 'sdk.gen.ts'), 'generated');
    await assert.rejects(compareTrees(actual, expected), /sdk.gen.ts/);
    await writeFile(join(actual, 'sdk.gen.ts'), 'edited');
    await assert.rejects(compareTrees(actual, expected), /sdk.gen.ts/);
    assert.equal(await readFile(join(actual, 'sdk.gen.ts'), 'utf8'), 'edited');
    await writeFile(join(actual, 'sdk.gen.ts'), 'generated');
    await compareTrees(actual, expected);
    await writeFile(join(actual, 'obsolete.ts'), 'old route');
    await assert.rejects(compareTrees(actual, expected), /obsolete.ts/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('runtime endpoint literals and provider subprocess imports cannot bypass generated SDK', async () => {
  const root = await mkdtemp(join(tmpdir(), 'gc-boundary-'));
  try {
    await mkdir(join(root, 'src/generated'), { recursive: true });
    await writeFile(join(root, 'src/generated/sdk.gen.ts'), 'const url = "/v0/cities";');
    await writeFile(join(root, 'src/client.ts'), 'sdk.getV0Cities(options);');
    await assertGeneratedBoundary(root);
    await writeFile(join(root, 'src/client.ts'), 'const path = `/v0/city/${city}/sessions`;');
    await assert.rejects(assertGeneratedBoundary(root), /handwritten GC route/);
    await writeFile(join(root, 'src/client.ts'), 'import { exec } from "node:child_process";');
    await assert.rejects(assertGeneratedBoundary(root), /subprocess/);
  } finally { await rm(root, { recursive: true, force: true }); }
});

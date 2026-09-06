import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir, hostname } from "node:os";
import { join } from "node:path";
import { Journal } from "../src/journal.js";

test("journal excludes another owner and preserves a dead owner's lock during recovery", async () => {
  const dir = await mkdtemp(join(tmpdir(), "bb-journal-test-")); const journal = new Journal(dir);
  try {
    const first = await journal.acquire("thread");
    await assert.rejects(journal.acquire("thread"), /owned by/);
    await first.release();
    const lock = `${journal.path("thread")}.lock`;
    await mkdir(lock);
    const owner = { pid: 2147483647, hostname: hostname(), token: "crashed-owner" };
    await writeFile(join(lock, "owner.json"), JSON.stringify(owner));
    const recovered = await journal.acquire("thread");
    const preserved = (await readdir(dir)).find(name => name.includes(".stale-"));
    assert.ok(preserved);
    assert.deepEqual(JSON.parse(await readFile(join(dir, preserved, "owner.json"), "utf8")), owner);
    await recovered.release();
  } finally { await rm(dir, { recursive: true, force: true }); }
});

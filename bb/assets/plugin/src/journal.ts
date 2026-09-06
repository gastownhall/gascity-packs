import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, rename, rmdir, unlink, writeFile } from "node:fs/promises";
import { hostname } from "node:os";
import { join } from "node:path";
import { atomicJson } from "./config.js";
import type { Target } from "./catalog.js";

export interface Receipt {
  target: Target;
  threadId?: string;
  alias?: string;
  sessionId?: string;
  create?: { request_id: string; event_cursor: string };
  turn?: { clientRequestId: string; digest: string; state: "submitting" | "accepted" | "completed" | "failed"; request_id?: string; event_cursor?: string; messageDigest?: string; baselineMessageIds?: string[] };
}
export class Journal {
  constructor(readonly directory: string) {}
  path(threadId: string) { return join(this.directory, `${createHash("sha256").update(threadId).digest("hex")}.json`); }
  async get(threadId: string): Promise<Receipt | undefined> {
    try { return JSON.parse(await readFile(this.path(threadId), "utf8")); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined; throw error; }
  }
  put(threadId: string, value: Receipt) { return atomicJson(this.path(threadId), value); }
  async acquire(threadId: string): Promise<Lease> {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    const lock = `${this.path(threadId)}.lock`;
    const owner = { pid: process.pid, hostname: hostname(), token: randomUUID() };
    for (;;) {
      try { await mkdir(lock, { mode: 0o700 }); break; }
      catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
        const previous = await this.owner(lock);
        if (!previous || !/^[a-zA-Z0-9-]+$/.test(previous.token) || previous.hostname !== hostname())
          throw new Error(`Unverifiable ownership at ${lock}. Preserve this lock and inspect its original host before recovery.`);
        try { process.kill(previous.pid, 0); }
        catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ESRCH") throw error;
          // Only one contender may retire this exact dead owner's lock. Keep
          // both the claim and the old lock as evidence, including after crashes.
          const claim = `${lock}.reclaim-${previous.token}`;
          try { await mkdir(claim, { mode: 0o700 }); }
          catch (error) {
            if ((error as NodeJS.ErrnoException).code === "EEXIST") throw new Error(`Recovery already claimed ${lock}; inspect ${claim} before retrying.`);
            throw error;
          }
          await rename(lock, `${lock}.stale-${previous.token}`);
          continue;
        }
        throw new Error(`This BB thread is owned by process ${previous.pid} on ${previous.hostname}. Release the BB thread or stop that bridge before recovery.`);
      }
    }
    await writeFile(join(lock, "owner.json"), JSON.stringify(owner), { mode: 0o600, flag: "wx" });
    let released = false;
    return { release: async () => {
      if (released) return;
      const current = await this.owner(lock);
      if (current?.token !== owner.token) throw new Error(`Journal ownership changed at ${lock}; refusing to remove another owner's lock`);
      // Remove only these known ephemeral files, never recurse through a lock.
      await unlink(join(lock, "owner.json"));
      await rmdir(lock);
      released = true;
    } };
  }
  private async owner(lock: string): Promise<Owner | undefined> {
    try {
      const value = JSON.parse(await readFile(join(lock, "owner.json"), "utf8"));
      return Number.isSafeInteger(value.pid) && value.pid > 0 && typeof value.token === "string" && typeof value.hostname === "string" ? value : undefined;
    } catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT" || error instanceof SyntaxError) return undefined; throw error; }
  }
  async locked<T>(threadId: string, action: () => Promise<T>): Promise<T> {
    const lease = await this.acquire(threadId);
    try { return await action(); } finally { await lease.release(); }
  }
}
export interface Lease { release(): Promise<void> }
interface Owner { pid: number; hostname: string; token: string }

import { createHash } from "node:crypto";
import { mkdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { atomicJson } from "./config.js";
import type { Target } from "./catalog.js";

export interface Receipt {
  target: Target;
  sessionId?: string;
  create?: { request_id: string; event_cursor: string };
  turn?: { clientRequestId: string; digest: string; state: "submitting" | "accepted" | "completed" | "failed"; request_id?: string; event_cursor?: string };
}
export class Journal {
  constructor(readonly directory: string) {}
  path(threadId: string) { return join(this.directory, `${createHash("sha256").update(threadId).digest("hex")}.json`); }
  async get(threadId: string): Promise<Receipt | undefined> {
    try { return JSON.parse(await readFile(this.path(threadId), "utf8")); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined; throw error; }
  }
  put(threadId: string, value: Receipt) { return atomicJson(this.path(threadId), value); }
  async locked<T>(threadId: string, action: () => Promise<T>): Promise<T> {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    const lock = `${this.path(threadId)}.lock`;
    try { await mkdir(lock, { mode: 0o700 }); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "EEXIST") throw new Error("This BB thread has an active or interrupted operation. Inspect its Gas City session and journal before retrying.");
      throw error;
    }
    try { return await action(); } finally { await rm(lock, { recursive: true }); }
  }
}

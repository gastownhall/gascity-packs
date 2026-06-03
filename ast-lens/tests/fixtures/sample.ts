/**
 * User session store with optional write-through caching.
 *
 * Safe for use from a single event loop; all mutating methods funnel
 * through the private session map. Exported surface is the Store class
 * plus a handful of free functions.
 */
import { EventEmitter } from "events";
import { createHash } from "crypto";

export const DEFAULT_TTL = 30 * 60 * 1000;

const MAX_SESSIONS = 4096;

export interface SessionData {
  [key: string]: string;
}

export interface Session {
  id: string;
  userId: number;
  createdAt: number;
  expiresAt: number;
  data: SessionData;
}

export interface Repository {
  get(id: string): Session | undefined;
  save(session: Session): void;
  delete(id: string): void;
  readonly size: number;
}

export enum SessionState {
  Active = "active",
  Expired = "expired",
  Unknown = "unknown",
}

export type Clock = () => number;

interface StoreOptions {
  ttl?: number;
  clock?: Clock;
}

export class StoreError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StoreError";
  }
}

export class NotFoundError extends StoreError {}

export class ExpiredError extends StoreError {}

export class Store extends EventEmitter implements Repository {
  private sessions: Map<string, Session>;
  private ttl: number;
  private clock: Clock;

  constructor(options: StoreOptions = {}) {
    super();
    this.sessions = new Map();
    this.ttl = options.ttl ?? DEFAULT_TTL;
    this.clock = options.clock ?? Date.now;
  }

  get(id: string): Session | undefined {
    const session = this.sessions.get(id);
    if (session === undefined) {
      return undefined;
    }
    if (this.isExpired(session)) {
      this.emit("expired", id);
      return undefined;
    }
    return session;
  }

  save(session: Session): void {
    if (!session.id) {
      throw new StoreError("invalid session");
    }
    if (this.sessions.size >= MAX_SESSIONS) {
      this.evictOldest();
    }
    if (session.expiresAt === 0) {
      session.expiresAt = this.clock() + this.ttl;
    }
    this.sessions.set(session.id, session);
    this.emit("saved", session.id);
  }

  delete(id: string): void {
    this.sessions.delete(id);
  }

  get size(): number {
    return this.sessions.size;
  }

  purge(): number {
    let removed = 0;
    const now = this.clock();
    for (const [id, session] of this.sessions) {
      if (session.expiresAt !== 0 && now > session.expiresAt) {
        this.sessions.delete(id);
        removed += 1;
      }
    }
    return removed;
  }

  stats(): { total: number; active: number } {
    const now = this.clock();
    let active = 0;
    for (const session of this.sessions.values()) {
      if (!this.isExpired(session)) {
        active += 1;
      }
    }
    return { total: this.sessions.size, active };
  }

  private isExpired(session: Session): boolean {
    return session.expiresAt !== 0 && this.clock() > session.expiresAt;
  }

  private evictOldest(): void {
    let oldestId: string | undefined;
    let oldest = Number.POSITIVE_INFINITY;
    for (const [id, session] of this.sessions) {
      if (session.createdAt < oldest) {
        oldest = session.createdAt;
        oldestId = id;
      }
    }
    if (oldestId !== undefined) {
      this.sessions.delete(oldestId);
    }
  }
}

export function newSession(id: string, userId: number): Session {
  return {
    id,
    userId,
    createdAt: Date.now(),
    expiresAt: 0,
    data: {},
  };
}

export function mergeData(
  dst: SessionData | undefined,
  src: SessionData,
): SessionData {
  const out: SessionData = dst ?? {};
  for (const key of Object.keys(src)) {
    out[key] = src[key];
  }
  return out;
}

export const buildStore = (ttl: number = DEFAULT_TTL): Store => {
  return new Store({ ttl });
};

export const hashId = (raw: string): string => {
  return createHash("sha256").update(raw).digest("hex");
};

function validateId(id: string): void {
  if (id.length < 8) {
    throw new StoreError("id too short");
  }
  if (id.includes(" ")) {
    throw new StoreError("id contains space");
  }
}

function countActive(store: Store): number {
  return store.stats().active;
}

const dumpStats = (store: Store): string => {
  const { total, active } = store.stats();
  return `sessions=${total} active=${active}`;
};

export function withRetry<T>(fn: () => T, times: number = 3): T {
  let last: unknown;
  for (let i = 0; i < times; i += 1) {
    try {
      return fn();
    } catch (err) {
      last = err;
    }
  }
  throw last;
}

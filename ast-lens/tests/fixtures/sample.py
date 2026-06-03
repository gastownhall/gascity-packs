"""User session store with optional write-through caching.

This module is safe for concurrent use within a single process; the
public API guards mutable state with a re-entrant lock.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


DEFAULT_TTL = 30 * 60
MAX_SESSIONS = 4096


class StoreError(Exception):
    """Base class for all store errors."""


class NotFoundError(StoreError):
    """Raised when a session id is absent from the store."""


class ExpiredError(StoreError):
    """Raised when a session exists but its TTL has elapsed."""


@dataclass
class Session:
    """A single user session held by the store."""

    id: str
    user_id: int
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    data: dict = field(default_factory=dict)

    def is_expired(self, now: float) -> bool:
        """Report whether this session has passed its expiry instant."""
        return self.expires_at != 0.0 and now > self.expires_at

    def touch(self, ttl: float, now: float) -> None:
        """Extend this session's expiry by ttl seconds from now."""
        self.expires_at = now + ttl


class Store:
    """In-memory session store with optional write-through cache."""

    def __init__(
        self,
        ttl: float = DEFAULT_TTL,
        cache: Optional[object] = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()
        self._ttl = ttl
        self._cache = cache
        self._now = now

    def get(self, sid: str) -> Session:
        """Return the session for sid or raise NotFound / Expired."""
        with self._lock:
            sess = self._sessions.get(sid)
            if sess is None:
                raise NotFoundError(sid)
            if sess.is_expired(self._now()):
                raise ExpiredError(sid)
            return sess

    def save(self, sess: Session) -> None:
        """Insert or replace a session, evicting if at capacity."""
        if not sess.id:
            raise StoreError("invalid session")
        with self._lock:
            if len(self._sessions) >= MAX_SESSIONS:
                self._evict_oldest()
            if sess.expires_at == 0.0:
                sess.touch(self._ttl, self._now())
            self._sessions[sess.id] = sess
            if self._cache is not None:
                self._write_through(sess)

    def delete(self, sid: str) -> None:
        """Remove a session if present; absence is not an error."""
        with self._lock:
            self._sessions.pop(sid, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def purge(self) -> int:
        """Remove all expired sessions; return the count removed."""
        removed = 0
        with self._lock:
            now = self._now()
            for sid in list(self._sessions):
                if self._sessions[sid].is_expired(now):
                    del self._sessions[sid]
                    removed += 1
        return removed

    def stats(self) -> tuple[int, int]:
        """Return (total, active) session counts."""
        with self._lock:
            now = self._now()
            active = sum(
                1 for s in self._sessions.values() if not s.is_expired(now)
            )
            return len(self._sessions), active

    def _evict_oldest(self) -> None:
        """Drop the session with the earliest created_at (private)."""
        oldest_id = None
        oldest = float("inf")
        for sid, sess in self._sessions.items():
            if sess.created_at < oldest:
                oldest = sess.created_at
                oldest_id = sid
        if oldest_id is not None:
            del self._sessions[oldest_id]

    def _write_through(self, sess: Session) -> None:
        """Mirror a session into the attached cache, best-effort."""
        try:
            self._cache.set(f"sess:{sess.id}", sess.user_id, self._ttl)
        except Exception:
            pass


def new_session(sid: str, user_id: int) -> Session:
    """Build a Session with a fresh creation timestamp."""
    return Session(id=sid, user_id=user_id)


def merge_data(dst: Optional[dict], src: dict) -> dict:
    """Copy src entries into dst, returning the mutated dst."""
    if dst is None:
        dst = {}
    for key, value in src.items():
        dst[key] = value
    return dst


def build_store(ttl: float = DEFAULT_TTL, cache: Optional[object] = None) -> Store:
    """Construct a Store, wiring up the supplied cache if present."""
    store = Store(ttl=ttl, cache=cache)
    return store


def _validate_id(sid: str) -> None:
    """Enforce the internal id format (private helper)."""
    if len(sid) < 8:
        raise StoreError("id too short")
    if " " in sid:
        raise StoreError("id contains space")


def _count_active(store: Store) -> int:
    """Tally non-expired sessions (private helper)."""
    total, active = store.stats()
    return active


def _dump_stats(store: Store) -> str:
    """Render store internals for diagnostics (private helper)."""
    total, active = store.stats()
    return f"sessions={total} active={active}"


def with_retry(times: int = 3):
    """Decorator: retry the wrapped callable up to `times` times."""

    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            last = None
            for _ in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last = exc
            if last is not None:
                raise last

        return wrapper

    return decorator


@with_retry(times=2)
def flush_store(store: Store) -> int:
    """Purge a store, retrying transient failures."""
    return store.purge()


class Metrics:
    """Lightweight counter bag for store observability."""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0

    def record_hit(self) -> None:
        """Increment the hit counter."""
        self.hits += 1

    def record_miss(self) -> None:
        """Increment the miss counter."""
        self.misses += 1

    def ratio(self) -> float:
        """Return the hit ratio, or 0.0 when no observations exist."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

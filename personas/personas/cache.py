"""Warm-cache + TTL lifecycle — materialized personas kept warm for reuse.

The README lifecycle: materialize -> execute -> dematerialize -> *warm* -> age out.
This module owns the **warm** and **age-out** phases. A materialized persona — its
assembled, ready-to-overlay working context — lingers in a shared, JSON-backed cache
so the next agent that needs it reuses it **without paying the materialize cost
again**, and it is evicted once it goes cold per the configured
:class:`~personas.registry.CachePolicy`:

- **Sliding idle TTL** (default 30 min): refreshed on every reuse. Evicts a persona
  no agent has equipped within the window.
- **Absolute ceiling** (default 2 h): from first materialize. Force-refreshes even a
  continuously-reused persona so it picks up registry updates and the cache stays
  bounded.

What is cached is the **materialized payload**, not just a last-used timestamp: each
:class:`WarmEntry` carries the persona's rendered ``overlay`` (the working context the
equip step assembles) plus a ``fingerprint`` of the persona definition it was rendered
from. :meth:`WarmCache.equip` takes a ``materialize`` thunk and calls it **only** on a
cold or stale equip — a warm reuse returns the stored overlay untouched, which is the
cost the cache exists to amortize. The fingerprint makes that amortization safe: if the
registry definition drifts, the stored overlay is re-materialized immediately rather
than waiting for the ceiling, so a warm reuse never serves a stale persona.

Eviction is lazy: every :meth:`WarmCache.equip` / :meth:`WarmCache.status` sweeps
expired entries first, and :meth:`WarmCache.sweep` can be called explicitly. ``now``
is injected into every time-dependent method so the policy is deterministically
testable; callers pass :func:`time.time`.

Writes are atomic (temp file + ``os.replace``) so a concurrent reader never sees a
half-written cache. Concurrent writers are last-writer-wins — acceptable for a warm
cache whose entries are always re-derivable from the registry.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from typing import Callable, Optional

from personas.registry import CachePolicy

#: Bumped from v0 when entries gained the materialized ``overlay`` + ``fingerprint``.
#: The reader tolerates rows missing those fields, so a v0 file still loads (its entries
#: simply re-materialize on next equip), and the cache is always re-derivable anyway.
SCHEMA = "personas.warm-cache.v1"


@dataclass(frozen=True)
class WarmEntry:
    """One materialized persona in the warm cache.

    ``overlay`` is the materialized payload — the rendered working context a warm reuse
    returns instead of re-assembling. ``fingerprint`` is a digest of the persona
    definition it was rendered from, so :meth:`WarmCache.equip` can detect a registry
    edit and re-materialize before the ceiling. Both default to empty for a
    metadata-only entry (no materializer supplied) and for forward-compatible reads of a
    pre-payload cache file.
    """

    persona_id: str
    materialized_at: float  # epoch seconds of first materialize (drives the ceiling)
    last_used_at: float     # epoch seconds of most recent equip (drives the idle TTL)
    use_count: int          # how many times it has been equipped while warm
    overlay: str = ""       # the materialized working context (what the cache amortizes)
    fingerprint: str = ""   # digest of the persona definition this overlay was made from

    def idle_age(self, now: float) -> float:
        return max(0.0, now - self.last_used_at)

    def total_age(self, now: float) -> float:
        return max(0.0, now - self.materialized_at)

    def expiry_reason(self, policy: CachePolicy, now: float) -> Optional[str]:
        """``None`` if live; else ``"ceiling"`` or ``"idle"`` (ceiling checked first)."""
        if self.total_age(now) > policy.ceiling_ttl_seconds:
            return "ceiling"
        if self.idle_age(now) > policy.idle_ttl_seconds:
            return "idle"
        return None

    def is_live(self, policy: CachePolicy, now: float) -> bool:
        return self.expiry_reason(policy, now) is None

    def remaining_idle(self, policy: CachePolicy, now: float) -> float:
        return policy.idle_ttl_seconds - self.idle_age(now)

    def remaining_ceiling(self, policy: CachePolicy, now: float) -> float:
        return policy.ceiling_ttl_seconds - self.total_age(now)


@dataclass(frozen=True)
class EquipOutcome:
    """Result of :meth:`WarmCache.equip` — the warm entry and whether it was a reuse."""

    entry: WarmEntry
    was_warm: bool                # True = reused an already-warm persona (no materialize)
    evicted: tuple[WarmEntry, ...]  # entries swept on this equip (cold/expired)

    @property
    def overlay(self) -> str:
        """The materialized working context for this equip (served warm or freshly made)."""
        return self.entry.overlay


@dataclass(frozen=True)
class EntryStatus:
    """A warm entry decorated with its live/expired verdict for inspection."""

    entry: WarmEntry
    live: bool
    expiry_reason: Optional[str]
    remaining_idle: float
    remaining_ceiling: float


class WarmCache:
    """A JSON-backed warm cache of materialized personas under a single policy."""

    def __init__(self, path: str | os.PathLike[str], policy: CachePolicy) -> None:
        self.path = os.fspath(path)
        self.policy = policy

    # ---- persistence ------------------------------------------------------- #

    def _read(self) -> dict[str, WarmEntry]:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (FileNotFoundError, ValueError, OSError):
            # Missing or corrupt cache is not an error: a warm cache is always
            # re-derivable, so we start empty rather than fail the equip path.
            return {}
        entries: dict[str, WarmEntry] = {}
        for rec in raw.get("entries", []):
            try:
                entries[str(rec["persona_id"])] = WarmEntry(
                    persona_id=str(rec["persona_id"]),
                    materialized_at=float(rec["materialized_at"]),
                    last_used_at=float(rec["last_used_at"]),
                    use_count=int(rec.get("use_count", 1)),
                    # Absent on a v0 (pre-payload) file: degrade to a metadata-only entry
                    # that re-materializes on its next equip rather than failing the read.
                    overlay=str(rec.get("overlay", "")),
                    fingerprint=str(rec.get("fingerprint", "")),
                )
            except (KeyError, TypeError, ValueError):
                continue  # skip malformed rows, keep the rest
        return entries

    def _write(self, entries: dict[str, WarmEntry]) -> None:
        ordered = sorted(entries.values(), key=lambda e: e.persona_id)
        doc = {"schema": SCHEMA, "entries": [asdict(e) for e in ordered]}
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        # Atomic replace: write a sibling temp file, fsync, then rename over the target.
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".warm-cache.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # ---- introspection ----------------------------------------------------- #

    def entries(self) -> dict[str, WarmEntry]:
        """All persisted entries (including any that are now expired)."""
        return self._read()

    def get(self, persona_id: str, now: float) -> Optional[WarmEntry]:
        """Return the entry for ``persona_id`` only if it is still live, else ``None``."""
        entry = self._read().get(persona_id)
        if entry is not None and entry.is_live(self.policy, now):
            return entry
        return None

    def status(self, now: float, *, prune: bool = True) -> list[EntryStatus]:
        """Live + expired verdict for every entry, newest-used first.

        With ``prune`` (default) expired entries are swept from disk as a side effect,
        matching the lazy-eviction contract; the returned list still describes them.
        """
        entries = self._read()
        out = [
            EntryStatus(
                entry=e,
                live=e.is_live(self.policy, now),
                expiry_reason=e.expiry_reason(self.policy, now),
                remaining_idle=e.remaining_idle(self.policy, now),
                remaining_ceiling=e.remaining_ceiling(self.policy, now),
            )
            for e in entries.values()
        ]
        out.sort(key=lambda s: s.entry.last_used_at, reverse=True)
        if prune:
            live = {pid: e for pid, e in entries.items() if e.is_live(self.policy, now)}
            if len(live) != len(entries):
                self._write(live)
        return out

    # ---- mutation ---------------------------------------------------------- #

    def equip(
        self,
        persona_id: str,
        now: float,
        *,
        materialize: Optional[Callable[[], str]] = None,
        fingerprint: str = "",
    ) -> EquipOutcome:
        """Materialize ``persona_id`` (or reuse it if already warm), then persist.

        Sweeps expired entries first (lazy eviction), then either reuses a still-warm
        persona or materializes a fresh one:

        - **Warm reuse** (``was_warm`` True). A live entry whose payload is still valid is
          *touched* — ``last_used_at`` slides to ``now`` and ``use_count`` increments —
          and its stored ``overlay`` is returned **without calling** ``materialize``.
          This is the cost the warm cache exists to amortize.
        - **Materialize** (``was_warm`` False). On a cold, ceiling/idle-expired, or
          definition-drifted persona, ``materialize`` (if given) is invoked once to
          assemble the overlay, and the entry is stored fresh with ``materialized_at``
          reset to ``now`` — so a ceiling refresh and a registry edit both genuinely
          re-read the registry.

        ``materialize`` is the (potentially expensive) thunk that assembles the persona's
        working context; omit it for a metadata-only entry (overlay stays empty), which
        preserves the pre-payload behavior. ``fingerprint`` is the current persona
        definition's digest: a live entry whose stored fingerprint differs is treated as
        stale and re-materialized, so an edited persona is picked up immediately rather
        than only at the ceiling. When ``fingerprint`` is empty no drift check is done.
        """
        entries = self._read()
        evicted = tuple(
            e for e in entries.values() if not e.is_live(self.policy, now)
        )
        live = {pid: e for pid, e in entries.items() if e.is_live(self.policy, now)}

        existing = live.get(persona_id)
        # A warm reuse needs a live entry that (a) was rendered from the current
        # definition — or no fingerprint was supplied to check against — and (b) actually
        # carries a payload to return when a materializer is in play. Otherwise we
        # re-materialize, paying the cost the cache could not amortize this time.
        fingerprint_ok = not fingerprint or (
            existing is not None and existing.fingerprint == fingerprint
        )
        has_payload = materialize is None or (existing is not None and existing.overlay != "")
        if existing is not None and fingerprint_ok and has_payload:
            entry = replace(existing, last_used_at=now, use_count=existing.use_count + 1)
            was_warm = True
        else:
            overlay = materialize() if materialize is not None else ""
            entry = WarmEntry(
                persona_id=persona_id,
                materialized_at=now,
                last_used_at=now,
                use_count=1,
                overlay=overlay,
                fingerprint=fingerprint,
            )
            was_warm = False

        live[persona_id] = entry
        self._write(live)
        return EquipOutcome(entry=entry, was_warm=was_warm, evicted=evicted)

    def sweep(self, now: float) -> list[WarmEntry]:
        """Evict every expired entry and return what was removed."""
        entries = self._read()
        evicted = [e for e in entries.values() if not e.is_live(self.policy, now)]
        if evicted:
            live = {pid: e for pid, e in entries.items() if e.is_live(self.policy, now)}
            self._write(live)
        return evicted

    def evict(self, persona_id: str) -> bool:
        """Dematerialize a specific persona now (regardless of TTL). True if removed."""
        entries = self._read()
        if persona_id not in entries:
            return False
        del entries[persona_id]
        self._write(entries)
        return True

    def clear(self) -> int:
        """Drop the whole warm cache. Returns the number of entries removed."""
        n = len(self._read())
        self._write({})
        return n


# --------------------------------------------------------------------------- #
# Cache-path resolution                                                          #
# --------------------------------------------------------------------------- #

_CACHE_BASENAME = "warm-cache.json"


def default_cache_path(start_dir: str | None = None, env: Optional[dict] = None) -> str:
    """Resolve where the shared warm cache lives.

    Precedence (first hit wins):

    1. ``PERSONAS_CACHE_FILE`` — an explicit file path.
    2. ``PERSONAS_CACHE_DIR`` — a directory; the cache is ``<dir>/warm-cache.json``.
    3. ``GC_RIG_ROOT`` — the rig repo (shared by all of a rig's agents);
       ``<rig>/.beads/personas/warm-cache.json``. This is the intended home: a cache
       under ``.beads`` is shared, so the next agent reuses a warm persona.
    4. Walk up from ``start_dir`` (or cwd) for a ``.beads`` directory; use
       ``<that>/.beads/personas/warm-cache.json``.
    5. Fall back to ``~/.gc/runtime/personas/warm-cache.json``.
    """
    env = os.environ if env is None else env

    explicit = env.get("PERSONAS_CACHE_FILE")
    if explicit:
        return os.path.abspath(explicit)

    cache_dir = env.get("PERSONAS_CACHE_DIR")
    if cache_dir:
        return os.path.abspath(os.path.join(cache_dir, _CACHE_BASENAME))

    rig_root = env.get("GC_RIG_ROOT")
    if rig_root and os.path.isdir(rig_root):
        return os.path.join(rig_root, ".beads", "personas", _CACHE_BASENAME)

    d = os.path.abspath(start_dir or os.getcwd())
    for _ in range(24):
        if os.path.isdir(os.path.join(d, ".beads")):
            return os.path.join(d, ".beads", "personas", _CACHE_BASENAME)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    home = env.get("GC_HOME") or os.path.expanduser("~/.gc")
    return os.path.join(home, "runtime", "personas", _CACHE_BASENAME)

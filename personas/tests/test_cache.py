"""personas — warm-cache + TTL lifecycle tests.

Owns the lifecycle math (README "Lifecycle TTL"): materialize vs warm reuse, the sliding
idle TTL, the absolute ceiling, lazy + explicit eviction, and a durable round-trip.
``now`` is injected throughout so the policy is deterministic. Pure stdlib + pytest.
"""

from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from personas import cache as C  # noqa: E402
from personas.registry import CachePolicy  # noqa: E402

# Small, exact TTLs so the arithmetic in assertions is obvious.
POLICY = CachePolicy(idle_ttl_seconds=100.0, ceiling_ttl_seconds=1000.0)


@pytest.fixture
def warm(tmp_path):
    return C.WarmCache(tmp_path / "warm-cache.json", POLICY)


# ---- materialize vs warm reuse --------------------------------------------- #


def test_cold_equip_materializes(warm):
    out = warm.equip("p", now=0.0)
    assert out.was_warm is False
    assert out.entry.use_count == 1
    assert out.entry.materialized_at == 0.0
    assert out.entry.last_used_at == 0.0


def test_warm_equip_reuses_and_touches(warm):
    warm.equip("p", now=0.0)
    out = warm.equip("p", now=50.0)  # within idle TTL
    assert out.was_warm is True
    assert out.entry.use_count == 2
    assert out.entry.materialized_at == 0.0     # unchanged
    assert out.entry.last_used_at == 50.0       # slid forward


def test_get_returns_live_entry_only(warm):
    warm.equip("p", now=0.0)
    assert warm.get("p", now=50.0) is not None
    assert warm.get("p", now=200.0) is None     # idle-expired
    assert warm.get("absent", now=0.0) is None


# ---- sliding idle TTL ------------------------------------------------------ #


def test_idle_expiry(warm):
    warm.equip("p", now=0.0)
    # 101s of idle (> 100s) -> expired and re-materialized fresh on next equip.
    out = warm.equip("p", now=101.0)
    assert out.was_warm is False
    assert out.entry.materialized_at == 101.0
    assert out.entry.use_count == 1
    assert any(e.persona_id == "p" for e in out.evicted)


def test_idle_slides_on_reuse(warm):
    warm.equip("p", now=0.0)
    warm.equip("p", now=80.0)   # refresh idle clock
    warm.equip("p", now=160.0)  # 80s since last use -> still live
    assert warm.get("p", now=160.0) is not None


# ---- absolute ceiling ------------------------------------------------------ #


def test_ceiling_forces_refresh_even_when_reused(warm):
    warm.equip("p", now=0.0)
    # Keep it warm via reuse right up to the ceiling...
    for t in (90.0, 180.0, 270.0, 360.0, 450.0, 540.0, 630.0, 720.0, 810.0, 900.0, 990.0):
        out = warm.equip("p", now=t)
        assert out.was_warm is True
    # ...but past the 1000s ceiling it is force-refreshed (materialized anew).
    out = warm.equip("p", now=1001.0)
    assert out.was_warm is False
    assert out.entry.materialized_at == 1001.0
    assert out.entry.use_count == 1


def test_expiry_reason_prefers_ceiling(warm):
    e = C.WarmEntry("p", materialized_at=0.0, last_used_at=0.0, use_count=1)
    # Past both windows; ceiling is the reported reason.
    assert e.expiry_reason(POLICY, now=2000.0) == "ceiling"
    # Past idle only.
    assert e.expiry_reason(POLICY, now=150.0) == "idle"
    # Within both.
    assert e.expiry_reason(POLICY, now=50.0) is None


# ---- eviction: lazy, sweep, evict, clear ----------------------------------- #


def test_equip_sweeps_other_expired_entries(warm):
    warm.equip("stale", now=0.0)
    out = warm.equip("fresh", now=500.0)   # 'stale' is now idle-expired (>100s)
    assert "stale" in [e.persona_id for e in out.evicted]
    assert warm.get("stale", now=500.0) is None
    assert warm.get("fresh", now=500.0) is not None


def test_sweep_returns_evicted(warm):
    warm.equip("a", now=0.0)
    warm.equip("b", now=50.0)               # both live; no eviction yet
    evicted = warm.sweep(now=120.0)         # 'a' idle-expired (120>100); 'b' live (70<100)
    assert [e.persona_id for e in evicted] == ["a"]
    assert warm.get("b", now=120.0) is not None


def test_evict_specific(warm):
    warm.equip("p", now=0.0)
    assert warm.evict("p") is True
    assert warm.evict("p") is False         # already gone
    assert warm.get("p", now=0.0) is None


def test_clear_drops_all(warm):
    warm.equip("a", now=0.0)
    warm.equip("b", now=0.0)
    assert warm.clear() == 2
    assert warm.entries() == {}


# ---- status ---------------------------------------------------------------- #


def test_status_reports_live_and_remaining(warm):
    warm.equip("p", now=0.0)
    [s] = warm.status(now=40.0)
    assert s.live is True
    assert s.expiry_reason is None
    assert s.remaining_idle == pytest.approx(60.0)      # 100 - 40
    assert s.remaining_ceiling == pytest.approx(960.0)  # 1000 - 40


def test_status_prunes_expired_by_default(warm):
    warm.equip("p", now=0.0)
    warm.status(now=200.0)                  # idle-expired -> pruned as a side effect
    assert warm.entries() == {}


def test_status_can_skip_prune(warm):
    warm.equip("p", now=0.0)
    statuses = warm.status(now=200.0, prune=False)
    assert statuses and statuses[0].live is False
    assert "p" in warm.entries()            # still on disk


# ---- persistence ----------------------------------------------------------- #


def test_round_trips_through_disk(warm):
    warm.equip("p", now=0.0)
    warm.equip("p", now=10.0)
    reopened = C.WarmCache(warm.path, POLICY)
    e = reopened.entries()["p"]
    assert e.use_count == 2
    assert e.last_used_at == 10.0


def test_corrupt_cache_is_treated_as_empty(tmp_path):
    path = tmp_path / "warm-cache.json"
    path.write_text("{ not json")
    wc = C.WarmCache(path, POLICY)
    assert wc.entries() == {}
    # And it recovers — a subsequent equip writes a clean file.
    wc.equip("p", now=0.0)
    assert "p" in wc.entries()


def test_missing_cache_file_is_empty(warm):
    assert warm.entries() == {}
    assert warm.sweep(now=0.0) == []


# ---- path resolution ------------------------------------------------------- #


def test_cache_path_prefers_explicit_file(tmp_path):
    env = {"PERSONAS_CACHE_FILE": str(tmp_path / "x.json")}
    assert C.default_cache_path(env=env) == os.path.abspath(str(tmp_path / "x.json"))


def test_cache_path_uses_cache_dir(tmp_path):
    env = {"PERSONAS_CACHE_DIR": str(tmp_path)}
    assert C.default_cache_path(env=env) == os.path.abspath(str(tmp_path / "warm-cache.json"))


def test_cache_path_uses_rig_root(tmp_path):
    env = {"GC_RIG_ROOT": str(tmp_path)}
    got = C.default_cache_path(env=env)
    assert got == os.path.join(str(tmp_path), ".beads", "personas", "warm-cache.json")


def test_cache_path_walks_up_for_beads(tmp_path):
    beads = tmp_path / ".beads"
    beads.mkdir()
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)
    got = C.default_cache_path(start_dir=str(start), env={})
    assert got == os.path.join(str(tmp_path), ".beads", "personas", "warm-cache.json")


# ---- materialized payload: the cost the warm cache amortizes ---------------- #


class _Materializer:
    """A counting overlay thunk so a test can assert exactly when materialize ran."""

    def __init__(self, text: str = "OVERLAY") -> None:
        self.text = text
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.text


def test_cold_equip_runs_materialize_and_stores_overlay(warm):
    mk = _Materializer("MATERIALIZED")
    out = warm.equip("p", now=0.0, materialize=mk, fingerprint="fp1")
    assert out.was_warm is False
    assert mk.calls == 1
    assert out.overlay == "MATERIALIZED"          # EquipOutcome.overlay convenience
    assert out.entry.overlay == "MATERIALIZED"
    assert out.entry.fingerprint == "fp1"


def test_warm_reuse_serves_cached_overlay_without_rematerializing(warm):
    mk = _Materializer("MATERIALIZED")
    warm.equip("p", now=0.0, materialize=mk, fingerprint="fp1")
    out = warm.equip("p", now=50.0, materialize=mk, fingerprint="fp1")  # within idle TTL
    assert out.was_warm is True
    assert out.overlay == "MATERIALIZED"          # same payload, served warm
    assert mk.calls == 1                           # materialize was NOT called again
    assert out.entry.use_count == 2


def test_idle_expiry_rematerializes(warm):
    mk = _Materializer()
    warm.equip("p", now=0.0, materialize=mk, fingerprint="fp")
    out = warm.equip("p", now=101.0, materialize=mk, fingerprint="fp")  # idle-expired
    assert out.was_warm is False
    assert mk.calls == 2                           # paid the materialize cost again


def test_ceiling_refresh_rematerializes(warm):
    mk = _Materializer()
    warm.equip("p", now=0.0, materialize=mk, fingerprint="fp")
    # Kept warm by steady reuse (each within the 100s idle window) right up to the
    # ceiling — no re-materialize...
    for t in (90.0, 180.0, 270.0, 360.0, 450.0, 540.0, 630.0, 720.0, 810.0, 900.0, 990.0):
        warm.equip("p", now=t, materialize=mk, fingerprint="fp")
    assert mk.calls == 1
    # ...then past the 1000s ceiling it is force-refreshed.
    out = warm.equip("p", now=1001.0, materialize=mk, fingerprint="fp")
    assert out.was_warm is False
    assert mk.calls == 2
    assert out.entry.materialized_at == 1001.0


# ---- fingerprint: pick up registry edits before the ceiling ----------------- #


def test_fingerprint_drift_rematerializes_within_ttl(warm):
    v1, v2 = _Materializer("OVERLAY-v1"), _Materializer("OVERLAY-v2")
    warm.equip("p", now=0.0, materialize=v1, fingerprint="fp-v1")
    # Same persona, still well within the idle TTL, but its definition changed:
    out = warm.equip("p", now=10.0, materialize=v2, fingerprint="fp-v2")
    assert out.was_warm is False                   # re-materialized despite being time-live
    assert out.overlay == "OVERLAY-v2"
    assert out.entry.fingerprint == "fp-v2"
    assert out.entry.materialized_at == 10.0       # ceiling clock reset on refresh
    assert v1.calls == 1 and v2.calls == 1


def test_matching_fingerprint_reuses_within_ttl(warm):
    mk = _Materializer()
    warm.equip("p", now=0.0, materialize=mk, fingerprint="fp")
    out = warm.equip("p", now=10.0, materialize=mk, fingerprint="fp")
    assert out.was_warm is True
    assert mk.calls == 1


def test_no_fingerprint_skips_the_drift_check(warm):
    # Omitting the fingerprint disables drift detection: a live entry is reused on TTL
    # alone (the pre-payload behavior), even though the materializer text differs.
    a, b = _Materializer("A"), _Materializer("B")
    warm.equip("p", now=0.0, materialize=a)        # no fingerprint
    out = warm.equip("p", now=10.0, materialize=b)  # no fingerprint
    assert out.was_warm is True
    assert out.overlay == "A"                       # still serving the first payload
    assert b.calls == 0


# ---- payload persistence + the v0 -> v1 upgrade path ------------------------ #


def test_overlay_round_trips_through_disk_and_serves_warm(warm):
    mk = _Materializer("PERSISTED")
    warm.equip("p", now=0.0, materialize=mk, fingerprint="fp")
    # A fresh cache object over the same file == another agent/process on the shared cache.
    reopened = C.WarmCache(warm.path, POLICY)
    e = reopened.entries()["p"]
    assert e.overlay == "PERSISTED"
    assert e.fingerprint == "fp"
    out = reopened.equip("p", now=20.0, materialize=mk, fingerprint="fp")
    assert out.was_warm is True                     # reused across the process boundary
    assert out.overlay == "PERSISTED"
    assert mk.calls == 1                            # the other process did not re-materialize


def test_get_returns_entry_with_overlay(warm):
    warm.equip("p", now=0.0, materialize=_Materializer("OV"), fingerprint="fp")
    e = warm.get("p", now=10.0)
    assert e is not None
    assert e.overlay == "OV"
    assert e.fingerprint == "fp"


def test_metadata_only_entry_rematerializes_when_payload_needed(warm):
    # A pre-payload (v0) entry, or any equip that stored no overlay, has nothing to serve
    # warm: a later equip that DOES supply a materializer must re-materialize.
    warm.equip("p", now=0.0)                        # metadata-only: overlay == ""
    assert warm.entries()["p"].overlay == ""
    mk = _Materializer("FRESH")
    out = warm.equip("p", now=10.0, materialize=mk)
    assert out.was_warm is False                    # had no payload to reuse
    assert out.overlay == "FRESH"
    assert mk.calls == 1


def test_equip_without_materializer_stays_metadata_only(warm):
    out = warm.equip("p", now=0.0)
    assert out.overlay == ""
    assert out.entry.fingerprint == ""

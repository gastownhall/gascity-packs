"""cockpit — discovery / probe / descriptor tests.

The probe and readiness logic are exercised hermetically: ``_http_get_json`` is
monkeypatched so no network is touched, covering reachable / unreachable, version
match/mismatch, and missing-path verdicts. The descriptor round-trips on disk
under ``tmp_path`` and ``GC_HOME`` is honored.

Pure stdlib + pytest.
"""

from __future__ import annotations

import os
import sys
import urllib.error

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cockpit import discovery as D  # noqa: E402

FAKE_OPENAPI = {
    "info": {"title": "Gas City Supervisor API", "version": "0.1.0"},
    "paths": {"/health": {}, "/v0/cities": {}, "/v0/readiness": {}},
}
FAKE_HEALTH = {"status": "ok", "build_id": "abc-dirty"}


def _getter(mapping):
    """Build a fake _http_get_json that dispatches by URL suffix."""

    def getter(url, timeout):
        for suffix, val in mapping.items():
            if url.endswith(suffix):
                if isinstance(val, Exception):
                    raise val
                return val
        raise OSError(f"unexpected url {url}")

    return getter


def test_gc_home_honors_env(monkeypatch):
    monkeypatch.setenv("GC_HOME", "/tmp/gchome")
    assert D.gc_home() == "/tmp/gchome"
    assert D.descriptor_path() == os.path.join("/tmp/gchome", D.DESCRIPTOR_RELPATH)


def test_probe_api_reachable(monkeypatch):
    monkeypatch.setattr(
        D, "_http_get_json", _getter({"/openapi.json": FAKE_OPENAPI, "/health": FAKE_HEALTH})
    )
    p = D.probe_api("http://x:8372")
    assert p["reachable"] is True
    assert p["api_version"] == "0.1.0"
    assert p["api_title"] == "Gas City Supervisor API"
    assert "/health" in p["paths"]
    assert p["build_id"] == "abc-dirty"
    assert p["errors"] == []


def test_probe_api_health_failure_is_non_fatal(monkeypatch):
    monkeypatch.setattr(
        D,
        "_http_get_json",
        _getter({"/openapi.json": FAKE_OPENAPI, "/health": urllib.error.URLError("boom")}),
    )
    p = D.probe_api("http://x:8372")
    assert p["reachable"] is True  # openapi is the reachability signal
    assert any("health" in e for e in p["errors"])


def test_probe_api_unreachable(monkeypatch):
    monkeypatch.setattr(
        D, "_http_get_json", _getter({"/openapi.json": urllib.error.URLError("refused")})
    )
    p = D.probe_api("http://x:8372")
    assert p["reachable"] is False
    assert p["errors"]


def test_assess_readiness_ok():
    probe = {"reachable": True, "api_version": "0.1.0", "paths": ["/a", "/b"]}
    v = D.assess_readiness(probe, "0.1.0", ["/a", "/b"])
    assert v["ready"] is True
    assert v["missing_paths"] == []


def test_assess_readiness_version_mismatch():
    probe = {"reachable": True, "api_version": "9.9.9", "paths": ["/a"]}
    v = D.assess_readiness(probe, "0.1.0", ["/a"])
    assert v["ready"] is False
    assert v["version_ok"] is False


def test_assess_readiness_missing_paths():
    probe = {"reachable": True, "api_version": "0.1.0", "paths": ["/a"]}
    v = D.assess_readiness(probe, "0.1.0", ["/a", "/b"])
    assert v["ready"] is False
    assert v["missing_paths"] == ["/b"]


def test_assess_readiness_unreachable_lists_all_paths():
    v = D.assess_readiness({"reachable": False}, "0.1.0", ["/a", "/b"])
    assert v["ready"] is False
    assert v["missing_paths"] == ["/a", "/b"]


def test_descriptor_round_trip(tmp_path):
    probe = {"base_url": "http://x:8372", "api_version": "0.1.0", "api_title": "T"}
    desc = D.build_descriptor(probe, cities=["c1"], home=str(tmp_path))
    assert desc["kind"] == D.DESCRIPTOR_KIND
    assert desc["base_url"] == "http://x:8372"
    assert desc["cities"] == ["c1"]
    assert desc["auth"]["type"] == "localhost-trust"
    out = tmp_path / "sub" / "d.json"
    written = D.write_descriptor(desc, str(out))
    assert os.path.exists(written)
    assert D.read_descriptor(str(out)) == desc


def test_read_descriptor_absent(tmp_path):
    assert D.read_descriptor(str(tmp_path / "nope.json")) is None

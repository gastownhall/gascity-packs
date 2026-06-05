"""cockpit — CLI surface tests (ready / discover / contract / adapter).

Own the CLI contract and its exit-code state machine: ready returns 0 / 1 / 2 for
ready / incompatible / unreachable; discover writes a descriptor; contract and
adapter render both text and JSON. The /v0 API is faked by monkeypatching
``discovery._http_get_json`` so nothing touches the network.

Pure stdlib + pytest. The pack root is importable so ``cockpit.cli.main`` resolves.
"""

from __future__ import annotations

import io
import json
import os
import sys
import urllib.error

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cockpit import cli  # noqa: E402
from cockpit import contract as K  # noqa: E402
from cockpit import discovery as D  # noqa: E402


def run(argv):
    out = io.StringIO()
    rc = cli.main(argv, out=out)
    return rc, out.getvalue()


def _openapi_with(paths, version="0.1.0"):
    return {
        "info": {"title": "Gas City Supervisor API", "version": version},
        "paths": {p: {} for p in paths},
    }


def _patch_api(monkeypatch, openapi, health=None):
    health = health if health is not None else {"status": "ok", "build_id": "b-dirty"}

    def getter(url, timeout):
        if url.endswith("/openapi.json"):
            return openapi
        if url.endswith("/health"):
            return health
        raise OSError(f"unexpected url {url}")

    monkeypatch.setattr(D, "_http_get_json", getter)


# ---- contract -------------------------------------------------------------- #

def test_contract_json():
    rc, s = run(["contract", "--json"])
    assert rc == 0
    assert json.loads(s)["api"]["required_version"] == "0.1.0"


def test_contract_text():
    rc, s = run(["contract"])
    assert rc == 0
    assert "required version: 0.1.0" in s
    assert "/v0/city/{cityName}/extmsg/adapters" in s


# ---- ready ----------------------------------------------------------------- #

def test_ready_ok(monkeypatch):
    req = K.required_paths(K.load_contract())
    _patch_api(monkeypatch, _openapi_with(req))
    rc, s = run(["ready"])
    assert rc == 0
    assert "COCKPIT-READY" in s


def test_ready_version_mismatch(monkeypatch):
    req = K.required_paths(K.load_contract())
    _patch_api(monkeypatch, _openapi_with(req, version="9.9.9"))
    rc, s = run(["ready"])
    assert rc == 1
    assert "MISMATCH" in s


def test_ready_missing_paths(monkeypatch):
    _patch_api(monkeypatch, _openapi_with(["/health"]))  # missing most required
    rc, s = run(["ready"])
    assert rc == 1
    assert "MISSING" in s


def test_ready_unreachable(monkeypatch):
    def boom(url, timeout):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(D, "_http_get_json", boom)
    rc, s = run(["ready"])
    assert rc == 2
    assert "UNREACHABLE" in s


def test_ready_json_ok(monkeypatch):
    req = K.required_paths(K.load_contract())
    _patch_api(monkeypatch, _openapi_with(req))
    rc, s = run(["ready", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["verdict"]["ready"] is True


# ---- discover -------------------------------------------------------------- #

def test_discover_write(monkeypatch, tmp_path):
    _patch_api(monkeypatch, _openapi_with(["/health"]))
    out = tmp_path / "desc.json"
    rc, s = run(["discover", "--out", str(out), "--city", "mycity"])
    assert rc == 0
    assert out.exists()
    desc = json.loads(out.read_text())
    assert desc["api_version"] == "0.1.0"
    assert desc["cities"] == ["mycity"]


def test_discover_no_write_says_so(monkeypatch):
    _patch_api(monkeypatch, _openapi_with(["/health"]))
    rc, s = run(["discover"])
    assert rc == 0
    assert "not written" in s


def test_discover_unreachable(monkeypatch):
    def boom(url, timeout):
        raise urllib.error.URLError("x")

    monkeypatch.setattr(D, "_http_get_json", boom)
    rc, s = run(["discover"])
    assert rc == 2


# ---- adapter --------------------------------------------------------------- #

def test_adapter_json_fills_city():
    rc, s = run(["adapter", "--city", "mycity", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["method"] == "POST"
    assert data["endpoint"] == "/v0/city/mycity/extmsg/adapters"
    assert data["body"]["provider"] == "cockpit"


def test_adapter_text_flags_runtime_and_leaves_template():
    rc, s = run(["adapter"])
    assert rc == 0
    assert "RUNTIME" in s
    assert "{cityName}" in s  # no --city -> template left in place

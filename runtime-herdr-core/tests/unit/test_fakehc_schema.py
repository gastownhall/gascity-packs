"""The fake-hc schema guard: every fake result and every client
request is validated against the hc OpenRPC schema vendored at the pinned tag."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Dict

import pytest

from fakehc import FakeHc
from fakehc.rawclient import raw_call
from fakehc.schema import PROVENANCE_PATH, SCHEMA_PATH, SchemaGuard

TERMINAL: Dict[str, object] = {
    "address": "t1",
    "labels": {},
    "argv": ["sh"],
    "cwd": "/",
    "state": "live",
    "created_ms": 1,
    "screen": "exact",
    "cols": 200,
    "rows": 120,
}


def provenance() -> Dict[str, str]:
    doc = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return {str(k): str(v) for k, v in doc.items()}


def test_vendored_schema_matches_its_recorded_provenance() -> None:
    pin = provenance()
    data = SCHEMA_PATH.read_bytes()
    assert hashlib.sha256(data).hexdigest() == pin["sha256"]
    doc = json.loads(data)
    assert doc["info"]["version"] == pin["tag"].lstrip("v")
    assert doc["info"]["title"] == "herdr-core"


def test_guard_accepts_a_valid_result_and_flags_an_off_schema_one() -> None:
    guard = SchemaGuard.vendored()
    assert guard.check_result("terminal.get", TERMINAL) == []
    bad = dict(TERMINAL, address=7)
    assert guard.check_result("terminal.get", bad) != []
    missing = {k: v for k, v in TERMINAL.items() if k != "created_ms"}
    assert guard.check_result("terminal.get", missing) != []


def test_guard_flags_params_hc_does_not_declare() -> None:
    guard = SchemaGuard.vendored()
    assert guard.check_params("terminal.send", {"terminal": "t1", "text": "x"}) == []
    assert guard.check_params("terminal.send", {"terminal": "t1", "text": "x", "bogus": 1}) != []
    assert guard.check_params("terminal.send", {"text": "x"}) != []
    assert guard.check_params("terminal.read", {"terminal": "t1", "lines": -1}) != []


def test_guard_excuses_only_hc_190() -> None:
    guard = SchemaGuard.vendored()
    assert guard.check_result("terminal.list", {"terminals": [TERMINAL], "hidden_finished": 0}) == []
    assert guard.check_result("terminal.list", {"terminals": [], "hidden_finished": 0, "machines": "x"}) != []
    assert guard.check_result("terminal.list", {"hidden_finished": 0}) != []


def test_every_fake_method_is_an_hc_method() -> None:
    assert set(FakeHc.METHODS) <= SchemaGuard.vendored().methods


def test_every_fake_method_is_guarded(fake_hc: FakeHc, short_tmp: Path) -> None:
    sock = fake_hc.socket_path
    raw_call(sock, "hello", {"generation": 1})
    raw_call(sock, "server.status", {})
    run = raw_call(
        sock,
        "terminal.run",
        {
            "argv": ["/bin/sh", "-c", "cat"],
            "cwd": str(short_tmp),
            "name": "ga",
            "labels": {"gc.city": "c"},
            "keep": False,
            "no_parent": True,
            "no_notify": True,
        },
    )
    address = run["result"]["address"]
    for method, params in [
        ("terminal.get", {"terminal": address}),
        ("terminal.list", {"all": True, "labels": {"gc.city": "c"}}),
        ("terminal.label", {"terminal": address, "labels": {"gc.pid": "1"}}),
        ("terminal.keep", {"terminal": address, "keep": False}),
        ("terminal.read", {"terminal": address, "lines": 0}),
        ("terminal.send", {"terminal": address, "text": "x"}),
        ("terminal.keys", {"terminal": address, "keys": ["enter"]}),
        ("terminal.interrupt", {"terminal": address, "timeout": 1.0}),
        ("terminal.kill", {"terminal": address}),
        ("terminal.rm", {"terminal": address}),
        ("server.stop", {}),
    ]:
        reply = raw_call(sock, method, params)
        assert "result" in reply, (method, reply)
    assert fake_hc.guarded_methods == set(FakeHc.METHODS)


def test_off_schema_requests_are_recorded(fake_hc: FakeHc) -> None:
    raw_call(fake_hc.socket_path, "terminal.list", {"all": True, "bogus": True})
    violations = list(fake_hc.schema_violations)
    fake_hc.schema_violations.clear()  # the fixture would fail the test otherwise
    assert any("terminal.list" in v and "params" in v for v in violations)


@pytest.mark.skipif(
    os.environ.get("GC_HC_SCHEMA_FETCH") != "1",
    reason="network check against the pinned tag; CI sets GC_HC_SCHEMA_FETCH=1",
)
def test_vendored_schema_is_the_pinned_tags_released_schema() -> None:
    pin = provenance()
    repo = pin["repository"].replace("https://github.com/", "")
    url = f"https://raw.githubusercontent.com/{repo}/{pin['tag']}/{pin['released_path']}"
    last: Exception = AssertionError("no attempt")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                released = response.read()
            break
        except OSError as err:  # transient network trouble: retry, then fail
            last = err
            time.sleep(2 * (attempt + 1))
    else:
        raise last
    assert released == SCHEMA_PATH.read_bytes()


def test_known_error_kinds_are_the_schemas() -> None:
    from gc_runtime_herdr_core.hc.errors import KNOWN_ERROR_KINDS

    assert KNOWN_ERROR_KINDS == SchemaGuard.vendored().error_kinds()

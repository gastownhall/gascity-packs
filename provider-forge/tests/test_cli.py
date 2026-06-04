"""provider-forge — CLI surface tests (list / doctor / roster / targets).

These own the CLI contract: filtering, the doctor readiness state machine (with
a monkeypatched PATH + auth so the three outcomes — ready / missing-cli /
missing-auth — and the non-zero exit on breakage are all exercised hermetically),
roster-to-file, and targets. They drive a synthetic catalog written under
``tmp_path`` (via ``--catalog``) so nothing depends on the host's installed CLIs
except the explicit doctor-on-shipped smoke test.

Pure stdlib + pytest. The pack root is importable so ``forge.cli.main`` resolves.
"""

from __future__ import annotations

import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest  # noqa: E402

from forge import catalog as C  # noqa: E402
from forge import cli  # noqa: E402


# --------------------------------------------------------------------------- #
# A synthetic catalog on disk: two live providers (one with auth, one without)  #
# plus a scaffold provider, and one excluded model.                            #
# --------------------------------------------------------------------------- #

SYNTH_TOML = """
schema_version = "provider-forge.v1"
default_provider = "bravo"

[providers.alpha]
cli = "alpha-cli"
overlay = "alpha"
status = "live"
auth = "~/.alpha/auth.json"

[[providers.alpha.models]]
id = "a-small"
model = "alpha-small"
in_cost = 0.50
out_cost = 1.50
run_target = "alpha-small"

[[providers.alpha.models]]
id = "a-special"
model = "alpha-special"
in_cost = 1.00
out_cost = 1.00
run_target = "alpha-special"
exclude_from_roster = true

[providers.bravo]
cli = "bravo-cli"
overlay = "bravo"
status = "live"
native = true

[[providers.bravo.models]]
id = "b-mid"
model = "bravo-mid"
in_cost = 2.00
out_cost = 6.00
run_target = "bravo-mid"

[providers.charlie]
cli = "charlie-cli"
overlay = "charlie"
status = "scaffold"

[[providers.charlie.models]]
id = "c-future"
model = "charlie-future"
in_cost = 4.00
out_cost = 8.00
run_target = "charlie-future"
"""


@pytest.fixture()
def cat_path(tmp_path):
    p = tmp_path / "catalog.toml"
    p.write_text(SYNTH_TOML)
    return str(p)


def _run(argv, cat_path=None):
    """Invoke the CLI, capturing stdout; return (rc, stdout)."""
    buf = io.StringIO()
    full = list(argv)
    if cat_path is not None:
        full = ["--catalog", cat_path, *full]
    rc = cli.main(full, out=buf)
    return rc, buf.getvalue()


# --------------------------------------------------------------------------- #
# list — live default vs --all                                                 #
# --------------------------------------------------------------------------- #

def test_list_default_live_only(cat_path):
    rc, out = _run(["list", "--json"], cat_path)
    assert rc == 0
    records = json.loads(out)
    providers = {r["provider"] for r in records}
    assert providers == {"alpha", "bravo"}  # charlie (scaffold) excluded
    # exclude_from_roster model still appears in `list` (it's a real model)
    assert any(r["id"] == "a-special" for r in records)


def test_list_all_includes_scaffold(cat_path):
    rc, out = _run(["list", "--all", "--json"], cat_path)
    assert rc == 0
    providers = {r["provider"] for r in json.loads(out)}
    assert providers == {"alpha", "bravo", "charlie"}


def test_list_table_default_omits_scaffold_model(cat_path):
    rc, out = _run(["list"], cat_path)
    assert rc == 0
    assert "charlie-future" not in out  # scaffold model hidden without --all
    assert "alpha-small" in out
    rc2, out2 = _run(["list", "--all"], cat_path)
    assert "charlie-future" in out2  # shown with --all


# --------------------------------------------------------------------------- #
# doctor — readiness state machine (monkeypatched PATH + auth)                  #
# --------------------------------------------------------------------------- #

def test_doctor_all_ready(cat_path, monkeypatch):
    # both CLIs "on PATH"; alpha's auth file "exists"; bravo needs no auth.
    monkeypatch.setattr(cli, "_which", lambda c: "/fake/bin/" + c)
    monkeypatch.setattr(C.Path, "exists", lambda self: True)
    rc, out = _run(["doctor", "--json"], cat_path)
    assert rc == 0
    payload = json.loads(out)
    assert payload["ok"] is True
    by = {p["provider"]: p for p in payload["providers"]}
    assert by["alpha"]["status"] == cli.READY
    assert by["bravo"]["status"] == cli.READY
    assert by["bravo"]["auth"] is None  # no auth required


def test_doctor_missing_cli(cat_path, monkeypatch):
    # alpha CLI missing -> missing-cli and non-zero exit; bravo fine.
    def which(c):
        return None if c == "alpha-cli" else "/fake/bin/" + c
    monkeypatch.setattr(cli, "_which", which)
    monkeypatch.setattr(C.Path, "exists", lambda self: True)
    rc, out = _run(["doctor", "--json"], cat_path)
    assert rc == 1  # broken live provider -> non-zero
    by = {p["provider"]: p for p in json.loads(out)["providers"]}
    assert by["alpha"]["status"] == cli.MISSING_CLI
    assert by["alpha"]["ready"] is False
    assert by["bravo"]["status"] == cli.READY


def test_doctor_missing_auth(cat_path, monkeypatch):
    # CLI present, but alpha's auth file does NOT exist -> missing-auth.
    monkeypatch.setattr(cli, "_which", lambda c: "/fake/bin/" + c)
    monkeypatch.setattr(C.Path, "exists", lambda self: False)
    rc, out = _run(["doctor", "--json"], cat_path)
    assert rc == 1
    by = {p["provider"]: p for p in json.loads(out)["providers"]}
    assert by["alpha"]["status"] == cli.MISSING_AUTH
    assert by["alpha"]["ready"] is False
    # bravo declares no auth -> still ready even though exists()==False
    assert by["bravo"]["status"] == cli.READY


def test_doctor_missing_cli_dominates_missing_auth(cat_path, monkeypatch):
    # both CLI missing AND auth missing -> report missing-cli (the dominant fault).
    monkeypatch.setattr(cli, "_which", lambda c: None)
    monkeypatch.setattr(C.Path, "exists", lambda self: False)
    rc, out = _run(["doctor", "--json"], cat_path)
    assert rc == 1
    by = {p["provider"]: p for p in json.loads(out)["providers"]}
    assert by["alpha"]["status"] == cli.MISSING_CLI


def test_doctor_table_reports_not_ready(cat_path, monkeypatch):
    monkeypatch.setattr(cli, "_which", lambda c: None)
    rc, out = _run(["doctor"], cat_path)
    assert rc == 1
    assert "NOT READY" in out


def test_doctor_on_shipped_catalog_smoke():
    # On THIS machine claude+codex are installed/authed; assert the surface runs
    # and returns a well-formed payload (rc reflects real readiness).
    buf = io.StringIO()
    rc = cli.main(["doctor", "--json"], out=buf)
    payload = json.loads(buf.getvalue())
    assert set(payload.keys()) == {"ok", "providers"}
    assert {p["provider"] for p in payload["providers"]} == {"claude", "codex"}
    assert rc in (0, 1)


# --------------------------------------------------------------------------- #
# roster — stdout + --out file                                                 #
# --------------------------------------------------------------------------- #

def test_roster_stdout(cat_path):
    rc, out = _run(["roster"], cat_path)
    assert rc == 0
    assert out.startswith("#")
    assert "[[tier]]" in out
    # a-special excluded; cost order a-small(2.0) < b-mid(8.0)
    i_small = out.index('"a-small"')
    i_mid = out.index('"b-mid"')
    assert i_small < i_mid
    assert "a-special" not in out


def test_roster_out_file_round_trips(cat_path, tmp_path):
    out_file = tmp_path / "advisor.toml"
    rc, _ = _run(["roster", "--out", str(out_file)], cat_path)
    assert rc == 0
    assert out_file.is_file()
    # reload the catalog independently and compare tiers
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore
    parsed = tomllib.loads(out_file.read_text())["tier"]
    expected = C.load_catalog(cat_path).roster_tiers()
    got = [
        {k: t[k] for k in ("id", "provider", "model", "run_target", "rank", "in_cost", "out_cost")}
        for t in parsed
    ]
    assert got == expected


def test_roster_provider_filter_cli(cat_path):
    rc, out = _run(["roster", "--provider", "bravo"], cat_path)
    assert rc == 0
    assert '"b-mid"' in out
    assert '"a-small"' not in out


def test_roster_unknown_provider_errors(cat_path):
    rc, out = _run(["roster", "--provider", "nope"], cat_path)
    assert rc == 2  # fails loudly, does not emit an empty roster


# --------------------------------------------------------------------------- #
# targets                                                                       #
# --------------------------------------------------------------------------- #

def test_targets_lists_live_run_targets(cat_path):
    rc, out = _run(["targets", "--json"], cat_path)
    assert rc == 0
    records = json.loads(out)
    rts = {r["run_target"]: r for r in records}
    # live providers only (charlie scaffold excluded), incl. the excluded model's
    # target (run targets are about gc session configs, independent of roster).
    assert set(rts) == {"alpha-small", "alpha-special", "bravo-mid"}
    assert rts["bravo-mid"]["provider"] == "bravo"
    assert rts["bravo-mid"]["model"] == "bravo-mid"


def test_targets_maps_provider_and_model(cat_path):
    rc, out = _run(["targets"], cat_path)
    assert rc == 0
    assert "alpha-small" in out and "alpha" in out


# --------------------------------------------------------------------------- #
# bad catalog path via CLI                                                      #
# --------------------------------------------------------------------------- #

def test_cli_bad_catalog_exits_2(tmp_path):
    rc, _ = _run(["list"], str(tmp_path / "missing.toml"))
    assert rc == 2

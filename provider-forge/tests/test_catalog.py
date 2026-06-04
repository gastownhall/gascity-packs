"""provider-forge — catalog reader + roster-generation tests.

Covers the engine contract (the source-of-truth layer):

  * the SHIPPED catalog.toml parses, and its live/scaffold split is what we expect;
  * a synthetic catalog exercises cost-ordering, rank-from-1, exclude_from_roster,
    and the (provider, model) row views deterministically;
  * the generated roster round-trips back through tomllib into the same tiers;
  * the roster matches the LIVE codex+claude set: exactly 7 tiers, cost-ordered,
    with codex-auto-review (exclude_from_roster) omitted;
  * generation is deterministic (byte-identical across repeated calls).

Pure stdlib + pytest; no third-party deps. The pack root is made importable so
``import forge...`` works regardless of where pytest is launched from.
"""

from __future__ import annotations

import os
import sys

# Make the pack root importable when pytest is run from anywhere.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:  # mirror the loader shim so the round-trip assertions use the same backend
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

import pytest  # noqa: E402

from forge import catalog as C  # noqa: E402
from forge.cli import render_roster_toml  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
# --------------------------------------------------------------------------- #

# A small, self-contained catalog with a known cost ordering and one excluded
# model, plus a scaffold provider — independent of the shipped catalog so the
# ordering/exclusion assertions can't drift when real costs change.
SYNTH_TOML = """
schema_version = "provider-forge.v1"
default_provider = "claude"

[providers.alpha]
cli = "alpha-cli"
overlay = "alpha"
status = "live"
auth = "~/.alpha/auth.json"
reasoning_levels = ["low", "high"]
default_reasoning = "low"

[[providers.alpha.models]]
id = "a-big"
model = "alpha-big"
context = 100000
in_cost = 9.00
out_cost = 30.00
run_target = "alpha-big"

[[providers.alpha.models]]
id = "a-small"
model = "alpha-small"
context = 100000
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
reasoning_levels = []

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
reasoning_levels = []
"""


@pytest.fixture()
def synth() -> C.Catalog:
    return C.parse_catalog(tomllib.loads(SYNTH_TOML))


@pytest.fixture()
def shipped() -> C.Catalog:
    return C.load_catalog()  # the pack's own catalog.toml


# --------------------------------------------------------------------------- #
# 1. shipped catalog parses + live/scaffold split                              #
# --------------------------------------------------------------------------- #

def test_shipped_catalog_parses(shipped: C.Catalog):
    assert shipped.schema_version == "provider-forge.v1"
    assert shipped.default_provider == "claude"
    names = {p.name for p in shipped.providers}
    # the two live providers must be present
    assert {"claude", "codex"} <= names


def test_shipped_live_vs_scaffold(shipped: C.Catalog):
    live = {p.name for p in shipped.live()}
    scaffold = {p.name for p in shipped.scaffold()}
    assert live == {"claude", "codex"}
    # the scaffolds declared in the catalog header
    assert {"gemini", "copilot", "cursor", "kiro", "omp", "opencode", "pi"} <= scaffold
    assert live.isdisjoint(scaffold)


def test_codex_provider_fields(shipped: C.Catalog):
    codex = shipped.provider("codex")
    assert codex.is_live
    assert codex.cli == "codex"
    assert codex.auth_path() == C.Path(os.path.expanduser("~/.codex/auth.json"))
    assert codex.default_reasoning == "medium"
    assert "xhigh" in codex.reasoning_levels


# --------------------------------------------------------------------------- #
# 2. model views: live-only vs all                                             #
# --------------------------------------------------------------------------- #

def test_models_live_only_excludes_scaffold(synth: C.Catalog):
    live_models = synth.models(live_only=True)
    providers = {m.provider for m in live_models}
    assert providers == {"alpha", "bravo"}  # charlie is scaffold -> excluded
    # all three alpha models present (exclusion only applies to the roster)
    assert {m.id for m in live_models} == {"a-big", "a-small", "a-special", "b-mid"}


def test_models_all_includes_scaffold_providers(synth: C.Catalog):
    # charlie declares no models, so the row count is unchanged, but live()==2
    # and providers list includes the scaffold.
    assert len(synth.scaffold()) == 1
    assert synth.scaffold()[0].name == "charlie"
    # live_only=False would include scaffold providers' models if they had any.
    assert synth.models(live_only=False) == synth.models(live_only=True)


# --------------------------------------------------------------------------- #
# 3. roster: cost-order, rank-from-1, exclusion                                #
# --------------------------------------------------------------------------- #

def test_roster_cost_ordered_rank_from_one(synth: C.Catalog):
    tiers = synth.roster_tiers()
    # a-special is excluded; remaining 3 cost-ordered ascending:
    #   a-small 0.5+1.5=2.0 ; bravo-mid 2.0+6.0=8.0 ; a-big 9.0+30.0=39.0
    assert [t["id"] for t in tiers] == ["a-small", "b-mid", "a-big"]
    assert [t["rank"] for t in tiers] == [1, 2, 3]


def test_roster_excludes_exclude_from_roster(synth: C.Catalog):
    ids = {t["id"] for t in synth.roster_tiers()}
    assert "a-special" not in ids


def test_roster_tier_fields_exact(synth: C.Catalog):
    t = synth.roster_tiers()[0]
    assert set(t.keys()) == {
        "id", "provider", "model", "run_target", "rank", "in_cost", "out_cost",
    }
    assert t == {
        "id": "a-small",
        "provider": "alpha",
        "model": "alpha-small",
        "run_target": "alpha-small",
        "rank": 1,
        "in_cost": 0.50,
        "out_cost": 1.50,
    }


def test_roster_provider_filter(synth: C.Catalog):
    tiers = synth.roster_tiers(providers=["bravo"])
    assert [t["id"] for t in tiers] == ["b-mid"]
    assert tiers[0]["rank"] == 1  # rank re-based within the filtered set


def test_roster_tie_break_is_deterministic():
    # two models with identical cost -> stable (provider, id) tie-break.
    toml = """
schema_version = "provider-forge.v1"
default_provider = "x"
[providers.zeta]
cli = "z"
status = "live"
[[providers.zeta.models]]
id = "z1"
model = "zeta-1"
in_cost = 1.0
out_cost = 1.0
run_target = "zeta-1"
[providers.alpha]
cli = "a"
status = "live"
[[providers.alpha.models]]
id = "a1"
model = "alpha-1"
in_cost = 1.0
out_cost = 1.0
run_target = "alpha-1"
"""
    cat = C.parse_catalog(tomllib.loads(toml))
    tiers = cat.roster_tiers()
    # equal cost -> ordered by provider name then id: alpha before zeta
    assert [t["provider"] for t in tiers] == ["alpha", "zeta"]
    assert [t["rank"] for t in tiers] == [1, 2]


# --------------------------------------------------------------------------- #
# 4. roster TOML round-trips + determinism                                     #
# --------------------------------------------------------------------------- #

def test_roster_toml_round_trips(synth: C.Catalog):
    text = render_roster_toml(synth)
    reparsed = tomllib.loads(text)
    assert "tier" in reparsed
    got = [
        {k: t[k] for k in ("id", "provider", "model", "run_target", "rank", "in_cost", "out_cost")}
        for t in reparsed["tier"]
    ]
    assert got == synth.roster_tiers()


def test_roster_render_is_deterministic(synth: C.Catalog):
    a = render_roster_toml(synth)
    b = render_roster_toml(synth)
    assert a == b  # byte-identical


def test_roster_header_documents_cost_caveat(synth: C.Catalog):
    text = render_roster_toml(synth)
    head = text.splitlines()[0]
    assert head.startswith("#")
    low = text.lower()
    assert "estimate" in low  # cost/estimate caveat present
    assert "$/mtok" in low


# --------------------------------------------------------------------------- #
# 5. roster matches the LIVE codex+claude set (the integration contract)       #
# --------------------------------------------------------------------------- #

def test_shipped_roster_is_seven_tiers_no_auto_review(shipped: C.Catalog):
    tiers = shipped.roster_tiers()
    assert len(tiers) == 7
    ids = [t["id"] for t in tiers]
    # cost-ordered live set from catalog.toml (auto-review excluded)
    assert ids == ["spark", "mini", "haiku", "gpt54", "sonnet", "gpt55", "opus"]
    assert "auto-review" not in ids
    assert [t["rank"] for t in tiers] == [1, 2, 3, 4, 5, 6, 7]


def test_shipped_roster_round_trips_to_same_tiers(shipped: C.Catalog):
    text = render_roster_toml(shipped)
    reparsed = tomllib.loads(text)["tier"]
    assert len(reparsed) == 7
    # ranks strictly ascending and costs non-decreasing (cost-ordered)
    ranks = [t["rank"] for t in reparsed]
    costs = [t["in_cost"] + t["out_cost"] for t in reparsed]
    assert ranks == sorted(ranks)
    assert costs == sorted(costs)


def test_shipped_auto_review_excluded_but_listed_as_model(shipped: C.Catalog):
    # auto-review is still a real model row (shows in `list`/`targets`), it is
    # only omitted from the ROSTER.
    codex_model_ids = {m.id for m in shipped.provider("codex").models}
    assert "auto-review" in codex_model_ids
    roster_ids = {t["id"] for t in shipped.roster_tiers()}
    assert "auto-review" not in roster_ids


# --------------------------------------------------------------------------- #
# 6. error handling                                                            #
# --------------------------------------------------------------------------- #

def test_missing_required_key_raises():
    bad = """
[providers.x]
cli = "x"
status = "live"
[[providers.x.models]]
id = "m"
model = "x-m"
in_cost = 1.0
out_cost = 1.0
"""  # run_target missing
    with pytest.raises(C.CatalogError):
        C.parse_catalog(tomllib.loads(bad))


def test_bad_status_raises():
    bad = """
[providers.x]
cli = "x"
status = "experimental"
"""
    with pytest.raises(C.CatalogError):
        C.parse_catalog(tomllib.loads(bad))


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(C.CatalogError):
        C.load_catalog(tmp_path / "does-not-exist.toml")

"""The experimental pack must be a separately installable base-pack alternative."""
import json
from pathlib import Path
import tomllib

import pytest

from gc_live_city import gc_output, gc_test_bin, run_gc, write_city

ROOT = Path(__file__).resolve().parents[1]


def test_pack_identity_and_matching_roles():
    pack = ROOT / "gascity-jev"
    assert tomllib.loads((pack / "pack.toml").read_text())["pack"]["name"] == "gascity-jev"
    roles = tomllib.loads((pack / "roles/pack.toml").read_text())
    assert roles["pack"]["name"] == "gascity-jev-roles"
    assert (pack / "roles" / roles["imports"]["gc"]["source"]).resolve() == pack


@pytest.mark.parametrize("pack", ["gascity", "gascity-jev"])
def test_alternative_pack_loads_real_formulas_and_roles(pack, tmp_path, gc_test_bin):
    source = ROOT / pack
    workspace = write_city(tmp_path, {"gc": source}, {"gc": source / "roles"})
    gc_output(gc_test_bin, workspace, "import", "install")
    formulas = gc_output(gc_test_bin, workspace, "formula", "list")
    for name in ("build-basic", "github-issue-triage", "github-pr-review"):
        assert name in formulas
    agents = gc_output(gc_test_bin, workspace, "agent", "list")
    assert "gc.implementation-worker" in agents
    assert "gc.review-synthesizer" in agents
    # Inspect the resolved workflow, not just the source TOML: the role import
    # must not accidentally pull the other pack into this city's formula set.
    result = run_gc(gc_test_bin, workspace, "formula", "show", "build-basic", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    if result.stderr:
        print(result.stderr)
    build = json.loads(result.stdout)
    assert ("jev_mode" in json.dumps(build)) == (pack == "gascity-jev")


def test_jev_artifact_provenance_names_the_selected_pack():
    prompts = ROOT / "gascity-jev/assets/workflows"
    text = "\n".join(path.read_text() for path in prompts.rglob("*.md"))
    assert "methodology: {pack: gascity-jev," in text
    assert "methodology: {pack: gascity," not in text

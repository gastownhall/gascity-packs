"""personas — registry load + validation tests.

Owns the contract of ``personas.toml``: the shipped roster parses and carries the full
10-persona suite the README specifies; the cache TTL policy resolves from minute/hour
convenience keys; and malformed config is rejected loudly. Pure stdlib + pytest.
"""

from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from personas import registry as R  # noqa: E402

_SHIPPED = os.path.join(_ROOT, "personas.toml")

# The roster the README "initial roster" promises.
EXPECTED_IDS = {
    "principal-backend-engineer",
    "principal-frontend-engineer",
    "principal-systems-engineer",
    "principal-security-engineer",
    "principal-data-engineer",
    "principal-platform-engineer",
    "principal-api-designer",
    "principal-test-engineer",
    "principal-refactoring-engineer",
    "principal-docs-engineer",
}


# ---- shipped roster -------------------------------------------------------- #


def test_shipped_roster_has_full_suite():
    config = R.load_config(_SHIPPED)
    assert set(config.ids) == EXPECTED_IDS
    assert len(config.personas) == 10


def test_every_persona_is_complete():
    config = R.load_config(_SHIPPED)
    for p in config.personas:
        assert p.domain, f"{p.id} missing domain"
        assert p.when_to_equip, f"{p.id} missing when_to_equip"
        assert p.verification_bar, f"{p.id} missing verification_bar"
        assert p.playbook, f"{p.id} missing playbook"
        assert p.match_keywords, f"{p.id} has no match_keywords"
        assert p.skills, f"{p.id} brings no skills"
        assert p.tools, f"{p.id} brings no tools"


def test_keywords_are_lowercased_on_load():
    config = R.load_config(_SHIPPED)
    for p in config.personas:
        for kw in p.match_keywords:
            assert kw == kw.lower()


def test_shipped_cache_policy_is_the_documented_default():
    config = R.load_config(_SHIPPED)
    assert config.cache.idle_ttl_seconds == 30 * 60
    assert config.cache.ceiling_ttl_seconds == 2 * 3600


def test_default_persona_resolves():
    config = R.load_config(_SHIPPED)
    assert config.default_persona_id == "principal-backend-engineer"
    assert config.default_persona.id == "principal-backend-engineer"


def test_title_is_humanized():
    p = R.load_config(_SHIPPED).get("principal-backend-engineer")
    assert p.title == "Principal Backend Engineer"


# ---- defaults / missing file ----------------------------------------------- #


def test_missing_file_falls_back_to_builtin():
    config = R.load_config("/nonexistent/personas.toml")
    assert len(config.personas) >= 1
    assert config.has(config.default_persona_id)


def test_none_path_is_builtin_default():
    config = R.load_config(None)
    assert config is not None
    assert len(config.personas) >= 1


# ---- cache policy parsing -------------------------------------------------- #


def test_cache_seconds_override_convenience_keys():
    cfg = R.from_mapping(
        {
            "persona": [{"id": "p", "domain": "d"}],
            "cache": {"idle_ttl_minutes": 30, "idle_ttl_seconds": 5, "ceiling_ttl_seconds": 10},
        }
    )
    assert cfg.cache.idle_ttl_seconds == 5
    assert cfg.cache.ceiling_ttl_seconds == 10


def test_cache_ceiling_below_idle_is_rejected():
    with pytest.raises(R.RegistryError):
        R.from_mapping(
            {
                "persona": [{"id": "p", "domain": "d"}],
                "cache": {"idle_ttl_seconds": 100, "ceiling_ttl_seconds": 10},
            }
        )


# ---- malformed config ------------------------------------------------------ #


def test_empty_roster_rejected():
    with pytest.raises(R.RegistryError):
        R._finalise(personas=[], cache=R.CachePolicy(), default_persona_id=None)


def test_duplicate_ids_rejected():
    with pytest.raises(R.RegistryError):
        R.from_mapping({"persona": [{"id": "dup"}, {"id": "dup"}]})


def test_unknown_default_persona_rejected():
    with pytest.raises(R.RegistryError):
        R.from_mapping(
            {"persona": [{"id": "a"}], "registry": {"default_persona": "nope"}}
        )


def test_persona_missing_id_rejected():
    with pytest.raises(R.RegistryError):
        R.from_mapping({"persona": [{"domain": "no id here"}]})


def test_match_keywords_must_be_array():
    with pytest.raises(R.RegistryError):
        R.from_mapping({"persona": [{"id": "a", "match_keywords": "backend"}]})


# ---- id validation --------------------------------------------------------- #


@pytest.mark.parametrize("bad", ["", "   ", "Has Space", "UPPER", "trailing-", "-leading", "a--b", "a_b"])
def test_invalid_id_rejected(bad):
    with pytest.raises(R.RegistryError):
        R.from_mapping({"persona": [{"id": bad}]})


def test_id_is_stripped_of_surrounding_whitespace():
    cfg = R.from_mapping({"persona": [{"id": "  principal-x  ", "domain": "d"}]})
    assert cfg.ids == ("principal-x",)


@pytest.mark.parametrize("ok", ["a", "p", "dup", "v2", "principal-backend-engineer"])
def test_valid_ids_accepted(ok):
    cfg = R.from_mapping({"persona": [{"id": ok}]})
    assert cfg.ids == (ok,)


# ---- weight validation ----------------------------------------------------- #


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), float("-inf"), "abc"])
def test_bad_weight_rejected(bad):
    with pytest.raises(R.RegistryError):
        R.from_mapping({"persona": [{"id": "p", "weight": bad}]})


def test_weight_defaults_to_one():
    cfg = R.from_mapping({"persona": [{"id": "p"}]})
    assert cfg.get("p").weight == 1.0


def test_valid_weight_parsed():
    cfg = R.from_mapping({"persona": [{"id": "p", "weight": 2.5}]})
    assert cfg.get("p").weight == 2.5


# ---- term hygiene (keywords / skills / tools) ------------------------------ #


def test_keywords_trimmed_deduped_and_lowercased():
    cfg = R.from_mapping(
        {"persona": [{"id": "p", "match_keywords": [" API ", "api", "Api", "", "  ", "rest"]}]}
    )
    # "API"/"api"/"Api" collapse to one; blanks dropped; first-seen order kept.
    assert cfg.get("p").match_keywords == ("api", "rest")


def test_skills_and_tools_trimmed_and_deduped_case_sensitively():
    cfg = R.from_mapping(
        {"persona": [{"id": "p", "skills": [" tdd ", "tdd", ""], "tools": ["Read", "Read", " Edit "]}]}
    )
    assert cfg.get("p").skills == ("tdd",)
    assert cfg.get("p").tools == ("Read", "Edit")


# ---- canonical loader (default_registry_path / load_default) ---------------- #


def test_default_registry_path_points_at_shipped_file():
    path = R.default_registry_path()
    assert path == _SHIPPED
    assert os.path.exists(path)


def test_load_default_loads_the_shipped_roster():
    config = R.load_default()
    assert set(config.ids) == EXPECTED_IDS
    assert config.default_persona.id == "principal-backend-engineer"


# ---- integrity lint (validate) --------------------------------------------- #


def test_shipped_registry_passes_validate():
    assert R.validate(R.load_default()) == []


def test_builtin_default_config_passes_validate():
    # The fallback roster must itself be complete — it ships when personas.toml is gone.
    assert R.validate(R.default_config()) == []


def test_validate_flags_an_incomplete_persona():
    cfg = R.from_mapping({"persona": [{"id": "bare"}]})
    issues = R.validate(cfg)
    joined = "\n".join(issues)
    for field in ("domain", "when_to_equip", "verification_bar", "playbook"):
        assert f"bare: missing {field}" in joined
    assert any("match_keywords" in i for i in issues)
    assert any("skills" in i for i in issues)
    assert any("tools" in i for i in issues)


def test_validate_clean_persona_has_no_issues():
    cfg = R.from_mapping(
        {
            "persona": [
                {
                    "id": "complete-one",
                    "domain": "d",
                    "when_to_equip": "w",
                    "verification_bar": "v",
                    "playbook": "p",
                    "match_keywords": ["k"],
                    "skills": ["tdd"],
                    "tools": ["Read"],
                }
            ]
        }
    )
    assert R.validate(cfg) == []

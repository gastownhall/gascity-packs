"""personas — equip/match engine tests.

Owns the equip decision: the right persona wins for a clearly-domain task, the choice
is explainable (the matched terms are reported), plural/singular forms match, ties break
deterministically, and a no-signal task falls back to the default. Pure stdlib + pytest.
"""

from __future__ import annotations

import dataclasses
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from personas import match as M  # noqa: E402
from personas import registry as R  # noqa: E402

_SHIPPED = os.path.join(_ROOT, "personas.toml")


def cfg() -> R.PersonasConfig:
    return R.load_config(_SHIPPED)


# ---- singularization helper ------------------------------------------------ #


def test_singular_handles_common_plurals():
    assert M._singular("tests") == "test"
    assert M._singular("apis") == "api"
    assert M._singular("queries") == "query"
    assert M._singular("vulnerabilities") == "vulnerability"
    assert M._singular("batches") == "batch"


def test_singular_preserves_double_s_and_short_words():
    assert M._singular("class") == "class"
    assert M._singular("loss") == "loss"
    assert M._singular("is") == "is"
    assert M._singular("as") == "as"


# ---- routing to the right persona ------------------------------------------ #


def test_backend_task_routes_to_backend():
    r = M.match_persona(cfg(), "implement a REST endpoint backed by Postgres with idempotent writes")
    assert r.best.id == "principal-backend-engineer"
    assert not r.is_fallback


def test_security_task_routes_to_security():
    r = M.match_persona(cfg(), "audit the upload handler for SSRF and sql injection")
    assert r.best.id == "principal-security-engineer"


def test_frontend_task_routes_to_frontend():
    r = M.match_persona(cfg(), "build an accessible React modal component with keyboard focus")
    assert r.best.id == "principal-frontend-engineer"


def test_systems_task_routes_to_systems():
    r = M.match_persona(cfg(), "fix the race condition and deadlock in the concurrent worker pool")
    assert r.best.id == "principal-systems-engineer"


def test_platform_task_routes_to_platform():
    r = M.match_persona(cfg(), "set up the kubernetes deployment and ci/cd pipeline with a rollback")
    assert r.best.id == "principal-platform-engineer"


def test_data_task_routes_to_data():
    r = M.match_persona(cfg(), "build an idempotent ETL pipeline that backfills the warehouse")
    assert r.best.id == "principal-data-engineer"


def test_test_task_routes_to_test_engineer():
    r = M.match_persona(cfg(), "write integration tests and raise coverage for the module")
    assert r.best.id == "principal-test-engineer"


def test_refactor_task_routes_to_refactoring():
    r = M.match_persona(cfg(), "refactor and simplify this tangled module to cut duplication")
    assert r.best.id == "principal-refactoring-engineer"


def test_docs_task_routes_to_docs():
    r = M.match_persona(cfg(), "rewrite the README and write a getting-started tutorial")
    assert r.best.id == "principal-docs-engineer"


def test_api_design_task_routes_to_api_designer():
    r = M.match_persona(cfg(), "design a backward-compatible openapi contract and deprecation path")
    assert r.best.id == "principal-api-designer"


# ---- explainability + structure -------------------------------------------- #


def test_result_reports_matched_terms():
    r = M.match_persona(cfg(), "audit for sql injection")
    assert r.matched  # non-empty
    assert any("injection" in m for m in r.matched)
    assert r.score > 0


def test_phrase_keyword_scores_more_than_single_word():
    # "sql injection" (phrase) should outscore a lone single-word hit.
    single = M.score_persona(
        cfg().get("principal-security-engineer"),
        {"audit"},
        " audit ",
    )
    phrase = M.score_persona(
        cfg().get("principal-security-engineer"),
        set("sql injection".split()),
        " sql injection ",
    )
    assert phrase.score > single.score


def test_runners_up_excludes_best():
    r = M.match_persona(cfg(), "audit the auth flow for sql injection vulnerabilities")
    assert r.best.id not in {s.persona.id for s in r.runners_up}


# ---- fallback + determinism ------------------------------------------------ #


def test_no_signal_falls_back_to_default():
    r = M.match_persona(cfg(), "do the thing with the stuff")
    assert r.is_fallback
    assert r.best.id == cfg().default_persona_id
    assert r.score == 0.0
    assert r.ranked == ()


def test_empty_task_is_fallback():
    r = M.match_persona(cfg(), "")
    assert r.is_fallback


def test_match_is_deterministic():
    task = "audit the auth flow for sql injection vulnerabilities in the api"
    first = M.match_persona(cfg(), task)
    again = M.match_persona(cfg(), task)
    assert first.best.id == again.best.id
    assert first.score == again.score
    assert [s.persona.id for s in first.ranked] == [s.persona.id for s in again.ranked]


def test_ranked_is_sorted_by_score_desc():
    r = M.match_persona(cfg(), "audit the auth flow for sql injection in the api endpoint")
    scores = [s.score for s in r.ranked]
    assert scores == sorted(scores, reverse=True)


def test_tie_breaks_by_id_when_scores_equal():
    # Two single-keyword personas; an ambiguous task that hits exactly one keyword each.
    config = R.from_mapping(
        {
            "persona": [
                {"id": "bbb", "domain": "d", "match_keywords": ["widget"]},
                {"id": "aaa", "domain": "d", "match_keywords": ["widget"]},
            ]
        }
    )
    r = M.match_persona(config, "build a widget")
    assert r.best.id == "aaa"  # equal score + weight -> id ascending


# ---- matching boundaries (whole-word, adjacency, case) --------------------- #


def _one(pid: str, keywords: list[str], domain: str = "isolated-domain-vocab") -> R.PersonasConfig:
    """A single-persona config for asserting one matching rule in isolation."""
    return R.from_mapping({"persona": [{"id": pid, "domain": domain, "match_keywords": keywords}]})


def test_keyword_matches_whole_word_only():
    # "api" must not fire inside "therapist" or "rapidly" — substring matching would.
    config = _one("api-persona", ["api"])
    r = M.match_persona(config, "the therapist rapidly reviewed the design")
    assert r.is_fallback


def test_keyword_fires_on_a_standalone_word():
    config = _one("api-persona", ["api"])
    r = M.match_persona(config, "design the public api surface")
    assert r.best.id == "api-persona"
    assert not r.is_fallback


def test_multi_word_keyword_requires_adjacency():
    # The phrase keyword "load balancer" fires only when the words are adjacent, in order.
    config = _one("infra", ["load balancer"])
    assert M.match_persona(config, "configure the load balancer").best.id == "infra"
    # Words present but neither adjacent nor forming the phrase -> no match.
    assert M.match_persona(config, "balance the heavy server load").is_fallback


def test_keyword_match_is_case_insensitive():
    # The registry lowercases keywords on load; normalize() lowercases the task.
    config = _one("p", ["API"])
    assert config.get("p").match_keywords == ("api",)
    r = M.match_persona(config, "Design the public API Surface")
    assert r.best.id == "p"


def test_whitespace_only_task_is_fallback():
    r = M.match_persona(cfg(), "   \t  \n ")
    assert r.is_fallback


# ---- empty-roster boundary ------------------------------------------------- #


def test_match_empty_roster_raises_clear_error():
    empty = R.PersonasConfig(personas=(), cache=R.CachePolicy())
    try:
        M.match_persona(empty, "anything")
    except ValueError as e:
        assert "empty persona roster" in str(e)
    else:
        raise AssertionError("expected ValueError on an empty roster")


def test_equip_empty_roster_raises_clear_error():
    empty = R.PersonasConfig(personas=(), cache=R.CachePolicy())
    try:
        M.equip(empty, "anything")
    except ValueError as e:
        assert "empty persona roster" in str(e)
    else:
        raise AssertionError("expected ValueError on an empty roster")


# ---- overlay / materialize ------------------------------------------------- #


def _backend(config: R.PersonasConfig) -> R.Persona:
    return config.get("principal-backend-engineer")


def test_render_overlay_includes_persona_essentials():
    p = _backend(cfg())
    md = M.render_overlay(p)
    assert f"# Equipped persona: {p.title}" in md
    assert p.domain in md
    assert p.playbook in md
    assert "**Verification bar" in md and p.verification_bar in md
    assert "**Skills to lean on:**" in md
    assert "**Tools:**" in md


def test_render_overlay_reports_matched_terms():
    config = cfg()
    result = M.match_persona(config, "audit the upload handler for sql injection")
    md = M.render_overlay(result.best, result)
    assert "Matched on:" in md
    assert "score" in md
    # Every reported term should be named in the provenance line.
    for term in result.matched:
        assert term in md


def test_render_overlay_marks_fallback():
    config = cfg()
    result = M.match_persona(config, "do the thing with the stuff")
    assert result.is_fallback
    md = M.render_overlay(result.best, result)
    assert "No strong task match" in md
    assert "default" in md


def test_render_overlay_without_result_has_no_provenance():
    md = M.render_overlay(_backend(cfg()))
    assert "Matched on:" not in md
    assert "No strong task match" not in md


def test_render_overlay_omits_empty_sections_for_lean_persona():
    lean = R.Persona(
        id="lean-persona",
        domain="",
        when_to_equip="",
        verification_bar="",
        playbook="",
        match_keywords=(),
        skills=(),
        tools=(),
    )
    md = M.render_overlay(lean)
    assert md.startswith("# Equipped persona: Lean Persona")
    # Nothing to say beyond the heading — no empty section labels.
    assert "**Domain.**" not in md
    assert "**Playbook.**" not in md
    assert "**Skills to lean on:**" not in md
    assert "**Tools:**" not in md
    assert "**Verification bar" not in md


def test_render_overlay_ends_with_single_newline():
    md = M.render_overlay(_backend(cfg()))
    assert md.endswith("\n")
    assert not md.endswith("\n\n")


def test_render_overlay_is_deterministic():
    p = _backend(cfg())
    assert M.render_overlay(p) == M.render_overlay(p)


# ---- equip (select + overlay) ---------------------------------------------- #


def test_equip_selects_persona_and_materializes_overlay():
    e = M.equip(cfg(), "implement a REST endpoint backed by Postgres with idempotent writes")
    assert e.persona.id == "principal-backend-engineer"
    assert not e.is_fallback
    assert e.overlay.strip()  # non-empty overlay
    assert f"# Equipped persona: {e.persona.title}" in e.overlay


def test_equip_overlay_matches_render_overlay():
    e = M.equip(cfg(), "audit the auth flow for sql injection vulnerabilities")
    assert e.overlay == M.render_overlay(e.result.best, e.result)


def test_equip_result_agrees_with_match_persona():
    config = cfg()
    task = "build an accessible React modal component with keyboard focus"
    e = M.equip(config, task)
    direct = M.match_persona(config, task)
    assert e.result.best.id == direct.best.id
    assert e.result.score == direct.score


def test_equip_falls_back_when_no_signal():
    e = M.equip(cfg(), "do the thing with the stuff")
    assert e.is_fallback
    assert e.persona.id == cfg().default_persona_id
    assert "No strong task match" in e.overlay


# ---- provenance (factored out of render_overlay) --------------------------- #


def test_render_provenance_none_is_empty():
    assert M.render_provenance(None) == ""


def test_render_provenance_matches_the_overlay_line():
    result = M.match_persona(cfg(), "audit the upload handler for sql injection")
    prov = M.render_provenance(result)
    assert prov.startswith("_Matched on:")
    # render_overlay folds in exactly this line when given a result.
    assert prov in M.render_overlay(result.best, result)


def test_render_provenance_marks_fallback():
    result = M.match_persona(cfg(), "do the thing with the stuff")
    assert result.is_fallback
    prov = M.render_provenance(result)
    assert "No strong task match" in prov
    assert prov in M.render_overlay(result.best, result)


# ---- persona_fingerprint (what the warm cache keys staleness on) ------------ #


def _lean(**over) -> R.Persona:
    base = dict(
        id="p",
        domain="d",
        when_to_equip="w",
        verification_bar="v",
        playbook="pb",
        match_keywords=("k",),
        skills=("s",),
        tools=("t",),
        weight=1.0,
    )
    base.update(over)
    return R.Persona(**base)


def test_persona_fingerprint_is_stable_and_sha256_hex():
    p = _backend(cfg())
    fp = M.persona_fingerprint(p)
    assert fp == M.persona_fingerprint(p)
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_persona_fingerprint_changes_on_every_overlay_field():
    fp0 = M.persona_fingerprint(_lean())
    # Each of these is rendered by render_overlay, so a change must be detected.
    assert M.persona_fingerprint(_lean(id="q")) != fp0          # id drives the title
    assert M.persona_fingerprint(_lean(domain="d2")) != fp0
    assert M.persona_fingerprint(_lean(playbook="pb2")) != fp0
    assert M.persona_fingerprint(_lean(skills=("s", "s2"))) != fp0
    assert M.persona_fingerprint(_lean(tools=("t2",))) != fp0
    assert M.persona_fingerprint(_lean(verification_bar="v2")) != fp0


def test_persona_fingerprint_ignores_non_overlay_fields():
    fp0 = M.persona_fingerprint(_lean())
    # These steer routing but never appear in the overlay — editing them must NOT
    # invalidate a warm entry (it would re-materialize an identical overlay for nothing).
    assert M.persona_fingerprint(_lean(when_to_equip="totally different")) == fp0
    assert M.persona_fingerprint(_lean(match_keywords=("x", "y", "z"))) == fp0
    assert M.persona_fingerprint(_lean(weight=9.0)) == fp0


def test_persona_fingerprint_tracks_render_overlay():
    # The invariant the warm cache relies on: when the rendered overlay changes, so does
    # the fingerprint, so a definition edit is never served stale.
    base = _backend(cfg())
    edited = dataclasses.replace(base, playbook=base.playbook + " And one more rule.")
    assert M.render_overlay(edited) != M.render_overlay(base)
    assert M.persona_fingerprint(edited) != M.persona_fingerprint(base)

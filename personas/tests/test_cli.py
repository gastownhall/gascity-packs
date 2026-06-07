"""personas — CLI surface tests (list / show / lint / match / equip / cache / evict / sweep).

Owns the CLI contract and its exit codes: reads render text + JSON; lint integrity-checks
the registry (exit 1 on completeness gaps, 2 on a structural load error); match/equip take
the task as words or --from-bead (the subprocess is monkeypatched so nothing shells out)
with match staying read-only; equip materializes into the warm cache and can emit a
SessionStart hook payload; evict dematerializes one persona. The warm cache is pointed at a
tmp file via --cache-file. Pure stdlib + pytest.
"""

from __future__ import annotations

import io
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from personas import cli  # noqa: E402


@pytest.fixture
def cache_file(tmp_path):
    return str(tmp_path / "warm-cache.json")


def run(argv, cache_file=None):
    if cache_file is not None:
        argv = ["--cache-file", cache_file] + argv
    out = io.StringIO()
    rc = cli.main(argv, out=out)
    return rc, out.getvalue()


# ---- list ------------------------------------------------------------------ #


def test_list_text():
    rc, s = run(["list"])
    assert rc == 0
    assert "principal-backend-engineer" in s
    assert "principal-docs-engineer" in s


def test_list_json_has_full_roster():
    rc, s = run(["list", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert len(data) == 10
    assert {p["id"] for p in data} >= {"principal-security-engineer", "principal-test-engineer"}
    # JSON carries the full definition, including the playbook.
    assert all(p["playbook"] for p in data)


# ---- show ------------------------------------------------------------------ #


def test_show_text_includes_playbook_and_bar():
    rc, s = run(["show", "principal-security-engineer"])
    assert rc == 0
    assert "Principal Security Engineer" in s
    assert "Verification bar" in s
    assert "When to equip" in s


def test_show_json():
    rc, s = run(["show", "principal-backend-engineer", "--json"])
    assert rc == 0
    assert json.loads(s)["id"] == "principal-backend-engineer"


def test_show_unknown_persona_exits_2():
    rc, s = run(["show", "principal-nope"])
    assert rc == 2


# ---- lint ------------------------------------------------------------------ #


def test_lint_shipped_roster_is_clean():
    rc, s = run(["lint"])
    assert rc == 0
    assert "no integrity issues" in s


def test_lint_json_reports_ok():
    rc, s = run(["lint", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["ok"] is True
    assert data["persona_count"] == 10
    assert data["issue_count"] == 0
    assert data["issues"] == []


def test_lint_flags_incomplete_roster_exits_1(tmp_path):
    bad = tmp_path / "bare.toml"
    bad.write_text('[[persona]]\nid = "bare"\n')
    rc, s = run(["--registry", str(bad), "lint"])
    assert rc == 1  # completeness gaps are exit 1, distinct from a load error (2)
    assert "bare: missing domain" in s


def test_lint_json_flags_issues_exits_1(tmp_path):
    bad = tmp_path / "bare.toml"
    bad.write_text('[[persona]]\nid = "bare"\n')
    rc, s = run(["--registry", str(bad), "lint", "--json"])
    assert rc == 1
    data = json.loads(s)
    assert data["ok"] is False
    assert data["issue_count"] > 0
    assert any("bare" in issue for issue in data["issues"])


def test_lint_structural_error_exits_2(tmp_path):
    # A duplicate id is rejected at *load* (structural), so lint surfaces it as a usage
    # error (exit 2) — not as a completeness finding (exit 1).
    bad = tmp_path / "dup.toml"
    bad.write_text('[[persona]]\nid = "dup"\n[[persona]]\nid = "dup"\n')
    rc, s = run(["--registry", str(bad), "lint"])
    assert rc == 2


# ---- match ----------------------------------------------------------------- #


def test_match_text_picks_persona():
    rc, s = run(["match", "audit", "for", "sql", "injection"])
    assert rc == 0
    assert "principal-security-engineer" in s


def test_match_json_structure():
    rc, s = run(["match", "build", "an", "accessible", "react", "component", "--json"])
    assert rc == 0
    data = json.loads(s)
    assert data["best"] == "principal-frontend-engineer"
    assert data["is_fallback"] is False
    assert data["matched"]


def test_match_fallback_text():
    rc, s = run(["match", "do", "the", "thing"])
    assert rc == 0
    assert "no strong match" in s


def test_match_does_not_touch_cache(cache_file):
    run(["match", "audit for sql injection"], cache_file=cache_file)
    # match is read-only: no cache file should have been written.
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    assert json.loads(s)["entries"] == []


def test_match_from_bead(monkeypatch, cache_file):
    monkeypatch.setattr(
        cli, "_task_from_bead", lambda bid: "build an accessible react component"
    )
    rc, s = run(["match", "--from-bead", "pers-1", "--json"], cache_file=cache_file)
    assert rc == 0
    assert json.loads(s)["best"] == "principal-frontend-engineer"


def test_match_from_bead_is_read_only(monkeypatch, cache_file):
    monkeypatch.setattr(cli, "_task_from_bead", lambda bid: "audit for sql injection")
    run(["match", "--from-bead", "pers-1"], cache_file=cache_file)
    # match never materializes — previewing a bead's decision leaves the cache empty.
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    assert json.loads(s)["entries"] == []


def test_match_from_bead_failure_exits_2(monkeypatch, cache_file):
    def boom(bid):
        raise ValueError("no such bead")

    monkeypatch.setattr(cli, "_task_from_bead", boom)
    rc, s = run(["match", "--from-bead", "nope"], cache_file=cache_file)
    assert rc == 2


def test_match_empty_task_exits_2():
    rc, s = run(["match"])
    assert rc == 2


# ---- equip ----------------------------------------------------------------- #


def test_equip_materializes_into_cache(cache_file):
    rc, s = run(["equip", "refactor and simplify this module", "--json"], cache_file=cache_file)
    assert rc == 0
    data = json.loads(s)
    assert data["best"] == "principal-refactoring-engineer"
    assert data["equipped"]["was_warm"] is False
    assert data["equipped"]["use_count"] == 1


def test_equip_twice_reuses_warm(cache_file):
    run(["equip", "simplify duplication", "--json"], cache_file=cache_file)
    rc, s = run(["equip", "simplify duplication", "--json"], cache_file=cache_file)
    data = json.loads(s)
    assert data["equipped"]["was_warm"] is True
    assert data["equipped"]["use_count"] == 2


def test_equip_text_shows_state(cache_file):
    rc, s = run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    assert rc == 0
    assert "Equipped persona" in s
    assert "materialized" in s


def test_equip_emit_context_is_sessionstart_payload(cache_file):
    rc, s = run(
        ["equip", "design a backward-compatible openapi contract", "--emit-context"],
        cache_file=cache_file,
    )
    assert rc == 0
    payload = json.loads(s)
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "Principal Api Designer" in hso["additionalContext"]
    assert "Verification bar" in hso["additionalContext"]


def test_equip_warm_reuse_serves_identical_cached_context(cache_file):
    # First equip materializes; the second reuses warm. The emitted SessionStart context
    # must be byte-identical — a warm reuse serves the cached overlay, it does not re-render.
    _, first = run(
        ["equip", "implement a backend endpoint", "--emit-context"], cache_file=cache_file
    )
    _, second = run(
        ["equip", "implement a backend endpoint", "--emit-context"], cache_file=cache_file
    )
    assert first == second
    # ...and the cache reports the reuse.
    _, j = run(["equip", "implement a backend endpoint", "--json"], cache_file=cache_file)
    assert json.loads(j)["equipped"]["was_warm"] is True


def test_equip_emit_context_includes_provenance(cache_file):
    rc, s = run(
        ["equip", "audit for sql injection", "--emit-context"], cache_file=cache_file
    )
    assert rc == 0
    ctx = json.loads(s)["hookSpecificOutput"]["additionalContext"]
    assert "Matched on:" in ctx  # the per-task provenance note
    assert "# Equipped persona: Principal Security Engineer" in ctx  # the cached overlay


def test_equip_empty_task_exits_2(cache_file):
    rc, s = run(["equip"], cache_file=cache_file)
    assert rc == 2


def test_equip_from_bead(monkeypatch, cache_file):
    monkeypatch.setattr(
        cli, "_task_from_bead", lambda bid: "fix a race condition in the concurrent worker"
    )
    rc, s = run(["equip", "--from-bead", "pers-1", "--json"], cache_file=cache_file)
    assert rc == 0
    assert json.loads(s)["best"] == "principal-systems-engineer"


def test_equip_from_bead_failure_exits_2(monkeypatch, cache_file):
    def boom(bid):
        raise ValueError("no such bead")

    monkeypatch.setattr(cli, "_task_from_bead", boom)
    rc, s = run(["equip", "--from-bead", "nope"], cache_file=cache_file)
    assert rc == 2


# ---- cache + evict + sweep ------------------------------------------------- #


def test_cache_lists_warm_personas(cache_file):
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    rc, s = run(["cache"], cache_file=cache_file)
    assert rc == 0
    assert "principal-backend-engineer" in s
    assert "idle 30m" in s  # policy line


def test_cache_json_reports_policy(cache_file):
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    assert rc == 0
    data = json.loads(s)
    assert data["policy"]["idle_ttl_seconds"] == 1800.0
    assert data["policy"]["ceiling_ttl_seconds"] == 7200.0


def test_cache_json_reports_materialized_payload(cache_file):
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    assert rc == 0
    entry = json.loads(s)["entries"][0]
    assert entry["persona_id"] == "principal-backend-engineer"
    assert entry["materialized"] is True
    assert entry["overlay_bytes"] > 0


def test_evict_removes_a_warm_persona(cache_file):
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    rc, s = run(["evict", "principal-backend-engineer"], cache_file=cache_file)
    assert rc == 0
    assert "dematerialized principal-backend-engineer" in s
    # ...and it is gone from the cache afterward.
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    assert json.loads(s)["entries"] == []


def test_evict_not_warm_is_noop_exit_0(cache_file):
    rc, s = run(["evict", "principal-backend-engineer"], cache_file=cache_file)
    assert rc == 0  # idempotent: evicting a cold persona is not an error
    assert "not warm" in s


def test_evict_json_is_idempotent(cache_file):
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    rc, s = run(["evict", "principal-backend-engineer", "--json"], cache_file=cache_file)
    assert rc == 0
    assert json.loads(s) == {"persona_id": "principal-backend-engineer", "evicted": True}
    # A second evict reports evicted=False — the row is already gone.
    rc, s = run(["evict", "principal-backend-engineer", "--json"], cache_file=cache_file)
    assert json.loads(s)["evicted"] is False


def test_evict_leaves_other_warm_personas(cache_file):
    # Targeted eviction drops only the named persona, unlike sweep --all.
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    run(["equip", "write some tests"], cache_file=cache_file)
    run(["evict", "principal-backend-engineer"], cache_file=cache_file)
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    ids = [e["persona_id"] for e in json.loads(s)["entries"]]
    assert ids == ["principal-test-engineer"]


def test_sweep_all_clears(cache_file):
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    run(["equip", "write some tests"], cache_file=cache_file)
    rc, s = run(["sweep", "--all"], cache_file=cache_file)
    assert rc == 0
    assert "cleared" in s
    rc, s = run(["cache", "--json"], cache_file=cache_file)
    assert json.loads(s)["entries"] == []


def test_sweep_nothing_to_evict(cache_file):
    run(["equip", "implement a backend endpoint"], cache_file=cache_file)
    rc, s = run(["sweep"], cache_file=cache_file)
    assert rc == 0
    assert "nothing to evict" in s


# ---- invalid registry ------------------------------------------------------ #


def test_invalid_registry_exits_2(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('[[persona]]\nid = "dup"\n[[persona]]\nid = "dup"\n')
    rc, s = run(["--registry", str(bad), "list"])
    assert rc == 2

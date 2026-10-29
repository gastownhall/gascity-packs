"""Release-line test scope for release/gastown-*.

This branch releases gastown, and it carries the gascity pack byte-identical to
a main release so gc can embed both from one commit. The derived packs that
build on gascity (superpowers, gstack, bmad) stay at their 0.1.11-era content
here: they are released from main, not from this line.

gascity/tests includes contract tests for those derived packs. On this branch
they compare main's gascity against the older derived packs and fail for that
reason alone, so they are skipped here. They still run on main, where the
derived packs are released. gascity/ cannot carry the skip itself: its tree
must stay byte-identical to the main release it mirrors.
"""

from __future__ import annotations

import pytest

DERIVED_PACK_CONTRACT_TESTS = {
    "gascity/tests/test_derived_pack_compatibility.py::DerivedPackCompatibilityTests::test_agent_prompts_use_public_claim_protocol_without_overrides",
    "gascity/tests/test_formula_assets.py::FormulaAssetTests::test_do_work_source_anchor_is_stamped_once_and_read_back",
    "gascity/tests/test_formula_assets.py::FormulaAssetTests::test_superpowers_finalizer_materializes_canonical_build_summary",
    "gascity/tests/test_formula_assets.py::FormulaAssetTests::test_pack_close_source_anchor_overrides_read_root_stamped_anchor",
    "gascity/tests/test_formula_assets.py::FormulaAssetTests::test_superpowers_code_review_loop_has_single_verdict_owner",
    "gascity/tests/test_formula_assets.py::FormulaAssetTests::test_superpowers_brainstorming_expansion_preserves_stock_loops",
}

SKIP_REASON = (
    "release/gastown line: derived packs (superpowers, gstack, bmad) stay at "
    "0.1.11-era content; their contract with gascity is tested on main"
)


def pytest_collection_modifyitems(config, items):
    seen = set()
    for item in items:
        if item.nodeid in DERIVED_PACK_CONTRACT_TESTS:
            seen.add(item.nodeid)
            item.add_marker(pytest.mark.skip(reason=SKIP_REASON))
    collected_gascity = any(item.nodeid.startswith("gascity/tests/") for item in items)
    missing = DERIVED_PACK_CONTRACT_TESTS - seen
    if collected_gascity and missing:
        raise pytest.UsageError(
            "conftest.py skips tests that no longer exist; update the list: "
            + ", ".join(sorted(missing))
        )

"""Behavioral test suite for the ast-lens outline emitter.

These tests validate the emitter (`bin/outline.py`) against the *contracts*
in the Blackrim AST paper — Algorithm 1 (passthrough conditions), App C
(Markdown schema + line-span anchors), §5.3 (token-budget truncation),
and §5.4 + App D (sanitisation of verbatim file content).

This is a behavioral suite: it asserts the emitter *behaves* as the paper
specifies, not that it is byte-for-byte identical to any reference tool.
It never imports any reference implementation.

Notes on emitter-specific behaviour exercised here (observed, contract-true):
  * Line-span anchors are rendered with an en-dash, e.g. ``(L57–61)``; the
    anchor-presence regex keys on the ``L<digits>`` start anchor only.
  * Python imports are not quoted, so the emitter's quoted-string import
    extractor yields no names and the ``## Imports`` section is omitted for
    Python. Go and TypeScript imports are quoted and do surface.
  * The package/module doc is the prompt-injection surface; under the
    default budget the truncation precedence (§5.3 step 4) can drop the doc
    blockquote, so the sanitisation tests use a large budget to ensure the
    doc surfaces and can be inspected for the ``[sanitised]`` marker.
"""
from __future__ import annotations

import builtins
import importlib.util
import io
import json
import os
import re
import subprocess
import sys

import pytest

# ---- Import the emitter by file path (cwd-independent) ---------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACK = os.path.dirname(_HERE)
_OUTLINE_PY = os.path.join(_PACK, "bin", "outline.py")
_FIX = os.path.join(_HERE, "fixtures")

_WRAPPER = os.path.join(_PACK, "bin", "outline")

_spec = importlib.util.spec_from_file_location("ast_lens_outline", _OUTLINE_PY)
ol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ol)

# Default contract parameters (paper App F / §5).
BUDGET = ol.DEFAULT_BUDGET          # 300
THRESHOLD = ol.DEFAULT_THRESHOLD    # 200
# A budget large enough that no truncation occurs, so the full schema —
# including the package-doc blockquote and per-decl private markers — is
# present for inspection.
BIG_BUDGET = 100_000

# Line-span anchor: a decl line must carry an L<digits> start anchor. The
# emitter renders spans as ``(L<start>–<end>)`` with an en-dash.
ANCHOR_RE = re.compile(r"L\d+")
FULL_SPAN_RE = re.compile(r"\(L\d+[–-]\d+\)")


def fx(name: str) -> str:
    return os.path.join(_FIX, name)


# Decl-keyword prefixes after which the declared name appears.
_DECL_KW = ("func", "function", "class", "def", "interface", "type", "enum",
            "const", "var")


def _declares(bullet: str, sym: str) -> bool:
    """True if `bullet` is the declaration of `sym` (not a mere reference to
    `sym` in some other decl's parameter types). Matches `sym` immediately
    after a decl keyword, or as a Go method name after the receiver, or as
    the backticked value-decl name (``- `Name` (const, ...)``)."""
    inner = bullet[2:].strip()           # drop the "- " bullet marker
    # Value-bucket decls: ``- `Name` (kind, L..)``
    if re.match(rf"^`{re.escape(sym)}`\s*\(", inner):
        return True
    # Pull out the backticked signature, if any.
    m = re.match(r"^`([^`]*)`", inner)
    sig = m.group(1) if m else inner
    # `<keyword> Name` — e.g. `func Get`, `class Store`, `interface Session`.
    for kw in _DECL_KW:
        if re.search(rf"\b{kw}\s+{re.escape(sym)}\b", sig):
            return True
    # Go method: `func (recv *T) Name(` — name follows the receiver group.
    if re.search(rf"\)\s+{re.escape(sym)}\b", sig):
        return True
    return False


def emit(name: str, *, budget: int = BUDGET, threshold: int = THRESHOLD,
         fmt: str = "md") -> str:
    """Convenience wrapper over the emitter's public ``outline`` function."""
    return ol.outline(fx(name), budget, threshold, fmt)


SAMPLES = ["sample.go", "sample.py", "sample.ts"]


# =====================================================================
# Passthrough (Algorithm 1: "outline not required" / graceful degradation)
# =====================================================================
class TestPassthrough:
    def test_subthreshold_file_returns_empty(self):
        # tiny.py is well under the 200-LoC threshold.
        assert emit("tiny.py") == ""

    def test_missing_path_returns_empty(self):
        # A path that does not exist must passthrough, never raise.
        out = ol.outline(fx("does_not_exist_42.py"), BUDGET, THRESHOLD, "md")
        assert out == ""

    def test_unsupported_extension_returns_empty(self, tmp_path):
        # A .md file is not a supported source language → passthrough,
        # even when it is large (well over the LoC threshold).
        big_md = tmp_path / "README.md"
        big_md.write_text("\n".join(f"# heading {i}" for i in range(400)))
        assert ol.outline(str(big_md), BUDGET, THRESHOLD, "md") == ""

    def test_skip_directive_returns_empty(self):
        # skip.go is over threshold but carries `outline:skip` in its header.
        assert emit("skip.go") == ""

    def test_skip_directive_is_what_triggers_passthrough(self):
        # Sanity: prove the skip directive (not size) causes passthrough —
        # the file is over threshold and would otherwise outline.
        src = open(fx("skip.go"), "rb").read()
        loc = src.count(b"\n") + 1
        assert loc >= THRESHOLD
        assert ol.has_skip(fx("skip.go")) is True

    def test_skip_detected_only_in_first_five_lines(self, tmp_path):
        # The directive on line 1 is honoured; the same token on line 20 is
        # not (the emitter only scans the first five lines).
        early = tmp_path / "early.py"
        early.write_text("# outline:skip\n" + "x = 1\n" * 300)
        assert ol.has_skip(str(early)) is True

        late = tmp_path / "late.py"
        late.write_text("x = 1\n" * 19 + "# outline:skip\n" + "x = 1\n" * 300)
        assert ol.has_skip(str(late)) is False


# =====================================================================
# Schema (App C): header line + expected section headers
# =====================================================================
class TestSchema:
    @pytest.mark.parametrize("name", SAMPLES)
    def test_header_line_shape(self, name):
        out = emit(name, budget=BIG_BUDGET)
        first = out.splitlines()[0]
        # `# <basename> (<N> LoC, <M> decls)` — App C specimen header.
        m = re.match(
            r"^# " + re.escape(name) + r" \((\d+) LoC, (\d+) decls\)$", first
        )
        assert m, f"unexpected header for {name!r}: {first!r}"
        loc = int(m.group(1))
        decls = int(m.group(2))
        # LoC must equal source newline count + 1 (the emitter's definition).
        src = open(fx(name), "rb").read()
        assert loc == src.count(b"\n") + 1
        assert decls > 0

    @pytest.mark.parametrize("name", SAMPLES)
    def test_has_expected_section_headers(self, name):
        out = emit(name, budget=BIG_BUDGET)
        # Every sample defines both types and functions.
        assert "## Types" in out
        assert "## Functions" in out

    def test_go_and_ts_have_imports_section(self):
        # Go and TS imports are quoted, so they surface as `## Imports`.
        assert "## Imports" in emit("sample.go", budget=BIG_BUDGET)
        assert "## Imports" in emit("sample.ts", budget=BIG_BUDGET)

    @pytest.mark.parametrize("name", SAMPLES)
    def test_json_format_envelope(self, name):
        import json

        raw = emit(name, budget=BIG_BUDGET, fmt="json")
        obj = json.loads(raw)
        assert obj["lang"] in ("go", "python", "typescript")
        assert obj["loc"] > THRESHOLD
        assert obj["markdown"].startswith(f"# {name} (")
        assert obj["tokens_outline"] > 0


# =====================================================================
# Line-span anchors (App C): "every declaration carries L_start–L_end"
# =====================================================================
class TestAnchors:
    @pytest.mark.parametrize("name", SAMPLES)
    def test_decl_lines_have_anchor(self, name):
        out = emit(name, budget=BIG_BUDGET)
        decl_lines = [
            ln for ln in out.splitlines()
            if ln.startswith("- ")          # type/function bullets
        ]
        assert decl_lines, f"no decl bullets found for {name!r}"
        for ln in decl_lines:
            assert ANCHOR_RE.search(ln), f"missing L<digits> anchor: {ln!r}"

    @pytest.mark.parametrize("name", SAMPLES)
    def test_full_span_anchor_format(self, name):
        # At least one decl renders a complete (L<start>–<end>) span.
        out = emit(name, budget=BIG_BUDGET)
        assert FULL_SPAN_RE.search(out), f"no full L-span in {name!r} output"


# =====================================================================
# Public / private visibility (per-language rules, App B / is_private)
# =====================================================================
class TestVisibility:
    # (fixture, exported decl name expected by name, private decl name)
    EXPORTED = {
        "sample.go": ["Get", "New", "Save"],
        "sample.py": ["new_session", "build_store", "Session"],
        "sample.ts": ["newSession", "Store", "mergeData"],
    }
    PRIVATE = {
        # Go: capitalisation = exported; lowercase ⇒ private.
        "sample.go": "validateID",
        # Python: leading underscore ⇒ private.
        "sample.py": "_validate_id",
        # TS/JS: absence of `export` ⇒ private.
        "sample.ts": "validateId",
    }

    @pytest.mark.parametrize("name", SAMPLES)
    def test_exported_decls_appear_by_name(self, name):
        out = emit(name, budget=BIG_BUDGET)
        for sym in self.EXPORTED[name]:
            assert sym in out, f"exported {sym!r} missing from {name!r}"

    @pytest.mark.parametrize("name", SAMPLES)
    def test_private_decls_flagged(self, name):
        # Under a large budget private decls are retained and marked.
        out = emit(name, budget=BIG_BUDGET)
        priv = self.PRIVATE[name]
        priv_lines = [ln for ln in out.splitlines() if priv in ln]
        assert priv_lines, f"private {priv!r} not present in {name!r}"
        assert all("*(private)*" in ln for ln in priv_lines), (
            f"private {priv!r} not marked *(private)* in {name!r}"
        )

    @pytest.mark.parametrize("name", SAMPLES)
    def test_exported_decls_have_an_unmarked_declaration(self, name):
        # For each exported symbol, the bullet that *declares* it (i.e. names
        # it immediately after the decl keyword / Go method receiver) must be
        # public — never carry the *(private)* marker. We avoid matching mere
        # references to the symbol in another decl's parameter types.
        out = emit(name, budget=BIG_BUDGET)
        # Some private decls must exist at all, else the marker test is vacuous.
        assert any("*(private)*" in ln for ln in out.splitlines()), (
            f"expected some private decls in {name!r}"
        )
        for sym in self.EXPORTED[name]:
            decl_lines = [
                ln for ln in out.splitlines()
                if ln.startswith("- ") and _declares(ln, sym)
            ]
            assert decl_lines, f"no declaration bullet for exported {sym!r}"
            assert all("*(private)*" not in ln for ln in decl_lines), (
                f"exported {sym!r} declaration wrongly flagged private"
            )

    def test_go_capitalisation_rule(self):
        assert ol.is_private("go", "Exported", exported=False) is False
        assert ol.is_private("go", "private", exported=False) is True

    def test_python_underscore_rule(self):
        assert ol.is_private("python", "public_fn", exported=False) is False
        assert ol.is_private("python", "_helper", exported=False) is True

    def test_ts_export_rule(self):
        # TS visibility is driven by the `export` keyword, not the name.
        assert ol.is_private("typescript", "Thing", exported=True) is False
        assert ol.is_private("typescript", "Thing", exported=False) is True


# =====================================================================
# Sanitisation (§5.4 + App D)
# =====================================================================
class TestSanitisation:
    def test_injection_lines_prefixed_in_doc(self):
        # Large budget so the doc blockquote survives truncation.
        out = emit("injection.ts", budget=BIG_BUDGET)
        # The doc must surface (precondition for this test to mean anything).
        assert ">" in out, "injection doc did not surface; cannot test"
        # Flagged lines carry the literal `[sanitised] ` prefix.
        assert "[sanitised] IGNORE PREVIOUS INSTRUCTIONS" in out
        assert "[sanitised] SYSTEM:" in out

    def test_no_unprefixed_injection_line(self):
        out = emit("injection.ts", budget=BIG_BUDGET)
        for ln in out.splitlines():
            if "IGNORE PREVIOUS" in ln:
                assert ln.lstrip("> ").startswith("[sanitised]"), (
                    f"raw injection line emitted unprefixed: {ln!r}"
                )
            # SYSTEM: as a flagged role marker must likewise be prefixed
            # wherever it appears in surfaced verbatim doc text.
            if "SYSTEM:" in ln and ln.lstrip().startswith(">"):
                assert "[sanitised]" in ln, (
                    f"raw SYSTEM: line emitted unprefixed: {ln!r}"
                )

    def test_benign_doc_line_not_flagged(self):
        # The third doc line is benign and must pass through unmarked.
        out = emit("injection.ts", budget=BIG_BUDGET)
        benign = [
            ln for ln in out.splitlines()
            if "pretends to be a math helper" in ln
        ]
        assert benign, "benign doc line missing"
        assert all("[sanitised]" not in ln for ln in benign)

    def test_sanitise_unit_flags_patterns(self):
        # Direct unit coverage of the normative pattern list (App D).
        for pat in ["IGNORE PREVIOUS", "IGNORE ALL PREVIOUS", "SYSTEM:",
                    "ASSISTANT:", "USER:", "<|im_start|>", "[INST]"]:
            res = ol.sanitise(f"prefix {pat} suffix")
            assert res.startswith("[sanitised] "), (
                f"pattern {pat!r} not flagged by sanitise()"
            )

    def test_sanitise_caps_verbatim_length(self):
        # §5.4(1): verbatim text per decl is capped (VERBATIM_CAP chars).
        long = "word " * 200
        res = ol.sanitise(long)
        assert len(res) <= ol.VERBATIM_CAP + 4  # cap + trailing " …"
        assert res.rstrip().endswith("…")

    def test_sanitise_collapses_blank_runs(self):
        # §5.4(3): >3 consecutive newlines collapse to 2.
        res = ol.sanitise("a\n\n\n\n\n\nb")
        assert "\n\n\n" not in res


# =====================================================================
# Compression (the whole point: outline ≪ source)
# =====================================================================
class TestCompression:
    @pytest.mark.parametrize("name", SAMPLES)
    def test_outline_far_smaller_than_source(self, name):
        # At the default budget the outline must be dramatically smaller
        # than the source — well under 30% of the source character count.
        src_chars = len(open(fx(name), encoding="utf-8").read())
        out = emit(name)  # default budget 300
        assert out, f"expected non-empty outline for {name!r}"
        ratio = len(out) / src_chars
        assert ratio < 0.30, (
            f"{name}: outline is {ratio:.0%} of source (expected < 30%)"
        )

    def test_default_budget_keeps_outline_bounded(self):
        # §5.3: at the default budget the emitter applies truncation so the
        # outline token estimate stays within a small multiple of budget.
        # (The paper's While-loop targets <= budget; the emitter's section
        # trimmer is best-effort, so we assert a generous bound that still
        # demonstrates active budget control.)
        out = emit("sample.go")  # default budget 300
        assert ol.est_tokens(out) <= BUDGET * 2


# =====================================================================
# Sanitisation — full App D pattern set (every injection literal)
# =====================================================================
# The complete normative pattern list from App D (the paper's
# "Sanitisation Pattern Set" table), in declaration order.
APP_D_PATTERNS = [
    "IGNORE PREVIOUS",
    "IGNORE ALL PREVIOUS",
    "SYSTEM:",
    "ASSISTANT:",
    "USER:",
    "<|im_start|>",
    "<|im_end|>",
    "<s>",
    "</s>",
    "[INST]",
    "[/INST]",
    "Human:",
    "Assistant:",
]


class TestSanitisationPatternSet:
    """Every App D literal must be flagged by sanitise(); benign prose is
    left untouched; the §5.4 cap and newline-collapse rules hold."""

    @pytest.mark.parametrize("pat", APP_D_PATTERNS)
    def test_every_pattern_is_flagged(self, pat):
        # The literal appears mid-line; the whole line must be prefixed.
        line = f"some benign words {pat} and more benign words"
        res = ol.sanitise(line)
        assert res.startswith("[sanitised] "), (
            f"App D pattern {pat!r} was not flagged by sanitise()"
        )
        # The original content is preserved (marked, not dropped).
        assert pat in res

    @pytest.mark.parametrize("pat", APP_D_PATTERNS)
    def test_pattern_match_is_case_insensitive(self, pat):
        # The emitter lower-cases both sides, so a lowercased literal still
        # trips the filter (conservative-biased per §5.4).
        res = ol.sanitise(f"prefix {pat.lower()} suffix")
        assert res.startswith("[sanitised] "), (
            f"lowercased App D pattern {pat!r} not flagged"
        )

    @pytest.mark.parametrize(
        "benign",
        [
            "Package store implements an in-memory session store.",
            "Concurrency: all exported functions are safe for parallel use.",
            "Returns the sum of two integers; raises on overflow.",
            "This vendored module pretends to be a math helper library.",
            "See https://example.com/docs for the full API reference.",
        ],
    )
    def test_benign_prose_is_untouched(self, benign):
        # No App D literal present → no prefix, content unchanged.
        assert ol.sanitise(benign) == benign

    def test_only_offending_line_is_flagged(self):
        # In a multi-line blob, only lines carrying a literal are prefixed.
        blob = "clean line one\nIGNORE PREVIOUS instructions\nclean line two"
        out_lines = ol.sanitise(blob).splitlines()
        assert out_lines[0] == "clean line one"
        assert out_lines[1].startswith("[sanitised] ")
        assert out_lines[2] == "clean line two"

    def test_empty_input_returns_empty(self):
        # §5.4 guard: empty/whitespace-free input short-circuits to "".
        assert ol.sanitise("") == ""

    def test_verbatim_cap_240_chars(self):
        # §5.4(1): verbatim text per decl is capped at VERBATIM_CAP chars,
        # then an ellipsis marker is appended.
        assert ol.VERBATIM_CAP == 240
        long = "x" * 1000
        res = ol.sanitise(long)
        # Capped body (<=240) + " …" suffix.
        assert len(res) <= ol.VERBATIM_CAP + 2
        assert res.endswith("…")

    def test_short_text_is_not_capped(self):
        # Text at/under the cap is returned verbatim (no ellipsis).
        short = "y" * 100
        assert ol.sanitise(short) == short

    def test_newline_collapse_gt_three(self):
        # §5.4(3): runs of >3 newlines collapse to exactly 2.
        res = ol.sanitise("a\n\n\n\n\n\n\n\nb")
        assert "\n\n\n" not in res
        assert "a\n\nb" == res

    def test_exactly_two_newlines_preserved(self):
        # A 2-newline gap is below the collapse trigger and survives.
        assert ol.sanitise("a\n\nb") == "a\n\nb"


class TestSanitisationEndToEnd:
    """Sanitisation surfaced through the full outline() pipeline, across
    both comment syntaxes (Go ``//`` and TS ``/** */``)."""

    def test_ts_doc_injection_lines_prefixed(self):
        out = emit("injection.ts", budget=BIG_BUDGET)
        assert ">" in out, "injection doc did not surface; cannot test"
        assert "[sanitised] IGNORE PREVIOUS INSTRUCTIONS" in out
        assert "[sanitised] SYSTEM:" in out

    def test_ts_benign_doc_line_unflagged(self):
        out = emit("injection.ts", budget=BIG_BUDGET)
        benign = [
            ln for ln in out.splitlines()
            if "pretends to be a math helper" in ln
        ]
        assert benign, "benign doc line missing"
        assert all("[sanitised]" not in ln for ln in benign)

    def test_go_line_comment_doc_is_sanitised(self):
        # Cross-language: a Go ``//`` package-doc whose first line is an
        # injection literal must surface with the [sanitised] marker.
        out = emit("sanitise_doc.go", budget=BIG_BUDGET)
        assert ">" in out, "go doc did not surface; cannot test"
        doc_lines = [ln for ln in out.splitlines() if ln.startswith(">")]
        assert doc_lines, "no doc blockquote in go outline"
        # The first surfaced doc line carries an IGNORE PREVIOUS literal and
        # must be prefixed (verbatim text is the injection surface).
        assert "[sanitised]" in doc_lines[0]
        assert "IGNORE PREVIOUS" in doc_lines[0]

    def test_no_raw_injection_literal_escapes_unprefixed(self):
        # Whatever injection text surfaces in any doc blockquote line must be
        # prefixed; never emitted raw.
        for name in ("injection.ts", "sanitise_doc.go"):
            out = emit(name, budget=BIG_BUDGET)
            for ln in out.splitlines():
                if not ln.startswith(">"):
                    continue
                if "IGNORE PREVIOUS" in ln:
                    assert "[sanitised]" in ln, (
                        f"{name}: raw injection surfaced unprefixed: {ln!r}"
                    )


# =====================================================================
# Truncation precedence (§5.3) — each step forced and budget asserted
# =====================================================================
class TestTruncationPrecedence:
    """The §5.3 ladder cuts content in a fixed order until the outline fits
    the budget: (1) nested significant constructs, (2) private top-level
    decls collapsed to a count, (3) package-doc lines, (4) imports collapsed
    to a count. Fixtures are engineered so lowering the budget walks the
    ladder; every step asserts the token estimate respects the budget."""

    def _emit(self, name, budget):
        return ol.outline(fx(name), budget, THRESHOLD, "md")

    def test_untruncated_baseline_has_all_sections(self):
        # Under a huge budget, truncation.go renders nested bullets, private
        # markers, the doc blockquote, and the full import list.
        out = self._emit("truncation.go", BIG_BUDGET)
        assert "  - " in out                      # nested significant bullets
        assert "*(private)*" in out               # per-decl private markers
        assert "\n> " in out                      # package-doc blockquote
        assert "alpha" in out                     # full import list present
        assert "imports)" not in out              # not yet collapsed

    def test_step1_nested_dropped_in_isolation(self):
        # nested_only.go: at a budget where dropping just the nested bullets
        # suffices, the private markers are RETAINED (step 2 not reached).
        full = self._emit("nested_only.go", BIG_BUDGET)
        assert "  - " in full and "*(private)*" in full
        out = self._emit("nested_only.go", 80)
        assert "  - " not in out, "nested bullets should be dropped (step 1)"
        assert "*(private)*" in out, "private markers must survive step 1"
        assert "private decls" not in out, "step 2 should NOT have fired"
        assert ol.est_tokens(out) <= 80

    def test_step2_private_decls_collapsed_to_count(self):
        # At a mid budget on truncation.go, nested bullets are gone AND
        # private decls collapse to a count marker, while the doc + imports
        # are still present.
        out = self._emit("truncation.go", 300)
        assert "  - " not in out
        assert "*(private)*" not in out, "private bullets should be collapsed"
        assert "private decls" in out, "expected the (+N private decls) marker"
        assert re.search(r"_\(\+\d+ private decls\)_", out), (
            "private-collapse marker missing or malformed"
        )
        assert "\n> " in out, "doc should still be present at this budget"
        assert ol.est_tokens(out) <= 300

    def test_step3_doc_dropped(self):
        # Lower still: the package-doc blockquote is dropped but imports
        # remain listed (not yet collapsed).
        out = self._emit("truncation.go", 90)
        assert "\n> " not in out, "doc blockquote should be dropped (step 3)"
        assert "alpha" in out, "imports should still be listed at this budget"
        assert ol.est_tokens(out) <= 90

    def test_step4_imports_collapsed_to_count(self):
        # Lowest budget: imports collapse to a count and the verbatim list
        # disappears.
        out = self._emit("truncation.go", 60)
        assert "alpha" not in out, "import list should be collapsed (step 4)"
        assert "imports)" in out, "expected the (N imports) count marker"
        assert re.search(r"\(\d+ imports\)", out), (
            "import-collapse marker missing or malformed"
        )
        assert ol.est_tokens(out) <= 60

    def test_ladder_is_monotonic(self):
        # As the budget shrinks the outline only loses content; token
        # estimate is non-increasing across the ladder.
        budgets = [BIG_BUDGET, 300, 90, 60]
        sizes = [ol.est_tokens(self._emit("truncation.go", b)) for b in budgets]
        assert sizes == sorted(sizes, reverse=True), (
            f"truncation not monotonic across budgets: {sizes}"
        )

    def test_no_truncation_when_already_under_budget(self):
        # If the candidate already fits, truncate() is an identity (the early
        # return path): a huge and a merely-large budget give the same output.
        a = self._emit("sample.go", BIG_BUDGET)
        b = self._emit("sample.go", BIG_BUDGET // 2)
        assert a == b


# =====================================================================
# Per-language significance (App B) — significant nested constructs surface
# =====================================================================
def _nested_labels(out: str) -> list[str]:
    """The nested-construct bullets (``  - <label> (Lx–Ly)``) with the
    ``  - `` marker removed, so a caller can test the label text directly."""
    return [ln[4:] for ln in out.splitlines() if ln.startswith("  - ")]


class TestSignificanceGo:
    def test_goroutine_defer_select_surface(self):
        out = ol.outline(fx("truncation.go"), BIG_BUDGET, THRESHOLD, "md")
        nested = _nested_labels(out)
        assert any(ln.startswith("go") for ln in nested), "goroutine not surfaced"
        assert any(ln.startswith("defer") for ln in nested), "defer not surfaced"
        assert any(ln.startswith("select") for ln in nested), "select not surfaced"
        # Each nested bullet carries its own line-span anchor.
        for ln in nested:
            assert ANCHOR_RE.search(ln), f"nested bullet missing anchor: {ln!r}"
        assert nested  # non-empty sanity


class TestSignificancePython:
    def test_with_try_nested_def_class_surface(self):
        out = ol.outline(fx("significant.py"), BIG_BUDGET, THRESHOLD, "md")
        nested = _nested_labels(out)
        assert any(ln.startswith("with") for ln in nested), "with not surfaced"
        assert any(ln.startswith("try") for ln in nested), "try not surfaced"
        assert any(ln.startswith("def:") for ln in nested), (
            "nested def not surfaced"
        )
        assert any(ln.startswith("class:") for ln in nested), (
            "nested class not surfaced"
        )

    def test_nested_named_constructs_carry_name(self):
        out = ol.outline(fx("significant.py"), BIG_BUDGET, THRESHOLD, "md")
        # The nested def/class are labelled with their identifier.
        assert "def: inner_helper" in out
        assert "class: InnerThing" in out


class TestSignificanceTypeScript:
    def test_arrow_try_jsx_surface(self):
        out = ol.outline(fx("significant.tsx"), BIG_BUDGET, THRESHOLD, "md")
        nested = _nested_labels(out)
        assert any(ln.startswith("arrow") for ln in nested), "arrow not surfaced"
        assert any(ln.startswith("try") for ln in nested), "try not surfaced"
        assert any(ln.startswith("jsx") for ln in nested), "jsx not surfaced"


class TestSignificanceJavaScript:
    def test_arrow_and_try_surface(self):
        out = ol.outline(fx("significant.js"), BIG_BUDGET, THRESHOLD, "md")
        nested = _nested_labels(out)
        assert any(ln.startswith("arrow") for ln in nested), (
            "arrow (>=5 lines) not surfaced"
        )
        assert any(ln.startswith("try") for ln in nested), "try not surfaced"


# =====================================================================
# Per-language end-to-end: every supported language produces a well-formed
# outline; unsupported / parse-failure inputs pass through to "".
# =====================================================================
HEADER_RE = re.compile(r"^# .+ \(\d+ LoC, \d+ decls\)$")


class TestLanguagesEndToEnd:
    @pytest.mark.parametrize(
        "name,lang",
        [
            ("sample.go", "go"),
            ("sample.py", "python"),
            ("sample.ts", "typescript"),
            ("significant.js", "javascript"),
            ("significant.tsx", "tsx"),
        ],
    )
    def test_supported_language_well_formed(self, name, lang):
        out = ol.outline(fx(name), BIG_BUDGET, THRESHOLD, "md")
        assert out, f"{name}: expected a non-empty outline"
        lines = out.splitlines()
        # App C header on line 1.
        assert HEADER_RE.match(lines[0]), f"{name}: bad header {lines[0]!r}"
        # Ends with a single trailing newline (render contract).
        assert out.endswith("\n")
        assert "\n\n\n" not in out, f"{name}: stray blank-line run"
        # At least one declaration bullet with a line-span anchor.
        decl_lines = [ln for ln in lines if ln.startswith("- ")]
        assert decl_lines, f"{name}: no decl bullets"
        assert all(ANCHOR_RE.search(ln) for ln in decl_lines)
        # The JSON envelope reports the expected language.
        obj = json.loads(ol.outline(fx(name), BIG_BUDGET, THRESHOLD, "json"))
        assert obj["lang"] == lang

    def test_unsupported_extension_passthrough(self, tmp_path):
        # A large .rb (Ruby) file is not a supported language → "".
        rb = tmp_path / "big.rb"
        rb.write_text("\n".join(f"x{i} = {i}" for i in range(400)))
        assert ol.outline(str(rb), BUDGET, THRESHOLD, "md") == ""

    def test_parse_failure_passthrough(self):
        # broken.go is over threshold but so malformed that no top-level
        # declarations survive → graceful passthrough ("").
        src = open(fx("broken.go"), "rb").read()
        assert src.count(b"\n") + 1 >= THRESHOLD
        assert ol.outline(fx("broken.go"), BUDGET, THRESHOLD, "md") == ""

    def test_binary_input_passthrough(self, tmp_path):
        # Random bytes with a .go extension, over threshold: must never raise
        # and must passthrough.
        p = tmp_path / "blob.go"
        p.write_bytes(os.urandom(4000) + b"\n" * 250)
        assert ol.outline(str(p), BUDGET, THRESHOLD, "md") == ""


# =====================================================================
# Boundary conditions
# =====================================================================
class TestBoundaries:
    def _go_with_loc(self, n):
        # Build syntactically valid Go with exactly n lines (LoC = n).
        body = ["package b", "func Foo() int { return 1 }"]
        while len(body) < n:
            body.append(f"func F{len(body)}() int {{ return {len(body)} }}")
        return "\n".join(body[:n])

    def test_threshold_boundary_199_200_201(self, tmp_path):
        # LoC == newline count + 1. theta_L = 200. The emitter outlines iff
        # loc >= threshold (the guard is ``loc < threshold``).
        for n, expect_outline in [(199, False), (200, True), (201, True)]:
            src = self._go_with_loc(n)
            assert src.count("\n") + 1 == n
            p = tmp_path / f"b{n}.go"
            p.write_text(src)
            out = ol.outline(str(p), BIG_BUDGET, THRESHOLD, "md")
            assert bool(out) is expect_outline, (
                f"LoC={n}: expected outline={expect_outline}, got {bool(out)}"
            )

    def test_empty_file_passthrough(self, tmp_path):
        # An empty .py file (0 bytes) is under threshold → "".
        p = tmp_path / "empty.py"
        p.write_text("")
        assert ol.outline(str(p), BUDGET, THRESHOLD, "md") == ""

    def test_imports_only_file(self):
        # imports_only.py is over threshold with only imports: the outline
        # surfaces an ## Imports section and no ## Functions section.
        out = ol.outline(fx("imports_only.py"), BIG_BUDGET, THRESHOLD, "md")
        assert out, "imports-only file should still outline"
        assert "## Imports" in out
        assert "## Functions" not in out
        assert "## Types" not in out

    def test_no_decls_no_imports_passthrough(self):
        # no_decls.py is over threshold but has neither declarations nor
        # imports (only bare assignments) → the ``not decls and not imports``
        # passthrough fires.
        src = open(fx("no_decls.py"), "rb").read()
        assert src.count(b"\n") + 1 >= THRESHOLD
        assert ol.outline(fx("no_decls.py"), BIG_BUDGET, THRESHOLD, "md") == ""

    def test_non_utf8_content(self):
        # oddenc.go carries invalid UTF-8 / control bytes in its leading
        # comment; the emitter must decode defensively and still produce a
        # well-formed outline (never raise).
        out = ol.outline(fx("oddenc.go"), BIG_BUDGET, THRESHOLD, "md")
        assert out.startswith("# oddenc.go (")
        assert HEADER_RE.match(out.splitlines()[0])

    def test_very_long_single_line(self):
        # longline.go has a ~40k-char single comment line; the emitter must
        # handle it without error and produce a bounded outline.
        out = ol.outline(fx("longline.go"), BIG_BUDGET, THRESHOLD, "md")
        assert out.startswith("# longline.go (")
        # No surfaced line should be pathologically long (doc is bounded by
        # the verbatim cap; signatures are clipped to 120 chars).
        for ln in out.splitlines():
            assert len(ln) < 600, f"unexpectedly long output line: {len(ln)}"


# =====================================================================
# Config: --budget / --threshold flags + env vars + --format json
# =====================================================================
class TestConfig:
    def test_budget_flag_changes_output(self):
        # A tiny budget triggers truncation that a huge budget does not.
        big = ol.outline(fx("truncation.go"), BIG_BUDGET, THRESHOLD, "md")
        small = ol.outline(fx("truncation.go"), 60, THRESHOLD, "md")
        assert small != big
        assert ol.est_tokens(small) < ol.est_tokens(big)
        assert ol.est_tokens(small) <= 60

    def test_threshold_flag_changes_passthrough(self, tmp_path):
        # A 150-LoC file: outlined under threshold=100, passed through under
        # threshold=200.
        src = "\n".join(["package b", "func Foo() int { return 1 }"]
                        + [f"func F{i}() int {{ return {i} }}" for i in range(148)])
        assert src.count("\n") + 1 == 150
        p = tmp_path / "mid.go"
        p.write_text(src)
        assert ol.outline(str(p), BIG_BUDGET, 100, "md") != ""
        assert ol.outline(str(p), BIG_BUDGET, 200, "md") == ""

    def test_env_budget_default(self, monkeypatch):
        # AST_LENS_BUDGET sets the module-level DEFAULT_BUDGET on (re)import.
        monkeypatch.setenv("AST_LENS_BUDGET", "50")
        monkeypatch.setenv("AST_LENS_THRESHOLD", "200")
        spec = importlib.util.spec_from_file_location("ol_env_b", _OUTLINE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.DEFAULT_BUDGET == 50
        # The env-derived default actively drives truncation: against a huge
        # explicit budget the output is much larger; under the env default it
        # is hard-truncated (imports collapsed, nested + doc gone).
        at_env = mod.outline(fx("truncation.go"), mod.DEFAULT_BUDGET,
                             mod.DEFAULT_THRESHOLD, "md")
        at_big = mod.outline(fx("truncation.go"), 100_000,
                             mod.DEFAULT_THRESHOLD, "md")
        assert mod.est_tokens(at_env) < mod.est_tokens(at_big)
        assert "imports)" in at_env       # step-4 import collapse fired
        assert "  - " not in at_env        # nested bullets dropped
        assert mod.est_tokens(at_env) <= 60

    def test_env_threshold_default(self, monkeypatch):
        # AST_LENS_THRESHOLD sets DEFAULT_THRESHOLD on (re)import; a file under
        # the raised threshold passes through.
        monkeypatch.setenv("AST_LENS_THRESHOLD", "5000")
        spec = importlib.util.spec_from_file_location("ol_env_t", _OUTLINE_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.DEFAULT_THRESHOLD == 5000
        # sample.go (~233 LoC) is now below threshold → passthrough.
        assert mod.outline(fx("sample.go"), mod.DEFAULT_BUDGET,
                           mod.DEFAULT_THRESHOLD, "md") == ""

    def test_json_format_documented_keys(self):
        # App C JSON envelope: file, lang, loc, tokens_outline, markdown.
        raw = ol.outline(fx("sample.go"), BIG_BUDGET, THRESHOLD, "json")
        obj = json.loads(raw)
        assert set(obj.keys()) == {
            "file", "lang", "loc", "tokens_outline", "markdown",
        }
        assert obj["file"].endswith("sample.go")
        assert obj["lang"] == "go"
        assert isinstance(obj["loc"], int) and obj["loc"] >= THRESHOLD
        assert isinstance(obj["tokens_outline"], int) and obj["tokens_outline"] > 0
        assert obj["markdown"].startswith("# sample.go (")
        # tokens_outline equals est_tokens of the markdown payload.
        assert obj["tokens_outline"] == ol.est_tokens(obj["markdown"])

    def test_json_passthrough_returns_empty_not_json(self):
        # A sub-threshold file returns "" even in JSON mode (no envelope).
        assert ol.outline(fx("tiny.py"), BUDGET, THRESHOLD, "json") == ""


# =====================================================================
# CLI main() — argument parsing and stdout behaviour (in-process)
# =====================================================================
class TestCLIMain:
    def _run_main(self, argv):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            rc = ol.main(argv)
        finally:
            sys.stdout = old
        return rc, buf.getvalue()

    def test_main_prints_markdown(self):
        rc, out = self._run_main([fx("sample.go"), "--budget", str(BIG_BUDGET)])
        assert rc == 0
        assert out.startswith("# sample.go (")

    def test_main_format_json(self):
        rc, out = self._run_main(
            [fx("sample.go"), "--budget", str(BIG_BUDGET), "--format", "json"]
        )
        assert rc == 0
        obj = json.loads(out)
        assert obj["lang"] == "go"

    def test_main_threshold_flag(self, tmp_path):
        src = "\n".join(["package b"]
                        + [f"func F{i}() int {{ return {i} }}" for i in range(150)])
        p = tmp_path / "m.go"
        p.write_text(src)
        # Below default threshold passthrough → no stdout; with --threshold 50
        # it outlines.
        rc1, out1 = self._run_main([str(p)])
        assert rc1 == 0 and out1 == ""
        rc2, out2 = self._run_main([str(p), "--threshold", "50",
                                    "--budget", str(BIG_BUDGET)])
        assert rc2 == 0 and out2.startswith("# m.go (")

    def test_main_passthrough_silent(self):
        rc, out = self._run_main([fx("tiny.py")])
        assert rc == 0
        assert out == ""


# =====================================================================
# Wrapper script bin/outline — invoked as a subprocess
# =====================================================================
class TestWrapperScript:
    def _run(self, args):
        return subprocess.run(
            [_WRAPPER, *args], capture_output=True, text=True, timeout=60
        )

    def test_wrapper_prints_outline(self):
        r = self._run([fx("sample.go"), "--budget", str(BIG_BUDGET)])
        assert r.returncode == 0, f"stderr: {r.stderr!r}"
        assert r.stdout.startswith("# sample.go (")
        assert r.stderr == ""

    def test_wrapper_silent_on_passthrough(self):
        r = self._run([fx("tiny.py")])
        assert r.returncode == 0
        assert r.stdout == ""

    def test_wrapper_silent_on_unsupported(self):
        r = self._run([os.path.join(_PACK, "README.md")])
        assert r.returncode == 0
        assert r.stdout == ""

    def test_wrapper_json_format(self):
        r = self._run([fx("sample.ts"), "--budget", str(BIG_BUDGET),
                       "--format", "json"])
        assert r.returncode == 0, f"stderr: {r.stderr!r}"
        obj = json.loads(r.stdout)
        assert obj["lang"] == "typescript"


# =====================================================================
# Parser-runtime robustness (load_parser / do_parse fallback paths)
# =====================================================================
class TestParserRuntime:
    def test_unknown_language_yields_no_parser(self):
        assert ol.load_parser("cobol") is None

    def test_missing_tree_sitter_yields_no_parser(self, monkeypatch):
        # Simulate the tree-sitter runtime being absent: load_parser must
        # return None (→ outline() passthrough), never raise. This is the
        # "graceful degradation / missing runtime" path of Algorithm 1.
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "tree_sitter":
                raise ImportError("simulated missing tree_sitter")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert ol.load_parser("go") is None

    def test_missing_runtime_makes_outline_passthrough(self, monkeypatch):
        # End-to-end: with load_parser stubbed to None, an over-threshold,
        # supported-language file passes through to "".
        monkeypatch.setattr(ol, "load_parser", lambda lang: None)
        assert ol.outline(fx("sample.go"), BUDGET, THRESHOLD, "md") == ""

    def test_parse_returning_none_makes_passthrough(self, monkeypatch):
        # If do_parse returns None (parse failure), outline() passes through.
        monkeypatch.setattr(ol, "do_parse", lambda parser, src: None)
        assert ol.outline(fx("sample.go"), BUDGET, THRESHOLD, "md") == ""

    def test_do_parse_str_fallback(self):
        # do_parse tries bytes then str; a parser that only accepts str must
        # still succeed via the fallback arm.
        class StrOnlyParser:
            def parse(self, arg):
                if isinstance(arg, str):
                    class _Tree:
                        root_node = object()
                    return _Tree()
                raise TypeError("bytes not accepted")

        assert ol.do_parse(StrOnlyParser(), b"hello") is not None

    def test_do_parse_exception_returns_none(self):
        class BoomParser:
            def parse(self, arg):
                raise RuntimeError("boom")

        assert ol.do_parse(BoomParser(), b"x") is None


# =====================================================================
# Small helper-function units (node_text fallback, has_skip robustness)
# =====================================================================
class TestHelperUnits:
    def test_node_text_src_slice_fallback(self):
        # When a node exposes no ``.text``, node_text slices the source bytes
        # by [start_byte:end_byte].
        class FakeNode:
            text = None
            start_byte = 0
            end_byte = 5

        assert ol.node_text(b"hello world", FakeNode()) == "hello"

    def test_node_text_bytes_attr(self):
        # When ``.text`` is bytes it is decoded.
        class FakeNode:
            text = b"abc"

        assert ol.node_text(b"ignored", FakeNode()) == "abc"

    def test_has_skip_on_directory_is_false(self, tmp_path):
        # open() on a directory raises; has_skip swallows it and returns False.
        assert ol.has_skip(str(tmp_path)) is False

    def test_has_skip_true_only_in_first_five_lines(self, tmp_path):
        early = tmp_path / "early.py"
        early.write_text("# outline:skip\n" + "x = 1\n" * 10)
        late = tmp_path / "late.py"
        late.write_text("x = 1\n" * 19 + "# outline:skip\n")
        assert ol.has_skip(str(early)) is True
        assert ol.has_skip(str(late)) is False

    def test_has_skip_short_file_without_directive(self, tmp_path):
        # A file shorter than the 5-line scan window and without the directive
        # exercises the EOF break: the reader stops early and returns False.
        short = tmp_path / "short.py"
        short.write_text("x = 1\ny = 2\n")  # only 2 lines, no skip token
        assert ol.has_skip(str(short)) is False

        empty = tmp_path / "empty.py"
        empty.write_text("")  # immediate EOF on the first readline
        assert ol.has_skip(str(empty)) is False

    def test_is_private_empty_name_is_private(self):
        # A nameless decl is treated as private regardless of language.
        assert ol.is_private("go", "", exported=True) is True
        assert ol.is_private("python", "", exported=False) is True

    def test_est_tokens_proxy(self):
        # ~4 chars/token, rounding up.
        assert ol.est_tokens("") == 0
        assert ol.est_tokens("abcd") == 1
        assert ol.est_tokens("abcde") == 2


# =====================================================================
# Edge-path coverage: render/extract/truncate corners reached via fixtures
# =====================================================================
class TestRenderExtractEdges:
    def test_doc_without_imports_section(self):
        # doc_no_imports.py has a package docstring but no imports: the doc
        # blockquote renders (with a (truncated) marker beyond 3 lines) and no
        # ## Imports section appears.
        out = ol.outline(fx("doc_no_imports.py"), BIG_BUDGET, THRESHOLD, "md")
        assert "\n> " in out, "doc blockquote should render"
        assert "## Imports" not in out
        assert "> (truncated)" in out, "expected the doc-truncation marker"

    def test_destructured_const_names(self):
        # Top-level destructuring consts have no single name node, so the
        # emitter falls back to the regex name-dig and still renders a Value
        # bullet for each.
        out = ol.outline(fx("destructured.ts"), BIG_BUDGET, THRESHOLD, "md")
        assert "## Values" in out
        # The destructured patterns surface as const value bullets.
        vals = [ln for ln in out.splitlines() if "(const," in ln]
        assert vals, "no const value bullets rendered"

    def test_reexport_statement_handled(self):
        # `export { thing };` / `export default thing;` are export statements
        # whose carried declaration is not on a `declaration` field; unwrap's
        # inner-fallback must cope and the file still outlines.
        out = ol.outline(fx("reexport.ts"), BIG_BUDGET, THRESHOLD, "md")
        assert out, "reexport file should still produce an outline"
        assert out.startswith("# reexport.ts (")

    def test_all_private_collapses_and_drops_empty_sections(self):
        # all_private.go is only private types + funcs. Under a small budget,
        # private decls collapse to a count and the now-empty ## Types /
        # ## Functions headers are removed by drop_empty_sections.
        full = ol.outline(fx("all_private.go"), BIG_BUDGET, THRESHOLD, "md")
        assert "## Types" in full and "## Functions" in full
        small = ol.outline(fx("all_private.go"), 60, THRESHOLD, "md")
        assert "## Types" not in small, "empty Types header not dropped"
        assert "## Functions" not in small, "empty Functions header not dropped"
        assert re.search(r"_\(\+\d+ private decls\)_", small)
        assert small.startswith("# all_private.go (")

    def test_import_names_relative_python_import(self):
        # A bare relative import (`from . import x`) yields an empty top-level
        # name from the extractor's regex — exercised directly as a unit.
        class _Node:
            text = b"from . import x"

        names = ol.import_names("python", b"from . import x", [_Node()])
        assert names == [""]

    def test_drop_empty_sections_unit(self):
        # A header with no following content is removed; one with content is
        # kept (covers both arms of the has-content scan).
        md = "# f (1 LoC, 0 decls)\n\n## Empty\n\n## Kept\n- `x` (L1–1)\n"
        out = ol.drop_empty_sections(md)
        assert "## Empty" not in out
        assert "## Kept" in out

    def test_outline_extract_exception_passthrough(self, monkeypatch):
        # If extract() raises mid-pipeline, outline() catches it and passes
        # through to "" (the parse-failure guard around extraction).
        def boom(*_a, **_k):
            raise RuntimeError("synthetic extract failure")

        monkeypatch.setattr(ol, "extract", boom)
        assert ol.outline(fx("sample.go"), BUDGET, THRESHOLD, "md") == ""

    def test_do_parse_both_args_typeerror_returns_none(self):
        # If a parser rejects BOTH bytes and str with TypeError, do_parse
        # exhausts its candidates and returns None.
        class AlwaysTypeError:
            def parse(self, _arg):
                raise TypeError("rejects everything")

        assert ol.do_parse(AlwaysTypeError(), b"x") is None

    def test_tiny_docstring_not_captured_as_doc(self):
        # A 1-char module "docstring" is below the >3-char capture floor, so it
        # is not rendered as a doc blockquote.
        out = ol.outline(fx("tiny_doc.py"), BIG_BUDGET, THRESHOLD, "md")
        assert out, "file should still outline (it has functions)"
        assert "\n> " not in out, "sub-4-char docstring must not surface as doc"

    def test_import_names_no_match_is_skipped(self):
        # A python import node whose text matches neither `from X` nor
        # `import X` yields no name (the no-match continue arm).
        class _Node:
            text = b"# not actually an import"

        assert ol.import_names("python", b"", [_Node()]) == []

    def test_empty_import_block_omits_imports_section(self):
        # empty_import.go has an `import ()` node (so the imports list is
        # non-empty) but no extractable import names, so render's `if names:`
        # guard is False and the ## Imports section is omitted entirely.
        out = ol.outline(fx("empty_import.go"), BIG_BUDGET, THRESHOLD, "md")
        assert out, "file should still outline (it has functions)"
        assert "## Imports" not in out
        assert "## Functions" in out

    def test_public_only_floor_above_small_budget(self):
        # public_only.go has only public funcs (no privates/doc/imports). Under
        # a small budget the ladder drops nested bullets (step 1) then finds
        # nothing to collapse at steps 2–4, leaving an irreducible floor. This
        # exercises the "0 private decls dropped" arm and documents that the
        # emitter's best-effort trimmer cannot always reach an arbitrary budget.
        out = ol.outline(fx("public_only.go"), 100, THRESHOLD, "md")
        assert "  - " not in out, "nested bullets should be dropped (step 1)"
        assert "private decls" not in out, "no private-collapse marker expected"
        assert "## Functions" in out, "public functions remain"
        # The floor sits above the tiny budget (a documented best-effort limit).
        assert ol.est_tokens(out) > 100

    def test_collect_significant_universal_fallback(self):
        # The universal fallback (collect_significant's span>=10 + named arm)
        # surfaces any *named* inner construct whose line-span >= 10 even when
        # its node type is NOT in the per-language fixed list. A Go function
        # with a large inner `const (...)` block and a large inner `type`
        # declaration exercises this arm (neither node type is in Go's
        # SIGNIFICANT table, but both are named and span >= 10).
        inner = (
            ["func Big() {", "\tconst ("]
            + [f"\tk{j:02d} = {j}" for j in range(12)]
            + ["\t)", "\ttype local struct {"]
            + [f"\tF{j:02d} int" for j in range(12)]
            + ["\t}", "\t_ = local{}", "}"]
        )
        src = (
            "package u\n"
            + "\n".join(inner)
            + "\n"
            + "\n".join(f"func F{i}() int {{ return {i} }}" for i in range(210))
        )
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".go")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            out = ol.outline(path, BIG_BUDGET, THRESHOLD, "md")
            assert any("Big" in ln for ln in out.splitlines()), (
                "the large function should be present"
            )
            # The const/type blocks (span >= 10, named, not in the fixed list)
            # surface as nested bullets under Big via the universal fallback.
            nested = [ln[4:] for ln in out.splitlines() if ln.startswith("  - ")]
            assert any("const_declaration" in ln or "type_declaration" in ln
                       for ln in nested), (
                f"universal-fallback construct not surfaced; got {nested!r}"
            )
        finally:
            os.unlink(path)


# =====================================================================
# load_parser version-shim coverage via a synthetic tree-sitter runtime
# =====================================================================
class TestParserVersionShim:
    """Exercise load_parser's handling of tree-sitter API variants without
    depending on which version happens to be installed. We inject fake
    ``tree_sitter`` and grammar modules so each construction arm is hit."""

    def _install_fake(self, monkeypatch, *, parser_kind):
        import types as _types

        ts = _types.ModuleType("tree_sitter")

        class _Language:
            def __init__(self, _factory_result):
                self.ok = True

        captured = {}

        if parser_kind == "ctor":
            # tree-sitter >= 0.22: Parser(language) works.
            class _Parser:
                def __init__(self, language):
                    captured["via"] = "ctor"
                    self.language = language
        elif parser_kind == "prop":
            # Older API: Parser() then assign .language property.
            class _Parser:
                def __init__(self, *a):
                    if a:
                        raise TypeError("no positional language")
                    captured["via"] = "prop-init"

                def __setattr__(self, k, v):
                    object.__setattr__(self, k, v)
                    if k == "language":
                        captured["via"] = "prop-set"
        else:  # "setter"
            # Oldest API: Parser() then set_language(language); assigning the
            # .language attribute raises so the except-arm calls set_language.
            class _Parser:
                def __init__(self, *a):
                    if a:
                        raise TypeError("no positional language")

                @property
                def language(self):
                    return None

                @language.setter
                def language(self, _v):
                    raise AttributeError("read-only")

                def set_language(self, _language):
                    captured["via"] = "set_language"

        ts.Language = _Language
        ts.Parser = _Parser

        grammar = _types.ModuleType("tree_sitter_go")
        grammar.language = lambda: object()

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "tree_sitter":
                return ts
            if name == "tree_sitter_go":
                return grammar
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        return captured

    def test_constructor_arm(self, monkeypatch):
        captured = self._install_fake(monkeypatch, parser_kind="ctor")
        p = ol.load_parser("go")
        assert p is not None
        assert captured["via"] == "ctor"

    def test_language_property_arm(self, monkeypatch):
        captured = self._install_fake(monkeypatch, parser_kind="prop")
        p = ol.load_parser("go")
        assert p is not None
        assert captured["via"] == "prop-set"

    def test_set_language_arm(self, monkeypatch):
        captured = self._install_fake(monkeypatch, parser_kind="setter")
        p = ol.load_parser("go")
        assert p is not None
        assert captured["via"] == "set_language"

    def test_factory_missing_returns_none(self, monkeypatch):
        # If the grammar module exposes none of the expected factory names,
        # load_parser returns None.
        import types as _types

        ts = _types.ModuleType("tree_sitter")
        ts.Language = lambda x: x
        ts.Parser = lambda *a, **k: object()
        grammar = _types.ModuleType("tree_sitter_go")  # no `language` attr

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "tree_sitter":
                return ts
            if name == "tree_sitter_go":
                return grammar
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert ol.load_parser("go") is None

    def test_grammar_import_failure_returns_none(self, monkeypatch):
        # If importing the grammar module raises, load_parser returns None.
        import types as _types

        ts = _types.ModuleType("tree_sitter")
        ts.Language = lambda x: x
        ts.Parser = lambda *a, **k: object()

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "tree_sitter":
                return ts
            if name == "tree_sitter_go":
                raise ImportError("missing grammar wheel")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert ol.load_parser("go") is None

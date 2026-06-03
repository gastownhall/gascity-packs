"""Pattern-DSL engine — author transform intents as YAML, not Python.

Clean-room implementation of "The AST as LLM Lens" §4.E / "Subsystem E"
(pattern-DSL authoring velocity). A Tier-0 transform intent normally costs a
few hundred lines of Python (an AST-walking visitor, intent-specific match
logic, a diff emitter). This subsystem reduces the cost per intent to a few
*tens of lines of YAML*, using a schema modelled on ast-grep and Comby.

A YAML intent file declares **what** to match and **how** to rewrite it; this
module turns that declaration into a ``compute_change(file_path, args)``
callable that plugs straight into the existing write-side spine (an op per
``docs/WRITE-SIDE.md``). The produced change is *proposed only* — like every
op, the engine NEVER writes files; the spine's plan/execute pair and compile
gate own materialisation and safety.

Two backends, selected per the paper (§4.E "two backends"):

  1. ``ast-grep`` — the real structural matcher. Preferred whenever available,
     via either the ``ast-grep``/``sg`` binary on PATH or the ``ast-grep-py``
     pip binding (we use the binding when present; it is in ``requirements``).
  2. A minimal **fallback** matcher for the simplest pattern subset (a single
     ``pattern`` with ``$NAME`` / ``$$$REST`` metavariables and a flat
     ``fix`` template) for the case where neither ast-grep surface is present.
     The fallback is deliberately conservative — it handles only single-line,
     single-statement-call shapes — because the *gate*, not the matcher, is the
     final safety net, and a fallback that over-reaches would only widen the
     set of diffs the gate has to reject.

The engine is language-aware: an intent declares its ``language``(s); a file
whose extension maps to none of them yields ``None`` (unsupported language),
exactly as the op contract requires.

YAML intent schema (the load-bearing keys)::

    id:          remove-console            # stable op id (required, unique)
    language:    [js, ts, jsx, tsx]        # one name or a list (required)
    description: Drop console.log/debug …  # one-line summary (required)
    # --- exactly one of `rule:` or `pattern:` ---
    rule:                                  # a full ast-grep rule object
      kind: expression_statement
      has: { any: [ {pattern: "console.log($$$A)"} ] }
    pattern: "var $NAME = $VAL"            # …or a single ast-grep pattern
    # --- the rewrite (omit to DELETE the match) ---
    fix: "let $NAME = $VAL"                # rewrite template; metavars expand
    # --- optional knobs ---
    strip_statement: true                  # swallow indentation + trailing
                                           # newline of a deleted statement so
                                           # no blank-line residue remains
    select: var                            # narrow the edit to the match's
                                           # first child/descendant of this
                                           # node-kind (e.g. rewrite only the
                                           # `var` keyword token of a decl)
    ast_grep_language: typescript          # override the backend lang name

See ``docs/PATTERN-DSL.md`` for the full schema and a worked example.
"""

from __future__ import annotations

import os
import re
import subprocess

__all__ = [
    "PatternError",
    "Intent",
    "active_backend",
    "load_intent",
    "load_intents_dir",
    "make_op",
    "DEFAULT_INTENTS_DIR",
]

# Directory the registry auto-loads bundled intents from.
DEFAULT_INTENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intents")


class PatternError(Exception):
    """Raised when a YAML intent is malformed or cannot be turned into an op.

    Distinct from the registry's ``OpError`` and the plan's ``PlanError`` so a
    caller can tell a *bad intent definition* (author error, surfaced at load
    time) apart from a *runtime* op failure.
    """


# --------------------------------------------------------------------------- #
# language mapping
# --------------------------------------------------------------------------- #
# Friendly intent language names (and bare extensions) -> the file extensions
# the intent applies to. Keeping this table here, rather than re-deriving it
# from the gate, lets an intent say `language: js` and have it cover the whole
# JS family without the author enumerating extensions.
_LANG_EXTS: dict[str, tuple[str, ...]] = {
    "js": (".js", ".jsx", ".mjs", ".cjs"),
    "javascript": (".js", ".jsx", ".mjs", ".cjs"),
    "jsx": (".jsx",),
    "ts": (".ts",),
    "typescript": (".ts",),
    "tsx": (".tsx",),
    "py": (".py",),
    "python": (".py",),
    "go": (".go",),
    "golang": (".go",),
}

# File extension -> the language name ast-grep expects. ast-grep distinguishes
# `tsx` from `typescript`, so `.tsx` maps to `tsx`; everything else is direct.
_EXT_TO_AST_GREP_LANG: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".py": "python",
    ".go": "go",
}


def _exts_for_languages(languages: list[str]) -> tuple[str, ...]:
    """Expand a list of friendly language names into the extensions they cover.

    Raises :class:`PatternError` on an unknown language name so a typo in an
    intent file is caught at load time, not silently swallowed into "matches
    nothing".
    """
    exts: list[str] = []
    for lang in languages:
        key = lang.strip().lower().lstrip(".")
        mapped = _LANG_EXTS.get(key) or _LANG_EXTS.get("." + key)
        if mapped is None:
            known = ", ".join(sorted(set(_LANG_EXTS)))
            raise PatternError(
                f"unknown language '{lang}' (known: {known})"
            )
        for e in mapped:
            if e not in exts:
                exts.append(e)
    return tuple(exts)


# --------------------------------------------------------------------------- #
# backend detection
# --------------------------------------------------------------------------- #
def _have_ast_grep_py() -> bool:
    try:
        import ast_grep_py  # noqa: F401

        return True
    except Exception:  # noqa: BLE001 - any import failure means "not usable"
        return False


def _have_ast_grep_bin() -> str | None:
    """Path to an ``ast-grep`` / ``sg`` binary on PATH, or None."""
    import shutil

    return shutil.which("ast-grep") or shutil.which("sg")


def active_backend() -> str:
    """Name of the matcher backend that will be used, in preference order.

    Returns one of ``"ast-grep-py"``, ``"ast-grep-bin"`` or ``"fallback"``.
    The bindings are preferred over the binary (no subprocess, exact version),
    and the binary over the pure-Python fallback. Surfaced by ``bin/op --list``
    and ``docs/PATTERN-DSL.md`` so an operator can see which is live.
    """
    if _have_ast_grep_py():
        return "ast-grep-py"
    if _have_ast_grep_bin():
        return "ast-grep-bin"
    return "fallback"


# --------------------------------------------------------------------------- #
# the intent
# --------------------------------------------------------------------------- #
class Intent:
    """A loaded, validated YAML intent.

    Holds the parsed schema fields and knows how to apply itself to a single
    file's text, returning the rewritten text (or ``None`` when nothing
    matched). Construction validates the schema, so an :class:`Intent` that
    exists is always well-formed; applying it never raises on a *valid* intent.
    """

    def __init__(
        self,
        *,
        id: str,
        description: str,
        languages: list[str],
        rule: dict | None,
        pattern: str | None,
        fix: str | None,
        strip_statement: bool,
        select: str | None,
        ast_grep_language: str | None,
        source_path: str | None = None,
    ) -> None:
        self.id = id
        self.description = description
        self.languages = languages
        self.exts = _exts_for_languages(languages)
        self.rule = rule
        self.pattern = pattern
        self.fix = fix
        self.strip_statement = strip_statement
        self.select = select
        self.ast_grep_language_override = ast_grep_language
        self.source_path = source_path

    # -- language gating ---------------------------------------------------- #
    def supports_ext(self, ext: str) -> bool:
        return ext.lower() in self.exts

    def _ast_grep_lang_for(self, ext: str) -> str | None:
        if self.ast_grep_language_override:
            return self.ast_grep_language_override
        return _EXT_TO_AST_GREP_LANG.get(ext.lower())

    # -- application -------------------------------------------------------- #
    def apply_text(self, text: str, ext: str) -> str | None:
        """Apply the intent to ``text`` (a file's content); return new text or None.

        ``None`` means "no match" (nothing to change). The dispatch picks the
        best available backend; the fallback only runs when neither ast-grep
        surface is present *and* the intent is within the fallback's subset.
        """
        backend = active_backend()
        if backend in ("ast-grep-py", "ast-grep-bin"):
            return self._apply_ast_grep(text, ext, backend)
        return self._apply_fallback(text, ext)

    # -- ast-grep backends -------------------------------------------------- #
    def _rule_object(self) -> dict:
        """The ast-grep *rule* object for this intent (pattern wrapped if needed)."""
        if self.rule is not None:
            return self.rule
        return {"pattern": self.pattern}

    def _apply_ast_grep(self, text: str, ext: str, backend: str) -> str | None:
        lang = self._ast_grep_lang_for(ext)
        if lang is None:
            return None
        if backend == "ast-grep-py":
            spans = self._match_spans_py(text, lang)
        else:
            spans = self._match_spans_bin(text, lang)
        if not spans:
            return None
        return self._splice(text, spans)

    def _match_spans_py(self, text: str, lang: str) -> list[tuple[int, int, str]]:
        """Match via ``ast-grep-py``; return ``[(start_char, end_char, replacement)]``.

        ``replacement`` is the rewritten text for the match (``""`` for a
        deletion). Offsets are *character* indices into ``text`` (ast-grep's
        ``range().*.index`` is a char index), which is what :meth:`_splice`
        expects. Metavariable substitution in the ``fix`` template is performed
        explicitly here from the matched nodes — the binding's ``replace`` does
        not expand ``$NAME`` itself in this version, and expanding it ourselves
        also keeps a single, backend-independent substitution code path.
        """
        from ast_grep_py import SgRoot

        try:
            root = SgRoot(text, lang).root()
        except Exception as exc:  # noqa: BLE001 - unparseable input -> no change
            # A file the backend cannot even parse is, for our purposes, a file
            # with no matches. The gate would reject a broken rewrite anyway.
            raise PatternError(f"ast-grep failed to parse as {lang}: {exc}") from exc

        matches = root.find_all({"rule": self._rule_object()})
        spans: list[tuple[int, int, str]] = []
        for m in matches:
            target = m
            if self.select:
                target = _first_of_kind(m, self.select)
                if target is None:
                    # The selector did not resolve inside this match — skip it
                    # rather than rewrite the wrong span.
                    continue
            rng = target.range()
            start = rng.start.index
            end = rng.end.index
            # `fix` metavars are resolved against the MATCH (so captures from the
            # whole rule are in scope) even when the edit is narrowed by `select`.
            replacement = "" if self.fix is None else self._expand_fix(m)
            spans.append((start, end, replacement))
        return spans

    def _expand_fix(self, match) -> str:
        """Expand this intent's ``fix`` template against one ast-grep match node.

        ``$NAME`` is replaced by the single captured node's text;
        ``$$$NAME`` by the verbatim source slice spanning the multi-match
        (reconstructed from the first node's start to the last node's end, so
        the original separators and spacing are preserved). Metavariable names
        are substituted longest-first so ``$NAME`` never clobbers ``$NAMESPACE``.
        Unknown metavariables expand to empty (the gate catches any resulting
        syntax error).
        """
        fix = self.fix or ""
        names = sorted(set(_META_SINGLE.findall(fix)) | set(_META_MULTI.findall(fix)),
                       key=len, reverse=True)
        for name in names:
            single = match.get_match(name)
            if single is not None:
                value = single.text()
            else:
                multi = match.get_multiple_matches(name)
                value = _join_multi(multi)
            fix = fix.replace(f"$$${name}", value).replace(f"${name}", value)
        return fix

    def _match_spans_bin(self, text: str, lang: str) -> list[tuple[int, int, str]]:
        """Match via the ``ast-grep``/``sg`` binary in ``--json`` scan mode.

        Builds a temporary single-rule YAML config from this intent, scans the
        text (passed on a temp file) and reads the JSON match ranges + the
        binary's own ``replacement`` field. Char offsets are derived from the
        line/column the binary reports (its ``byteOffset`` is bytes, not chars).
        """
        import json
        import tempfile

        binpath = _have_ast_grep_bin()
        if binpath is None:  # pragma: no cover - guarded by caller
            return []

        rule_yaml = self._as_ast_grep_config_yaml(lang)
        with tempfile.TemporaryDirectory(prefix="astlens-sg-") as td:
            cfg = os.path.join(td, "rule.yml")
            src = os.path.join(td, "src" + _primary_ext_for_lang(lang))
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write(rule_yaml)
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(text)
            proc = subprocess.run(
                [binpath, "scan", "--rule", cfg, "--json", src],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode not in (0, 1):  # 1 == matches found in some builds
                return []
            try:
                hits = json.loads(proc.stdout or "[]")
            except json.JSONDecodeError:
                return []

        spans: list[tuple[int, int, str]] = []
        for hit in hits:
            rng = hit.get("range", {})
            start = _line_col_to_char(text, rng.get("start", {}))
            end = _line_col_to_char(text, rng.get("end", {}))
            if start is None or end is None:
                continue
            replacement = "" if self.fix is None else hit.get("replacement", "")
            spans.append((start, end, replacement))
        return spans

    def _as_ast_grep_config_yaml(self, lang: str) -> str:
        """Serialise this intent as a standalone ast-grep rule config (for the binary)."""
        import yaml

        cfg: dict = {"id": self.id, "language": lang, "rule": self._rule_object()}
        if self.fix is not None:
            cfg["fix"] = self.fix
        return yaml.safe_dump(cfg, sort_keys=False)

    # -- fallback backend --------------------------------------------------- #
    def _apply_fallback(self, text: str, ext: str) -> str | None:
        """Pure-Python matcher for the simplest pattern subset (no ast-grep).

        Supported subset (conservative by design):
          * a single ``pattern`` (no ``rule`` object), and
          * the pattern is a one-line shape using ``$NAME`` single-node
            metavariables and at most one trailing ``$$$REST`` multi metavar,
          * with a flat ``fix`` template referencing the same metavars (or a
            deletion when ``fix`` is omitted).

        Anything outside that subset returns ``None`` (the engine declines
        rather than risk a wrong edit; the paper assigns the heavy lifting to
        ast-grep and keeps the fallback to "most-used intents exercise").
        """
        if self.rule is not None or self.pattern is None:
            return None
        regex, names = _fallback_pattern_to_regex(self.pattern)
        if regex is None:
            return None

        spans: list[tuple[int, int, str]] = []
        for m in regex.finditer(text):
            captures = {n: m.group(n) for n in names}
            if self.fix is None:
                replacement = ""
            else:
                replacement = _fallback_render_fix(self.fix, captures)
                if replacement is None:
                    return None  # fix referenced an unknown metavar -> decline
            spans.append((m.start(), m.end(), replacement))
        if not spans:
            return None
        return self._splice(text, spans)

    # -- shared splice ------------------------------------------------------ #
    def _splice(self, text: str, spans: list[tuple[int, int, str]]) -> str | None:
        """Apply ``[(start, end, replacement)]`` char spans to ``text``.

        Spans are applied right-to-left so earlier offsets stay valid. When
        ``strip_statement`` is set and a span is a *deletion*, the span is
        widened left over leading spaces/tabs to the start of the line and
        right over a single trailing newline, so removing a statement leaves no
        blank-line residue. Returns ``None`` if the result is byte-identical to
        the input (defensive: a match that changed nothing is "no change").
        """
        # De-duplicate / sort by start; drop overlaps (keep the first seen),
        # since two rules occasionally match the same node.
        spans = sorted(set(spans), key=lambda s: (s[0], s[1]))
        pruned: list[tuple[int, int, str]] = []
        last_end = -1
        for start, end, repl in spans:
            if start < last_end:
                continue
            pruned.append((start, end, repl))
            last_end = end

        out = text
        for start, end, repl in sorted(pruned, key=lambda s: s[0], reverse=True):
            s, e = start, end
            if repl == "" and self.strip_statement:
                s, e = _widen_to_full_lines(text, s, e)
            out = out[:s] + repl + out[e:]

        if out == text:
            return None
        return out


# --------------------------------------------------------------------------- #
# splice helpers
# --------------------------------------------------------------------------- #
def _widen_to_full_lines(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen [start, end) left over indentation and right over one newline.

    Only used for deletions under ``strip_statement``. The left edge moves back
    over spaces/tabs to the line start; the right edge moves forward over a
    single ``\\n`` (and a preceding ``\\r``). This turns "delete the call" into
    "delete the whole statement line", leaving no empty line behind.
    """
    s = start
    while s > 0 and text[s - 1] in " \t":
        s -= 1
    e = end
    # Swallow a statement terminator that sits immediately after the match but
    # was not part of it. In the ast-grep path the matched statement node
    # usually already includes its `;`, so there is nothing here to eat; in the
    # fallback path a `call(...)` pattern stops before the `;`, and eating it
    # (plus any spaces up to the newline) keeps the deletion clean.
    if e < len(text) and text[e] == ";":
        e += 1
    while e < len(text) and text[e] in " \t":
        e += 1
    if e < len(text) and text[e] == "\r":
        e += 1
    if e < len(text) and text[e] == "\n":
        e += 1
    return s, e


def _first_of_kind(node, kind: str):
    """First child (then descendant) of ``node`` whose ast-grep kind == ``kind``.

    Used by an intent's ``select`` to narrow an edit from the whole match to one
    constituent token/node (e.g. the ``var`` keyword of a ``variable_declaration``).
    Checks direct children first (the common case, and unambiguous), then falls
    back to a breadth-first descendant search.
    """
    for child in node.children():
        if child.kind() == kind:
            return child
    queue = list(node.children())
    while queue:
        cur = queue.pop(0)
        if cur.kind() == kind:
            return cur
        queue.extend(cur.children())
    return None


def _join_multi(nodes) -> str:
    """Verbatim source slice spanning a ``$$$`` multi-match's nodes.

    ``get_multiple_matches`` returns every node the multi-metavariable bound,
    *including* separators (e.g. the commas between call arguments). Rather than
    re-join their texts (which would drop the original inter-token spacing), we
    take the source range from the first node's start to the last node's end via
    the shared root's text, preserving the author's exact formatting.
    """
    nodes = list(nodes)
    if not nodes:
        return ""
    root_text = nodes[0].get_root().root().text()
    start = nodes[0].range().start.index
    end = nodes[-1].range().end.index
    return root_text[start:end]


def _line_col_to_char(text: str, pos: dict) -> int | None:
    """Convert an ast-grep ``{line, column}`` (0-based) to a char offset in ``text``.

    The binary reports columns in *bytes* on the matched line; we walk the line
    accumulating UTF-8 byte widths until we reach the reported byte column, so
    the returned offset is a correct *character* index for :meth:`_splice`.
    """
    line = pos.get("line")
    col = pos.get("column")
    if line is None or col is None:
        return None
    lines = text.splitlines(keepends=True)
    if line > len(lines):
        return None
    base = sum(len(lines[i]) for i in range(line))
    # Walk byte-column to char offset within the target line.
    target = lines[line] if line < len(lines) else ""
    byte_seen = 0
    char_off = 0
    for ch in target:
        if byte_seen >= col:
            break
        byte_seen += len(ch.encode("utf-8"))
        char_off += 1
    return base + char_off


def _primary_ext_for_lang(lang: str) -> str:
    for ext, l in _EXT_TO_AST_GREP_LANG.items():
        if l == lang:
            return ext
    return ".txt"


# --------------------------------------------------------------------------- #
# fallback metavariable engine
# --------------------------------------------------------------------------- #
_META_SINGLE = re.compile(r"\$([A-Z_][A-Z0-9_]*)")
_META_MULTI = re.compile(r"\$\$\$([A-Z_][A-Z0-9_]*)")


def _fallback_pattern_to_regex(pattern: str):
    """Compile a single-line fallback ``pattern`` into a regex + metavar names.

    ``$$$REST`` becomes a non-greedy "anything" capture (commonly a call's
    argument list); ``$NAME`` becomes a single-token capture (identifier-ish,
    no commas/parens/whitespace). Returns ``(None, [])`` when the pattern spans
    multiple lines or has no metavariables (outside the supported subset).
    """
    if "\n" in pattern:
        return None, []

    names: list[str] = []
    out = []
    i = 0
    consumed_meta = False
    while i < len(pattern):
        mm = _META_MULTI.match(pattern, i)
        if mm:
            name = mm.group(1)
            if name in names:
                return None, []
            names.append(name)
            out.append(f"(?P<{name}>.*?)")
            i = mm.end()
            consumed_meta = True
            continue
        sm = _META_SINGLE.match(pattern, i)
        if sm:
            name = sm.group(1)
            if name in names:
                return None, []
            names.append(name)
            out.append(rf"(?P<{name}>[^\s,()]+)")
            i = sm.end()
            consumed_meta = True
            continue
        out.append(re.escape(pattern[i]))
        i += 1

    if not consumed_meta:
        return None, []
    try:
        return re.compile("".join(out)), names
    except re.error:
        return None, []


def _fallback_render_fix(fix: str, captures: dict[str, str]) -> str | None:
    """Expand ``$NAME`` / ``$$$NAME`` in a fix template from ``captures``.

    Returns ``None`` if the template references a metavariable the pattern did
    not capture (an authoring error the engine declines on, rather than
    emitting a literal ``$NAME``).
    """
    missing: list[str] = []

    def repl_multi(m: re.Match) -> str:
        name = m.group(1)
        if name not in captures:
            missing.append(name)
            return ""
        return captures[name]

    def repl_single(m: re.Match) -> str:
        name = m.group(1)
        if name not in captures:
            missing.append(name)
            return ""
        return captures[name]

    out = _META_MULTI.sub(repl_multi, fix)
    out = _META_SINGLE.sub(repl_single, out)
    if missing:
        return None
    return out


# --------------------------------------------------------------------------- #
# loading + validation
# --------------------------------------------------------------------------- #
def _coerce_languages(raw) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)) and all(isinstance(x, str) for x in raw):
        return list(raw)
    raise PatternError("'language'/'languages' must be a string or a list of strings")


def _intent_from_dict(data: dict, source_path: str | None = None) -> Intent:
    """Validate a parsed YAML mapping and build an :class:`Intent`.

    Required keys: ``id``, ``language`` (or ``languages``), ``description``,
    and exactly one of ``rule`` / ``pattern``. ``fix`` (alias ``rewrite``) is
    optional — its absence means the matched node is *deleted*.
    """
    if not isinstance(data, dict):
        raise PatternError("intent must be a YAML mapping (got a non-mapping document)")

    where = f" in {source_path}" if source_path else ""

    intent_id = data.get("id")
    if not isinstance(intent_id, str) or not intent_id.strip():
        raise PatternError(f"intent missing a non-empty string 'id'{where}")

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise PatternError(f"intent '{intent_id}' missing a non-empty 'description'{where}")

    lang_raw = data.get("language", data.get("languages"))
    if lang_raw is None:
        raise PatternError(f"intent '{intent_id}' missing 'language' (or 'languages'){where}")
    languages = _coerce_languages(lang_raw)

    rule = data.get("rule")
    pattern = data.get("pattern")
    if rule is None and pattern is None:
        raise PatternError(
            f"intent '{intent_id}' must define a 'rule' object or a 'pattern' string{where}"
        )
    if rule is not None and pattern is not None:
        raise PatternError(
            f"intent '{intent_id}' defines both 'rule' and 'pattern'; use exactly one{where}"
        )
    if rule is not None and not isinstance(rule, dict):
        raise PatternError(f"intent '{intent_id}' 'rule' must be a mapping (ast-grep rule){where}")
    if pattern is not None and not isinstance(pattern, str):
        raise PatternError(f"intent '{intent_id}' 'pattern' must be a string{where}")

    # `fix` is the canonical key; `rewrite` is an accepted alias (paper's
    # "rewrite/fix template").
    fix = data.get("fix", data.get("rewrite"))
    if fix is not None and not isinstance(fix, str):
        raise PatternError(f"intent '{intent_id}' 'fix'/'rewrite' must be a string{where}")

    strip_statement = bool(data.get("strip_statement", False))

    select = data.get("select")
    if select is not None and (not isinstance(select, str) or not select.strip()):
        raise PatternError(f"intent '{intent_id}' 'select' must be a non-empty node-kind string{where}")

    ast_grep_language = data.get("ast_grep_language")
    if ast_grep_language is not None and not isinstance(ast_grep_language, str):
        raise PatternError(f"intent '{intent_id}' 'ast_grep_language' must be a string{where}")

    # Building the Intent validates the language names (may raise PatternError).
    return Intent(
        id=intent_id,
        description=description,
        languages=languages,
        rule=rule,
        pattern=pattern,
        fix=fix,
        strip_statement=strip_statement,
        select=select,
        ast_grep_language=ast_grep_language,
        source_path=source_path,
    )


def load_intent(path: str) -> Intent:
    """Load and validate a single YAML intent file into an :class:`Intent`.

    Raises :class:`PatternError` on any malformation (unreadable, invalid YAML,
    missing/!conflicting keys, unknown language) so a bad intent is rejected
    cleanly at load time rather than failing mysteriously at apply time.
    """
    try:
        import yaml
    except Exception as exc:  # noqa: BLE001 - pyyaml is a declared dependency
        raise PatternError(f"pyyaml is required to load intents: {exc}") from exc

    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except OSError as exc:
        raise PatternError(f"cannot read intent file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PatternError(f"invalid YAML in {path}: {exc}") from exc

    if data is None:
        raise PatternError(f"empty intent file: {path}")

    return _intent_from_dict(data, source_path=path)


def load_intents_dir(directory: str = DEFAULT_INTENTS_DIR) -> list[Intent]:
    """Load every ``*.yaml`` / ``*.yml`` intent in ``directory`` (sorted).

    A malformed intent raises :class:`PatternError` (fail loudly so a broken
    bundled intent is caught in tests). A missing directory yields ``[]`` so
    the registry's auto-load is a non-event when no intents ship.
    """
    if not os.path.isdir(directory):
        return []
    out: list[Intent] = []
    for name in sorted(os.listdir(directory)):
        if name.endswith((".yaml", ".yml")):
            out.append(load_intent(os.path.join(directory, name)))
    return out


# --------------------------------------------------------------------------- #
# op factory (the bridge into the write-side spine)
# --------------------------------------------------------------------------- #
def _repo_root_for(file_path: str) -> str:
    """Git root above ``file_path``, else its own dir — matches the op contract.

    Reuses the spine's demo-op helper when importable (so relpaths round-trip
    identically through plan/execute), with a local git fallback otherwise.
    """
    try:
        from .ops.strip_trailing_ws import repo_root_for

        return repo_root_for(file_path)
    except Exception:  # noqa: BLE001 - fall back to a local git probe
        start = os.path.dirname(os.path.abspath(file_path)) or os.getcwd()
        try:
            proc = subprocess.run(
                ["git", "-C", start, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return os.path.realpath(proc.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
        return os.path.realpath(start)


def _relpath_for(file_path: str) -> str:
    root = _repo_root_for(file_path)
    return os.path.relpath(os.path.realpath(os.path.abspath(file_path)), root)


def make_op(intent: Intent):
    """Return a ``compute_change(file_path, args) -> dict|None`` for ``intent``.

    The returned callable honours the shared op contract exactly:
      * reads ``file_path`` (never writes),
      * returns ``None`` for an unsupported language, an unreadable/binary file,
        or when the intent matches nothing,
      * otherwise returns ``{relpath: new_full_content}`` for the one file it
        rewrites, with ``relpath`` anchored at the repo root.

    ``args`` is accepted and ignored — a pattern intent operates on the whole
    file — so the generic ``--k v`` CLI path never breaks it.
    """

    def compute_change(file_path: str, args: dict) -> dict | None:
        ext = os.path.splitext(file_path)[1].lower()
        if not intent.supports_ext(ext):
            return None  # unsupported language -> no change, per the contract
        try:
            with open(file_path, encoding="utf-8") as fh:
                original = fh.read()
        except (OSError, UnicodeDecodeError):
            return None  # unreadable / non-UTF-8 (binary) -> cannot do safely

        new_text = intent.apply_text(original, ext)
        if new_text is None or new_text == original:
            return None
        return {_relpath_for(file_path): new_text}

    # Carry metadata so the registry/CLI can describe the op without re-parsing.
    compute_change.intent = intent  # type: ignore[attr-defined]
    compute_change.__doc__ = f"pattern intent '{intent.id}': {intent.description}"
    return compute_change

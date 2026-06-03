#!/usr/bin/env python3
"""
ast-lens — outline emitter.

A clean-room implementation of "outline-first reading" from the Blackrim AST
paper (§5 algorithm, App B significance, App C schema, App D sanitisation).
Emits a compact Markdown structural summary of a source file so an LLM agent
can navigate by structure instead of paying the full-file read tax.

Design commitments (from the paper):
  * Pure function, read-only, stateless (re-parses each call).            §4.2
  * Polyglot via one substrate (tree-sitter), one schema, graceful
    fallback-to-passthrough (empty output) on parse error / missing
    runtime / sub-threshold file.                                         Alg 1
  * Normative truncation precedence to a token budget.                    §5.3
  * Sanitisation of verbatim content fed into the agent's context.        §5.4

This is a from-spec implementation; it deliberately does NOT try to match the
reference `gt outline` byte-for-byte.
"""
from __future__ import annotations
import sys, os, re, json, argparse

# ---- Defaults (paper App F; overridable via flags/env) --------------------
DEFAULT_BUDGET = int(os.environ.get("AST_LENS_BUDGET", "300"))      # B
DEFAULT_THRESHOLD = int(os.environ.get("AST_LENS_THRESHOLD", "200"))  # theta_L
DOC_KEEP_LINES = 3        # package-doc lines kept before truncation   §5.3(4)
VERBATIM_CAP = 240        # chars of verbatim doc per decl              §5.4(1)

EXT_LANG = {
    ".go": "go", ".py": "python",
    ".ts": "typescript", ".tsx": "tsx", ".mts": "typescript", ".cts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
}

# Prompt-injection literals flagged (not dropped) during sanitisation. App D.
INJECTION_PATTERNS = [
    "IGNORE PREVIOUS", "IGNORE ALL PREVIOUS", "SYSTEM:", "ASSISTANT:", "USER:",
    "<|im_start|>", "<|im_end|>", "<s>", "</s>", "[INST]", "[/INST]",
    "Human:", "Assistant:",
]


def est_tokens(s: str) -> int:
    """Cheap tokenizer proxy (~4 chars/token). Budget is a soft target."""
    return (len(s) + 3) // 4


# ---- Sanitisation (§5.4 + App D) ------------------------------------------
def sanitise(text: str) -> str:
    if not text:
        return ""
    out_lines = []
    for line in text.splitlines():
        flagged = any(pat.lower() in line.lower() for pat in INJECTION_PATTERNS)
        if flagged:
            line = "[sanitised] " + line
        out_lines.append(line)
    text = "\n".join(out_lines)
    # Collapse >3 consecutive newlines to 2 (defeat layout injection). §5.4(3)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Truncate verbatim to the per-decl cap. §5.4(1)
    if len(text) > VERBATIM_CAP:
        text = text[:VERBATIM_CAP].rstrip() + " …"
    return text


# ---- Per-language extraction config ---------------------------------------
# Categories are language-neutral (the paper's Tier-2 §8.2 category idea, used
# from the start so significance rules are written against categories, not raw
# grammar node names). Each language maps its node types into these buckets.
DECL_KINDS = {
    "go": {
        "function_declaration": "func", "method_declaration": "method",
        "type_declaration": "type", "import_declaration": "import",
        "const_declaration": "const", "var_declaration": "var",
    },
    "python": {
        "function_definition": "func", "class_definition": "class",
        "decorated_definition": "decorated", "import_statement": "import",
        "import_from_statement": "import",
    },
    "typescript": {
        "function_declaration": "func", "class_declaration": "class",
        "interface_declaration": "interface", "type_alias_declaration": "type",
        "enum_declaration": "enum", "lexical_declaration": "const",
        "variable_declaration": "var", "import_statement": "import",
        "abstract_class_declaration": "class",
    },
    "javascript": {
        "function_declaration": "func", "class_declaration": "class",
        "lexical_declaration": "const", "variable_declaration": "var",
        "import_statement": "import",
    },
}
DECL_KINDS["tsx"] = DECL_KINDS["typescript"]

# Significant nested constructs (App B), expressed by node type per language.
SIGNIFICANT = {
    "go": {"go_statement": "go", "defer_statement": "defer",
           "select_statement": "select", "type_switch_statement": "switch",
           "func_literal": "closure"},
    "python": {"function_definition": "def", "class_definition": "class",
               "with_statement": "with", "try_statement": "try"},
    "typescript": {"arrow_function": "arrow", "function_declaration": "func",
                   "try_statement": "try", "jsx_element": "jsx"},
    "javascript": {"arrow_function": "arrow", "function_declaration": "func",
                   "try_statement": "try", "jsx_element": "jsx"},
}
SIGNIFICANT["tsx"] = SIGNIFICANT["typescript"]


# lang → (grammar module, language-factory function names to try)
_GRAMMAR = {
    "go": ("tree_sitter_go", ["language"]),
    "python": ("tree_sitter_python", ["language"]),
    "javascript": ("tree_sitter_javascript", ["language"]),
    "typescript": ("tree_sitter_typescript", ["language_typescript"]),
    "tsx": ("tree_sitter_typescript", ["language_tsx"]),
}


def load_parser(lang: str):
    """Return a canonical tree-sitter Parser for lang, or None (→ passthrough)."""
    try:
        from tree_sitter import Language, Parser
    except Exception:
        return None
    mod_name, fns = _GRAMMAR.get(lang, (None, None))
    if mod_name is None:
        return None
    try:
        mod = __import__(mod_name)
        factory = next((getattr(mod, f) for f in fns if hasattr(mod, f)), None)
        if factory is None:
            return None
        language = Language(factory())
        try:
            return Parser(language)                # tree-sitter >= 0.22
        except TypeError:
            p = Parser()
            try:
                p.language = language
            except Exception:
                p.set_language(language)
            return p
    except Exception:
        return None


def do_parse(parser, src: bytes):
    """tree-sitter's parse() signature varies by version (bytes vs str). Try both."""
    for arg in (src, src.decode("utf-8", "replace")):
        try:
            return parser.parse(arg)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def node_text(src: bytes, node) -> str:
    t = getattr(node, "text", None)
    if t is not None:
        return t.decode("utf-8", "replace") if isinstance(t, (bytes, bytearray)) else str(t)
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def find_name(node, _depth=0):
    """Best-effort declaration name. Recurses one level into the spec/declarator
    wrappers Go (type_spec/const_spec/var_spec) and TS/JS (variable_declarator)
    use, where the identifier hangs off the inner node rather than the decl."""
    n = node.child_by_field_name("name")
    if n is not None:
        return n
    for c in node.named_children:
        if c.type in ("identifier", "type_identifier", "property_identifier"):
            return c
    if _depth < 2:
        for c in node.named_children:
            if c.type.endswith(("_spec", "_declarator")) or c.type in (
                    "lexical_declaration", "variable_declaration"):
                r = find_name(c, _depth + 1)
                if r is not None:
                    return r
    return None


def clean_doc(text: str) -> str:
    """Strip comment chrome (/** * */ // #) from a doc blob, line by line."""
    out = []
    for ln in text.splitlines():
        ln = re.sub(r"^\s*(/\*\*?|\*/|\*|//+|#+)\s?", "", ln).strip()
        if ln:
            out.append(ln)
    return "\n".join(out)


def is_private(lang: str, name: str, exported: bool) -> bool:
    if not name:
        return True
    if lang == "go":
        return not name[0].isupper()          # Go: capitalisation = exported
    if lang == "python":
        return name.startswith("_")
    return not exported                          # TS/JS: `export` = public


# ---- Extraction ------------------------------------------------------------
class Decl:
    __slots__ = ("kind", "name", "sig", "l0", "l1", "private", "nested")

    def __init__(self, kind, name, sig, l0, l1, private):
        self.kind, self.name, self.sig = kind, name, sig
        self.l0, self.l1, self.private = l0, l1, private
        self.nested = []                         # list[(label, l0, l1)]


def unwrap(node):
    """Peel export/decorator wrappers to the carried declaration."""
    exported = False
    while node.type in ("export_statement", "decorated_definition"):
        if node.type == "export_statement":
            exported = True
        inner = node.child_by_field_name("declaration") or node.child_by_field_name("definition")
        if inner is None:
            inner = next((c for c in node.named_children
                          if c.type not in ("decorator", "export")), None)
        if inner is None:
            break
        node = inner
    return node, exported


def collect_significant(lang: str, body, src: bytes):
    """Universal-fallback significance: named/labelled inner constructs, or any
    construct with line-span >= 10. Plus the per-language fixed list (App B)."""
    sig_map = SIGNIFICANT.get(lang, {})
    found = []
    seen = set()

    def walk(n, depth):
        for c in n.named_children:
            span = c.end_point[0] - c.start_point[0] + 1
            label = sig_map.get(c.type)
            named = find_name(c)
            if label and (label not in ("arrow", "closure") or span >= 5):
                nm = node_text(src, named) if named else label
                key = (c.start_point[0], label)
                if key not in seen:
                    seen.add(key)
                    found.append((f"{label}: {nm}" if named else label,
                                  c.start_point[0] + 1, c.end_point[0] + 1))
            elif span >= 10 and named is not None:
                key = (c.start_point[0], "blk")
                if key not in seen:
                    seen.add(key)
                    found.append((f"{c.type}: {node_text(src, named)}",
                                  c.start_point[0] + 1, c.end_point[0] + 1))
            if depth < 3:
                walk(c, depth + 1)

    walk(body, 0)
    return found[:4]                              # cap per decl


def first_sig_line(src: bytes, node) -> str:
    """Signature = the declaration's first line, trimmed (body elided)."""
    txt = node_text(src, node)
    line = txt.split("\n", 1)[0].strip()
    line = line.rstrip("{(").strip()
    return line[:120]


def extract(lang: str, root, src: bytes):
    decls, imports, doc = [], [], ""
    for child in root.named_children:
        node, exported = unwrap(child)
        kind = DECL_KINDS.get(lang, {}).get(node.type)
        # module/package doc: leading comment(s) or python docstring
        if not decls and not doc:
            if node.type == "comment" or (lang == "python" and node.type == "expression_statement"):
                raw = node_text(src, node).strip()
                if lang == "python":
                    raw = raw.strip('"').strip("'").strip()   # unwrap docstring quotes
                if raw and len(raw) > 3:                        # clean_doc strips comment chrome
                    doc = raw
        if kind is None:
            continue
        if kind == "import":
            imports.append(node)
            continue
        name_node = find_name(node)
        name = node_text(src, name_node) if name_node is not None else ""
        if not name and kind in ("const", "var"):
            # e.g. `const foo = () => {}` — dig for the bound identifier
            m = re.search(r"\b([A-Za-z_$][\w$]*)\b", first_sig_line(src, node).split("=", 1)[0])
            name = m.group(1) if m else ""
        d = Decl(kind, name, first_sig_line(src, node),
                 node.start_point[0] + 1, node.end_point[0] + 1,
                 is_private(lang, name, exported))
        if kind in ("func", "method", "class"):
            body = node.child_by_field_name("body") or node
            d.nested = collect_significant(lang, body, src)
        decls.append(d)
    return decls, imports, doc


def import_names(lang: str, src: bytes, nodes):
    names = []
    for n in nodes:
        t = node_text(src, n)
        if lang == "python":
            # Python imports are unquoted: `import os` / `from x.y import z`.
            m = re.search(r"^\s*(?:from\s+([\w.]+)|import\s+([\w.]+))", t)
            if m:
                names.append((m.group(1) or m.group(2)).split(".")[0])
            continue
        for q in re.findall(r'["\']([^"\']+)["\']', t):
            names.append(q.split("/")[-1] if lang == "go" else q)
    return names


# ---- Render (App C schema) -------------------------------------------------
TYPE_KINDS = {"type", "interface", "enum", "class"}


def render(path, lang, loc, decls, imports, doc, src) -> str:
    name = os.path.basename(path)
    n = len(decls)
    L = [f"# {name} ({loc} LoC, {n} decls)"]
    if doc:
        d = sanitise(clean_doc(doc))
        dl = d.splitlines()[:DOC_KEEP_LINES]
        L.append("")
        L += [f"> {x}" for x in dl]
        if len(d.splitlines()) > DOC_KEEP_LINES:
            L.append("> (truncated)")
    if imports:
        names = import_names(lang, src, imports)
        if names:
            L += ["", "## Imports", ", ".join(names[:24])]
    types = [d for d in decls if d.kind in TYPE_KINDS]
    funcs = [d for d in decls if d.kind in ("func", "method")]
    others = [d for d in decls if d not in types and d not in funcs]
    if types:
        L.append("\n## Types")
        for d in types:
            vis = "" if not d.private else " *(private)*"
            L.append(f"- `{d.sig}`{vis} (L{d.l0}–{d.l1})")
    if funcs:
        L.append("\n## Functions")
        for d in funcs:
            vis = "" if not d.private else " *(private)*"
            L.append(f"- `{d.sig}`{vis} (L{d.l0}–{d.l1})")
            for label, a, b in d.nested:
                L.append(f"  - {label} (L{a}–{b})")
    if others:
        consts = [d for d in others if not d.private]
        L.append("\n## Values")
        for d in consts[:12]:
            L.append(f"- `{d.name}` ({d.kind}, L{d.l0}–{d.l1})")
    return "\n".join(L).rstrip() + "\n"


# ---- Truncation precedence (§5.3) -----------------------------------------
def truncate(md: str, decls, budget: int) -> str:
    """Normative-ish reduction: shed nested (private→public), then collapse
    private decls, then doc, then imports. Re-render is overkill here; we trim
    the rendered text section-by-section to stay <= budget."""
    if est_tokens(md) <= budget:
        return md
    lines = md.split("\n")

    def fits():
        return est_tokens("\n".join(lines)) <= budget

    # 1) drop nested bullets (the "  - " lines), private-owned first is approximated
    lines = [l for l in lines if not l.startswith("  - ")]
    if fits():
        return "\n".join(lines).rstrip() + "\n"
    # 2) collapse private function/type bullets to a count
    kept, dropped = [], 0
    for l in lines:
        if "*(private)*" in l:
            dropped += 1
            continue
        kept.append(l)
    if dropped:
        kept.append(f"\n_(+{dropped} private decls)_")
    lines = kept
    if fits():
        return "\n".join(lines).rstrip() + "\n"
    # 3) drop the doc blockquote
    lines = [l for l in lines if not l.startswith(">")]
    if fits():
        return "\n".join(lines).rstrip() + "\n"
    # 4) collapse imports to a count
    out, in_imp = [], False
    for l in lines:
        if l == "## Imports":
            in_imp = True
            out.append(l)
            continue
        if in_imp and l and not l.startswith("#"):
            out.append(f"({l.count(',') + 1} imports)")
            in_imp = False
            continue
        in_imp = in_imp and not l.startswith("#")
        out.append(l)
    return "\n".join(out).rstrip() + "\n"


def drop_empty_sections(md: str) -> str:
    """Remove `## Section` headers left content-less (e.g. after truncation)."""
    lines = md.split("\n")
    out = []
    for i, l in enumerate(lines):
        if l.startswith("## "):
            has = False
            for nxt in lines[i + 1:]:
                if nxt.startswith(("## ", "# ")):
                    break
                s = nxt.strip()
                if s and not s.startswith("_(+"):   # ignore collapse markers
                    has = True
                    break
            if not has:
                continue
        out.append(l)
    return "\n".join(out).rstrip() + "\n"


# ---- Main ------------------------------------------------------------------
def has_skip(path) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                if "outline:skip" in line:
                    return True
    except Exception:
        pass
    return False


def outline(path, budget, threshold, fmt):
    try:
        with open(path, "rb") as f:
            src = f.read()
    except Exception:
        return ""                                  # passthrough
    loc = src.count(b"\n") + 1
    lang = EXT_LANG.get(os.path.splitext(path)[1].lower())
    if lang is None or loc < threshold or has_skip(path):
        return ""                                  # Alg 1: outline not required
    parser = load_parser(lang)
    if parser is None:
        return ""                                  # missing runtime → passthrough
    try:
        tree = do_parse(parser, src)
        if tree is None:
            return ""                              # parse failure → passthrough
        decls, imports, doc = extract(lang, tree.root_node, src)
    except Exception:
        return ""                                  # parse failure → passthrough
    if not decls and not imports:
        return ""
    md = render(path, lang, loc, decls, imports, doc, src)
    md = truncate(md, decls, budget)
    md = drop_empty_sections(md)
    md = re.sub(r"\n{3,}", "\n\n", md)             # collapse stray blank runs
    if fmt == "json":
        return json.dumps({
            "file": path, "lang": lang, "loc": loc,
            "tokens_outline": est_tokens(md), "markdown": md,
        }, indent=2)
    return md


def main(argv=None):
    ap = argparse.ArgumentParser(description="Emit a Markdown outline of a source file.")
    ap.add_argument("file")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--format", choices=["md", "json"], default="md")
    args = ap.parse_args(argv)
    out = outline(args.file, args.budget, args.threshold, args.format)
    if out:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

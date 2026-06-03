"""``extract-to-package`` — lift a top-level Go declaration into a new package.

A clean-room write-side op for "The AST as LLM Lens" (§5.D, *extract to
package*). This is the most complex of the compound symbolic ops, so the v1
implementation is deliberately CONSERVATIVE: it supports a single, clearly
specified case for **Go** and returns ``None`` (declining safely) for anything
beyond that scope. The compile gate downstream re-parses the emitted files, but
the op never relies on the gate to catch a risky rewrite — it refuses up front.

Contract (shared across all write-side ops)::

    def compute_change(file_path: str, args: dict) -> dict | None

Returns ``{relpath: new_full_content}`` for EVERY file it changes (``relpath``
relative to the repo root = the git root above ``file_path``, else the file's
directory), or ``None`` when there is nothing to do / it cannot do so safely.
``compute_change`` is a pure function: it parses, computes new content, and
returns it. It NEVER writes files or mutates the tree, and imports nothing from
the spine (gate/plan/registry).

Supported case (v1)
-------------------
Move ONE *exported* top-level declaration named ``args["symbol"]`` out of the
Go file ``file_path`` into a brand-new sibling package directory
``args["target"]`` (relative to the source file's directory), as
``<target>/<name>.go`` with ``package <target>`` and only the imports the moved
declaration actually uses. References to the symbol *within the original
package's files* are rewritten to call it qualified through the new package
(``Symbol`` → ``<target>.Symbol``), adding ``import "<module>/<target>"`` to
each caller that needs it.

The moved declaration may be:

* a ``func`` (a free function), or
* a ``type`` together with all methods declared on that type in ``file_path``,
  or
* a single-name ``const`` or ``var`` (``const Name = ...`` / ``var Name = ...``).

Declined (``None``) — out of scope for v1
-----------------------------------------
* non-Go input (extension is not ``.go``);
* the symbol is not found, or is declared more than once;
* the symbol is *unexported* (lower-case first letter) — it could not be
  referenced from the new package;
* the moved declaration depends on an *unexported* top-level identifier of the
  source package (that dependency would have to move too);
* the symbol is a *method* on a type that stays behind;
* a grouped ``const (...)`` / ``var (...)`` block, or a multi-name spec
  (``var a, b = ...``) — only a lone single-name value decl is handled;
* the target package directory already exists on disk, or the target name is
  not a valid Go identifier;
* anything that fails to parse, or whose emitted form is not ``gofmt``-clean.

Tooling: source is parsed with **tree-sitter-go** (already a pack dependency,
in-process); emitted Go is formatted with **gofmt** (``gofmt`` on the host
``PATH``). If ``gofmt`` is unavailable the op declines rather than emit
unformatted Go.
"""
from __future__ import annotations

import os
import re
import subprocess

# A human-readable reason for the most recent decline, for diagnostics/tests.
# Set on every ``None`` return; read it right after a call. (Module-level state
# is a diagnostic side-channel only — it does not affect the pure return value.)
last_reason: str | None = None


def _decline(reason: str) -> None:
    global last_reason
    last_reason = reason
    return None


# --------------------------------------------------------------------------- #
# tree-sitter-go loader (mirrors bin/outline.py's defensive shim).
# --------------------------------------------------------------------------- #
def _load_go_parser():
    """Return a tree-sitter Parser for Go, or ``None`` (→ decline)."""
    try:
        import tree_sitter_go
        from tree_sitter import Language, Parser
    except Exception:
        return None
    try:
        language = Language(tree_sitter_go.language())
    except Exception:
        return None
    try:
        return Parser(language)                       # tree-sitter >= 0.22
    except TypeError:                                 # pragma: no cover
        p = Parser()
        try:
            p.language = language
        except Exception:
            p.set_language(language)
        return p


def _parse(parser, src: bytes):
    for arg in (src, src.decode("utf-8", "replace")):
        try:
            return parser.parse(arg)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _txt(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# gofmt
# --------------------------------------------------------------------------- #
def _gofmt(content: str) -> str | None:
    """Format Go source with gofmt. Returns the formatted text, or ``None`` if
    gofmt is missing or rejects the input (syntactically invalid)."""
    try:
        proc = subprocess.run(
            ["gofmt"],
            input=content.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# repo-relative path resolution (git root above file_path, else its dir).
# --------------------------------------------------------------------------- #
def _repo_root(file_path: str) -> str:
    d = os.path.dirname(os.path.abspath(file_path))
    cur = d
    while True:
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return d                                  # no git root → file's dir
        cur = parent


def _relpath(path: str, root: str) -> str:
    return os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")


# --------------------------------------------------------------------------- #
# Go module path resolution (for the import string of the new package).
# --------------------------------------------------------------------------- #
def _module_path(pkg_dir: str) -> tuple[str | None, str | None]:
    """Walk up from ``pkg_dir`` to the nearest ``go.mod``; return
    ``(module_path, import_path_of_pkg_dir)``. If no go.mod is found, return
    ``(None, None)`` — callers then fall back to a relative single-element
    import path (best-effort; the gate still verifies parseability)."""
    cur = os.path.abspath(pkg_dir)
    while True:
        gomod = os.path.join(cur, "go.mod")
        if os.path.isfile(gomod):
            try:
                with open(gomod, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        m = re.match(r"\s*module\s+(\S+)", line)
                        if m:
                            mod = m.group(1)
                            rel = os.path.relpath(
                                os.path.abspath(pkg_dir), cur
                            ).replace(os.sep, "/")
                            imp = mod if rel == "." else f"{mod}/{rel}"
                            return mod, imp
            except OSError:
                pass
            return None, None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None, None
        cur = parent


# --------------------------------------------------------------------------- #
# Decl model
# --------------------------------------------------------------------------- #
class _Decl:
    """A top-level declaration node with the metadata the op needs."""

    __slots__ = ("node", "kind", "name", "recv_type")

    def __init__(self, node, kind, name, recv_type=None):
        self.node = node
        self.kind = kind            # "func" | "method" | "type" | "const" | "var"
        self.name = name
        self.recv_type = recv_type  # for methods: the type the method is on


def _receiver_type_name(src: bytes, method_node) -> str | None:
    """The bare type name a method is declared on (``*T`` and ``T`` → ``T``).
    Returns ``None`` for receivers whose base type is qualified (``*pkg.T``),
    which v1 never moves."""
    recv = method_node.child_by_field_name("receiver")
    if recv is None:
        return None
    for pd in recv.named_children:
        tnode = pd.child_by_field_name("type")
        if tnode is None:
            continue
        if tnode.type == "pointer_type":
            inner = tnode.named_children[0] if tnode.named_children else None
            tnode = inner
        if tnode is None:
            return None
        if tnode.type == "type_identifier":
            return _txt(src, tnode)
        return None                                   # qualified / generic recv
    return None


def _single_spec_name(src: bytes, decl_node):
    """For a const/var declaration, return the single declared name, or ``None``
    if it is a grouped block or a multi-name spec (out of scope)."""
    specs = [c for c in decl_node.named_children if c.type.endswith("_spec")]
    if len(specs) != 1:
        return None
    spec = specs[0]
    names = [c for c in spec.named_children if c.type == "identifier"]
    if len(names) != 1:
        return None
    return _txt(src, names[0])


def _collect_top_level(src: bytes, root):
    """Walk the file's top-level declarations into ``_Decl`` records."""
    out: list[_Decl] = []
    for child in root.named_children:
        t = child.type
        if t == "function_declaration":
            nm = child.child_by_field_name("name")
            if nm is not None:
                out.append(_Decl(child, "func", _txt(src, nm)))
        elif t == "method_declaration":
            nm = child.child_by_field_name("name")
            rt = _receiver_type_name(src, child)
            if nm is not None:
                out.append(_Decl(child, "method", _txt(src, nm), rt))
        elif t == "type_declaration":
            specs = [c for c in child.named_children if c.type == "type_spec"]
            if len(specs) == 1:
                nm = specs[0].child_by_field_name("name")
                if nm is not None:
                    out.append(_Decl(child, "type", _txt(src, nm)))
        elif t in ("const_declaration", "var_declaration"):
            nm = _single_spec_name(src, child)
            if nm is not None:
                kind = "const" if t == "const_declaration" else "var"
                out.append(_Decl(child, kind, nm))
    return out


# --------------------------------------------------------------------------- #
# Identifier reference walk
# --------------------------------------------------------------------------- #
def _is_qualifiable_ref(node) -> bool:
    """True if an ``identifier``/``type_identifier`` node is a *bare* reference
    that should be qualified — i.e. it is NOT the ``.field`` half of a selector
    (``x.Sym``) and NOT a struct-literal field *key* (``T{Sym: ...}``)."""
    par = node.parent
    if par is None:
        return True
    if par.type == "selector_expression":
        fld = par.child_by_field_name("field")
        if fld is not None and fld.start_byte == node.start_byte:
            return False                              # the `.field` part
    # Struct-literal field key: keyed_element → (literal_element=KEY, ... =VALUE)
    if par.type == "literal_element":
        gp = par.parent
        if gp is not None and gp.type == "keyed_element":
            key = gp.child_by_field_name("key")
            if key is not None and key.start_byte == par.start_byte:
                return False                          # the field-name key
    return True


def _find_refs(src: bytes, root, name: str):
    """All byte-offsets of bare references to ``name`` (identifier/
    type_identifier), excluding selector fields and struct-literal keys.
    Returns a list of (start_byte, end_byte)."""
    hits: list[tuple[int, int]] = []

    def walk(n):
        for c in n.named_children:
            if c.type in ("identifier", "type_identifier") and _txt(src, c) == name:
                if _is_qualifiable_ref(c):
                    hits.append((c.start_byte, c.end_byte))
            walk(c)

    walk(root)
    return hits


def _toplevel_names(decls: list[_Decl]) -> set[str]:
    return {d.name for d in decls if d.kind in ("func", "type", "const", "var")}


def _identifiers_used(src: bytes, nodes) -> set[str]:
    """Every bare identifier/type_identifier referenced anywhere inside the
    given nodes (used to detect unexported package-level dependencies and to
    decide which imports to carry)."""
    used: set[str] = set()

    def walk(n):
        for c in n.named_children:
            if c.type in ("identifier", "type_identifier", "package_identifier"):
                if _is_qualifiable_ref(c):
                    used.add(_txt(src, c))
                else:
                    # The operand of a selector (``pkg`` in ``pkg.X``) is a real
                    # reference we DO want, even though the field is not.
                    par = c.parent
                    if par is not None and par.type == "selector_expression":
                        op = par.child_by_field_name("operand")
                        if op is not None and op.start_byte == c.start_byte:
                            used.add(_txt(src, c))
            walk(c)

    for n in nodes:
        walk(n)
    return used


# --------------------------------------------------------------------------- #
# Imports
# --------------------------------------------------------------------------- #
class _Import:
    __slots__ = ("alias", "path", "local")

    def __init__(self, alias, path):
        self.alias = alias              # explicit alias or None
        self.path = path                # the quoted import path, unquoted
        # The local name an import binds: alias if given, else last path element.
        self.local = alias if alias else path.rstrip("/").split("/")[-1]


def _parse_imports(src: bytes, root) -> list[_Import]:
    out: list[_Import] = []
    for child in root.named_children:
        if child.type != "import_declaration":
            continue
        specs = []
        for c in child.named_children:
            if c.type == "import_spec":
                specs.append(c)
            elif c.type == "import_spec_list":
                specs.extend(s for s in c.named_children if s.type == "import_spec")
        for spec in specs:
            path_node = spec.child_by_field_name("path")
            name_node = spec.child_by_field_name("name")
            if path_node is None:
                continue
            raw = _txt(src, path_node).strip()
            path = raw[1:-1] if len(raw) >= 2 and raw[0] in "\"`" else raw
            alias = _txt(src, name_node) if name_node is not None else None
            out.append(_Import(alias, path))
    return out


def _render_imports(imports: list[_Import]) -> str:
    """Render an import block (gofmt will re-sort/group; we just need valid Go)."""
    if not imports:
        return ""
    if len(imports) == 1:
        imp = imports[0]
        prefix = f"{imp.alias} " if imp.alias else ""
        return f'import {prefix}"{imp.path}"\n'
    lines = ["import ("]
    for imp in imports:
        prefix = f"{imp.alias} " if imp.alias else ""
        lines.append(f'\t{prefix}"{imp.path}"')
    lines.append(")")
    return "\n".join(lines) + "\n"


def _used_locals(src: bytes, root) -> set[str]:
    """Local names referenced anywhere outside import declarations — i.e. every
    selector operand (``pkg`` in ``pkg.X``) plus bare identifiers/types. Used to
    decide which imports are still live after a decl is removed."""
    used: set[str] = set()

    def walk(n):
        for c in n.named_children:
            if c.type == "import_declaration":
                continue
            if c.type in ("identifier", "type_identifier", "package_identifier"):
                used.add(_txt(src, c))
            walk(c)

    walk(root)
    return used


def _prune_unused_imports(parser, text: str) -> str:
    """Remove import specs whose local name is no longer referenced in ``text``.
    A removed symbol can orphan the import it used; an unused import is a Go
    *compile error*, so the shrunken source must not keep one. Side-effect
    imports (blank ``_`` and dot ``.``) are always kept. Returns new text (or
    the input unchanged if nothing is prunable / it cannot parse)."""
    src = text.encode("utf-8")
    tree = _parse(parser, src)
    if tree is None or tree.root_node.has_error:
        return text
    root = tree.root_node
    used = _used_locals(src, root)

    drop_spans: list[tuple[int, int]] = []
    for child in root.named_children:
        if child.type != "import_declaration":
            continue
        # Flatten the import specs (single `import "x"` or grouped `import (...)`).
        spec_nodes = []
        for c in child.named_children:
            if c.type == "import_spec":
                spec_nodes.append(c)
            elif c.type == "import_spec_list":
                spec_nodes.extend(s for s in c.named_children if s.type == "import_spec")
        kept = 0
        dead = []
        for spec in spec_nodes:
            name_node = spec.child_by_field_name("name")
            path_node = spec.child_by_field_name("path")
            if path_node is None:
                kept += 1
                continue
            alias = _txt(src, name_node) if name_node is not None else None
            if alias in ("_", "."):                   # side-effect import: keep
                kept += 1
                continue
            raw = _txt(src, path_node).strip()
            path = raw[1:-1] if len(raw) >= 2 and raw[0] in "\"`" else raw
            local = alias if alias else path.rstrip("/").split("/")[-1]
            if local in used:
                kept += 1
            else:
                dead.append(spec)
        if not dead:
            continue
        if kept == 0:
            drop_spans.append((child.start_byte, child.end_byte))  # whole decl
        else:
            for spec in dead:
                drop_spans.append((spec.start_byte, spec.end_byte))
    if not drop_spans:
        return text
    return _cut_spans(src, drop_spans)


# --------------------------------------------------------------------------- #
# Source-file surgery: drop a set of node spans, return the remaining text.
# --------------------------------------------------------------------------- #
def _attached_doc_start(src: bytes, root, node) -> int:
    """If a doc comment immediately precedes ``node`` — a single ``/* ... */``
    block, or a contiguous run of ``// ...`` line comments (tree-sitter parses
    each ``//`` line as its own ``comment`` node) with no blank line breaking
    the run or separating it from the decl — return the start byte of the
    earliest comment in that run, so the whole doc moves/removes with the decl.
    Otherwise return ``node.start_byte``.

    "Contiguous" means the byte gap between adjacent items contains only
    whitespace and at most one newline; a blank line (>=2 newlines) detaches the
    comment, matching gofmt's notion of an attached doc comment."""
    siblings = [c for c in root.named_children if c.start_byte < node.start_byte]
    start = node.start_byte
    # Walk backward from the decl over an unbroken run of attached comments.
    next_start = node.start_byte
    for child in reversed(siblings):
        if child.type != "comment":
            break
        gap = src[child.end_byte:next_start]
        if gap.count(b"\n") > 1 or gap.strip(b" \t\r\n") != b"":
            break                                     # blank line / code in gap
        txt = _txt(src, child)
        if not (txt.startswith("//") or txt.startswith("/*")):
            break
        start = child.start_byte
        next_start = child.start_byte
        if txt.startswith("/*"):
            break                                     # a block comment is whole
    return start


def _cut_spans(src: bytes, spans: list[tuple[int, int]]) -> str:
    """Remove byte spans from ``src``; collapse the blank lines they leave."""
    spans = sorted(spans)
    out = bytearray()
    pos = 0
    for s, e in spans:
        out += src[pos:s]
        pos = e
    out += src[pos:]
    text = out.decode("utf-8", "replace")
    # Collapse 3+ blank lines (left by removed decls) to a single blank line.
    text = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", text)
    return text


# --------------------------------------------------------------------------- #
# Reference rewriting: qualify bare refs `Sym` → `<target>.Sym` and add import.
# --------------------------------------------------------------------------- #
_GO_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _qualify_in_file(src: bytes, root, name: str, target: str) -> str | None:
    """Rewrite bare references to ``name`` as ``target.name`` in this file's
    source. Returns new text, or ``None`` if there were no references."""
    refs = _find_refs(src, root, name)
    if not refs:
        return None
    out = bytearray()
    pos = 0
    repl = f"{target}.{name}".encode()
    for s, e in sorted(refs):
        out += src[pos:s]
        out += repl
        pos = e
    out += src[pos:]
    return out.decode("utf-8", "replace")


def _add_import_to_source(text: str, import_path: str, alias: str | None) -> str:
    """Insert an import for ``import_path`` into already-rewritten Go ``text``.
    gofmt will normalise placement/grouping afterward; we just need to land a
    syntactically valid import statement after the package clause / existing
    imports. Idempotent: if the path is already imported, returns text as-is."""
    quoted = f'"{import_path}"'
    if quoted in text:
        return text
    spec = f'{alias} {quoted}' if alias else quoted
    lines = text.split("\n")
    # Find the last existing import line / block to append after; else after the
    # package clause.
    insert_at = None
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("import ("):
            # grouped block: insert before the closing ')'
            j = i + 1
            while j < len(lines) and lines[j].strip() != ")":
                j += 1
            lines.insert(j, f"\t{spec}")
            return "\n".join(lines)
        if stripped.startswith("import "):
            insert_at = i + 1
        if stripped.startswith("package "):
            if insert_at is None:
                insert_at = i + 1
        i += 1
    if insert_at is None:
        insert_at = 1
    lines.insert(insert_at, f"import {spec}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def compute_change(file_path: str, args: dict) -> dict | None:
    """See module docstring. Pure: returns ``{relpath: content}`` or ``None``."""
    global last_reason
    last_reason = None

    symbol = (args or {}).get("symbol")
    target = (args or {}).get("target")
    if not symbol or not target:
        return _decline("missing 'symbol' or 'target' in args")

    if not file_path.endswith(".go"):
        return _decline("non-Go input (only .go is supported in v1)")

    # target is a single new sibling package name/dir relative to the source.
    target = target.strip().strip("/")
    if "/" in target or os.sep in target:
        return _decline("target must be a single new sibling package name (no path separators) in v1")
    if not _GO_IDENT_RE.match(target):
        return _decline(f"target {target!r} is not a valid Go package identifier")

    if not symbol[:1].isupper():
        return _decline(f"symbol {symbol!r} is unexported; v1 only moves exported symbols")

    try:
        with open(file_path, "rb") as fh:
            src = fh.read()
    except OSError as exc:
        return _decline(f"cannot read {file_path}: {exc}")

    parser = _load_go_parser()
    if parser is None:
        return _decline("tree-sitter-go runtime unavailable")
    tree = _parse(parser, src)
    if tree is None:
        return _decline("source did not parse")
    root = tree.root_node
    if root.has_error:
        return _decline("source has parse errors")

    pkg_dir = os.path.dirname(os.path.abspath(file_path))
    target_dir = os.path.join(pkg_dir, target)
    if os.path.exists(target_dir):
        return _decline(f"target directory {target!r} already exists; v1 only creates a new package")

    decls = _collect_top_level(src, root)

    # Locate the symbol. It must be a single func / type / const / var.
    primary = [d for d in decls
               if d.name == symbol and d.kind in ("func", "type", "const", "var")]
    methods_on_symbol = [d for d in decls
                         if d.kind == "method" and d.recv_type == symbol]

    if len(primary) == 0:
        # Is it (only) a method? Then its type stays behind → out of scope.
        if any(d.kind == "method" and d.name == symbol for d in decls):
            return _decline(
                f"{symbol!r} is a method on a type that stays behind; out of scope for v1"
            )
        return _decline(f"top-level decl {symbol!r} not found in {os.path.basename(file_path)}")
    if len(primary) > 1:
        return _decline(f"{symbol!r} is declared more than once; out of scope for v1")

    decl = primary[0]
    moved_nodes = [decl.node] + [m.node for m in methods_on_symbol]

    # --- dependency check: the moved code must not reference an *unexported*
    #     top-level identifier of the source package (it would have to move too).
    used = _identifiers_used(src, moved_nodes)
    pkg_names = _toplevel_names(decls)
    for nm in sorted(used):
        if nm == symbol:
            continue
        if nm in pkg_names and not nm[:1].isupper():
            return _decline(
                f"{symbol!r} depends on unexported package symbol {nm!r}; "
                "that would also need moving — out of scope for v1"
            )

    # --- imports the moved code actually uses -------------------------------
    file_imports = _parse_imports(src, root)
    by_local = {imp.local: imp for imp in file_imports}
    carried: list[_Import] = []
    seen_paths: set[str] = set()
    for nm in used:
        imp = by_local.get(nm)
        if imp is not None and imp.path not in seen_paths:
            carried.append(imp)
            seen_paths.add(imp.path)

    # --- build the new package file -----------------------------------------
    moved_src_parts = []
    for d in [decl] + methods_on_symbol:
        s = _attached_doc_start(src, root, d.node)
        moved_src_parts.append(src[s:d.node.end_byte].decode("utf-8", "replace"))
    moved_body = "\n\n".join(part.strip("\n") for part in moved_src_parts)

    new_file_chunks = [f"package {target}", ""]
    imp_block = _render_imports(carried)
    if imp_block:
        new_file_chunks.append(imp_block.rstrip("\n"))
        new_file_chunks.append("")
    new_file_chunks.append(moved_body)
    new_file_content = "\n".join(new_file_chunks).rstrip("\n") + "\n"

    new_file_fmt = _gofmt(new_file_content)
    if new_file_fmt is None:
        return _decline("emitted new-package file is not gofmt-clean (declined to avoid a risky change)")

    # --- shrink the source file (remove the moved decl + its methods + doc) ---
    cut: list[tuple[int, int]] = []
    for d in [decl] + methods_on_symbol:
        s = _attached_doc_start(src, root, d.node)
        cut.append((s, d.node.end_byte))
    shrunken = _cut_spans(src, cut)
    # The removed decl may have been the sole user of an import; an unused import
    # is a Go compile error, so prune any import the shrunken file no longer
    # references (carry-over of those imports already happened above).
    shrunken = _prune_unused_imports(parser, shrunken)
    shrunken_fmt = _gofmt(shrunken)
    if shrunken_fmt is None:
        return _decline("shrunken source file is not gofmt-clean (declined)")

    # --- import path of the new package (for callers) ------------------------
    _module, target_import = _module_path(target_dir)
    if target_import is None:
        # No go.mod found — fall back to the bare package name as the import
        # path. The compile gate still verifies the result parses; in a real
        # module this branch won't be taken.
        target_import = target

    root_dir = _repo_root(file_path)
    result: dict[str, str] = {}
    result[_relpath(file_path, root_dir)] = shrunken_fmt
    result[_relpath(os.path.join(target_dir, f"{_file_stem(symbol)}.go"), root_dir)] = new_file_fmt

    # --- rewrite callers in the SAME package directory -----------------------
    for entry in sorted(os.listdir(pkg_dir)):
        if not entry.endswith(".go") or entry.endswith("_test.go"):
            continue
        cand = os.path.join(pkg_dir, entry)
        if os.path.abspath(cand) == os.path.abspath(file_path):
            continue                                  # the source file already handled
        try:
            with open(cand, "rb") as fh:
                csrc = fh.read()
        except OSError:
            continue
        ctree = _parse(parser, csrc)
        if ctree is None or ctree.root_node.has_error:
            continue
        qualified = _qualify_in_file(csrc, ctree.root_node, symbol, target)
        if qualified is None:
            continue                                  # no references here
        # Guard against a self-named import collision (caller already uses an
        # identifier `target` as an import local) — decline rather than shadow.
        cimports = _parse_imports(csrc, ctree.root_node)
        for imp in cimports:
            if imp.local == target and imp.path != target_import:
                return _decline(
                    f"caller {entry} already binds import local {target!r}; "
                    "renaming to avoid the collision is out of scope for v1"
                )
        with_import = _add_import_to_source(qualified, target_import, None)
        caller_fmt = _gofmt(with_import)
        if caller_fmt is None:
            return _decline(f"rewritten caller {entry} is not gofmt-clean (declined)")
        result[_relpath(cand, root_dir)] = caller_fmt

    return result


def _file_stem(symbol: str) -> str:
    """File name stem for the new package file: the symbol lower-cased on its
    leading run (``Helper`` → ``helper``, ``HTTPDo`` → ``httpdo``)."""
    return symbol.lower()

"""Op registry: op name -> the module's ``compute_change`` (guarded/lazy).

The four write-side ops are built by *parallel* agents; only one
(``strip-trailing-ws``) is owned by the spine. The registry must therefore
tolerate any subset of the op modules being absent: a missing op module is
SKIPPED, never fatal, so one unfinished sibling never breaks the others.

Resolution is lazy. ``resolve(name)`` imports the backing module on demand and
caches the result. An import error (module not yet written, or it raises on
import) is captured and surfaced only when *that* op is requested — listing and
resolving other ops keeps working.

Each backing module must expose ``compute_change(file_path, args) -> dict|None``
per the shared contract. The registry validates that surface lazily and raises
a clear ``OpError`` if a present module is malformed.
"""

from __future__ import annotations

import importlib

__all__ = [
    "resolve",
    "available",
    "all_op_names",
    "listing_names",
    "OpError",
    "describe",
    "is_intent",
]


class OpError(Exception):
    """Raised when a requested op is unknown, unavailable, or malformed."""


# Stable op name -> backing module path. Order is the canonical listing order.
# `strip-trailing-ws` is the spine's demo op (always present). The other three
# are produced by sibling agents; their modules may not exist yet, and the
# guarded import below makes their absence a non-event.
_REGISTRY: dict[str, str] = {
    "strip-trailing-ws": "astlens.ops.strip_trailing_ws",
    "fix-imports": "astlens.ops.fix_imports",
    "rename-symbol": "astlens.ops.rename_symbol",
    "extract-to-package": "astlens.ops.extract_to_package",
}

# Cache: op name -> compute_change callable (populated on first successful resolve).
_RESOLVED: dict[str, object] = {}

# --------------------------------------------------------------------------- #
# Pattern-DSL intents (paper §4.E / "Subsystem E").
#
# In addition to the Python ops above, the registry surfaces every YAML intent
# under ``astlens/intents/`` as an op named by its ``id`` (so ``bin/op
# remove-console <file>`` plans it and ``bin/op remove-console! <file> <token>``
# executes it through the same gate). The loading is ADDITIVE and fully GUARDED:
# the pattern engine (and its pyyaml / ast-grep deps) are optional, and any
# failure to import the engine or parse an intent is swallowed here so a broken
# or absent intent never breaks the hand-written ops. A genuinely malformed
# intent still surfaces a clear error when *that* op is resolved (see `resolve`).
# --------------------------------------------------------------------------- #

# Cache: intent op-name -> the loaded Intent (None until first scan). A dict
# distinguishes "not yet scanned" (None) from "scanned, found these" ({}).
_INTENTS: dict[str, object] | None = None
# Per-intent load error captured at scan time, surfaced on resolve of that name.
_INTENT_ERRORS: dict[str, str] = {}


def _scan_intents() -> dict[str, object]:
    """Discover YAML intents once, returning ``{op_name: Intent}`` (cached).

    Guarded so the whole feature degrades to "no extra ops" when the pattern
    engine or its dependencies are unavailable. A *single* malformed intent
    does not sink the rest: its op name is still registered, but with a stored
    error that ``resolve`` raises only when that op is requested.
    """
    global _INTENTS
    if _INTENTS is not None:
        return _INTENTS

    found: dict[str, object] = {}
    try:
        from . import pattern as _pattern
    except Exception:  # noqa: BLE001 - engine/deps absent -> no intent ops
        _INTENTS = found
        return _INTENTS

    # Load the directory leniently: collect good intents, and remember the name
    # + error for any single bad file so listing/resolution stays informative.
    import os

    directory = _pattern.DEFAULT_INTENTS_DIR
    if os.path.isdir(directory):
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith((".yaml", ".yml")):
                continue
            path = os.path.join(directory, fname)
            try:
                intent = _pattern.load_intent(path)
            except Exception as exc:  # noqa: BLE001 - record, do not abort scan
                # Best-effort name: the file stem, so the op is still listed.
                name = os.path.splitext(fname)[0]
                _INTENT_ERRORS[name] = f"{type(exc).__name__}: {exc}"
                continue
            if intent.id in found or intent.id in _REGISTRY:
                _INTENT_ERRORS[intent.id] = (
                    f"duplicate op id '{intent.id}' from intent {path}"
                )
                continue
            found[intent.id] = intent

    _INTENTS = found
    return _INTENTS


def _intent_names() -> list[str]:
    """Intent op-names (good + errored), sorted, for listing/iteration."""
    intents = _scan_intents()
    return sorted(set(intents) | set(_INTENT_ERRORS))


def all_op_names() -> list[str]:
    """The canonical hand-written Python op names, present or not, in order.

    This deliberately excludes the pattern-DSL intents so the *spine's* notion
    of "the registered ops" stays exactly the four Python ops it owns. The
    combined, listing-facing set (Python ops + discovered intents) is
    :func:`listing_names`, which is what ``bin/op --list`` enumerates.
    """
    return list(_REGISTRY.keys())


def listing_names() -> list[str]:
    """Every op name to show in ``bin/op --list``: Python ops then intents.

    Hand-written Python ops first (canonical order), then the discovered
    pattern-DSL intents (sorted by id). Resolution (:func:`resolve`) and
    availability (:func:`available`) accept any name in this list.
    """
    return list(_REGISTRY.keys()) + _intent_names()


def _load_intent_op(name: str):
    """Build the ``compute_change`` for a pattern-DSL intent op ``name``.

    Raises OpError if the intent failed to load (malformed YAML, unknown
    language, etc.) — surfaced here, lazily, only when this op is requested, so
    one bad intent never breaks listing or the other ops.
    """
    intents = _scan_intents()
    intent = intents.get(name)
    if intent is None:
        err = _INTENT_ERRORS.get(name, "intent could not be loaded")
        raise OpError(f"pattern intent '{name}' is unavailable: {err}")
    try:
        from . import pattern as _pattern

        return _pattern.make_op(intent)
    except OpError:
        raise
    except Exception as exc:  # noqa: BLE001 - any build failure -> clear OpError
        raise OpError(f"pattern intent '{name}' failed to build an op: {exc}") from exc


def _load(name: str):
    """Import a backing module and return its ``compute_change``.

    Raises OpError if the module is absent, fails to import, or does not expose
    a callable ``compute_change``.
    """
    module_path = _REGISTRY[name]
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise OpError(
            f"op '{name}' is registered but its module '{module_path}' is not "
            f"available (built by a sibling agent?): {exc}"
        ) from exc
    fn = getattr(mod, "compute_change", None)
    if not callable(fn):
        raise OpError(
            f"op '{name}' module '{module_path}' does not expose a callable "
            f"compute_change(file_path, args) -> dict|None"
        )
    return fn


def resolve(name: str):
    """Return the ``compute_change`` callable for op ``name``.

    Lazy + cached. Raises :class:`OpError` if the name is unknown or its module
    is unavailable/malformed. Resolving one op never imports the others, so an
    unfinished sibling op cannot break this one.
    """
    if name not in _RESOLVED:
        if name in _REGISTRY:
            _RESOLVED[name] = _load(name)
        elif name in _intent_names():
            _RESOLVED[name] = _load_intent_op(name)
        else:
            known = ", ".join(listing_names())
            raise OpError(f"unknown op '{name}'. Registered ops: {known}")
    return _RESOLVED[name]


def available() -> dict[str, bool]:
    """Map each registered op name -> whether its module resolves right now.

    Probes by attempting a (cached) resolve and swallowing OpError, so it is
    safe to call when sibling op modules are still missing.
    """
    out: dict[str, bool] = {}
    for name in listing_names():
        try:
            resolve(name)
            out[name] = True
        except OpError:
            out[name] = False
    return out


def describe(name: str) -> str:
    """One-line description for an op, for ``bin/op --list``.

    Pattern-DSL intents carry their YAML ``description``; hand-written Python
    ops fall back to a generic label (their behaviour is documented in
    ``docs/WRITE-SIDE.md``). Never raises — a kind that cannot be described
    returns an empty string.
    """
    if name in _REGISTRY:
        return ""
    intent = _scan_intents().get(name)
    if intent is not None:
        return getattr(intent, "description", "") or ""
    return ""


def is_intent(name: str) -> bool:
    """True iff ``name`` is a pattern-DSL intent op (vs a hand-written Python op)."""
    return name not in _REGISTRY and name in _intent_names()

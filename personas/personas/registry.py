"""Persona registry — load + validate the principal-engineer roster (``personas.toml``).

Stdlib-only (TOML via :mod:`tomllib` on Python 3.11+; :mod:`tomli` fallback below).
The registry is the library of persona *definitions* (README "How it works" §1): each
persona is a role — its domain, the principal-engineer playbook for that domain, when
to equip it, the skills/tools it brings, and the verification bar it holds work to.

Nothing in the decision path is hard-coded: the roster, the match keywords, and the
warm-cache TTL policy all come from ``personas.toml``. A small built-in
:func:`default_config` keeps the engine working if that file is missing or deleted,
mirroring how ``model-advisor`` degrades to a built-in roster.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

try:  # Python >= 3.11 has tomllib in the stdlib.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only on < 3.11 via the tomli backport
    import tomli as tomllib  # type: ignore[no-redef]


class RegistryError(ValueError):
    """Raised when ``personas.toml`` is missing required structure or is invalid."""


#: A persona ``id`` is a stable, kebab-case handle: the warm cache keys on it, the CLI
#: shows/looks-up by it, and the equip hook overlays by it. Lowercase alphanumerics in
#: hyphen-separated groups — no leading/trailing/doubled hyphens, no spaces or uppercase.
_VALID_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# --------------------------------------------------------------------------- #
# Dataclasses                                                                   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Persona:
    """One principal-engineer persona — a role an agent equips for one task.

    ``match_keywords`` is the curated signal the equip/match engine scores a task
    description against (the same "description match" skills auto-fire on). ``weight``
    is an optional priority used only as a deterministic tie-break between equal scores.
    """

    id: str
    domain: str
    when_to_equip: str
    verification_bar: str
    playbook: str
    match_keywords: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    weight: float = 1.0

    @property
    def title(self) -> str:
        """Human title: ``principal-backend-engineer`` -> ``Principal Backend Engineer``."""
        return " ".join(w.capitalize() for w in self.id.replace("_", "-").split("-") if w)


@dataclass(frozen=True)
class CachePolicy:
    """Warm-cache TTL policy (README "Lifecycle TTL (the reasoning)").

    - ``idle_ttl_seconds`` — sliding idle window, refreshed on every reuse. A persona
      that no agent has equipped within this window is evicted (default 30 min).
    - ``ceiling_ttl_seconds`` — absolute cap since first materialize. Even a
      continuously-reused persona is force-refreshed past this so it picks up registry
      updates and the cache footprint stays bounded (default 2 h).

    Both are configurable via the ``[cache]`` table; the defaults are the starting
    point, not a law.
    """

    idle_ttl_seconds: float = 1800.0
    ceiling_ttl_seconds: float = 7200.0

    def __post_init__(self) -> None:
        if self.idle_ttl_seconds <= 0:
            raise RegistryError("[cache] idle TTL must be > 0")
        if self.ceiling_ttl_seconds <= 0:
            raise RegistryError("[cache] ceiling TTL must be > 0")
        if self.ceiling_ttl_seconds < self.idle_ttl_seconds:
            raise RegistryError(
                "[cache] ceiling TTL must be >= idle TTL "
                f"(got ceiling={self.ceiling_ttl_seconds}s < idle={self.idle_ttl_seconds}s)"
            )


@dataclass(frozen=True)
class PersonasConfig:
    """The fully-resolved persona configuration (roster + warm-cache policy)."""

    personas: tuple[Persona, ...]
    cache: CachePolicy
    #: Persona equipped when a task matches nothing (the generalist fallback). May be
    #: ``None``, in which case the match engine falls back to the first persona.
    default_persona_id: str | None = None

    def get(self, persona_id: str) -> Persona:
        for p in self.personas:
            if p.id == persona_id:
                return p
        raise KeyError(f"persona {persona_id!r} not in registry")

    def has(self, persona_id: str) -> bool:
        return any(p.id == persona_id for p in self.personas)

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.personas)

    @property
    def default_persona(self) -> Persona:
        """The fallback persona: the configured default, else the first in the roster."""
        if self.default_persona_id is not None:
            return self.get(self.default_persona_id)
        return self.personas[0]


# --------------------------------------------------------------------------- #
# Built-in default (safety net when personas.toml is absent)                    #
# --------------------------------------------------------------------------- #

#: A lean three-persona fallback so the engine never has an empty roster. Normal use
#: loads the shipped ``personas.toml`` (the full 10-persona roster); this only kicks
#: in if that file is missing or deleted (mirrors ``model-advisor``'s default roster).
DEFAULT_PERSONAS: tuple[Persona, ...] = (
    Persona(
        id="principal-backend-engineer",
        domain="Server-side services, APIs, data access, and business logic.",
        when_to_equip="Implementing or changing server-side logic, endpoints, or data access.",
        verification_bar="Inputs validated, errors handled, the change is covered by a test.",
        playbook="Think in contracts and failure modes. Validate at the boundary, keep "
        "the core pure, make state changes idempotent, and prove it with a test.",
        match_keywords=("backend", "api", "endpoint", "server", "database", "service"),
        skills=("tdd", "diagnose"),
        tools=("Read", "Edit", "Bash", "Grep"),
    ),
    Persona(
        id="principal-test-engineer",
        domain="Test strategy, coverage, and regression safety.",
        when_to_equip="Writing tests, raising coverage, or reproducing a bug as a test.",
        verification_bar="Tests fail before the fix and pass after; they assert behavior, not internals.",
        playbook="Test behavior at the seam, not implementation detail. Make the failing "
        "case first, keep tests fast and deterministic, and name them for the behavior.",
        match_keywords=("test", "tests", "coverage", "regression", "tdd", "fixture"),
        skills=("tdd", "verify"),
        tools=("Read", "Edit", "Bash"),
    ),
    Persona(
        id="principal-docs-engineer",
        domain="Technical writing, READMEs, and developer-facing documentation.",
        when_to_equip="Writing or revising docs, READMEs, or explanatory comments.",
        verification_bar="A new reader can act on it; examples run; nothing contradicts the code.",
        playbook="Write for the reader's next action. Lead with the why, show a runnable "
        "example, and keep claims verifiable against the code.",
        match_keywords=("docs", "documentation", "readme", "guide", "tutorial", "changelog"),
        skills=("init",),
        tools=("Read", "Edit", "Write"),
    ),
)


def default_config() -> PersonasConfig:
    """A complete, sensible fallback config used when no ``personas.toml`` is present."""
    return PersonasConfig(
        personas=DEFAULT_PERSONAS,
        cache=CachePolicy(),
        default_persona_id="principal-backend-engineer",
    )


# --------------------------------------------------------------------------- #
# Loading / validation                                                          #
# --------------------------------------------------------------------------- #


def load_config(path: str | os.PathLike[str] | None = None) -> PersonasConfig:
    """Load ``personas.toml`` from ``path`` (or return :func:`default_config`).

    If ``path`` is ``None`` or does not exist, the default config is returned so the
    engine always has a roster. A *malformed* config (no personas, duplicate ids, an
    unknown ``default_persona``) raises :class:`RegistryError`.
    """
    if path is None:
        return default_config()
    p = os.fspath(path)
    if not os.path.exists(p):
        return default_config()
    with open(p, "rb") as fh:
        raw = tomllib.load(fh)
    return from_mapping(raw)


def default_registry_path() -> str:
    """Absolute path to the roster shipped with the pack (``<pack>/personas.toml``).

    The one canonical answer to "where is the registry": the equip/match engine, the
    warm cache, the CLI, and the equip-on-task-pickup hook all resolve the shipped
    roster through here (or :func:`load_default`) instead of each re-deriving the path.
    """
    pack_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(pack_root, "personas.toml")


def load_default() -> PersonasConfig:
    """Load the roster shipped with the pack — the registry every consumer starts from.

    Equivalent to ``load_config(default_registry_path())``; degrades to
    :func:`default_config` (the built-in roster) if the shipped file is missing, so a
    caller always gets a usable registry.
    """
    return load_config(default_registry_path())


#: Text fields whose absence makes a persona *semantically* incomplete (as opposed to
#: structurally invalid, which loading rejects outright). Kept as data so the integrity
#: lint below reads as one obvious rule.
_REQUIRED_TEXT = ("domain", "when_to_equip", "verification_bar", "playbook")


def validate(config: PersonasConfig) -> list[str]:
    """Return registry *integrity* issues (empty list == healthy).

    Loading already rejects anything structurally invalid — a missing/duplicate/
    malformed ``id``, an unknown ``default_persona``, a bad ``weight``, a broken cache
    policy. This is the complementary *semantic-completeness* check the foundation
    exposes so the CLI (e.g. a ``personas lint``), the equip hook, and tests can assert
    every persona is actually usable: it has a domain, a playbook, a verification bar,
    signal to match on, and the skills/tools it brings.

    It returns human-readable strings rather than raising, so a caller can warn and keep
    going — the engine still runs on an incomplete persona, it just routes and overlays
    less well.
    """
    issues: list[str] = []
    for p in config.personas:
        for field in _REQUIRED_TEXT:
            if not getattr(p, field):
                issues.append(f"{p.id}: missing {field}")
        if not p.match_keywords:
            issues.append(f"{p.id}: no match_keywords (cannot be matched by keyword)")
        if not p.skills:
            issues.append(f"{p.id}: brings no skills")
        if not p.tools:
            issues.append(f"{p.id}: brings no tools")
    return issues


def from_mapping(raw: Mapping[str, object]) -> PersonasConfig:
    """Build a :class:`PersonasConfig` from a parsed-TOML mapping.

    Kept separate from :func:`load_config` so tests can drive it from a dict and the
    CLI can reuse the same validation on an already-parsed document.
    """
    personas = _parse_personas(raw.get("persona"))
    cache = _parse_cache(raw.get("cache"))

    reg = raw.get("registry") or {}
    if not isinstance(reg, Mapping):
        raise RegistryError("[registry] must be a table")
    default_id = reg.get("default_persona")
    default_id = str(default_id) if default_id is not None else None

    return _finalise(personas=personas, cache=cache, default_persona_id=default_id)


def _finalise(
    *,
    personas: list[Persona],
    cache: CachePolicy,
    default_persona_id: str | None,
) -> PersonasConfig:
    if not personas:
        raise RegistryError("roster is empty: at least one [[persona]] is required")
    ids = [p.id for p in personas]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise RegistryError(f"duplicate persona id(s): {dupes}")
    if default_persona_id is not None and default_persona_id not in ids:
        raise RegistryError(
            f"default_persona {default_persona_id!r} is not in the roster {sorted(ids)}"
        )
    return PersonasConfig(
        personas=tuple(personas),
        cache=cache,
        default_persona_id=default_persona_id,
    )


# ---- section parsers ------------------------------------------------------- #


def _as_list_of_tables(value: object, section: str) -> list[Mapping[str, object]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RegistryError(f"[[{section}]] must be an array of tables")
    out: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RegistryError(f"each [[{section}]] entry must be a table")
        out.append(item)
    return out


def _str_list(value: object, what: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RegistryError(f"{what} must be an array of strings")
    return tuple(str(v) for v in value)


def _clean_terms(values: tuple[str, ...], *, lower: bool) -> tuple[str, ...]:
    """Trim, drop blanks, and de-duplicate a term list, preserving first-seen order.

    Hands the match engine clean signal: keywords are lowercased (and compared
    lowercased for dedup) so ``"API"``/``"api"`` collapse to one; skills/tools keep
    their case (``"Read"``) but still trim and dedup. A term that is empty or all
    whitespace is dropped rather than smuggled through as a phantom keyword.
    """
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        term = v.strip().lower() if lower else v.strip()
        if not term or term in seen:
            continue
        seen.add(term)
        out.append(term)
    return tuple(out)


def _parse_weight(pid: str, raw: object) -> float:
    """Parse a persona ``weight``: a finite number > 0 (it feeds the match tie-break).

    The equip engine orders ties by ``(score, weight, id)``. A NaN weight makes that
    sort order undefined, and a non-positive weight inverts the intended priority — so
    both are rejected here, at the boundary, rather than corrupting routing later.
    """
    try:
        weight = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise RegistryError(f"persona {pid!r} weight must be a number, got {raw!r}")
    if not math.isfinite(weight) or weight <= 0:
        raise RegistryError(
            f"persona {pid!r} weight must be a finite number > 0, got {weight!r}"
        )
    return weight


def _parse_personas(value: object) -> list[Persona]:
    rows = _as_list_of_tables(value, "persona")
    if not rows:
        return list(DEFAULT_PERSONAS)
    personas: list[Persona] = []
    for i, r in enumerate(rows):
        if "id" not in r:
            raise RegistryError(f"[[persona]] #{i} missing 'id'")
        pid = str(r["id"]).strip()
        if not _VALID_ID.match(pid):
            raise RegistryError(
                f"[[persona]] #{i} id {str(r['id'])!r} is not a valid kebab-case id "
                "(lowercase alphanumerics in hyphen-separated groups, e.g. "
                "'principal-backend-engineer')"
            )
        personas.append(
            Persona(
                id=pid,
                domain=str(r.get("domain", "")),
                when_to_equip=str(r.get("when_to_equip", "")),
                verification_bar=str(r.get("verification_bar", "")),
                playbook=str(r.get("playbook", "")).strip(),
                match_keywords=_clean_terms(
                    _str_list(r.get("match_keywords"), f"persona {pid!r} match_keywords"),
                    lower=True,
                ),
                skills=_clean_terms(_str_list(r.get("skills"), f"persona {pid!r} skills"), lower=False),
                tools=_clean_terms(_str_list(r.get("tools"), f"persona {pid!r} tools"), lower=False),
                weight=_parse_weight(pid, r.get("weight", 1.0)),
            )
        )
    return personas


def _parse_cache(value: object) -> CachePolicy:
    """Parse ``[cache]``. Accepts minute/hour convenience keys or explicit seconds.

    Precedence per dimension: an explicit ``*_seconds`` key wins over the
    minute/hour convenience key, which wins over the default.
    """
    if value is None:
        return CachePolicy()
    if not isinstance(value, Mapping):
        raise RegistryError("[cache] must be a table")

    idle = CachePolicy().idle_ttl_seconds
    if "idle_ttl_minutes" in value:
        idle = float(value["idle_ttl_minutes"]) * 60.0
    if "idle_ttl_seconds" in value:
        idle = float(value["idle_ttl_seconds"])

    ceiling = CachePolicy().ceiling_ttl_seconds
    if "ceiling_ttl_hours" in value:
        ceiling = float(value["ceiling_ttl_hours"]) * 3600.0
    if "ceiling_ttl_seconds" in value:
        ceiling = float(value["ceiling_ttl_seconds"])

    return CachePolicy(idle_ttl_seconds=idle, ceiling_ttl_seconds=ceiling)

"""provider-forge — the catalog reader.

Loads ``catalog.toml`` (the source of truth) into typed, immutable records and
provides the derived views the CLI renders:

- :func:`load_catalog`     parse + validate ``catalog.toml`` into a :class:`Catalog`.
- :class:`Provider`        one provider (claude, codex, gemini, …): cli/auth/status/overlay.
- :class:`Model`           one (provider, model) row: id/model/run_target/costs/reasoning.
- :meth:`Catalog.live`     the live providers (CLI installed + authed, runnable now).
- :meth:`Catalog.models`   flat (provider, model) rows, optionally live-only.
- :meth:`Catalog.roster_tiers`  the cost-ordered tier list model-advisor consumes.

Pure stdlib: TOML via :mod:`tomllib` (Python >= 3.11) with a :mod:`tomli`
fallback below it, exactly mirroring model-advisor's loader shim. No I/O beyond
reading the catalog file; no third-party deps.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

try:  # Python >= 3.11 ships tomllib; older interpreters fall back to tomli.
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised only on < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

SCHEMA_VERSION = "provider-forge.v1"

# The catalog file ships at the pack root, next to pack.toml.
_DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "catalog.toml"

# Provider status values the catalog may declare.
STATUS_LIVE = "live"
STATUS_SCAFFOLD = "scaffold"


class CatalogError(Exception):
    """Raised when catalog.toml is missing, unparseable, or malformed."""


@dataclass(frozen=True)
class Model:
    """One (provider, model) row from the catalog.

    ``provider`` is the binding key (claude/codex/…); ``id`` is the short tier
    handle (haiku/spark/…); ``model`` is the wire model name. ``run_target`` is
    the gc session config this pair dispatches through. Costs are $/MTok.
    """

    provider: str
    id: str
    model: str
    run_target: str
    in_cost: float
    out_cost: float
    context: Optional[int] = None
    default_reasoning: Optional[str] = None
    note: Optional[str] = None
    exclude_from_roster: bool = False

    @property
    def cost_key(self) -> float:
        """Cost-ordering key: sum of input + output $/MTok (rank 1 = cheapest)."""
        return self.in_cost + self.out_cost


@dataclass(frozen=True)
class Provider:
    """One provider entry: its CLI, auth file, overlay, status, and models."""

    name: str
    cli: str
    overlay: str
    status: str
    native: bool = False
    auth: Optional[str] = None
    models_cache: Optional[str] = None
    reasoning_levels: tuple[str, ...] = ()
    default_reasoning: Optional[str] = None
    models: tuple[Model, ...] = ()

    @property
    def is_live(self) -> bool:
        return self.status == STATUS_LIVE

    def auth_path(self) -> Optional[Path]:
        """The provider's auth file as an absolute path (``~`` expanded), or None."""
        if not self.auth:
            return None
        return Path(os.path.expanduser(self.auth))


@dataclass(frozen=True)
class Catalog:
    """The parsed catalog: schema metadata + all providers."""

    schema_version: str
    default_provider: str
    providers: tuple[Provider, ...] = field(default_factory=tuple)

    # -- provider views ------------------------------------------------------
    def live(self) -> list[Provider]:
        """Live providers, in catalog declaration order."""
        return [p for p in self.providers if p.is_live]

    def scaffold(self) -> list[Provider]:
        """Scaffold providers (overlay present, CLI not yet installed)."""
        return [p for p in self.providers if not p.is_live]

    def provider(self, name: str) -> Provider:
        for p in self.providers:
            if p.name == name:
                return p
        raise KeyError(name)

    # -- model views ---------------------------------------------------------
    def models(self, *, live_only: bool = True) -> list[Model]:
        """All (provider, model) rows; live providers only unless ``live_only=False``.

        Preserves catalog order: providers in declaration order, models in the
        order they appear under each provider.
        """
        out: list[Model] = []
        for p in self.providers:
            if live_only and not p.is_live:
                continue
            out.extend(p.models)
        return out

    def roster_models(self, providers: Optional[Iterable[str]] = None) -> list[Model]:
        """Cost-ordered models for the advisor roster.

        Every LIVE provider's models except those flagged
        ``exclude_from_roster = true``, sorted ascending by combined $/MTok cost.
        Ties break by (provider, id) for a deterministic order. Optionally
        restrict to ``providers`` (an allow-list of provider names).
        """
        allow = set(providers) if providers is not None else None
        rows = [
            m
            for m in self.models(live_only=True)
            if not m.exclude_from_roster
            and (allow is None or m.provider in allow)
        ]
        rows.sort(key=lambda m: (m.cost_key, m.provider, m.id))
        return rows

    def roster_tiers(
        self, providers: Optional[Iterable[str]] = None
    ) -> list[dict[str, Any]]:
        """The advisor ``[[tier]]`` payloads, rank-assigned (rank 1 = cheapest).

        Each dict carries exactly the fields a model-advisor tier emits:
        ``id, provider, model, run_target, rank, in_cost, out_cost``.
        """
        tiers: list[dict[str, Any]] = []
        for rank, m in enumerate(self.roster_models(providers), start=1):
            tiers.append(
                {
                    "id": m.id,
                    "provider": m.provider,
                    "model": m.model,
                    "run_target": m.run_target,
                    "rank": rank,
                    "in_cost": m.in_cost,
                    "out_cost": m.out_cost,
                }
            )
        return tiers

    def __iter__(self) -> Iterator[Provider]:
        return iter(self.providers)


# --------------------------------------------------------------------------- #
# Parsing                                                                       #
# --------------------------------------------------------------------------- #

def _require(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise CatalogError(f"missing required key {key!r} in {where}")
    return d[key]


def _parse_model(provider: str, raw: dict, idx: int) -> Model:
    where = f"providers.{provider}.models[{idx}]"
    if not isinstance(raw, dict):
        raise CatalogError(f"{where} is not a table")
    return Model(
        provider=provider,
        id=str(_require(raw, "id", where)),
        model=str(_require(raw, "model", where)),
        run_target=str(_require(raw, "run_target", where)),
        in_cost=float(_require(raw, "in_cost", where)),
        out_cost=float(_require(raw, "out_cost", where)),
        context=int(raw["context"]) if raw.get("context") is not None else None,
        default_reasoning=raw.get("default_reasoning"),
        note=raw.get("note"),
        exclude_from_roster=bool(raw.get("exclude_from_roster", False)),
    )


def _parse_provider(name: str, raw: dict) -> Provider:
    where = f"providers.{name}"
    if not isinstance(raw, dict):
        raise CatalogError(f"{where} is not a table")
    status = str(raw.get("status", STATUS_SCAFFOLD))
    if status not in (STATUS_LIVE, STATUS_SCAFFOLD):
        raise CatalogError(
            f"{where}: status must be {STATUS_LIVE!r} or {STATUS_SCAFFOLD!r}, got {status!r}"
        )
    raw_models = raw.get("models", []) or []
    if not isinstance(raw_models, list):
        raise CatalogError(f"{where}.models must be an array of tables")
    models = tuple(
        _parse_model(name, m, i) for i, m in enumerate(raw_models)
    )
    levels = raw.get("reasoning_levels", []) or []
    if not isinstance(levels, list):
        raise CatalogError(f"{where}.reasoning_levels must be an array")
    return Provider(
        name=name,
        cli=str(_require(raw, "cli", where)),
        overlay=str(raw.get("overlay", name)),
        status=status,
        native=bool(raw.get("native", False)),
        auth=raw.get("auth"),
        models_cache=raw.get("models_cache"),
        reasoning_levels=tuple(str(x) for x in levels),
        default_reasoning=raw.get("default_reasoning"),
        models=models,
    )


def parse_catalog(data: dict) -> Catalog:
    """Build a :class:`Catalog` from an already-decoded TOML mapping."""
    if not isinstance(data, dict):
        raise CatalogError("catalog root is not a table")

    schema = str(data.get("schema_version", SCHEMA_VERSION))
    default_provider = str(data.get("default_provider", "claude"))

    raw_providers = data.get("providers", {})
    if not isinstance(raw_providers, dict):
        raise CatalogError("[providers] must be a table of provider entries")

    providers = tuple(
        _parse_provider(name, raw)
        for name, raw in raw_providers.items()
    )
    if not providers:
        raise CatalogError("catalog declares no [providers.*] entries")

    return Catalog(
        schema_version=schema,
        default_provider=default_provider,
        providers=providers,
    )


def load_catalog(path: str | os.PathLike[str] | None = None) -> Catalog:
    """Load and validate ``catalog.toml`` from ``path`` (default: the pack root)."""
    p = Path(path) if path is not None else _DEFAULT_CATALOG
    if not p.is_file():
        raise CatalogError(f"catalog not found: {p}")
    try:
        with open(p, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:  # pragma: no cover - defensive
        raise CatalogError(f"{p}: invalid TOML: {e}") from e
    return parse_catalog(data)


def default_catalog_path() -> Path:
    """The catalog file location this pack ships (pack root / catalog.toml)."""
    return _DEFAULT_CATALOG

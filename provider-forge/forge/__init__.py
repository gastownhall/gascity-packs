"""provider-forge — the canonical provider × model catalog for Gas City.

A pure-stdlib reader over ``catalog.toml`` (the source of truth: providers ×
models, ``status`` live|scaffold, ``run_target``, costs, ``reasoning_levels``,
``exclude_from_roster``). It powers four read-mostly surfaces:

- ``forge list``    — providers + models (live by default; ``--all`` adds scaffolds).
- ``forge doctor``  — per-live-provider CLI-on-PATH + auth-file readiness.
- ``forge roster``  — generate model-advisor's cost-ordered ``[[tier]]`` roster
  (the integration: maintain the model list once, here).
- ``forge targets`` — the ``run_target`` gc session configs the catalog expects.

Public surface (what the CLI and other tools build on):

- :mod:`forge.catalog` — :func:`~forge.catalog.load_catalog` into a
  :class:`~forge.catalog.Catalog` of :class:`~forge.catalog.Provider` /
  :class:`~forge.catalog.Model` records, plus the cost-ordered
  :meth:`~forge.catalog.Catalog.roster_tiers` view.
- :mod:`forge.cli`     — the ``list`` / ``doctor`` / ``roster`` / ``targets``
  command implementations and :func:`~forge.cli.render_roster_toml`.
"""

from __future__ import annotations

SCHEMA_VERSION = "provider-forge.v1"

from forge.catalog import (  # noqa: E402  (re-export after module docstring)
    Catalog,
    CatalogError,
    Model,
    Provider,
    load_catalog,
    parse_catalog,
    default_catalog_path,
)

__all__ = [
    "SCHEMA_VERSION",
    "Catalog",
    "CatalogError",
    "Model",
    "Provider",
    "load_catalog",
    "parse_catalog",
    "default_catalog_path",
]

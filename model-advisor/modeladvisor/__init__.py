"""model-advisor — Conservative Constrained Thompson Sampling (CC-TS) model-tier advisor.

Clean-room implementation of the CC-TS decision rule described in
``docs/DESIGN.md``. The advisor recommends the *cost-minimal* model tier for each
``(provider, agent, shape, tier)`` cell, subject to a per-task
quality-preservation guarantee.

Public surface (the pieces other beads / the CLI build on):

- :mod:`modeladvisor.config`  — load/validate ``advisor.toml`` into an
  :class:`~modeladvisor.config.AdvisorConfig` (roster, shapes, tolerance
  classes, hyperparameters).
- :mod:`modeladvisor.store`   — the cell store: build per-cell ``Beta(a, b)``
  posteriors from ``.beads/telemetry/invocations.jsonl`` and persist/rebuild the
  ``advisor-cells.json`` cache.
- :mod:`modeladvisor.engine`  — :func:`~modeladvisor.engine.recommend` and
  :func:`~modeladvisor.engine.inspect`, the pure/deterministic decision rule.

The engine is stdlib-only (no numpy/scipy): it uses a Wilson-style normal lower
confidence bound on the Beta posterior, exactly as DESIGN §5.2 specifies for the
v1 production default.
"""

from __future__ import annotations

SCHEMA_VERSION = "advisor.v1"

# Re-exported for convenience so callers can ``from modeladvisor import ...``.
from modeladvisor.config import (  # noqa: E402  (re-export after module docstring)
    AdvisorConfig,
    Hyperparams,
    Shape,
    Tier,
    ToleranceClass,
    load_config,
    default_config,
    SAMPLE_TOML,
)
from modeladvisor.store import Cell, CellStore  # noqa: E402
from modeladvisor.engine import recommend, inspect  # noqa: E402

__all__ = [
    "SCHEMA_VERSION",
    "AdvisorConfig",
    "Hyperparams",
    "Shape",
    "Tier",
    "ToleranceClass",
    "load_config",
    "default_config",
    "SAMPLE_TOML",
    "Cell",
    "CellStore",
    "recommend",
    "inspect",
]

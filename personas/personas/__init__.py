"""personas — dynamic principal-engineer persona equip for Gas City agents.

A pure-stdlib toolkit that picks the best-fit principal-engineer persona for a task,
equips it (materializing it into a shared warm cache so other agents reuse it), and
ages it out after a period of disuse. It does NOT run a backend; it is a registry, a
match rule, and a warm-cache lifecycle, surfaced as a CLI and a gas-town hook.

Public surface (what the CLI and the equip hook build on):

- :mod:`personas.registry`  — load + validate the roster and the warm-cache TTL
  policy from ``personas.toml`` (:class:`~personas.registry.Persona`,
  :class:`~personas.registry.PersonasConfig`).
- :mod:`personas.match`     — the equip/match engine: score every persona against a
  task description and return the best fit, explainably
  (:func:`~personas.match.match_persona`).
- :mod:`personas.cache`     — the warm-cache + TTL lifecycle: materialize, reuse
  (sliding-idle refresh), and evict on the configured policy
  (:class:`~personas.cache.WarmCache`).
- :mod:`personas.cli`       — the ``list`` / ``show`` / ``match`` / ``equip`` /
  ``cache`` / ``sweep`` command implementations.
"""

from __future__ import annotations

SCHEMA = "personas.v0"
__version__ = "0.1.0"

__all__ = ["SCHEMA", "__version__"]

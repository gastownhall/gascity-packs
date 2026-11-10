"""City infrastructure, recognised by its argv: the pack's copy of gascity
``internal/runtime/proctable/infrastructure_argv.go``.

Each entry is the argv words after argv[0] (which is ignored: these are
re-execs of whatever the operator's binary is called) that mark a
long-lived city infrastructure process: gc's managed Dolt scope watchdog,
bd's database proxy, gc's detached nudge poller. Such a process and its
whole subtree are never killed with a session (:mod:`.procs`).

CI checks this table against gc's ``IsCityInfrastructureArgv`` at the
pinned gascity commit (``tests/infra_argv_drift.py``), so a verb gc adds or
renames fails the pack's build instead of drifting.
"""

from __future__ import annotations

from typing import Final, Sequence, Tuple

MANAGED_DOLT_SCOPE_WATCHDOG_VERB: Final = "__gc-managed-dolt-scope-watchdog"
BD_PROXY_CHILD_VERB: Final = "db-proxy-child"
NUDGE_POLLER_VERB: Final = "nudge"
NUDGE_POLLER_SUBVERB: Final = "poll"

INFRASTRUCTURE_ARGV: Final[Tuple[Tuple[str, ...], ...]] = (
    (MANAGED_DOLT_SCOPE_WATCHDOG_VERB,),
    (BD_PROXY_CHILD_VERB,),
    (NUDGE_POLLER_VERB, NUDGE_POLLER_SUBVERB),
)
"""argv[1:] prefixes of city infrastructure (gc ``IsCityInfrastructureArgv``)."""


def infrastructure_prefix(argv: Sequence[str]) -> Tuple[str, ...]:
    """The :data:`INFRASTRUCTURE_ARGV` entry ``argv`` matches, or ``()``."""
    for prefix in INFRASTRUCTURE_ARGV:
        if len(argv) > len(prefix) and tuple(argv[1 : 1 + len(prefix)]) == prefix:
            return prefix
    return ()


def is_infrastructure_argv(argv: Sequence[str]) -> bool:
    """gc's ``proctable.IsCityInfrastructureArgv``: argv[0] is ignored."""
    return infrastructure_prefix(argv) != ()

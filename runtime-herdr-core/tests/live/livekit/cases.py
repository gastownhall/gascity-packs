"""The holder-crash matrix: which defence each case turns on, which kill it
takes, and what must happen to the city infrastructure an agent started.

Defences:

* **strip** (W): the pack's launcher removes ``HC_SCOPE`` at the agent's
  root, so hc's holder-loss sweep targets nothing the agent starts;
* **rescope** (S): the launcher moves the agent into its own scope under
  ``gascity-agents.slice``, out of the holder's ``hc-hold-*`` cgroup;
* **infra_scope**: the managed store and its watchdog get a scope of their
  own under ``gascity-infra.slice``, as gc does for infrastructure a gc
  command starts from inside an agent session (here the stand-in spawner
  does it with gc's ``systemd-run`` argv).

Case C turns everything off: the agents run as plain hc programs with no
launcher, so the test must see the infrastructure die (the negative control).

Kills: **K1** SIGKILLs the holder process (hc then sweeps by ``HC_SCOPE``);
**K2** SIGKILLs the holder's whole systemd unit, as systemd-oomd does (only
where hc places holders in units: the systemd lane).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Final, List, Literal, Optional, Tuple

Lane = Literal["plain", "systemd"]
Kill = Literal["K1", "K2"]
Expect = Literal["survives", "swept"]
WitnessExpect = Literal["survives", "dies"]
Role = Literal["watchdog", "dolt", "proxy"]

LANES: Final[Tuple[Lane, ...]] = ("plain", "systemd")
ROLES: Final[Tuple[Role, ...]] = ("watchdog", "dolt", "proxy")
SCOPED_ROLES: Final = frozenset({"watchdog", "dolt"})
"""What gc's infrastructure scope moves: the store and its watchdog. bd's
proxy is started by bd, not gc, and stays where the agent is."""

K2_AB_DEFERRED: Final = (
    "a cgroup-wide kill of cases A and B needs gc's own infrastructure scope around a real "
    "managed store started from a city; a later change adds these two runs"
)


@dataclass(frozen=True)
class Case:
    name: str
    strip: bool
    rescope: bool
    infra_scope: bool
    meaning: str


CASES: Final[Dict[str, Case]] = {
    "A": Case("A", strip=True, rescope=True, infra_scope=True, meaning="production"),
    "B": Case("B", strip=True, rescope=False, infra_scope=True, meaning="no re-scope"),
    "C": Case("C", strip=False, rescope=False, infra_scope=False, meaning="negative control: no launcher"),
    "D": Case("D", strip=True, rescope=True, infra_scope=False, meaning="launcher only"),
}


@dataclass(frozen=True)
class Run:
    case: Case
    kill: Kill
    lane: Lane
    expect: Expect
    deferred: Optional[str] = None

    @property
    def id(self) -> str:
        return f"{self.case.name}-{self.kill}-{self.lane}"


def expectation(case: Case, kill: Kill) -> Expect:
    """What happens to the agent-started infrastructure. Under K1 only the
    sweep can reach it, and only the strip prevents that; under K2 everything
    left in the holder's cgroup dies, so the negative control is the one case
    (of those this tier runs) that loses it."""
    if kill == "K1":
        return "survives" if case.strip else "swept"
    return "swept" if not case.rescope else "survives"


def witness_expectation(kill: Kill) -> WitnessExpect:
    """The negative control's witness: a process the agent leaves in the
    holder's cgroup with ``HC_SCOPE`` removed, so hc's sweep cannot reach it.
    It survives K1 and dies under K2, which shows the cgroup kill itself (not
    the sweep) does the killing."""
    return "dies" if kill == "K2" else "survives"


def matrix() -> List[Run]:
    """Every run: K1 for A-D on both lanes, K2 on the systemd lane (A and B deferred)."""
    runs: List[Run] = []
    for lane in LANES:
        for case in CASES.values():
            runs.append(Run(case, "K1", lane, expectation(case, "K1")))
    for case in CASES.values():
        deferred = K2_AB_DEFERRED if case.name in ("A", "B") else None
        runs.append(Run(case, "K2", "systemd", expectation(case, "K2"), deferred))
    return runs


def in_holder_cgroup(case: Case, role: Role, lane: Lane) -> Optional[bool]:
    """Whether ``role`` is expected inside the holder's ``hc-hold-*`` unit
    before the kill; None on the plain lane, where hc places no units."""
    if lane == "plain":
        return None
    if case.infra_scope and role in SCOPED_ROLES:
        return False
    return not case.rescope

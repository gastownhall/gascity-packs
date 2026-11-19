"""The soak profiles (``soak profile``, ``soak schedule``): the city, its
shape, its load and the length of each half, and the VM timers that run the
switch to v2 and the end.

Soak 2 repeats Soak 1's city shape and load rate on a fresh city with shorter
halves, so the two runs compare pack against pack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

from soaklib import Rec, SoakPaths

HOUR_S = 3600


@dataclass(frozen=True)
class Profile:
    """One soak run."""

    name: str
    city: str
    steady: int
    burst: int
    load: str
    mode: str
    legacy_s: int
    v2_s: int

    def data(self, paths: SoakPaths) -> Path:
        return paths.data_root / self.city

    def as_rec(self, paths: SoakPaths) -> Rec:
        return {
            "name": self.name,
            "city": self.city,
            "steady": self.steady,
            "burst": self.burst,
            "load": self.load,
            "mode": self.mode,
            "legacy_s": self.legacy_s,
            "v2_s": self.v2_s,
            "data": str(self.data(paths)),
        }


PROFILES: Dict[str, Profile] = {
    "soak1": Profile("soak1", "hc-soak", steady=6, burst=10, load="soak", mode="abort", legacy_s=12 * HOUR_S, v2_s=12 * HOUR_S),
    "soak2": Profile("soak2", "hc-soak2", steady=6, burst=10, load="soak", mode="abort", legacy_s=6 * HOUR_S, v2_s=6 * HOUR_S),
}
"""Every soak run by name; ``soak-phase4`` defaults to ``soak1``."""

DEFAULT_PROFILE = "soak1"


def profile(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError:
        raise LookupError(f"no soak profile {name!r} (known: {', '.join(sorted(PROFILES))})") from None


def timer_units(city: str) -> Tuple[str, str]:
    """The transient timers ``soak schedule`` creates for ``city``: the switch
    to v2 and the end."""
    return (f"soak-{city}-v2-switch.timer", f"soak-{city}-end.timer")


def schedule_argv(prof: Profile, paths: SoakPaths, env: Mapping[str, str]) -> List[List[str]]:
    """The ``systemd-run --user`` commands that run the switch to v2
    ``legacy_s`` after now and the end ``legacy_s + v2_s`` after now.

    A transient service gets the user manager's environment, not the
    caller's, so the caller's ``PATH`` (where gc, bd and dolt are) goes with it."""
    switch_timer, end_timer = timer_units(prof.city)
    bin_dir = paths.harness / "bin"
    path = env.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    jobs = (
        (switch_timer, prof.legacy_s, "switch to v2", [str(bin_dir / "soak-phase2"), prof.city, "soak-v2"]),
        (end_timer, prof.legacy_s + prof.v2_s, "end", [str(bin_dir / "soak-phase4"), "end", prof.name]),
    )
    return [
        [
            "systemd-run",
            "--user",
            f"--unit={unit[: -len('.timer')]}",
            f"--description=herdr-core soak {prof.name}: {what}",
            f"--on-active={after}s",
            "--timer-property=AccuracySec=1s",
            f"--setenv=PATH={path}",
            "--",
            *command,
        ]
        for unit, after, what, command in jobs
    ]


__all__ = ["DEFAULT_PROFILE", "PROFILES", "Profile", "profile", "schedule_argv", "timer_units"]

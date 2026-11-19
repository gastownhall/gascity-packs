"""``soak conf-run``: gc's runtime check and conformance run against the
pack, in a scratch city the harness removes after.

The pack starts no session and no core for an op that names no city
(``GC_EXEC_CITY_PATH`` unset), and the pinned gc gives ``gc runtime check``
and ``gc runtime conformance`` no city of their own. So both run with
``GC_EXEC_CITY_NAME``, ``GC_EXEC_CITY_PATH`` and ``GC_EXEC_STATE_DIR`` under
one fresh scratch directory: never a live city's path, because the
conformance kit starts and ends sessions in the city it is given. Every core
the run left under the scratch state root is stopped, then the directory is
removed, whatever failed."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional

from soakhc import Teardown
from soaklib import Rec, run, write_atomic

CONF_CITY_NAME = "soak-conf-scratch"
"""The scratch city's name: never a soak city's (those are ``hc-*``)."""

CHECK_TIMEOUT_S = 600.0
CONFORMANCE_TIMEOUT_S = 1800.0


@dataclass(frozen=True)
class ConfScratch:
    """One conformance run's scratch directory."""

    root: Path

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def city(self) -> Path:
        return self.root / "city"


def conf_env(base: Mapping[str, str], scratch: ConfScratch) -> Dict[str, str]:
    """``base`` with the scratch city and state root."""
    return dict(
        base,
        GC_EXEC_CITY_NAME=CONF_CITY_NAME,
        GC_EXEC_CITY_PATH=str(scratch.city),
        GC_EXEC_STATE_DIR=str(scratch.state),
    )


@dataclass(frozen=True)
class ConfRun:
    check: int
    conformance: int
    teardown: int
    scratch: str
    scratch_removed: bool

    @property
    def ok(self) -> bool:
        return self.check == 0 and self.conformance == 0 and self.teardown == 0 and self.scratch_removed

    def as_rec(self) -> Rec:
        return {
            "check": self.check,
            "conformance": self.conformance,
            "teardown": self.teardown,
            "scratch": self.scratch,
            "scratch_removed": self.scratch_removed,
        }


def conf_run(
    entry: str,
    out: Path,
    base_env: Mapping[str, str],
    *,
    teardown: Callable[[str], Teardown],
    gc_bin: str = "gc",
    tmp_dir: Optional[str] = None,
) -> ConfRun:
    """Run ``gc runtime check`` and ``gc runtime conformance --json`` on
    ``entry`` in a scratch city; write ``runtime-check.txt``,
    ``conformance.json``, ``conformance.err`` and ``conf-teardown.json`` to
    ``out``; stop the scratch cores with ``teardown`` and remove the scratch
    directory."""
    scratch = ConfScratch(Path(tempfile.mkdtemp(prefix="hcconf.", dir=tmp_dir)))
    try:
        scratch.state.mkdir(mode=0o700)
        os.chmod(scratch.state, 0o700)
        env = conf_env(base_env, scratch)
        cwd = str(scratch.root)
        check = run([gc_bin, "runtime", "check", entry], cwd=cwd, env=env, timeout=CHECK_TIMEOUT_S)
        (out / "runtime-check.txt").write_text(check.out + check.err, encoding="utf-8")
        conf = run([gc_bin, "runtime", "conformance", "--json", entry], cwd=cwd, env=env, timeout=CONFORMANCE_TIMEOUT_S)
        (out / "conformance.json").write_text(conf.out, encoding="utf-8")
        (out / "conformance.err").write_text(conf.err, encoding="utf-8")
        torn = teardown(str(scratch.state))
        write_atomic(out / "conf-teardown.json", json.dumps(torn.as_rec(), indent=2, sort_keys=True) + "\n")
    finally:
        shutil.rmtree(scratch.root, ignore_errors=True)
    return ConfRun(check.code, conf.code, 0 if torn.ok else 1, str(scratch.root), not scratch.root.exists())


__all__ = ["CONF_CITY_NAME", "ConfRun", "ConfScratch", "conf_env", "conf_run"]

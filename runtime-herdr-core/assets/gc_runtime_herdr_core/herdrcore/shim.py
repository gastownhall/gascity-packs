"""The in-agent ``hc`` shim, rendered from ``assets/shim/hc.in``.

``start`` (re)writes ``R/shim/bin/hc`` and ``R/shim/bin/herdr-core``
atomically whenever their content would change (another hc binary, another
discovery tuple). Each is a ``/bin/sh`` script that runs the template under
the pack's Python, isolated (``-I -S``), with the core's tuple baked in.
"""

from __future__ import annotations

import os
import shlex
from typing import Final, Mapping

from ..rpp.jsonval import dumps
from ..rpp.statedir import ensure_private_dir
from .config import read_private_file, write_private_file

SHIM_NAMES: Final = ("hc", "herdr-core")
CONFIG_MARKER: Final = "@CONFIG@"


def render(template: str, *, python: str, hc_bin: str, env: Mapping[str, str]) -> str:
    """The shim script for ``hc_bin`` and the core's discovery ``env``."""
    if template.count(CONFIG_MARKER) != 1:
        raise ValueError("the shim template must hold one config marker")
    config = dumps({"hc_bin": hc_bin, "env": dict(env)})
    code = template.replace(CONFIG_MARKER, repr(config))
    return f"#!/bin/sh\nexec {shlex.quote(python)} -I -S -c {shlex.quote(code)} \"$@\"\n"


def install(shim_dir: str, *, pack_dir: str, python: str, hc_bin: str, env: Mapping[str, str]) -> None:
    """Write the shims into ``shim_dir`` when they differ from what is there."""
    with open(os.path.join(pack_dir, "assets", "shim", "hc.in"), "r", encoding="utf-8") as handle:
        template = handle.read()
    content = render(template, python=python, hc_bin=hc_bin, env=env).encode("utf-8")
    ensure_private_dir(os.path.dirname(shim_dir))
    ensure_private_dir(shim_dir)
    for name in SHIM_NAMES:
        path = os.path.join(shim_dir, name)
        if read_private_file(path) != content:
            write_private_file(path, content, mode=0o700)

"""The pinned herdr-core for a live run, fetched and verified exactly as
``gc herdr-core install`` does it: the release manifest must agree with
``assets/hc-pin.json``, and the archive's sha256 must equal the pin's before
anything is written. Only the pinned binary is extracted; nothing is run.
The suites drive a binary only when :func:`unverified` finds it is that build."""

from __future__ import annotations

import os
from typing import Optional

from gc_runtime_herdr_core.herdrcore.config import BINARY_NAME
from gc_runtime_herdr_core.herdrcore.install import InstallError, directory_fetch, https_fetch, install, verify_installed
from gc_runtime_herdr_core.herdrcore.pin import HcPin, PinError, host_target
from gc_runtime_herdr_core.herdrcore.procs import default_source
from gc_runtime_herdr_core.rpp.cancel import CancelToken


class FetchError(Exception):
    """The pinned build could not be fetched or did not verify."""


def fetch_pinned(pin: HcPin, root: str, *, target: Optional[str] = None, releases_dir: Optional[str] = None) -> str:
    """Install the pinned build under ``root`` (``<root>/<version>/herdr-core``)
    and return the binary's path. ``releases_dir`` stands in for the release
    server (tests)."""
    try:
        name = target or host_target()
        fetch = directory_fetch(pin, releases_dir) if releases_dir else (lambda url, limit: https_fetch(url, limit))
        outcome = install(pin, root=root, target=name, fetch=fetch, procs=default_source(), cancel=CancelToken())
    except (InstallError, PinError, OSError) as err:
        raise FetchError(str(err)) from None
    return outcome.binary


def unverified(binary: str, pin: HcPin, *, target: Optional[str] = None) -> Optional[str]:
    """Why ``binary`` is not the pinned build :func:`fetch_pinned` installed
    (``<root>/<version>/herdr-core`` with its install record, the pin's
    archive and the recorded binary sha256), or None when it is."""
    try:
        name = target or host_target()
    except PinError as err:
        return str(err)
    version_dir = os.path.dirname(os.path.abspath(binary))
    if os.path.basename(binary) != BINARY_NAME or os.path.basename(version_dir) != str(pin.version):
        return f"{binary} is not <root>/{pin.version}/{BINARY_NAME}, where fetch_hc.py installs the pinned build"
    try:
        return verify_installed(pin, os.path.dirname(version_dir), name)
    except (PinError, OSError) as err:
        return f"{binary}: {err}"

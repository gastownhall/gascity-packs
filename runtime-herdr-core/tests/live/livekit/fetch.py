"""The pinned herdr-core for a live run, fetched and verified exactly as
``gc herdr-core install`` does it: the release manifest must agree with
``assets/hc-pin.json``, and the archive's sha256 must equal the pin's before
anything is written. Only the pinned binary is extracted; nothing is run."""

from __future__ import annotations

from typing import Optional

from gc_runtime_herdr_core.herdrcore.install import InstallError, directory_fetch, https_fetch, install
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

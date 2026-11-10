"""Staging a start config's files into the session's work directory, exactly
as the config carries them (gc stages nothing itself for this runtime).

Order and layout follow gc's own staging (gascity ``internal/runtime/staging.go``
and ``internal/overlay``): every ``pack_overlay_dirs`` entry, then
``overlay_dir``, then ``copy_files``. An overlay directory's top-level
``per-provider/`` subtree is not copied as such: only
``per-provider/<GC_PROVIDER>/``, flattened into the work directory, where
``GC_PROVIDER`` is the session environment's provider; a top-level ``.gc``
(gc's runtime mirror) is never staged. A missing source is skipped, as gc
does. Files keep their permission bits; later layers overwrite earlier ones.

gc JSON-merges its hook and settings files (``.claude/settings.json``,
``.gemini/settings.json``, ``.codex/hooks.json``, ``.cursor/hooks.json``,
``.agents/hooks.json``, ``.github/hooks/gascity.json``) into what the work
directory holds, and its Kiro overlay keeps an ``AGENTS.md`` already there.
This build does not merge: a file of either kind that existed before the
staging pass is left as it is, with a warning, so a rig's own settings are
never overwritten (a later layer of the same pass still wins, as in gc).

Not done here (gaps until gc stages on the host for packs): the merge
itself, a custom provider's family fallback, and the extra provider slots of
``install_agent_hooks``; only ``per-provider/<GC_PROVIDER>/`` is staged.
"""

from __future__ import annotations

import os
import shutil
from typing import Callable, Final, List, Optional, Set

from ..rpp.wire import StartConfig

PER_PROVIDER: Final = "per-provider"
RUNTIME_MIRROR: Final = ".gc"
MERGED_PATHS: Final = frozenset(
    os.path.join(*parts)
    for parts in (
        (".agents", "hooks.json"),
        (".claude", "settings.json"),
        (".gemini", "settings.json"),
        (".codex", "hooks.json"),
        (".cursor", "hooks.json"),
        (".github", "hooks", "gascity.json"),
    )
)
"""Files gc merges rather than copies (gascity ``internal/overlay/merge.go``)."""
KIRO: Final = "kiro"
KIRO_AGENTS_MD: Final = "AGENTS.md"


class StagingError(Exception):
    """A file could not be staged."""


def _copy_file(src: str, dst: str) -> None:
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, mode=0o755, exist_ok=True)
    if os.path.islink(dst) or os.path.isdir(dst):
        raise StagingError(f"cannot stage {src} over {dst}: not a regular file")
    shutil.copyfile(src, dst)
    shutil.copymode(src, dst)


class Stager:
    """One staging pass into ``work_dir``: what it wrote, and what it kept."""

    def __init__(self, work_dir: str) -> None:
        self.work_dir = work_dir
        self.staged: Set[str] = set()
        self.warnings: List[str] = []

    def _keep(self, rel: str, dst: str, keep: Callable[[str], bool]) -> bool:
        if not os.path.exists(dst) or not keep(rel):
            return False
        if rel == KIRO_AGENTS_MD:
            return True  # gc's Kiro overlay keeps any AGENTS.md already provided, this pass's included
        if dst in self.staged:
            return False
        self.warnings.append(f"kept the work directory's own {rel} (gc merges it; this runtime does not yet)")
        return True

    def copy_file(self, src: str, dst: str, rel: str, keep: Callable[[str], bool]) -> None:
        if self._keep(rel, dst, keep):
            return
        _copy_file(src, dst)
        self.staged.add(dst)

    def copy_tree(self, src: str, dst: str, *, skip: Optional[Callable[[str], bool]] = None, keep: Callable[[str], bool] = lambda rel: False) -> None:
        for root, dirs, files in os.walk(src):
            rel_root = os.path.relpath(root, src)
            rel_root = "" if rel_root == "." else rel_root
            kept = []
            for d in sorted(dirs):
                rel = os.path.join(rel_root, d)
                if skip is not None and skip(rel):
                    continue
                if os.path.islink(os.path.join(root, d)):
                    self.copy_file(os.path.join(root, d), os.path.join(dst, rel), rel, keep)
                    continue
                os.makedirs(os.path.join(dst, rel), mode=0o755, exist_ok=True)
                kept.append(d)
            dirs[:] = kept
            for name in sorted(files):
                rel = os.path.join(rel_root, name)
                if skip is not None and skip(rel):
                    continue
                self.copy_file(os.path.join(root, name), os.path.join(dst, rel), rel, keep)

    def overlay(self, src: str, provider: str) -> None:
        """Stage one overlay directory for ``provider``."""
        if not os.path.exists(src):
            return
        if not os.path.isdir(src):
            raise StagingError(f"overlay {src} is not a directory")
        self.copy_tree(src, self.work_dir, skip=_universal, keep=lambda rel: rel in MERGED_PATHS)
        if provider and os.sep not in provider and provider not in (".", ".."):
            provider_dir = os.path.join(src, PER_PROVIDER, provider)
            if os.path.isdir(provider_dir):
                self.copy_tree(
                    provider_dir,
                    self.work_dir,
                    skip=lambda rel: rel.split(os.sep, 1)[0] == RUNTIME_MIRROR,
                    keep=lambda rel: rel in MERGED_PATHS or (provider == KIRO and rel == KIRO_AGENTS_MD),
                )


def _universal(rel: str) -> bool:
    top = rel.split(os.sep, 1)[0]
    return top in (PER_PROVIDER, RUNTIME_MIRROR)


def copy_overlay(src: str, work_dir: str, provider: str) -> List[str]:
    """Stage one overlay directory for ``provider`` into ``work_dir``; returns warnings."""
    stager = Stager(work_dir)
    stager.overlay(src, provider)
    return stager.warnings


def stage_path(src: str, dst: str) -> None:
    """gc's ``StagePath``: a directory merges into ``dst``; a file lands at
    ``dst``, or inside it when ``dst`` is a directory."""
    if not os.path.exists(src):
        return
    if os.path.isdir(src):
        os.makedirs(dst, mode=0o755, exist_ok=True)
        Stager(dst).copy_tree(src, dst)
        return
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    if os.path.exists(dst) and os.path.samefile(src, dst):
        return
    _copy_file(src, dst)


def stage(cfg: StartConfig, provider: str) -> List[str]:
    """Stage everything ``cfg`` names into its work directory; returns warnings."""
    if not (cfg.pack_overlay_dirs or cfg.overlay_dir or cfg.copy_files):
        return []
    if not cfg.work_dir or not os.path.isabs(cfg.work_dir):
        raise StagingError("staging needs an absolute work_dir")
    try:
        os.makedirs(cfg.work_dir, mode=0o755, exist_ok=True)
        stager = Stager(cfg.work_dir)
        for overlay in cfg.pack_overlay_dirs:
            stager.overlay(overlay, provider)
        if cfg.overlay_dir:
            stager.overlay(cfg.overlay_dir, provider)
        for entry in cfg.copy_files:
            dst = os.path.join(cfg.work_dir, entry.rel_dst) if entry.rel_dst else cfg.work_dir
            stage_path(entry.src, dst)
    except OSError as err:
        raise StagingError(f"staging into the work directory failed: {err}") from None
    return stager.warnings

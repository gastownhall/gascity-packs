"""Staging a start config's files into the session's work directory, exactly
as the config carries them. The runtime declares ``fs.host``, so gc stages
the work directory on the host itself and leaves these fields out of the
config: then nothing is staged here. A gc older than ``fs.host``
(gastownhall/gascity#9023), or one whose cached handshake predates the
declaration, still sends them, and so does a current gc when it cannot read
whether a live box holds the name (``observe`` fails or answers unknown);
then they are staged here.

Order and layout follow gc's own staging (gascity ``internal/runtime/staging.go``
and ``internal/overlay``): every ``pack_overlay_dirs`` entry, then
``overlay_dir``, then ``copy_files``. An overlay directory's top-level
``per-provider/`` subtree is not copied as such: only
``per-provider/<GC_PROVIDER>/``, flattened into the work directory, where
``GC_PROVIDER`` is the session environment's provider; a top-level ``.gc``
(gc's runtime mirror) is never staged. A missing source is skipped, as gc
does. Files keep their permission bits; later layers overwrite earlier ones.

Nothing is written outside the work directory. Each path below it is opened
one component at a time from a directory descriptor, never through a
symlink, so a symlink where a file or directory would be written fails the
staging (gc writes through one); a file kept as it is (below) is only read.
Destinations join as gc joins them (Go's ``filepath.Join``: an absolute
``rel_dst`` stays below the work directory), and a ``copy_files`` entry
whose destination still leaves it is not staged, with a warning: gc adds its
hook files with city-relative destinations meant for container providers.

gc JSON-merges its hook and settings files (``.claude/settings.json``,
``.gemini/settings.json``, ``.codex/hooks.json``, ``.cursor/hooks.json``,
``.agents/hooks.json``, ``.github/hooks/gascity.json``) into what the work
directory holds, and its Kiro overlay keeps an ``AGENTS.md`` already there.
This build does not merge: a file of either kind that existed before the
staging pass is left as it is, with a warning, so a rig's own settings are
never overwritten (a later layer of the same pass still wins, as in gc).

Not done here (gc does them when it stages on the host under ``fs.host``):
the merge itself, a custom provider's family fallback, and the extra
provider slots of ``install_agent_hooks``; only
``per-provider/<GC_PROVIDER>/`` is staged.
"""

from __future__ import annotations

import errno
import os
import shutil
import stat
from typing import Callable, Final, List, Optional, Sequence, Set

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
_DIR_BELOW: Final = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class StagingError(Exception):
    """A file could not be staged."""


def _parts(work_dir: str, rel: str) -> Optional[List[str]]:
    """The components below ``work_dir`` of the destination gc names by
    ``rel`` (none for the work directory itself), or None when it leaves."""
    below = os.path.relpath(os.path.join(work_dir, rel.lstrip(os.sep)), work_dir).split(os.sep)
    if below == [os.curdir]:
        return []
    return None if below[0] == os.pardir else below


def _open_dir(work_dir: str, parts: Sequence[str]) -> int:
    """Open the directory ``parts`` below ``work_dir``, making what is
    missing, one component at a time and never through a symlink."""
    fd = os.open(work_dir, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for depth, part in enumerate(parts, 1):
            try:
                os.mkdir(part, 0o755, dir_fd=fd)
            except FileExistsError:
                pass
            try:
                child = os.open(part, _DIR_BELOW, dir_fd=fd)
            except OSError as err:
                if err.errno not in (errno.ENOTDIR, errno.ELOOP):
                    raise
                raise StagingError(f"{os.path.join(work_dir, *parts[:depth])} is a symlink or not a directory") from None
            fd, parent = child, fd
            os.close(parent)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _copy_file(src: str, work_dir: str, parts: Sequence[str]) -> None:
    """Copy the file ``src`` to ``parts`` below ``work_dir``, never through a
    symlink. A destination that already is ``src`` (a tree staged onto
    itself, or a hard link) is left as it is: opening it to write would empty
    it first (gc's copy does)."""
    if not stat.S_ISREG(os.stat(src).st_mode):
        raise StagingError(f"cannot stage {src}: not a regular file")
    fd = _open_dir(work_dir, parts[:-1])
    try:
        try:
            existing: Optional[os.stat_result] = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and not stat.S_ISREG(existing.st_mode):
            raise StagingError(f"cannot stage {src} over {os.path.join(work_dir, *parts)}: not a regular file")

        def below(name: str, flags: int) -> int:
            return os.open(name, flags | os.O_NOFOLLOW, 0o600, dir_fd=fd)

        with open(src, "rb") as reader:
            source = os.fstat(reader.fileno())
            if existing is not None and os.path.samestat(source, existing):
                return
            with open(parts[-1], "wb", opener=below) as writer:
                shutil.copyfileobj(reader, writer)
                os.fchmod(writer.fileno(), stat.S_IMODE(source.st_mode))
    finally:
        os.close(fd)


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

    def copy_file(self, src: str, parts: Sequence[str], rel: str, keep: Callable[[str], bool]) -> None:
        dst = os.path.join(self.work_dir, *parts)
        if self._keep(rel, dst, keep):
            return
        _copy_file(src, self.work_dir, parts)
        self.staged.add(dst)

    def copy_tree(self, src: str, at: Sequence[str] = (), *, skip: Optional[Callable[[str], bool]] = None, keep: Callable[[str], bool] = lambda rel: False) -> None:
        """Copy the tree ``src`` to ``at`` below the work directory."""
        for root, dirs, files in os.walk(src):
            rel_root = os.path.relpath(root, src)
            rel_root = "" if rel_root == "." else rel_root
            kept = []
            for d in sorted(dirs):
                rel = os.path.join(rel_root, d)
                if skip is not None and skip(rel):
                    continue
                if os.path.islink(os.path.join(root, d)):
                    self.copy_file(os.path.join(root, d), [*at, *rel.split(os.sep)], rel, keep)
                    continue
                if not os.path.isdir(os.path.join(self.work_dir, *at, rel)):
                    os.close(_open_dir(self.work_dir, [*at, *rel.split(os.sep)]))
                kept.append(d)
            dirs[:] = kept
            for name in sorted(files):
                rel = os.path.join(rel_root, name)
                if skip is not None and skip(rel):
                    continue
                self.copy_file(os.path.join(root, name), [*at, *rel.split(os.sep)], rel, keep)

    def overlay(self, src: str, provider: str) -> None:
        """Stage one overlay directory for ``provider``."""
        if not os.path.exists(src):
            return
        if not os.path.isdir(src):
            raise StagingError(f"overlay {src} is not a directory")
        self.copy_tree(src, skip=_universal, keep=lambda rel: rel in MERGED_PATHS)
        if provider and os.sep not in provider and provider not in (".", ".."):
            provider_dir = os.path.join(src, PER_PROVIDER, provider)
            if os.path.isdir(provider_dir):
                self.copy_tree(
                    provider_dir,
                    skip=lambda rel: rel.split(os.sep, 1)[0] == RUNTIME_MIRROR,
                    keep=lambda rel: rel in MERGED_PATHS or (provider == KIRO and rel == KIRO_AGENTS_MD),
                )


def _universal(rel: str) -> bool:
    top = rel.split(os.sep, 1)[0]
    return top in (PER_PROVIDER, RUNTIME_MIRROR)


def copy_overlay(src: str, work_dir: str, provider: str) -> List[str]:
    """Stage one overlay directory for ``provider`` into ``work_dir``; returns warnings."""
    os.makedirs(work_dir, mode=0o755, exist_ok=True)
    stager = Stager(work_dir)
    stager.overlay(src, provider)
    return stager.warnings


def stage_path(src: str, work_dir: str, rel: str = "") -> None:
    """gc's ``StagePath`` to ``rel`` below ``work_dir``, never outside it: a
    directory merges into the destination; a file lands there, or inside it
    when it is a directory. A source that is its own destination is skipped,
    a directory as well as a file, as gc skips it."""
    if not os.path.exists(src):
        return
    parts = _parts(work_dir, rel)
    if parts is None:
        raise StagingError("the destination leaves the work directory")
    is_tree = os.path.isdir(src)
    if not is_tree and (not parts or os.path.isdir(os.path.join(work_dir, *parts))):
        parts.append(os.path.basename(src))
    dst = os.path.join(work_dir, *parts)
    if os.path.exists(dst) and os.path.samefile(src, dst):
        return
    if is_tree:
        Stager(work_dir).copy_tree(src, parts)
    else:
        _copy_file(src, work_dir, parts)


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
            if _parts(cfg.work_dir, entry.rel_dst) is None:
                stager.warnings.append(f"did not stage {entry.src}: {entry.rel_dst} leaves the work directory")
                continue
            stage_path(entry.src, cfg.work_dir, entry.rel_dst)
    except OSError as err:
        raise StagingError(f"staging into the work directory failed: {err}") from None
    return stager.warnings

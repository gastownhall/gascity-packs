"""Unified installer for the magi pack.

Dispatches to per-target deployers under <pack-root>/<target>/. Records
state to .gc/runtime/packs/magi/state.json. Wraps every install in a bd
bead lifecycle (create, claim, close) with idempotency keyed on a
fingerprint of argv + env passthrough.

The ``--target claude`` path deploys directly from pack root via the
stage-and-swap pattern declared in plan v3 §7.1 STEP 0-6. Other targets
(``codex``, ``gemini``, ``openai``) invoke their own deploy script under
``<pack-root>/<target>/<script>``.

Post-deploy: when target is claude or codex and ``--skip-utilities`` is
unset, executes ``setup_utilities.sh`` so the ``.utilities/`` tree the
enforcement rules reference resolves portably.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path

from magi_common import BD_PUSH_TIMEOUT_SECONDS
from magi_common import CLIError
from magi_common import IDEMPOTENT_WINDOW_SECONDS
from magi_common import INSTALL_PLACEHOLDERS
from magi_common import PACK_DIR_PLACEHOLDER
from magi_common import SECRET_BEARING_FILES
from magi_common import SHAKEDOWN_TRIGGER_FILENAME
from magi_common import SUBSTITUTABLE_EXTENSIONS
from magi_common import TARGET_REGISTRY
from magi_common import attach_file_log
from magi_common import bd_available_current
from magi_common import bd_close
from magi_common import bd_create
from magi_common import bd_remember
from magi_common import bd_update
from magi_common import city_root
from magi_common import clear_inflight_sentinel
from magi_common import flag_fingerprint
from magi_common import load_pack_env
from magi_common import log_event
from magi_common import log_path
from magi_common import magi_utilities_source
from magi_common import now_utc_iso
from magi_common import pack_root
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import redact_secrets
from magi_common import runtime_dir
from magi_common import write_inflight_sentinel
from magi_common import write_state


_TARGET_CHOICES: tuple[str, ...] = ("claude", "codex", "gemini", "openai", "all")
_UTILITIES_AWARE_TARGETS: frozenset[str] = frozenset({"claude", "codex"})

# Subprocess timeouts.
_NPM_INSTALL_TIMEOUT_SECONDS: int = 600
_RSYNC_TIMEOUT_SECONDS: int = 900

# Per-surface deploy contract for the direct-deploy claude path (plan v3
# §7.2 surface-split table). Each entry maps a pack-source relative path
# to a deploy-side relative path. The deployer rsyncs each surface into
# the staging dir using these mappings.
_CLAUDE_DEPLOY_SURFACES: tuple[tuple[str, str], ...] = (
    ("CLAUDE.md", "CLAUDE.md"),
    ("settings.json.template", "settings.json"),
    ("agents", "agents"),
    ("claude-commands", "commands"),
    ("mcp-servers", "mcp-servers"),
    ("plugins", "plugins"),
    ("enforcement", "enforcement"),
    ("skills", "skills"),
    ("guidelines", "guidelines"),
    (".utilities", ".utilities"),
)

# Surfaces that participate in jq-equivalent deep-merge with any
# pre-existing deployed copy. Maps deploy-side relative path -> True.
_DEEP_MERGE_SURFACES: frozenset[str] = frozenset({"settings.json", ".mcp.json"})

# Rsync exclusions applied to every surface during the stage step.
_RSYNC_EXCLUDES: tuple[str, ...] = (
    ".DS_Store",
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    ".pytest_cache",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-install", allow_abbrev=False)
    parser.add_argument("--target", choices=_TARGET_CHOICES, required=True)
    parser.add_argument("--home", default=None, help="Override the install home directory.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; perform zero mutation.")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Forwarded to legacy deployers; never prompt."
    )
    parser.add_argument("--skip-prereqs", action="store_true", help="Forwarded to legacy deployers.")
    parser.add_argument(
        "--bd-push",
        action="store_true",
        help="After a successful install, run `bd dolt push`."
    )
    parser.add_argument("--no-bd", action="store_true", help="Suppress bd integration for this verb.")
    parser.add_argument(
        "--skip-utilities",
        action="store_true",
        help="Skip the post-deploy setup_utilities.sh step for claude/codex."
    )
    return parser


def _resolve_target_home(args: argparse.Namespace, target: str) -> str:
    if args.home: return os.path.expanduser(str(args.home))
    raw = str(TARGET_REGISTRY[target]["default_home"])
    return os.path.expanduser(raw)


def _build_env_passthrough(target: str) -> dict[str, str]:
    keys = TARGET_REGISTRY[target]["env"]
    if not isinstance(keys, (tuple, list)): return {}
    out: dict[str, str] = {}
    for name in keys:
        value = os.environ.get(str(name))
        if value is None: continue
        out[str(name)] = value
    return out


def _deployer_path(target: str) -> Path:
    registry = TARGET_REGISTRY[target]
    return pack_root() / str(registry["dir"]) / str(registry["script"])


def _deployer_argv(args: argparse.Namespace, target: str) -> list[str]:
    home = _resolve_target_home(args, target)
    argv: list[str] = [f"--target={home}"]
    if args.dry_run: argv.append("--dry-run")
    if args.non_interactive: argv.append("--non-interactive")
    if args.skip_prereqs: argv.append("--skip-prereqs")
    return argv


def _idempotent_match(prev: dict[str, object], fingerprint: str) -> bool:
    if prev.get("flag_fingerprint") != fingerprint: return False
    if prev.get("last_run_rc") != 0: return False
    ts = prev.get("last_run_timestamp")
    if not isinstance(ts, str): return False
    try:
        prev_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    delta = (datetime.now(timezone.utc) - prev_dt).total_seconds()
    return 0 <= delta < IDEMPOTENT_WINDOW_SECONDS


def _redacted_flag_record(target: str) -> dict[str, object]:
    keys = TARGET_REGISTRY[target]["env"]
    if not isinstance(keys, (tuple, list)): return {}
    record: dict[str, object] = {}
    for name in keys:
        value = os.environ.get(str(name))
        if value is None: continue
        record[str(name)] = value
    redacted = redact_secrets(record)
    return redacted if isinstance(redacted, dict) else {}


def _run_post_deploy_utilities(
    target: str,
    deploy_home: str,
    verb_log: Path,
    args: argparse.Namespace
) -> int | None:
    if target not in _UTILITIES_AWARE_TARGETS: return None
    if args.skip_utilities: return None
    if args.dry_run:
        log_event("install", f"utilities_skipped_dry_run target={target} home={deploy_home}")
        return None
    src = magi_utilities_source(verb="install")
    if src is None:
        log_event(
            "install",
            "utilities_source_unresolved skipping post-deploy setup_utilities.sh",
            level=logging.WARNING
        )
        return None
    setup_sh = src / "setup_utilities.sh"
    log_event("install", f"utilities_start source={src} target={deploy_home}")
    with verb_log.open("a", encoding="utf-8") as handle:
        result = subprocess.run(
            [str(setup_sh), "-y"],
            cwd=deploy_home,
            env=os.environ.copy(),
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False
        )
    log_event("install", f"utilities_done rc={result.returncode}")
    return result.returncode


def _write_shakedown_trigger() -> None:
    """Atomically drop a sentinel file for `magi doctor` to consume."""
    runtime_dir().mkdir(parents=True, exist_ok=True)
    trigger = runtime_dir() / SHAKEDOWN_TRIGGER_FILENAME
    tmp = trigger.with_suffix(".tmp")
    tmp.write_text(now_utc_iso(), encoding="utf-8")
    os.replace(str(tmp), str(trigger))
    log_event("install", f"shakedown_trigger_written path={trigger}")


def _bd_push_if_requested(verb_log: Path, args: argparse.Namespace) -> None:
    if not args.bd_push or args.no_bd: return
    log_event("install", "bd_push_start")
    with verb_log.open("a", encoding="utf-8") as handle:
        result = subprocess.run(
            ["bd", "dolt", "push"],
            stdout=handle,
            stderr=subprocess.STDOUT,
            timeout=BD_PUSH_TIMEOUT_SECONDS,
            check=False
        )
    log_event("install", f"bd_push_done rc={result.returncode}")


# ---------------------------------------------------------------------------
# Direct-deploy path for --target claude (plan v3 §7.1)
# ---------------------------------------------------------------------------


def _operator_line(verb_log: Path, message: str) -> None:
    """Print an operator-visible line to stdout and append to the verb log."""
    print(message)
    sys.stdout.flush()
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def _utc_short() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _backup_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")


def _resolve_user_name() -> str:
    raw = os.environ.get("USER")
    if raw: return raw
    return pwd.getpwuid(os.geteuid()).pw_name


def _build_placeholder_map(deploy_home: str, args: argparse.Namespace) -> dict[str, str]:
    """Return placeholder -> substitution map for the deployer.

    Required placeholders without a resolution raise CLIError. Optional
    placeholders fall back to their documented default (empty string for
    secret-bearing optional placeholders; ``127.0.0.1`` / ``1234`` for
    LM Studio host/port).
    """
    del args  # placeholders resolve from env + computed values only.
    user_home = os.environ.get("HOME") or str(Path.home())
    user_name = _resolve_user_name()
    lm_host = os.environ.get("LM_STUDIO_HOST") or "127.0.0.1"
    lm_port = os.environ.get("LM_STUDIO_PORT") or "1234"
    lm_url = os.environ.get("LM_STUDIO_URL") or f"http://{lm_host}:{lm_port}/v1"

    mapping: dict[str, str] = {
        PACK_DIR_PLACEHOLDER: deploy_home,
        "__USER_HOME__": user_home,
        "__USER_NAME__": user_name,
        "__CLAUDE_HOME__": deploy_home,
        "__LSP_PASS__": os.environ.get("LSP_PASS", ""),
        "__LSP_USER__": os.environ.get("LSP_USER", ""),
        "__LSP_IP__": os.environ.get("LSP_IP", ""),
        "__LSP_REMOTE_HOME__": os.environ.get("LSP_REMOTE_HOME", ""),
        "__BRAVE_API_KEY__": os.environ.get("BRAVE_API_KEY", ""),
        "__GITHUB_PERSONAL_ACCESS_TOKEN__": os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", ""),
        "__MY_GITEA_API_TOKEN__": os.environ.get("MY_GITEA_API_TOKEN", ""),
        "__MY_GITEA_HOST__": os.environ.get("MY_GITEA_HOST", ""),
        "__MY_GITEA_PORT__": os.environ.get("MY_GITEA_PORT", ""),
        "__LM_STUDIO_HOST__": lm_host,
        "__LM_STUDIO_PORT__": lm_port,
        "__LM_STUDIO_URL__": lm_url,
    }

    for token in INSTALL_PLACEHOLDERS:
        if token not in mapping:
            raise CLIError(
                f"placeholder {token!r} declared in INSTALL_PLACEHOLDERS but not resolved",
                exit_code=2
            )
    return mapping


def _whole_tree_backup_path(deploy_home: Path) -> Path:
    parent = deploy_home.parent
    return parent / f"{deploy_home.name}_backup-{_backup_stamp()}"


def _pre_mutation_targets(deploy_home: Path) -> list[Path]:
    """Return existing files in the deploy_home that need pre-mutation .bak."""
    targets: list[Path] = []
    if not deploy_home.is_dir(): return targets
    for rel in SECRET_BEARING_FILES:
        candidate = deploy_home / rel
        if candidate.is_file(): targets.append(candidate)
    for surface_name in ("CLAUDE.md",):
        candidate = deploy_home / surface_name
        if candidate.is_file(): targets.append(candidate)
    return targets


def _snapshot_pre_mutation(deploy_home: Path, verb_log: Path, dry_run: bool) -> list[Path]:
    """Snapshot every target file to ``<file>.pre-magi-<utc>.bak``."""
    stamp = _utc_short()
    snapshots: list[Path] = []
    for target in _pre_mutation_targets(deploy_home):
        bak = target.with_name(f"{target.name}.pre-magi-{stamp}.bak")
        if dry_run:
            _operator_line(verb_log, f"[dry-run] [magi-install] snapshot: {target} -> {bak}")
            snapshots.append(bak)
            continue
        shutil.copy2(target, bak)
        _operator_line(verb_log, f"[magi-install] snapshot: {target} -> {bak}")
        snapshots.append(bak)
    return snapshots


def _whole_tree_backup(deploy_home: Path, verb_log: Path, dry_run: bool) -> Path | None:
    if not deploy_home.is_dir():
        _operator_line(verb_log, f"[magi-install] backup skipped (no prior deploy at {deploy_home})")
        return None
    backup = _whole_tree_backup_path(deploy_home)
    if dry_run:
        _operator_line(verb_log, f"[dry-run] [1/7] backup: {deploy_home} -> {backup}")
        return backup
    if backup.exists():
        _operator_line(verb_log, f"[magi-install] backup path exists; skip: {backup}")
        return backup
    shutil.copytree(str(deploy_home), str(backup), symlinks=True)
    _operator_line(verb_log, f"[1/7] backup: {deploy_home} -> {backup}")
    return backup


def _rsync_surface(
    src: Path,
    dst: Path,
    verb_log: Path,
    dry_run: bool
) -> int:
    """rsync a single surface into the staging tree. Honors --dry-run."""
    if not src.exists():
        _operator_line(verb_log, f"[magi-install] surface missing in pack; skip: {src}")
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        if dry_run:
            _operator_line(verb_log, f"[dry-run] [2/7] rsync: {src} -> {dst}")
            return 0
        shutil.copy2(src, dst)
        _operator_line(verb_log, f"[2/7] rsync: {src} -> {dst}")
        return 0
    src_arg = str(src) + "/"
    dst_arg = str(dst) + "/"
    args: list[str] = ["rsync", "-a"]
    for token in _RSYNC_EXCLUDES:
        args.extend(["--exclude", token])
    if dry_run: args.append("--dry-run")
    args.extend([src_arg, dst_arg])
    with verb_log.open("a", encoding="utf-8") as handle:
        result = subprocess.run(
            args,
            stdout=handle,
            stderr=subprocess.STDOUT,
            timeout=_RSYNC_TIMEOUT_SECONDS,
            check=False
        )
    prefix = "[dry-run] " if dry_run else ""
    _operator_line(verb_log, f"{prefix}[2/7] rsync: {src} -> {dst} rc={result.returncode}")
    return result.returncode


def _is_substitutable(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in SUBSTITUTABLE_EXTENSIONS: return True
    return False


def _substitute_file(path: Path, mapping: dict[str, str]) -> int:
    """Apply placeholder substitution to one file. Returns substitution count."""
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    updated = original
    count = 0
    for token, replacement in mapping.items():
        if token not in updated: continue
        count += updated.count(token)
        updated = updated.replace(token, replacement)
    if updated == original: return 0
    path.write_text(updated, encoding="utf-8")
    return count


def _walk_substitute(stage_root: Path, mapping: dict[str, str], verb_log: Path, dry_run: bool) -> tuple[int, int]:
    """Walk staging tree, substitute placeholders, return (file_count, replacement_count)."""
    files_touched = 0
    replacements_total = 0
    for path in stage_root.rglob("*"):
        if not path.is_file(): continue
        if path.is_symlink(): continue
        if not _is_substitutable(path): continue
        if dry_run:
            replacements_total += 0
            continue
        count = _substitute_file(path, mapping)
        if count > 0:
            files_touched += 1
            replacements_total += count
    if dry_run:
        _operator_line(
            verb_log,
            f"[dry-run] [3/7] substitute: planned across files with extensions in SUBSTITUTABLE_EXTENSIONS"
        )
    else:
        _operator_line(
            verb_log,
            f"[3/7] substitute: {replacements_total} placeholders across {files_touched} files"
        )
    return files_touched, replacements_total


def _apply_secret_mode(stage_root: Path, verb_log: Path, dry_run: bool) -> int:
    """Set mode 0600 on every SECRET_BEARING_FILES member in the stage."""
    applied = 0
    for rel in SECRET_BEARING_FILES:
        candidate = stage_root / rel
        if not candidate.is_file(): continue
        if dry_run:
            _operator_line(verb_log, f"[dry-run] [4/7] chmod 0600: {candidate}")
            applied += 1
            continue
        os.chmod(str(candidate), 0o600)
        _operator_line(verb_log, f"[4/7] chmod 0600: {candidate}")
        applied += 1
    return applied


def _deep_merge_value(left: object, right: object) -> object:
    """Recursively merge right into left. Right wins on scalar conflicts; arrays concat-dedup."""
    if isinstance(left, dict) and isinstance(right, dict):
        merged: dict[str, object] = {}
        for key in list(left.keys()):
            if key in right:
                merged[key] = _deep_merge_value(left[key], right[key])
            else:
                merged[key] = left[key]
        for key, value in right.items():
            if key not in merged: merged[key] = value
        return merged
    if isinstance(left, list) and isinstance(right, list):
        combined: list[object] = list(left)
        for item in right:
            if item not in combined: combined.append(item)
        return combined
    return right


def _deep_merge_json_file(deployed: Path, staged: Path, verb_log: Path, dry_run: bool) -> int:
    """Deep-merge staged JSON into deployed JSON in-place inside the stage. Returns rc."""
    if not deployed.is_file(): return 0
    if dry_run:
        _operator_line(verb_log, f"[dry-run] [5/7] deep-merge: {deployed} <- {staged}")
        return 0
    try:
        existing = json.loads(deployed.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _operator_line(verb_log, f"[magi-install] deep-merge skipped (existing parse failed): {exc}")
        return 0
    try:
        incoming = json.loads(staged.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _operator_line(verb_log, f"[magi-install] deep-merge aborted (staged parse failed): {exc}")
        return 1
    merged = _deep_merge_value(existing, incoming)
    staged.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    if staged.name in SECRET_BEARING_FILES or staged.name == ".mcp.json":
        os.chmod(str(staged), 0o600)
    _operator_line(verb_log, f"[5/7] deep-merge: {deployed} <- {staged}")
    return 0


def _deep_merge_staged_files(stage_root: Path, deploy_home: Path, verb_log: Path, dry_run: bool) -> int:
    """Apply deep-merge for every _DEEP_MERGE_SURFACES member that exists in deploy_home."""
    worst_rc = 0
    for rel in _DEEP_MERGE_SURFACES:
        staged = stage_root / rel
        deployed = deploy_home / rel
        if not staged.is_file(): continue
        rc = _deep_merge_json_file(deployed, staged, verb_log, dry_run)
        if rc > worst_rc: worst_rc = rc
    return worst_rc


def _atomic_swap(stage_root: Path, deploy_home: Path, verb_log: Path, dry_run: bool) -> int:
    """Atomically move every file in stage onto deploy_home. Returns rc."""
    if dry_run:
        _operator_line(verb_log, f"[dry-run] [6/7] rename: {stage_root} -> {deploy_home}")
        return 0
    deploy_home.mkdir(parents=True, exist_ok=True)
    files_moved = 0
    for path in sorted(stage_root.rglob("*")):
        if path.is_dir(): continue
        rel = path.relative_to(stage_root)
        dest = deploy_home / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        path.replace(dest)
        files_moved += 1
    _operator_line(verb_log, f"[6/7] rename: {stage_root} -> {deploy_home} files={files_moved}")
    return 0


def _verify_secret_modes(deploy_home: Path, verb_log: Path, dry_run: bool) -> int:
    """Verify that every SECRET_BEARING_FILES member in deploy_home is mode 0600."""
    if dry_run: return 0
    worst_rc = 0
    for rel in SECRET_BEARING_FILES:
        candidate = deploy_home / rel
        if not candidate.is_file(): continue
        current_mode = stat.S_IMODE(candidate.stat().st_mode)
        if current_mode != 0o600:
            os.chmod(str(candidate), 0o600)
            _operator_line(
                verb_log,
                f"[magi-install] mode-verify fixup: {candidate} had {current_mode:#o}; reset to 0600"
            )
            worst_rc = max(worst_rc, 0)
        else:
            _operator_line(verb_log, f"[magi-install] mode-verify ok: {candidate} mode=0600")
    return worst_rc


def _npm_install_servers(deploy_home: Path, verb_log: Path, dry_run: bool) -> int:
    """Run `npm install --silent --no-fund --no-audit` for every mcp-server package.json."""
    servers_dir = deploy_home / "mcp-servers"
    if not servers_dir.is_dir():
        _operator_line(verb_log, f"[magi-install] mcp-servers absent at {servers_dir}; skip npm")
        return 0
    npm_path = shutil.which("npm")
    if npm_path is None:
        _operator_line(verb_log, "[magi-install] npm not on PATH; skip mcp-servers install")
        return 0
    worst_rc = 0
    count = 0
    for child in sorted(servers_dir.iterdir()):
        if not child.is_dir(): continue
        pkg = child / "package.json"
        if not pkg.is_file(): continue
        count += 1
        if dry_run:
            _operator_line(verb_log, f"[dry-run] [7/7] npm install: {child}")
            continue
        with verb_log.open("a", encoding="utf-8") as handle:
            result = subprocess.run(
                [npm_path, "install", "--silent", "--no-fund", "--no-audit"],
                cwd=str(child),
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=_NPM_INSTALL_TIMEOUT_SECONDS,
                check=False
            )
        _operator_line(verb_log, f"[7/7] npm install: {child} rc={result.returncode}")
        if result.returncode != 0 and worst_rc == 0: worst_rc = result.returncode
    if count == 0:
        _operator_line(verb_log, "[magi-install] mcp-servers: no package.json found; skip npm")
    return worst_rc


_PLIST_LABEL_REGEX: re.Pattern[str] = re.compile(
    r"(<key>Label</key>\s*<string>)com\.__USER_NAME__\.([^<]+)(</string>)"
)


def _rename_launchd_plists(deploy_home: Path, user_name: str, verb_log: Path, dry_run: bool) -> int:
    """Rename ``com.__USER_NAME__.*.plist`` to ``com.<user>.*.plist`` and update Label."""
    launchd_dir = deploy_home / "enforcement" / "launchd"
    if not launchd_dir.is_dir(): return 0
    renamed = 0
    for plist in sorted(launchd_dir.glob("com.__USER_NAME__.*.plist")):
        new_name = plist.name.replace("com.__USER_NAME__.", f"com.{user_name}.", 1)
        new_path = plist.with_name(new_name)
        if dry_run:
            _operator_line(verb_log, f"[dry-run] [magi-install] plist rename: {plist.name} -> {new_name}")
            continue
        content = plist.read_text(encoding="utf-8")
        replacement = rf"\g<1>com.{user_name}.\g<2>\g<3>"
        updated = _PLIST_LABEL_REGEX.sub(replacement, content)
        plist.write_text(updated, encoding="utf-8")
        plist.rename(new_path)
        _operator_line(verb_log, f"[magi-install] plist rename: {plist.name} -> {new_name}")
        renamed += 1
    return renamed


def _post_deploy_invariant_grep(deploy_home: Path, verb_log: Path, dry_run: bool) -> int:
    """Confirm zero residual ``${MAGI_PACK_DIR}`` matches under deploy_home."""
    if dry_run:
        _operator_line(verb_log, "[dry-run] [magi-install] post-deploy invariant grep skipped")
        return 0
    if not deploy_home.is_dir(): return 0
    residuals: list[str] = []
    for path in deploy_home.rglob("*"):
        if not path.is_file(): continue
        if path.is_symlink(): continue
        if not _is_substitutable(path): continue
        if ".utilities" in path.parts: continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if PACK_DIR_PLACEHOLDER in text:
            residuals.append(str(path))
    if residuals:
        _operator_line(
            verb_log,
            f"[magi-install] post-deploy invariant grep FAILED: {len(residuals)} residual matches"
        )
        for rpath in residuals:
            _operator_line(verb_log, f"[magi-install]   residual: {rpath}")
        return 1
    _operator_line(verb_log, "[magi-install] post-deploy invariant grep: 0 residual matches")
    return 0


def _stage_dir_for(deploy_home: Path) -> Path:
    return deploy_home.parent / f"{deploy_home.name}.staging-{_utc_short()}"


def _cleanup_stage(stage_root: Path, verb_log: Path) -> None:
    if not stage_root.exists(): return
    try:
        shutil.rmtree(str(stage_root))
        _operator_line(verb_log, f"[magi-install] stage cleanup: removed {stage_root}")
    except OSError as exc:
        _operator_line(verb_log, f"[magi-install] stage cleanup failed: {stage_root} ({exc})")


def _stage_pack_source(stage_root: Path, verb_log: Path, dry_run: bool) -> int:
    """rsync every claude-deploy surface from pack root into stage_root."""
    root = pack_root()
    if not dry_run: stage_root.mkdir(parents=True, exist_ok=True)
    worst_rc = 0
    for src_rel, dst_rel in _CLAUDE_DEPLOY_SURFACES:
        src = root / src_rel
        dst = stage_root / dst_rel
        rc = _rsync_surface(src, dst, verb_log, dry_run)
        if rc != 0 and worst_rc == 0: worst_rc = rc
    _operator_line(verb_log, f"[2/7] stage: pack root -> {stage_root}")
    return worst_rc


def _deploy_claude_from_pack_root(deploy_home: Path, args: argparse.Namespace, verb_log: Path) -> int:
    """Direct-deploy the claude target from pack root via stage-and-swap.

    Implements plan v3 §7.1 STEP 0-6 ordering: snapshot pre-mutation
    files, whole-tree backup, stage, substitute, chmod 0600 on
    secret-bearing files, deep-merge, atomic rename, mode verify, npm
    install, launchd plist rename, post-deploy invariant grep. This is
    the only deploy path for ``--target claude``.
    """
    dry_run = bool(args.dry_run)
    _operator_line(verb_log, f"[magi-install] mode=direct-deploy target=claude home={deploy_home}")

    # STEP 0: per-file pre-mutation snapshot.
    _snapshot_pre_mutation(deploy_home, verb_log, dry_run)

    # Whole-tree backup BEFORE any staging.
    _whole_tree_backup(deploy_home, verb_log, dry_run)

    # STEP 1: stage rsync source -> staging.
    stage_root = _stage_dir_for(deploy_home)
    cleanup_required = True
    try:
        rc = _stage_pack_source(stage_root, verb_log, dry_run)
        if rc != 0:
            _operator_line(verb_log, f"[magi-install] stage rsync rc={rc}; aborting")
            return rc

        # STEP 2: substitution over staging tree.
        mapping = _build_placeholder_map(str(deploy_home), args)
        _walk_substitute(stage_root, mapping, verb_log, dry_run)

        # STEP 3: secret-bearing-file mode 0600 in stage.
        _apply_secret_mode(stage_root, verb_log, dry_run)

        # STEP 4: deep-merge settings.json / .mcp.json against deployed copy.
        merge_rc = _deep_merge_staged_files(stage_root, deploy_home, verb_log, dry_run)
        if merge_rc != 0:
            _operator_line(verb_log, f"[magi-install] deep-merge rc={merge_rc}; aborting")
            return merge_rc

        # STEP 5: atomic rename stage -> deploy_home.
        swap_rc = _atomic_swap(stage_root, deploy_home, verb_log, dry_run)
        if swap_rc != 0: return swap_rc
        cleanup_required = False

        # STEP 6: post-rename verifications.
        _verify_secret_modes(deploy_home, verb_log, dry_run)

        # MCP servers npm install.
        _npm_install_servers(deploy_home, verb_log, dry_run)

        # Launchd plist rename.
        user_name = _resolve_user_name()
        _rename_launchd_plists(deploy_home, user_name, verb_log, dry_run)

        # Post-deploy invariant grep.
        invariant_rc = _post_deploy_invariant_grep(deploy_home, verb_log, dry_run)
        if invariant_rc != 0: return invariant_rc

        return 0
    finally:
        if cleanup_required: _cleanup_stage(stage_root, verb_log)


# ---------------------------------------------------------------------------
# Legacy exec-the-vendored-deployer path
# ---------------------------------------------------------------------------


def _exec_vendored_deployer(target: str, args: argparse.Namespace, verb_log: Path, deploy_home: str) -> int:
    deployer = _deployer_path(target)
    if not deployer.exists():
        log_event("install", f"deployer_missing target={target} path={deployer}", level=logging.ERROR)
        return 1
    if not os.access(str(deployer), os.X_OK):
        log_event("install", f"deployer_not_executable target={target} path={deployer}", level=logging.ERROR)
        return 1
    argv_for_harness = _deployer_argv(args, target)
    env_passthrough = _build_env_passthrough(target)
    env = os.environ.copy()
    env.update(env_passthrough)
    env["MAGI_PACK_ENV_LOADED"] = "1"
    log_event(
        "install",
        f"deployer_start target={target} home={deploy_home} argv={argv_for_harness}"
    )
    with verb_log.open("a", encoding="utf-8") as handle:
        proc = subprocess.run(
            [str(deployer), *argv_for_harness],
            cwd=str(deployer.parent),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False
        )
    log_event("install", f"deployer_done target={target} rc={proc.returncode}")
    return proc.returncode


def _deploy_target(target: str, args: argparse.Namespace, verb_log: Path, deploy_home: str) -> tuple[int, str]:
    """Dispatch to the correct deploy path for the given target.

    Returns (return_code, deploy_mode) where deploy_mode is ``"direct"``
    (claude — stage-and-swap from pack root) or ``"vendored"`` (codex /
    gemini / openai — exec the per-target deploy script).
    """
    if target == "claude":
        rc = _deploy_claude_from_pack_root(Path(deploy_home), args, verb_log)
        return rc, "direct"
    rc = _exec_vendored_deployer(target, args, verb_log, deploy_home)
    return rc, "vendored"


def _install_one(target: str, args: argparse.Namespace) -> int:
    load_pack_env()
    verb_log = log_path("install", target)
    attach_file_log("install", verb_log)

    deploy_home = _resolve_target_home(args, target)
    registry_env = TARGET_REGISTRY[target]["env"]
    env_keys: list[str] = list(registry_env) if isinstance(registry_env, (list, tuple)) else []
    fingerprint = flag_fingerprint(sys.argv[1:], env_keys)

    state = read_state()
    installs = state.setdefault("installs", {})
    if not isinstance(installs, dict):
        installs = {}
        state["installs"] = installs
    prev = installs.get(target, {})
    if not isinstance(prev, dict): prev = {}
    reuse_bead = _idempotent_match(prev, fingerprint)

    labels: dict[str, str] = {"pack": "magi", "verb": "install", "target": target, "role": "root"}
    bead_id: str | None = None
    if not args.no_bd:
        if reuse_bead:
            prior = prev.get("bead_id")
            if isinstance(prior, str): bead_id = prior
        if bead_id is None:
            bead_id = bd_create(
                title=f"magi install --target {target}",
                body=f"target={target} home={deploy_home} dry_run={args.dry_run}",
                labels=labels,
                verb="install"
            )
        if bead_id: bd_update(bead_id, claim=True, verb="install")

    if bead_id: write_inflight_sentinel(bead_id, "install", target)

    rc = 0
    deploy_mode = "vendored"
    closed = False
    try:
        rc, deploy_mode = _deploy_target(target, args, verb_log, deploy_home)
        utilities_rc = _run_post_deploy_utilities(target, deploy_home, verb_log, args)
        utilities_linked = utilities_rc == 0 if utilities_rc is not None else bool(
            prev.get("utilities_linked")
        )
        if rc == 0: _bd_push_if_requested(verb_log, args)
        if bead_id:
            outcome = "0" if rc == 0 else "1" if rc == 1 else "2" if rc == 2 else "1"
            bd_close(bead_id, outcome=outcome, verb="install")
            closed = True
        installs[target] = {
            "installed": rc == 0 and not args.dry_run,
            "target": deploy_home,
            "last_run_timestamp": now_utc_iso(),
            "last_run_rc": rc,
            "last_log": str(verb_log),
            "bead_id": bead_id,
            "feature_flags": _redacted_flag_record(target),
            "utilities_linked": utilities_linked,
            "flag_fingerprint": fingerprint,
            "deploy_mode": deploy_mode
        }
        state["installs"] = installs
        state["bd_available"] = bd_available_current()
        src = magi_utilities_source(verb="install")
        state["magi_utilities_source"] = str(src) if src else None
        write_state(state)
        if rc == 0 and not args.dry_run: _write_shakedown_trigger()
        if bead_id and rc == 0:
            bd_remember(
                f"install:{target}",
                f"home={deploy_home} timestamp={now_utc_iso()} bead={bead_id}",
                verb="install"
            )
        _operator_line(verb_log, f"[magi-install] bead closed: {bead_id} outcome={rc}")
        return rc
    finally:
        if bead_id and not closed: bd_close(bead_id, outcome="interrupted", verb="install")
        if bead_id: clear_inflight_sentinel(bead_id)


def main() -> int:
    """Entry point for magi-install."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        city = city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    log_event("install", f"city_root={city}")
    reconcile_orphans("install")

    if args.target == "all":
        worst = 0
        for target in ("claude", "codex", "gemini", "openai"):
            rc = _install_one(target, args)
            if rc > worst: worst = rc
        return worst
    return _install_one(args.target, args)


if __name__ == "__main__":
    sys.exit(main())

"""Prepare a separate copy of the released macOS app; never launch the original.

Electron 41.7 applies --user-data-dir in electron_main_delegate.cc before app JS
and uses it for RequestSingleInstanceLock. BB's updater additionally needs its
own cache: electron-updater computes that independently of Electron userData.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import subprocess
import sys
from urllib.parse import urlsplit

from full_e2e import validate_environment


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def isolated_updater_config(text, cache, *, cache_base=None):
    cache = Path(cache).resolve()
    base = Path(cache_base or (Path.home() / "Library/Caches")).resolve()
    relative = os.path.relpath(cache, base)
    # electron-updater uses path.join(baseCachePath, updaterCacheDirName).
    if (base / relative).resolve() != cache:
        raise ValueError("Updater cache did not resolve to the owned directory")
    updated, count = re.subn(r"(?m)^updaterCacheDirName:[^\n]*$",
                            "updaterCacheDirName: " + json.dumps(relative), text)
    if count != 1:
        raise ValueError("Expected one explicit released updater cache setting")
    return updated


def prepare_clone(manifest, directory, app_path="/Applications/bb.app"):
    if sys.platform != "darwin":
        raise ValueError("Native desktop preparation requires macOS")
    root, env = validate_environment(manifest)
    directory = Path(directory).resolve()
    if not directory.is_relative_to(root) or directory == root or directory.exists():
        raise ValueError("Desktop copy requires a new directory inside the marked installation")
    endpoint = urlsplit(manifest["bbUrl"])
    if endpoint.port in {None, 38886, 8372} or endpoint.path not in {"", "/"}:
        raise ValueError("Desktop cannot attach to a normal or ambiguous BB endpoint")
    source = Path(app_path).resolve(strict=True)
    source_info = source / "Contents/Info.plist"
    info_bytes = source_info.read_bytes()
    info = plistlib.loads(info_bytes)
    if info["CFBundleShortVersionString"] != manifest["versions"]["bb"]:
        raise ValueError("Installed desktop version differs from the tested BB release")
    executable = info["CFBundleExecutable"]
    if Path(executable).name != executable:
        raise ValueError("Invalid desktop executable name")
    production = source / "Contents/Resources/app.asar"
    updater = source / "Contents/Resources/app-update.yml"
    identity = {"version": info["CFBundleShortVersionString"], "app_asar_sha256": sha256(production),
                "original_executable_sha256": sha256(source / "Contents/MacOS" / executable),
                "original_info_sha256": sha256(source_info), "original_updater_sha256": sha256(updater)}
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    print("[desktop] Copying released app into owned scratch", flush=True)
    clone = directory / "bb-e2e.app"
    # Copy-on-write makes a complete independent bundle; no symlink reaches the
    # original app. Retain the clone and its evidence after every outcome.
    subprocess.run(["cp", "-cR", str(source), str(clone)], check=True, timeout=120)
    copied_asar = clone / "Contents/Resources/app.asar"
    if sha256(copied_asar) != identity["app_asar_sha256"]:
        raise ValueError("Desktop production archive changed while copying")
    user_data, disk_cache, updater_cache = [directory / name for name in ("profile", "disk-cache", "updater-cache")]
    for path in (user_data, disk_cache, updater_cache):
        path.mkdir(mode=0o700)
    new_info = dict(info)
    new_info["CFBundleIdentifier"] = "dev.bb.desktop.e2e." + secrets.token_hex(8)
    # The original plist/sidecar remain intact in the source bundle; only the
    # new clone's registration/cache configuration is changed.
    (clone / "Contents/Info.plist").write_bytes(plistlib.dumps(new_info))
    (clone / "Contents/Resources/app-update.yml").write_text(isolated_updater_config(updater.read_text(), updater_cache))
    print("[desktop] Signing only the copied bundle; production archive unchanged", flush=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(clone)], check=True, timeout=120,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(clone)], check=True, timeout=120,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (source_info.read_bytes() != info_bytes or sha256(production) != identity["app_asar_sha256"]
            or sha256(updater) != identity["original_updater_sha256"]
            or sha256(source / "Contents/MacOS" / executable) != identity["original_executable_sha256"]
            or sha256(copied_asar) != identity["app_asar_sha256"]):
        raise ValueError("Source or copied production artifact changed during preparation")
    spec = {"schema": 1, "root": str(root), "directory": str(directory), "envFile": manifest["envFile"], "sourceApp": str(source),
            "bbUrl": manifest["bbUrl"], "bbDataDir": env["BB_DATA_DIR"], "appPid": manifest["appPid"],
            "executablePath": str(clone / "Contents/MacOS" / executable), "appAsar": str(copied_asar),
            "userDataDir": str(user_data), "diskCacheDir": str(disk_cache), "updaterCacheDir": str(updater_cache),
            "bundleId": new_info["CFBundleIdentifier"], "identity": identity,
            "instrumentation": ["cloned-bundle", "unique-bundle-identifier", "isolated-profile-and-updater-cache",
                                "ad-hoc-signature", "external-network-rejecting-proxy", "mock-keychain"]}
    with (directory / "desktop.json").open("x") as output:
        json.dump(spec, output, indent=2); output.write("\n")
    print("[desktop] Prepared retained clone", flush=True)
    return spec


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-manifest", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--app", default="/Applications/bb.app")
    args = parser.parse_args()
    prepare_clone(json.loads(args.environment_manifest.read_text()), args.directory, args.app)

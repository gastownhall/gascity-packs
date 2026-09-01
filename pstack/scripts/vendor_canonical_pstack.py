#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "6fecddba65801f9b9c08b8b328d998ee5b09d290"
TARBALL = f"https://codeload.github.com/cursor/plugins/tar.gz/{COMMIT}"
GUIDE_URL = f"https://github.com/cursor/plugins/blob/{COMMIT}/pstack/docs/guide/README.md"
PREFIX_PARTS = ("pstack",)
LISTED = ("skills", "agents", "LICENSE", "README.md")
README_NOTICE = f"""# pstack (Gas City vendor)

This directory is the listed subset of official Cursor pstack at
`cursor/plugins` path `pstack` commit `{COMMIT}`. Copied paths are
`skills/`, `agents/`, `README.md`, and `LICENSE`. The Cursor product
guide is not copied. Read it at {GUIDE_URL}.

Gas City mapping lives outside this directory.

---

"""


def assert_safe_paths(dest: Path, runtime: Path) -> None:
    dest = dest.resolve()
    runtime = runtime.resolve()
    pack = PACK_ROOT.resolve()
    if dest in {pack, pack / "agents"}:
        raise SystemExit(f"refusing dest {dest}; that is pack-owned")
    if runtime == pack / "agents":
        raise SystemExit(f"refusing runtime {runtime}; that is pack-owned")


def copy_listed(src_pstack: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in LISTED:
        item = src_pstack / name
        if not item.exists():
            raise SystemExit(f"missing listed source {item}")
        target = dest / name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def write_pin(dest: Path) -> None:
    (dest / "upstream.toml").write_text(
        """[upstream]
source = "https://github.com/cursor/plugins"
path = "pstack"
commit = "6fecddba65801f9b9c08b8b328d998ee5b09d290"
license = "MIT"
provenance = "Official Cursor pstack plugin subtree. Gas City mapping lives outside vendor."

[vendor]
paths = [
  "vendor/pstack/skills",
  "vendor/pstack/agents",
  "vendor/pstack/README.md",
  "vendor/pstack/LICENSE",
]

[runtime_adaptation]
owner = "Gas City pack"
skills_copy = ["skills"]
pack_owned = ["agents", "formulas", "assets", "schemas", "principles", "mappings", "tests"]
rule = "Never edit vendored source to adapt provider or runtime behavior. Do not copy vendor agents onto pack-owned agents."
""",
        encoding="utf-8",
    )


UNCOPIED_LINKS = {
    "(./docs/guide/README.md)": f"({GUIDE_URL})",
    "(./automations/benny/FOR_AGENTS.md)": (
        f"(https://github.com/cursor/plugins/blob/{COMMIT}/pstack/automations/benny/FOR_AGENTS.md)"
    ),
    "(./automations/benny/)": (
        f"(https://github.com/cursor/plugins/blob/{COMMIT}/pstack/automations/benny/)"
    ),
}


def annotate_readme(dest: Path) -> None:
    path = dest / "README.md"
    body = path.read_text(encoding="utf-8")
    if body.startswith("# pstack (Gas City vendor)"):
        _, _, rest = body.partition("\n---\n\n")
        body = rest
    for old, new in UNCOPIED_LINKS.items():
        body = body.replace(old, new)
    path.write_text(README_NOTICE + body, encoding="utf-8")


def prune_unlisted(dest: Path) -> None:
    allowed = set(LISTED) | {"upstream.toml"}
    for child in dest.iterdir():
        if child.name in allowed:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def sync_runtime(vendor: Path, runtime: Path) -> None:
    if runtime.exists():
        shutil.rmtree(runtime)
    shutil.copytree(vendor / "skills", runtime)


def vendor(dest: Path, runtime: Path) -> None:
    assert_safe_paths(dest, runtime)
    with tempfile.TemporaryDirectory() as tmp:
        tarball = Path(tmp) / "plugins.tar.gz"
        with urllib.request.urlopen(TARBALL) as response, tarball.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        extract = Path(tmp) / "extract"
        extract.mkdir()
        with tarfile.open(tarball, "r:gz") as archive:
            archive.extractall(extract, filter="data")
        roots = [path for path in extract.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise SystemExit(f"expected one tarball root, got {roots}")
        src = roots[0].joinpath(*PREFIX_PARTS)
        if not src.is_dir():
            raise SystemExit(f"missing {src}")
        copy_listed(src, dest)
        annotate_readme(dest)
        write_pin(dest)
        prune_unlisted(dest)
        sync_runtime(dest, runtime)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=PACK_ROOT / "vendor" / "pstack")
    parser.add_argument("--runtime", type=Path, default=PACK_ROOT / "skills")
    args = parser.parse_args()
    vendor(args.dest, args.runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

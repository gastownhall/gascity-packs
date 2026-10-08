"""Use the same acceptance assertions through the retained native Electron page."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys

from live_assertions import AcceptanceFailure

HERE = Path(__file__).resolve().parent


@contextmanager
def desktop_journeys(runner, spec_path):
    """Route only UI driver commands; independent BB/GC assertions stay intact."""
    original = runner.command
    def command(*args, timeout=60):
        if len(args) >= 2 and args[0] == "node" and Path(args[1]).resolve() == HERE / "browser_driver.mjs":
            args = (args[0], HERE / "desktop_journey.mjs", "--spec", spec_path, "--", *args[2:])
        return original(*args, timeout=timeout)
    runner.command = command
    try: yield
    finally: runner.command = original


def native(runner):
    if sys.platform != "darwin":
        raise AcceptanceFailure("Native desktop acceptance requires macOS")
    spec_path = runner.manifest.get("desktopSpec")
    if not spec_path:
        raise AcceptanceFailure("Prepare and attach an isolated native desktop before its required case")
    spec = json.loads(Path(spec_path).read_text())
    if (Path(spec["root"]).resolve() != runner.root or spec["bbUrl"] != runner.manifest["bbUrl"]
            or spec["identity"]["version"] != runner.manifest["versions"]["bb"]):
        raise AcceptanceFailure("Native desktop belongs to a different test installation or release")
    with desktop_journeys(runner, spec_path):
        result = runner.conversation("desktop.native", "global", project="proj_personal")
        recall = runner.recall("desktop.native-memory", runner.conversations["desktop.native"])
    return {**result, **recall, "turns": 3, "surface": "released-macos-electron",
            "desktop_app_asar_sha256": spec["identity"]["app_asar_sha256"], "instrumentation": spec["instrumentation"]}


def case_functions(runner):
    return {"desktop.native": lambda: native(runner)} if sys.platform == "darwin" else {}

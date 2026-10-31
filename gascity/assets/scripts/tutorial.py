#!/usr/bin/env python3
"""Create the owned practice repository for the first local task."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

MARKER = "rfc8191-first-local-change-v1"
VERIFY_COMMAND = "python3 -m unittest discover -s tests -v"
TASK = """Fix the greeting function in hello.py. greet(\"Ada\") must return
\"Hello, Ada!\"; greet(\"\") must return \"Hello, world!\". Preserve the public greet
function and both acceptance tests. Implement the smallest useful change,
verify with python3 -m unittest discover -s tests -v, and commit the result.
This is a local-only task; do not push or create a pull request. Independent
review and verified local integration must happen before this source task closes.
"""


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE).strip()


def scaffold(destination):
    """Atomically create a practice repo; retries preserve all task changes."""
    destination = Path(destination).absolute()
    if destination.exists():
        try:
            if git(destination, "rev-parse", "--show-toplevel") == str(destination.resolve()) and git(destination, "config", "--local", "gascity.tutorial") == MARKER:
                return destination
        except subprocess.SubprocessError:
            pass
        raise ValueError(f"refusing existing path not owned by this tutorial: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".gascity-tutorial-", dir=destination.parent))
    try:
        (staging / "tests").mkdir()
        (staging / "hello.py").write_text("def greet(name):\n    return f\"Hello, {name}\"\n")
        (staging / "tests/test_hello.py").write_text(
            "import unittest\nfrom hello import greet\n\n"
            "class GreetingTests(unittest.TestCase):\n"
            "    def test_named_greeting(self):\n"
            "        self.assertEqual(greet(\"Ada\"), \"Hello, Ada!\")\n"
            "    def test_default_greeting(self):\n"
            "        self.assertEqual(greet(\"\"), \"Hello, world!\")\n"
        )
        (staging / "README.md").write_text(
            "# Your first Gas City change\n\nThis practice repository starts with two failing tests.\n"
            "The task is to fix greet, have a separate worker review it, and integrate\n"
            "the verified commit locally. It has no remote and requires no GitHub account.\n\n"
            "Run `python3 -m unittest discover -s tests -v` to see the bug.\n"
        )
        (staging / ".gitignore").write_text("__pycache__/\n*.pyc\n.beads/\n.gc/\n")
        git(staging, "init", "-b", "main")
        git(staging, "config", "--local", "user.name", "Gas City Tutorial")
        git(staging, "config", "--local", "user.email", "tutorial@example.invalid")
        git(staging, "config", "--local", "gascity.tutorial", MARKER)
        git(staging, "add", ".")
        git(staging, "-c", "commit.gpgsign=false", "commit", "-m", "tutorial: reproduce the greeting bug")
        # rename refuses a concurrently populated destination, preserving ownership.
        os.rename(staging, destination)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    import argparse
    import json
    from source_delivery import gc
    parser = argparse.ArgumentParser(description="Run or inspect your first guided local change.")
    parser.add_argument("action", choices=["start", "status"], default="start", nargs="?")
    args = parser.parse_args()
    city = os.environ.get("GC_CITY_PATH")
    if not city:
        raise ValueError("run this command inside an initialized city")
    destination = Path(city) / "projects" / "practice"
    if args.action == "start":
        print("[1/4] Preparing your local practice repository", flush=True)
        scaffold(destination)
    rigs = gc("rig", "list", "--json", json_output=True)["rigs"]
    practice = [rig for rig in rigs if rig["name"] == "practice"]
    if practice and Path(practice[0]["path"]).resolve() != destination.resolve():
        raise ValueError("an existing practice rig points elsewhere; no changes made to it")
    if not practice:
        if args.action == "status":
            print("The guided task has not started. Run gc gc tutorial start.")
            return
        print("[2/4] Registering the practice repository", flush=True)
        gc("rig", "add", str(destination), "--name", "practice")
    rows = gc("--rig", "practice", "bd", "list", "--all", "--metadata-field",
              "gc.tutorial=" + MARKER, "--limit", "0", "--json", json_output=True)
    if isinstance(rows, dict):
        rows = [rows]
    if len(rows) > 1:
        raise ValueError("multiple first-task records found; inspect before proceeding")
    if not rows:
        if args.action == "status":
            print("The practice repository exists; run gc gc tutorial start to submit its task.")
            return
        print("[3/4] Recording your first task", flush=True)
        source = gc("--rig", "practice", "bd", "create", "Fix the greeting bug",
                    "--description", TASK, "--metadata", json.dumps({"gc.tutorial": MARKER}),
                    "--json", json_output=True)
    else:
        source = rows[0]
    source_id = source["id"]
    status = source["status"]
    print(f"Source task: {source_id}; status: {status}", flush=True)
    if source["status"] == "closed":
        sha = source.get("metadata", {}).get("gc.delivery.integrated_sha")
        if not sha:
            raise ValueError("task was closed without verified integration evidence")
        git(destination, "merge-base", "--is-ancestor", sha, "HEAD")
        print(f"Verified local integration: {sha}\nRepository: {destination}")
        print("Continue with hands-on tutorial 1 using this same city.")
        return
    if args.action == "start":
        print("[4/4] Starting implementation and independent review", flush=True)
        print(gc("--rig", "practice", "sling", "practice/gc.run-operator", source_id, "--on", "quick-start",
                 "--var", "verify_command=" + VERIFY_COMMAND), end="")
    print("Watch: gc status\nInspect: gc gc tutorial status\nPause: gc stop\nResume: gc start")
    print("The source task closes only after the reviewed and tested commit is integrated locally.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        import sys
        print(f"tutorial: {exc}", file=sys.stderr)
        sys.exit(1)

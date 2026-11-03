#!/usr/bin/env python3
"""Create the owned practice repository for the first local task."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

MARKER = "rfc8191-first-local-change-v1"
MANAGED_HOOK_FILES = (".codex/hooks.json", ".codex/.hooks.json.gascity.lock")
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
        (staging / ".gitignore").write_text("__pycache__/\n*.pyc\n.beads/\n.gc/\n" + "".join("/" + hook + "\n" for hook in MANAGED_HOOK_FILES))
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



def finish_registration(repo):
    """Commit only owned tutorial infrastructure before pinning task input."""
    repo = Path(repo)
    if git(repo, "config", "--local", "gascity.tutorial") != MARKER:
        raise ValueError("registration requires the owned tutorial repository")
    changed = set(git(repo, "diff", "HEAD", "--name-only").splitlines())
    if changed - {".gitignore"}:
        raise ValueError("source changes exist; preserve unfinished work before registration")
    sinks = (".claude/skills/", ".codex/skills/", ".gemini/skills/", ".agents/skills/", ".opencode/skills/")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    if any(path not in (".beads/identity.toml", *MANAGED_HOOK_FILES) and not path.startswith(sinks) for path in untracked):
        raise ValueError("untracked source changes exist; preserve them before registration")
    path = repo / ".gitignore"
    text = path.read_text()
    # Provider initialization legitimately removes the broad .beads/ exclusion and writes
    # narrower runtime exclusions; no task source has run at this boundary.
    for sink in (*sinks, *("/" + hook for hook in MANAGED_HOOK_FILES)):
        if sink not in text.splitlines():
            text += "\n" + sink + "\n"
    path.write_text(text)
    git(repo, "add", "--", ".gitignore")
    identity = repo / ".beads/identity.toml"
    if identity.is_file():
        git(repo, "add", "--", ".beads/identity.toml")
    if git(repo, "diff", "--cached", "--name-only"):
        git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "tutorial: record local orchestration infrastructure")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("registration left source changes; refusing to submit work")

LESSONS = {
    "greeting": ("Fix the greeting bug", TASK, None),
    "api": ("Add a reusable greeting API", """Add greeting_parts(name) to hello.py. It must return a dictionary
with exactly two keys: name is the supplied name, or world for an empty name;
message is the greeting returned by the existing greet function. For Ada the
result is {"name": "Ada", "message": "Hello, Ada!"}; for an empty name it is
{"name": "world", "message": "Hello, world!"}. Preserve greet and its existing
acceptance tests. Add unittest coverage for both API cases, run
python3 -m unittest discover -s tests -v, and commit. Keep this local: independent
review, tests, integration and cleanup must pass before the source closes.
Do not push or create a pull request.
""", "greeting"),
    "client": ("Use the accepted greeting API from a command-line client", """Add client.py, a small command-line client that imports greeting_parts
from hello.py. Running python3 client.py Ada must print one JSON object with
name Ada and message Hello, Ada!; with no argument it must print name world and
message Hello, world!. Use json.dumps, preserve the accepted API and existing
tests, and add unittest coverage for both CLI invocations. Run
python3 -m unittest discover -s tests -v and commit. Use the accepted API rather
than reimplementing it. Keep this local: independent review, tests, integration
and cleanup must pass before the source closes. Do not push or create a PR.
""", "api"),
}


def lesson_marker(lesson):
    return MARKER if lesson == "greeting" else MARKER + ":" + lesson


def find_lesson_source(gc, lesson):
    rows = gc("gc", "--rig", "practice", "bd", "list", "--all", "--metadata-field",
              "gc.tutorial=" + lesson_marker(lesson), "--limit", "0", "--json", json_output=True)
    if isinstance(rows, dict):
        rows = [rows]
    if len(rows) > 1:
        raise ValueError(f"multiple {lesson} task records found; inspect before proceeding")
    return rows[0] if rows else None


def attached_workflow(gc, source):
    from source_delivery import attached_workflow as lookup
    return lookup(gc, source, "practice")


def verified_delivery(source, destination, gc):
    """Verify accepted source, native finalization, local ancestry and cleanup."""
    import json
    sha = source.get("metadata", {}).get("gc.delivery.integrated_sha")
    if source.get("status") != "closed" or not sha:
        raise ValueError("complete the previous lesson with verified local integration first")
    git(destination, "merge-base", "--is-ancestor", sha, "HEAD")
    workflow_id = source.get("metadata", {}).get("gc.delivery.workflow_root")
    if not workflow_id:
        raise ValueError("integration is recorded but workflow finalization evidence is missing")
    workflow = gc("gc", "bd", "show", workflow_id, "--json", json_output=True)
    if workflow["status"] != "closed":
        print(f"Code integrated at {sha}; workflow {workflow_id} is finishing cleanup.")
        return None
    if workflow.get("metadata", {}).get("gc.outcome") != "pass":
        raise ValueError(f"code integrated, but workflow {workflow_id} finalization did not pass")
    record = json.loads(workflow.get("metadata", {}).get("gc.delivery.record", "{}"))
    if not record.get("cleanup_complete") or Path(record["worktree"]).exists():
        raise ValueError("workflow finalization lacks verified cleanup evidence")
    if record.get("review_status") != "approved" or any(
        record.get(field) != sha for field in ("output_sha", "reviewed_sha", "tested_sha", "integrated_sha")
    ):
        raise ValueError("delivery evidence does not identify one approved, reviewed and tested integrated commit")
    return sha


def show_delivery_progress(source, workflow, lesson=None):
    """Report native delivery milestones; never infer success from elapsed time."""
    import json
    import re
    root = workflow["id"]
    metadata = workflow.get("metadata", {})
    try:
        record = json.loads(metadata.get("gc.delivery.record", "{}"))
    except (ValueError, TypeError) as error:
        raise ValueError(f"workflow {root} has unreadable delivery evidence") from error
    if not isinstance(record, dict):
        raise ValueError(f"workflow {root} delivery evidence must be an object")
    if record and record.get("source") != source["id"]:
        raise ValueError(f"workflow {root} delivery evidence belongs to a different source")

    print(f"Workflow: {root}", flush=True)
    if workflow["status"] == "closed" and metadata.get("gc.outcome") != "pass":
        reason = metadata.get("gc.failure_reason") or workflow.get("close_reason") or metadata.get("close_reason") or metadata.get("gc.outcome", "unknown result")
        worktree = record.get("worktree")
        retained = f" Recorded worktree: {worktree}." if worktree else ""
        if record.get("integrated_sha") or source.get("metadata", {}).get("gc.delivery.integrated_sha"):
            recovery = "Code is already integrated; inspect existing finalization with gc status and preserve unfinished work."
        else:
            command = (f"gc gc tutorial retry --lesson {lesson}" if lesson else
                       f"gc gc source-delivery retry --root {root} --source {source['id']}")
            recovery = f"Inspect gc status and correct the reported problem, then run {command}; preserve unfinished work."
        raise ValueError(f"workflow {root} stopped: {reason}; source task remains open.{retained} {recovery}")

    reviewed = record.get("reviewed_sha", "")
    verified = bool(record.get("review_status") == "approved" and
                    isinstance(reviewed, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", reviewed) and
                    all(record.get(key) == reviewed for key in ("output_sha", "tested_sha")))
    integrated = record.get("integrated_sha")
    if integrated and (not verified or integrated != reviewed):
        raise ValueError(f"workflow {root} has inconsistent integration evidence")
    if workflow["status"] == "closed" and not (integrated and record.get("cleanup_complete") is True):
        raise ValueError(f"workflow {root} ended without verified integration and cleanup")

    if integrated and record.get("cleanup_complete") is True:
        message = ("Local change integrated and cleaned up; source-task closure pending"
                   if workflow["status"] == "closed" else
                   "Local change integrated and cleaned up; workflow finalization pending")
    elif integrated:
        message = "Local change integrated; cleanup pending"
    elif verified:
        message = "Review and verification passed; local integration pending"
    elif record.get("review_status") == "approved":
        message = "Independent review approved; verification pending"
    elif record.get("review_status") == "changes_required":
        message = "Independent review requested changes; bounded repair is owned by the workflow"
    elif record.get("review_status") == "blocked":
        message = "Independent review reports a blocker; inspect the workflow"
    elif record.get("worktree"):
        message = "Implementation and independent review pending"
    else:
        message = "Input and worktree preparation pending"
    print(message, flush=True)



def show_runtime_progress(gc, workflow):
    """Read the active native assignment; stored state is not provider readiness."""
    if workflow.get("status") == "closed":
        return
    root = workflow["id"]
    try:
        rows = gc("gc", "--rig", "practice", "bd", "list", "--all", "--include-ephemeral",
                  "--metadata-field", "gc.root_bead_id=" + root, "--limit", "0", "--json", json_output=True)
        if isinstance(rows, dict):
            rows = [rows]
        for step in rows:
            if step.get("metadata", {}).get("gc.root_bead_id") != root or step.get("status") != "in_progress":
                continue
            print(f"Active step {step['id']}: {step.get('title', 'untitled')}", flush=True)
            assignee = step.get("assignee")
            if not assignee:
                continue
            session = gc("gc", "bd", "show", assignee, "--json", json_output=True)
            if isinstance(session, list):
                if len(session) != 1:
                    raise ValueError("session identity unavailable")
                session = session[0]
            if session.get("id") != assignee or not (session.get("issue_type") == "session" or
                                                     "gc:session" in session.get("labels", [])):
                raise ValueError("assignment is not a native session")
            metadata = session.get("metadata", {})
            state = metadata.get("state", "unknown")
            reason = metadata.get("sleep_reason") or metadata.get("state_reason", "")
            until = metadata.get("quarantined_until")
            if until:
                detail = f"recorded state {state}; quarantine until {until}"
            elif reason == "runtime-missing":
                detail = "runtime is missing (recorded by GC)"
            else:
                detail = f"recorded state {state}" + (f"; {reason}" if reason else "")
            print(f"Native session {assignee}: {detail}", flush=True)
            if until or reason == "runtime-missing":
                print(f"Inspect: gc session logs {assignee}; gc doctor. Preserve this source and unfinished work; do not close it to clear the blocker.", flush=True)
    except (RuntimeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Runtime observation unavailable: {error}. Inspect with gc status. No work was restarted.", flush=True)


def tutorial_admission(city):
    """Serialize the local tutorial's lookup/create/dispatch across processes."""
    import contextlib
    import fcntl
    import stat
    @contextlib.contextmanager
    def acquire():
        path = Path(city) / ".gc" / "tutorial-admission.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("tutorial admission lock must be a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)
    return acquire()


def main():
    import argparse
    from source_delivery import gc, InfrastructureError
    parser = argparse.ArgumentParser(description="Run or inspect a guided local delivery lesson.")
    parser.add_argument("action", choices=["start", "status", "retry"], default="start", nargs="?")
    parser.add_argument("--lesson", choices=list(LESSONS), default="greeting")
    args = parser.parse_args()
    city = os.environ.get("GC_CITY_PATH")
    if not city:
        raise ValueError("run this command inside an initialized city")
    if args.action == "status":
        return _run_lesson(args, city, gc)
    with tutorial_admission(city):
        return _run_lesson(args, city, gc)


def _run_lesson(args, city, gc):
    import json
    from source_delivery import InfrastructureError
    destination = Path(city) / "projects" / "practice"
    rigs = gc("gc", "rig", "list", "--json", json_output=True)["rigs"]
    practice = [rig for rig in rigs if rig["name"] == "practice"]
    if practice and Path(practice[0]["path"]).resolve() != destination.resolve():
        raise ValueError("an existing practice rig points elsewhere; no changes made to it")
    title, description, previous = LESSONS[args.lesson]
    predecessor = None
    if args.action in ("start", "retry") and previous:
        if not practice:
            raise ValueError("complete the guided quickstart first; its practice rig is required")
        predecessor = find_lesson_source(gc, previous)
        if predecessor is None:
            raise ValueError(f"complete the {previous} lesson first")
        accepted = verified_delivery(predecessor, destination, gc)
        if not accepted:
            raise ValueError(f"complete {previous} workflow finalization before starting {args.lesson}")
        description += f"\nRequired predecessor: {predecessor['id']}; accepted input commit: {accepted}.\n"
        print(f"Previous lesson: {predecessor['id']}; verified accepted commit: {accepted}", flush=True)
    if args.action == "start":
        print("[1/4] Preparing your local practice repository", flush=True)
        scaffold(destination)
    if not practice:
        if args.action == "retry":
            raise ValueError("the practice lesson has not started; run gc gc tutorial start first")
        if args.action == "status":
            print("The guided task has not started. Run gc gc tutorial start.")
            return
        print("[2/4] Registering the practice repository", flush=True)
        gc("gc", "rig", "add", str(destination), "--name", "practice")
    source = find_lesson_source(gc, args.lesson)
    if source is None:
        if args.action == "retry":
            raise ValueError(f"the {args.lesson} lesson has not started; run gc gc tutorial start --lesson {args.lesson} first")
        if args.action == "status":
            print(f"The {args.lesson} lesson has not started. Run gc gc tutorial start --lesson {args.lesson}.")
            return
        if args.lesson == "greeting":
            finish_registration(destination)
        elif git(destination, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("practice repository has unfinished source changes; preserve them before submitting the next lesson")
        print("[3/4] Recording your task", flush=True)
        dependency = ("--deps", predecessor["id"]) if predecessor else ()
        source = gc("gc", "--rig", "practice", "bd", "create", title,
                    "--description", description, "--metadata", json.dumps({"gc.tutorial": lesson_marker(args.lesson)}),
                    *dependency, "--json", json_output=True)
    source_id = source["id"]
    print(f"Source task: {source_id}; status: {source['status']}", flush=True)
    if source["status"] == "closed":
        sha = verified_delivery(source, destination, gc)
        if sha:
            print(f"Verified local integration: {sha}\nRepository: {destination}")
            print("Continue the hands-on tutorials using this same city and repository.")
        return
    if args.action == "status":
        existing = source.get("metadata", {}).get("gc.delivery.workflow_root") or attached_workflow(gc, source)
        if existing:
            workflow = gc("gc", "bd", "show", existing, "--json", json_output=True)
            if workflow["status"] == "closed" and workflow.get("metadata", {}).get("gc.outcome") != "pass":
                current = attached_workflow(gc, source)
                if current and current != existing:
                    workflow = gc("gc", "bd", "show", current, "--json", json_output=True)
            show_delivery_progress(source, workflow, args.lesson)
            show_runtime_progress(gc, workflow)
        else:
            print("Workflow attachment pending; no delivery is recorded yet.", flush=True)
    if args.action == "retry":
        existing = attached_workflow(gc, source)
        if not existing:
            raise ValueError("no previous workflow is recorded; use gc gc tutorial start")
        workflow = gc("gc", "bd", "show", existing, "--json", json_output=True)
        if workflow["status"] != "closed":
            print(f"Existing workflow: {existing}", flush=True)
        else:
            receipt = gc("gc", "gc", "source-delivery", "retry", "--root", existing,
                         "--source", source_id, json_output=True)
            if receipt["status"] == "existing":
                print(f"Existing workflow: {receipt['workflow']}", flush=True)
            else:
                print(f"Attached workflow {receipt['workflow']}; same source task and input {receipt['input_sha']}", flush=True)
                if receipt.get("retained_worktree"):
                    print(f"Previous unfinished work retained: {receipt['retained_worktree']}", flush=True)
    if args.action == "start":
        existing = attached_workflow(gc, source)
        if existing:
            print(f"Existing workflow: {existing}", flush=True)
        else:
            print("[4/4] Starting implementation and independent review", flush=True)
            try:
                routed = gc("gc", "--rig", "practice", "sling", "practice/gc.run-operator", source_id, "--on", "quick-start",
                            "--var", "verify_command=" + VERIFY_COMMAND)
            except InfrastructureError:
                # Another invocation may have attached after the read. The
                # native sling guard owns admission; observe its existing work.
                existing = attached_workflow(gc, source)
                if not existing:
                    raise
                print(f"Existing workflow: {existing}", flush=True)
            else:
                print(routed, end="")
    print(f"Watch: gc status\nInspect: gc gc tutorial status --lesson {args.lesson}\nPause: gc stop\nResume: gc start")
    print("The source task closes only after the reviewed and tested commit is integrated locally.")


if __name__ == "__main__":
    from source_delivery import InfrastructureError
    try:
        main()
    except (ValueError, subprocess.SubprocessError, InfrastructureError) as error:
        raise SystemExit(str(error)) from error

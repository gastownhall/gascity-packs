#!/usr/bin/env python3
"""Commit identity and local integration gates for the guided workflow.

Workspace provisioning remains owned by gc worktree. Durable workflow evidence
belongs on the source/workflow beads; this module keeps no parallel state store.
"""
from pathlib import Path
import os
import re
import subprocess
import sys


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def clean(repo):
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(f"dirty checkout: {repo}; preserve changes before continuing")



def task_input(repo, default_branch, input_sha=""):
    """Pin the mainline; a fixed retry input never fetches or advances it."""
    if not default_branch:
        raise ValueError("rig has no default branch; configure it before submitting work")
    git(repo, "check-ref-format", "refs/heads/" + default_branch)
    expected = "refs/heads/" + default_branch
    if git(repo, "symbolic-ref", "--quiet", "HEAD") != expected:
        raise ValueError(f"checkout must be on the configured default branch {default_branch}; preserve and switch branches explicitly")
    clean(repo)
    predecessor = git(repo, "rev-parse", "HEAD")
    if input_sha:
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", input_sha):
            raise ValueError("fixed input must be a full immutable commit SHA")
        if predecessor != input_sha:
            raise ValueError("retry input changed; preserve current work before choosing a different input")
        return expected, input_sha, input_sha
    if "origin" not in git(repo, "remote").splitlines():
        return expected, predecessor, predecessor
    remote_ref = "refs/remotes/origin/" + default_branch
    try:
        git(repo, "fetch", "--no-tags", "origin", "+" + expected + ":" + remote_ref)
    except subprocess.CalledProcessError as exc:
        raise InfrastructureError("cannot fetch the configured default branch from origin") from exc
    base = git(repo, "rev-parse", remote_ref)
    try:
        git(repo, "merge-base", "--is-ancestor", predecessor, base)
    except subprocess.CalledProcessError:
        try:
            git(repo, "merge-base", "--is-ancestor", base, predecessor)
        except subprocess.CalledProcessError as exc:
            raise ValueError("local default branch diverged from origin; reconcile explicitly") from exc
        # Local integration is a supported delivery boundary. A subsequent task
        # must include accepted local work even before the user publishes it.
        return expected, predecessor, predecessor
    # Native worktree ownership binds the input ref to the eventual local
    # integration target. Advance only a clean, unchanged mainline so cleanup
    # can prove that the delivered commit landed on that same local ref.
    if git(repo, "symbolic-ref", "--quiet", "HEAD") != expected or git(repo, "rev-parse", "HEAD") != predecessor:
        raise ValueError("default branch changed during fetch; retry from a clean checkout")
    clean(repo)
    git(repo, "merge", "--ff-only", "--no-edit", base)
    if git(repo, "symbolic-ref", "--quiet", "HEAD") != expected or git(repo, "rev-parse", "HEAD") != base:
        raise ValueError("default branch changed while selecting delivery input")
    clean(repo)
    return expected, base, base


def registered_rig(repo):
    rigs = gc("gc", "rig", "list", "--json", json_output=True)["rigs"]
    matches = [rig for rig in rigs if Path(rig["path"]).resolve() == Path(repo).resolve()]
    if len(matches) != 1:
        raise ValueError("repository must identify exactly one registered rig")
    return matches[0]


def configured_default_branch(repo):
    return registered_rig(repo).get("default_branch", "")


def integrate(repo, worktree, base, output, reviewed, tested):
    """Fast-forward only the exact reviewed/tested output from the fixed input.

    Returning the already integrated output makes retries after a landed merge
    safe. Callers close source work only after persisting this returned SHA.
    """
    for identity in (base, output, reviewed, tested):
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", identity):
            raise ValueError("evidence must use a full immutable commit SHA")
    repo, worktree = Path(repo).resolve(), Path(worktree).resolve()
    if repo == worktree:
        raise ValueError("implementation must use an isolated worktree")
    if not output or output != reviewed or output != tested:
        raise ValueError("output, review and test evidence must name the same commit")
    for path in (repo, worktree):
        clean(path)
        if git(path, "rev-parse", "--show-toplevel") != str(path):
            raise ValueError(f"not a worktree root: {path}")
        if not git(path, "symbolic-ref", "--quiet", "HEAD"):
            raise ValueError(f"detached worktree: {path}")
    if git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") != git(
        worktree, "rev-parse", "--path-format=absolute", "--git-common-dir"
    ):
        raise ValueError("worktree belongs to a different repository")
    if git(worktree, "rev-parse", "HEAD") != output:
        raise ValueError("worktree output changed after review or verification")
    # Disallow an unrelated output even when both evidence strings name it.
    git(repo, "merge-base", "--is-ancestor", base, output)
    current = git(repo, "rev-parse", "HEAD")
    if current != output:
        if current != base:
            raise ValueError("integration input changed; rebase and review explicitly")
        git(repo, "merge", "--ff-only", "--no-edit", output)
    if git(repo, "rev-parse", "HEAD") != output:
        raise ValueError("integration did not produce the verified output")
    clean(repo)
    return output


class InfrastructureError(RuntimeError):
    """A temporary store/runtime failure provided no content verdict."""


class ValidatorEnvironmentError(InfrastructureError):
    """The configured validator cannot run until its environment is repaired."""


def gc(*args, json_output=False):
    import json
    if not args or args[0] != "gc":
        raise ValueError("expected an explicit gc command")
    try:
        result = subprocess.check_output([os.environ.get("GC_BIN", "gc"), *args[1:]], text=True, stderr=sys.stderr)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InfrastructureError(f"Gas City operation unavailable: {exc}") from exc
    if not json_output:
        return result
    try:
        value = json.loads(result)
    except json.JSONDecodeError as exc:
        raise InfrastructureError("Gas City returned an unreadable observation") from exc
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def bead(bead_id):
    value = gc("gc", "bd", "show", bead_id, "--json", json_output=True)
    if not isinstance(value, dict) or value.get("id") != bead_id:
        raise ValueError(f"expected exactly one bead: {bead_id}")
    return value


def save(root, record):
    import json
    gc("gc", "bd", "update", root, "--set-metadata", "gc.delivery.record=" + json.dumps(record, separators=(",", ":")))


def load(root):
    import json
    value = bead(root).get("metadata", {}).get("gc.delivery.record")
    if not value:
        raise ValueError("missing prepared source delivery record")
    return json.loads(value)


def workspace_args(record):
    return [
        "--repo", record["repo"], "--root", record["worktree_root"],
        "--path", record["worktree"], "--branch", record["branch"],
        "--base", record["base_ref"], "--base-sha", record["base_sha"],
        "--bead", record["source"], "--store-ref", record.get("store_ref", record["repo"]),
        "--creator", "formula-quick-start", "--owner", "formula",
        "--generation", record["root"], "--json",
    ]


def prepare(root, source, repo, workspace_root, verify_command):
    import json
    repo = str(Path(repo).resolve())
    root_row = bead(root)
    input_sha = root_row.get("metadata", {}).get("gc.var.input_sha", "")
    existing = root_row.get("metadata", {}).get("gc.delivery.record")
    if existing:
        record = json.loads(existing)
        if (record["source"], record["repo"], record["verify_command"]) != (source, repo, verify_command):
            raise ValueError("retry changed source, repository or verification contract")
        if input_sha and record["base_sha"] != input_sha:
            raise ValueError("retry changed the fixed input contract")
    else:
        if bead(source).get("status") == "closed":
            raise ValueError("source task is already closed")
        base_ref, base, predecessor = task_input(repo, configured_default_branch(repo), input_sha)
        if not verify_command.strip():
            raise ValueError("a verification command is required")
        workspace_root = str(Path(workspace_root).resolve())
        # Root identity, rather than a title, makes branch/path ownership unique.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", root):
            raise ValueError("unsafe workflow root identity")
        store_ref = root_row.get("metadata", {}).get("gc.root_store_ref")
        if not store_ref:
            raise ValueError("workflow root has no authoritative store reference")
        record = dict(root=root, source=source, repo=repo, store_ref=store_ref, base_ref=base_ref,
                      base_sha=base, predecessor_sha=predecessor,
                      integration_ref=git(repo, "symbolic-ref", "--quiet", "HEAD"), worktree_root=workspace_root,
                      worktree=str(Path(workspace_root) / root), branch="gc/" + root,
                      verify_command=verify_command)
        # Pin the input before provisioning, so a crash cannot choose a newer base.
        save(root, record)
    # Native workflow finalization closes the source only after integration
    # and cleanup pass. Keeping input work open preserves remaining graph demand.
    source_link = root_row.get("metadata", {}).get("gc.source_bead_id")
    if source_link and source_link != source:
        raise ValueError("workflow source link differs from the prepared source")
    source_store_ref = record.get("store_ref") or root_row.get("metadata", {}).get("gc.root_store_ref")
    if not source_store_ref:
        raise ValueError("workflow source store reference is missing")
    gc("gc", "bd", "update", root, "--set-metadata", "gc.source_bead_id=" + source,
       "--set-metadata", "gc.source_store_ref=" + source_store_ref)
    if record.get("integrated_sha"):
        return record
    report = gc("gc", "worktree", "ensure", *workspace_args(record), json_output=True)
    record["attempt_id"] = report["provenance"]["attempt_id"]
    save(root, record)
    gc("gc", "bd", "update", source, "--set-metadata", "work_dir=" + record["worktree"],
       "--set-metadata", "gc.delivery.workflow_root=" + root)
    return record



VERIFY_TIMEOUT = 600


def _validator_session_processes(session_id):
    listing = subprocess.check_output(["/bin/ps", "-axo", "pid=,stat="],
                                     text=True, timeout=5)
    found = []
    for row in listing.splitlines():
        pid_text, state = row.split()[:2]
        pid = int(pid_text)
        try:
            if os.getsid(pid) == session_id:
                found.append((pid, state))
        except ProcessLookupError:
            pass
    return found


def _stop_validator(child):
    import signal
    import time
    def send(sig):
        for pid, _ in _validator_session_processes(child.pid):
            try:
                if os.getsid(pid) == child.pid:
                    os.kill(pid, sig)
            except ProcessLookupError:
                pass
    # The unreaped leader reserves this session identity throughout cleanup.
    try:
        send(signal.SIGTERM)
        time.sleep(2)
    finally:
        send(signal.SIGKILL)
    deadline = time.monotonic() + 5
    while True:
        active = [pid for pid, state in _validator_session_processes(child.pid)
                  if not state.startswith("Z")]
        if not active:
            child.wait(timeout=5)
            return
        if time.monotonic() >= deadline:
            raise ValidatorEnvironmentError(
                f"verification session {child.pid} did not stop; preserve the worktree "
                "and inspect its processes before retrying; source remains open")
        time.sleep(0.05)


def run_validator(command, tree):
    import signal
    import tempfile
    import time
    pending = 0
    captured = None
    def terminate(signum, frame):
        nonlocal pending
        # Never raise asynchronously: a signal can arrive inside Popen or while
        # entering cleanup. The bounded wait below delivers cancellation safely.
        pending = signum
    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        # A file retains diagnostics even when the shell dies before descendants.
        # Pipes let an inherited writer keep communicate() waiting indefinitely.
        with tempfile.TemporaryFile(mode="w+t") as output:
            child = None
            try:
                child = subprocess.Popen(command, shell=True, cwd=tree, stdout=output,
                                         stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + VERIFY_TIMEOUT
                while True:
                    if pending:
                        raise SystemExit(128 + pending)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, VERIFY_TIMEOUT)
                    try:
                        status = child.wait(timeout=min(0.1, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        continue
                output.seek(0)
                captured = output.read()
                if pending:
                    raise SystemExit(128 + pending)
                return subprocess.CompletedProcess(command, status, captured)
            except BaseException:
                try:
                    if child is not None and child.returncode is None:
                        _stop_validator(child)
                except Exception as exc:
                    raise ValidatorEnvironmentError(
                        f"cannot stop owned verification session {child.pid}: {exc}; "
                        "preserve its worktree and inspect before retrying") from exc
                finally:
                    output.seek(0)
                    print(output.read(), end="", flush=True)
                raise
    finally:
        signal.signal(signal.SIGTERM, previous)
        # Cancellation also wins if it arrived after the last wait/read check.
        # Preserve an existing cleanup error (and its environment hold).
        if pending and sys.exc_info()[0] is None:
            if captured is not None:
                print(captured, end="", flush=True)
            raise SystemExit(128 + pending)


def verify_output(root):
    import hashlib
    record = load(root)
    gc("gc", "worktree", "verify", *workspace_args(record), json_output=True)
    tree = record["worktree"]
    clean(tree)
    output = git(tree, "rev-parse", "HEAD")
    if record.get("reviewed_sha") != output or record.get("review_status") != "approved":
        raise ValueError("independent review has not approved the current output")
    result = run_validator(record["verify_command"], tree)
    print(result.stdout, end="")
    # Configuration failures must stay on the dispatcher's EX_CONFIG hold,
    # not its bounded temporary-infrastructure retry lane. Keep the actual
    # validator/interpreter diagnostic on stderr where the hold reason reads it.
    diagnostic = next((line.strip() for line in result.stdout.splitlines() if line.strip()),
                      "validator supplied no diagnostic")
    if result.returncode in (78, 126, 127):
        raise ValidatorEnvironmentError(
            f"verification command unavailable (exit {result.returncode}): {diagnostic}; "
            "restore its prerequisites or executable/PATH and retry the same workflow; source remains open")
    if result.returncode == 75:
        raise InfrastructureError(
            f"verification command temporarily unavailable (exit 75): {diagnostic}; source remains open")
    if result.returncode:
        raise ValueError(f"verification failed with exit {result.returncode}; source remains open")
    clean(tree)
    if git(tree, "rev-parse", "HEAD") != output:
        raise ValueError("verification changed the output commit")
    record.update(output_sha=output, tested_sha=output,
                  test_output_sha256=hashlib.sha256(result.stdout.encode()).hexdigest())
    save(root, record)
    return record


def workflow_beads(gc):
    """Read fresh, complete native work and graph rows before proving absence.

    Explicit fresh/strict selects the native execution-host census, bypasses
    indexed/API caches, and refuses any unavailable configured store or binding.
    A best-effort listing cannot establish that a workflow does not exist.
    """
    value = gc("gc", "beads", "list", "--all", "--fresh", "--strict", "--format=json", json_output=True)
    # gc() unwraps singleton arrays, but a cached/partial envelope is never the
    # authoritative direct-read contract. Reject it rather than treating it as
    # an empty set (including future partial/truncation indicators).
    if isinstance(value, dict) and isinstance(value.get("id"), str):
        value = [value]
    if not isinstance(value, list):
        raise InfrastructureError("complete native workflow observation unavailable")
    for row in value:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip()
                or not isinstance(row.get("status"), str) or not row["status"].strip()
                or not isinstance(row.get("metadata", {}), dict)
                or any(not isinstance(key, str) or not isinstance(item, str)
                       for key, item in row.get("metadata", {}).items())
                or not isinstance(row.get("labels", []), list)
                or any(not isinstance(label, str) for label in row.get("labels", []))
                or not isinstance(row.get("issue_type", ""), str)):
            raise InfrastructureError("complete native workflow observation is malformed")
    return value


def attached_workflow(gc, source, rig):
    """Follow native direct and convoy-first bindings without relaunching work."""
    def rows(*args):
        result = gc("gc", "--rig", rig, "bd", *args, json_output=True)
        return [result] if isinstance(result, dict) else result

    snapshot = workflow_beads(gc)
    scope = "rig:" + rig

    def keyed_roots(key, value, formula=None):
        matches = [row for row in snapshot if row.get("metadata", {}).get(key) == value
                   and (formula is None or row.get("metadata", {}).get("gc.formula_name", "").strip() == formula)]
        roots = []
        for row in matches:
            metadata = row.get("metadata", {})
            # Store refs identify logical source/root scope, never a physical
            # binding. The graph may live in infra while its scope is rig:….
            source_scope = metadata.get("gc.source_store_ref")
            root_scope = metadata.get("gc.root_store_ref")
            if source_scope and source_scope != scope:
                continue
            if not source_scope and root_scope and root_scope != scope:
                continue
            kind = metadata.get("gc.kind", "").strip().lower()
            contract = metadata.get("gc.formula_contract", "").strip().lower()
            controller = row.get("issue_type", "").strip().lower() in {
                "session", "startup-health-episode", "convergence", "op"}
            controller |= any(label.strip().lower() == "gc:session" for label in row.get("labels", []))
            if not controller and (kind == "workflow" or contract == "graph.v2"):
                if not source_scope and not root_scope:
                    raise ValueError("matching workflow scope is unavailable; inspect native store identity before retrying")
                roots.append(row)
        return roots

    roots_by_id = {}

    def add_root(row):
        previous = roots_by_id.get(row["id"])
        if previous is not None and previous != row:
            raise ValueError("ambiguous workflow identity across native stores; inspect before retrying")
        roots_by_id[row["id"]] = row

    for row in keyed_roots("gc.source_bead_id", source["id"]):
        add_root(row)
    # A bare-source --on launch initially binds through its synthetic input
    # convoy. prepare adds the delivery back-link later; it is not admission.
    excluded = {"gc:session", "gc:order-tracking", "order-tracking", "gc:op", "gc:fact", "gc:rt"}
    for convoy in rows("dep", "list", source["id"], "--direction", "up", "--type", "tracks", "--json"):
        if (convoy.get("issue_type") != "convoy" or
                convoy.get("metadata", {}).get("gc.synthetic", "").strip() != "true" or
                excluded.intersection(convoy.get("labels", []))):
            continue
        for row in keyed_roots("gc.input_convoy_id", convoy["id"], formula="quick-start"):
            add_root(row)
    roots = list(roots_by_id.values())
    live = [row for row in roots if row.get("status") != "closed"]
    if len(live) > 1:
        raise ValueError("multiple live workflows for this lesson; inspect the preserved source and workflows")
    if live:
        return live[0]["id"]
    if len(roots) == 1:
        return roots[0]["id"]
    if roots:
        hint = source.get("metadata", {}).get("gc.delivery.workflow_root")
        if any(row["id"] == hint for row in roots):
            return hint
        raise ValueError("multiple completed workflows for this lesson; inspect the preserved source and workflows")
    return None



def retry_delivery(root, source=None):
    """Admit one explicit bounded attempt through native sling; retain the old one."""
    workflow = bead(root)
    metadata = workflow.get("metadata", {})
    import json
    raw = metadata.get("gc.delivery.record")
    if raw:
        record = json.loads(raw)
        required = ("source", "repo", "store_ref", "base_sha", "integration_ref", "verify_command")
        if not isinstance(record, dict) or any(not isinstance(record.get(k), str) or not record[k].strip() for k in required):
            raise ValueError("retry has an incomplete prepared delivery record")
        if record.get("root") != root or not Path(record["repo"]).is_absolute():
            raise ValueError("retry record differs from its native workflow ownership")
        source_id = record["source"]
        if source and source != source_id:
            raise ValueError("retry source differs from the recorded workflow source")
        if metadata.get("gc.source_bead_id") != source_id:
            raise ValueError("retry source differs from the native workflow binding")
    else:
        if not source:
            raise ValueError("retry before preparation requires --source with the original task ID")
        convoy = metadata.get("gc.input_convoy_id")
        if not convoy:
            raise ValueError("unprepared retry has no native input convoy binding")
        inputs = gc("gc", "convoy", "status", convoy, "--json", json_output=True).get("children", [])
        if len(inputs) != 1 or inputs[0].get("id") != source:
            raise ValueError("retry must match exactly one original native input source")
        scope = metadata.get("gc.root_store_ref", "")
        if not scope.startswith("rig:"):
            raise ValueError("unprepared retry must identify its native rig store")
        matches = [r for r in gc("gc", "rig", "list", "--json", json_output=True)["rigs"] if r["name"] == scope[4:]]
        if len(matches) != 1:
            raise ValueError("unprepared retry must identify one registered rig")
        repo = str(Path(matches[0]["path"]).resolve())
        branch = matches[0].get("default_branch", "")
        source_id = source
        record = {"root": root, "source": source_id, "repo": repo, "store_ref": scope,
                  "base_sha": metadata.get("gc.var.input_sha") or git(repo, "rev-parse", "HEAD"),
                  "integration_ref": "refs/heads/" + branch,
                  "verify_command": metadata.get("gc.var.verify_command", "")}

    source_row = bead(source_id)
    if source_row["status"] == "closed":
        raise ValueError("source task already completed; inspect its delivery instead")
    rig = registered_rig(record["repo"])
    if record.get("store_ref") != "rig:" + rig["name"]:
        raise ValueError("retry store differs from the registered repository")
    if metadata.get("gc.formula_name") != "quick-start":
        raise ValueError("retry requires the native quick-start delivery workflow")

    def active_receipt():
        current = attached_workflow(gc, source_row, rig["name"])
        if current and bead(current)["status"] != "closed":
            return {"status": "existing", "source": source_id, "workflow": current}
        return None

    current = attached_workflow(gc, source_row, rig["name"])
    current_row = workflow if current == root else bead(current) if current else None
    if current_row and current_row["status"] != "closed":
        return {"status": "existing", "source": source_id, "workflow": current}
    if current != root:
        raise ValueError("source has a different current workflow; inspect it before retrying")
    if workflow["status"] != "closed" or metadata.get("gc.outcome") not in {"fail", "failed", "skipped", "canceled", "cancelled"}:
        raise ValueError("only a stopped unsuccessful workflow can start a new attempt")
    if record.get("integrated_sha") or source_row.get("metadata", {}).get("gc.delivery.integrated_sha"):
        raise ValueError("code is already integrated; preserve and inspect its existing finalization")
    verify = record.get("verify_command", "")
    if not verify.strip() or metadata.get("gc.var.verify_command") != verify:
        raise ValueError("retry verification differs from the native fixed contract")
    repo = record["repo"]
    clean(repo)
    expected_ref = "refs/heads/" + rig.get("default_branch", "")
    if record.get("integration_ref") != expected_ref or git(repo, "symbolic-ref", "--quiet", "HEAD") != expected_ref:
        raise ValueError("retry default branch changed; preserve the recorded input")
    base = record["base_sha"]
    fixed = metadata.get("gc.var.input_sha", "")
    if fixed and fixed != base:
        raise ValueError("retry input differs from the native fixed input contract")
    task_input(repo, rig["default_branch"], input_sha=base)
    try:
        admitted = gc("gc", "--rig", rig["name"], "sling", source_id, "--on", "quick-start",
                      "--var", "verify_command=" + verify, "--var", "input_sha=" + base)
    except InfrastructureError:
        observed = active_receipt()
        if observed and observed["workflow"] != root:
            return observed
        raise
    match = re.search(r"Attached workflow ([\w-]+)", admitted)
    if not match:
        observed = active_receipt()
        if observed:
            return observed
        raise ValueError("native GC did not admit a new attempt; inspect gc status: " + admitted)
    return {"status": "started", "source": source_id, "workflow": match.group(1),
            "previous_workflow": root, "input_sha": base,
            "retained_worktree": record.get("worktree")}


def main():
    import argparse
    import json
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "show", "review", "check", "integrate", "cleanup", "retry"])
    parser.add_argument("--root")
    parser.add_argument("--source")
    parser.add_argument("--repo")
    parser.add_argument("--workspace-root")
    parser.add_argument("--verify-command")
    parser.add_argument("--sha")
    parser.add_argument("--status", choices=["approved", "changes_required", "blocked"])
    parser.add_argument("--findings", default="")
    args = parser.parse_args()
    root = args.root
    if not root:
        subject = os.environ.get("GC_BEAD_ID")
        if not subject:
            raise ValueError("--root or GC_BEAD_ID is required")
        row = bead(subject)
        root = row.get("metadata", {}).get("gc.root_bead_id")
        if not root:
            raise ValueError("check subject has no workflow root")
    if args.action == "prepare":
        if not all((args.source, args.repo, args.workspace_root, args.verify_command)):
            raise ValueError("prepare requires source, repo, workspace-root and verify-command")
        record = prepare(root, args.source, args.repo, args.workspace_root, args.verify_command)
    elif args.action == "retry":
        record = retry_delivery(root, args.source)
    elif args.action == "check":
        record = verify_output(root)
    else:
        record = load(root)
        if args.action == "review":
            if not args.status or args.sha != git(record["worktree"], "rev-parse", "HEAD"):
                raise ValueError("review must name current output SHA and terminal status")
            clean(record["worktree"])
            if args.status == "approved" and args.findings.strip():
                raise ValueError("approval cannot retain unresolved findings")
            if args.status != "approved" and not args.findings.strip():
                raise ValueError("rejected review must explain required changes")
            record.update(reviewed_sha=args.sha, review_status=args.status, findings=args.findings)
            save(root, record)
        elif args.action == "integrate":
            gc("gc", "worktree", "verify", *workspace_args(record), json_output=True)
            if record.get("review_status") != "approved":
                raise ValueError("review is not approved")
            if record.get("integration_ref") and git(record["repo"], "symbolic-ref", "--quiet", "HEAD") != record["integration_ref"]:
                raise ValueError("integration branch changed; restore the recorded default branch explicitly")
            git(record["worktree"], "merge-base", "--is-ancestor", record["base_sha"], record.get("output_sha", ""))
            integrated = integrate(record["repo"], record["worktree"], record.get("predecessor_sha", record["base_sha"]),
                                   record.get("output_sha", ""), record.get("reviewed_sha", ""),
                                   record.get("tested_sha", ""))
            record["integrated_sha"] = integrated
            save(root, record)
            gc("gc", "bd", "update", record["source"], "--set-metadata",
               "gc.delivery.integrated_sha=" + integrated)
            # Leave the source open. The native finalizer owns source closure
            # after cleanup and every other required graph stage pass.
        elif args.action == "cleanup":
            if not record.get("integrated_sha"):
                raise ValueError("unintegrated work must be retained")
            if git(record["repo"], "merge-base", "--is-ancestor", record["integrated_sha"], "HEAD"):
                raise ValueError("integrated output no longer reachable")
            gc("gc", "worktree", "cleanup", *workspace_args(record), "--attempt-id", record["attempt_id"], json_output=True)
            record["cleanup_complete"] = True
            save(root, record)
    print(json.dumps(record, indent=2))


def _cli():
    """Keep the terminal failure first while preserving child diagnostics."""
    import contextlib
    import shutil
    import tempfile
    status = 0
    # Anonymous, process-owned I/O buffer: native gc diagnostics can precede
    # validation, but the dispatcher uses the first stderr line as its reason.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as diagnostics:
        try:
            with contextlib.redirect_stderr(diagnostics):
                main()
        except ValidatorEnvironmentError as exc:
            print(f"source delivery environment: {exc}", file=sys.stderr)
            status = 78
        except InfrastructureError as exc:
            print(f"source delivery infrastructure: {exc}", file=sys.stderr)
            status = 75
        except (ValueError, subprocess.SubprocessError) as exc:
            print(f"source delivery: {exc}", file=sys.stderr)
            status = 1
        finally:
            diagnostics.seek(0)
            shutil.copyfileobj(diagnostics, sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(_cli())

#!/usr/bin/env python3
"""Commit identity and local integration gates for the guided workflow.

Workspace provisioning remains owned by gc worktree. Durable workflow evidence
belongs on the source/workflow beads; this module keeps no parallel state store.
"""
from pathlib import Path
import os
import re
import subprocess


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE
    ).strip()


def clean(repo):
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError(f"dirty checkout: {repo}; preserve changes before continuing")



def task_input(repo, default_branch):
    """Pin the configured mainline, fetching origin when the repository has one."""
    if not default_branch:
        raise ValueError("rig has no default branch; configure it before submitting work")
    git(repo, "check-ref-format", "refs/heads/" + default_branch)
    expected = "refs/heads/" + default_branch
    if git(repo, "symbolic-ref", "--quiet", "HEAD") != expected:
        raise ValueError(f"checkout must be on the configured default branch {default_branch}; preserve and switch branches explicitly")
    clean(repo)
    predecessor = git(repo, "rev-parse", "HEAD")
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


def configured_default_branch(repo):
    rigs = gc("gc", "rig", "list", "--json", json_output=True)["rigs"]
    matches = [rig for rig in rigs if Path(rig["path"]).resolve() == Path(repo).resolve()]
    if len(matches) != 1:
        raise ValueError("repository must identify exactly one registered rig")
    return matches[0].get("default_branch", "")


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
    """A store/runtime observation failed before a content verdict existed."""


def gc(*args, json_output=False):
    import json
    if not args or args[0] != "gc":
        raise ValueError("expected an explicit gc command")
    try:
        result = subprocess.check_output([os.environ.get("GC_BIN", "gc"), *args[1:]], text=True)
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
    existing = root_row.get("metadata", {}).get("gc.delivery.record")
    if existing:
        record = json.loads(existing)
        if (record["source"], record["repo"], record["verify_command"]) != (source, repo, verify_command):
            raise ValueError("retry changed source, repository or verification contract")
    else:
        if bead(source).get("status") == "closed":
            raise ValueError("source task is already closed")
        base_ref, base, predecessor = task_input(repo, configured_default_branch(repo))
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


def verify_output(root):
    import hashlib
    record = load(root)
    gc("gc", "worktree", "verify", *workspace_args(record), json_output=True)
    tree = record["worktree"]
    clean(tree)
    output = git(tree, "rev-parse", "HEAD")
    if record.get("reviewed_sha") != output or record.get("review_status") != "approved":
        raise ValueError("independent review has not approved the current output")
    result = subprocess.run(record["verify_command"], shell=True, cwd=tree,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600)
    print(result.stdout, end="")
    if result.returncode:
        raise ValueError(f"verification failed with exit {result.returncode}; source remains open")
    clean(tree)
    if git(tree, "rev-parse", "HEAD") != output:
        raise ValueError("verification changed the output commit")
    record.update(output_sha=output, tested_sha=output,
                  test_output_sha256=hashlib.sha256(result.stdout.encode()).hexdigest())
    save(root, record)
    return record


def main():
    import argparse
    import json
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "show", "review", "check", "integrate", "cleanup"])
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


if __name__ == "__main__":
    try:
        main()
    except InfrastructureError as exc:
        import sys
        print(f"source delivery infrastructure: {exc}", file=sys.stderr)
        sys.exit(75)
    except (ValueError, subprocess.SubprocessError) as exc:
        import sys
        print(f"source delivery: {exc}", file=sys.stderr)
        sys.exit(1)

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


def gc(*args, json_output=False):
    import json
    result = subprocess.check_output([os.environ.get("GC_BIN", "gc"), *args], text=True)
    if not json_output:
        return result
    value = json.loads(result)
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def bead(bead_id):
    value = gc("bd", "show", bead_id, "--json", json_output=True)
    if not isinstance(value, dict) or value.get("id") != bead_id:
        raise ValueError(f"expected exactly one bead: {bead_id}")
    return value


def save(root, record):
    import json
    gc("bd", "update", root, "--set-metadata", "gc.delivery.record=" + json.dumps(record, separators=(",", ":")))


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
        "--bead", record["source"], "--store-ref", record["repo"],
        "--creator", "formula-quick-start", "--owner", "formula",
        "--generation", record["root"], "--json",
    ]


def prepare(root, source, repo, workspace_root, verify_command):
    import json
    repo = str(Path(repo).resolve())
    existing = bead(root).get("metadata", {}).get("gc.delivery.record")
    if existing:
        record = json.loads(existing)
        if (record["source"], record["repo"], record["verify_command"]) != (source, repo, verify_command):
            raise ValueError("retry changed source, repository or verification contract")
    else:
        if bead(source).get("status") == "closed":
            raise ValueError("source task is already closed")
        clean(repo)
        base_ref = git(repo, "symbolic-ref", "--quiet", "HEAD")
        base = git(repo, "rev-parse", "HEAD")
        if not verify_command.strip():
            raise ValueError("a verification command is required")
        workspace_root = str(Path(workspace_root).resolve())
        # Root identity, rather than a title, makes branch/path ownership unique.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", root):
            raise ValueError("unsafe workflow root identity")
        record = dict(root=root, source=source, repo=repo, base_ref=base_ref,
                      base_sha=base, predecessor_sha=base, worktree_root=workspace_root,
                      worktree=str(Path(workspace_root) / root), branch="gc/" + root,
                      verify_command=verify_command)
        # Pin the input before provisioning, so a crash cannot choose a newer base.
        save(root, record)
    if record.get("integrated_sha"):
        return record
    report = gc("worktree", "ensure", *workspace_args(record), json_output=True)
    record["attempt_id"] = report["provenance"]["attempt_id"]
    save(root, record)
    gc("bd", "update", source, "--set-metadata", "work_dir=" + record["worktree"])
    return record


def verify_output(root):
    import hashlib
    record = load(root)
    gc("worktree", "verify", *workspace_args(record), json_output=True)
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
            gc("worktree", "verify", *workspace_args(record), json_output=True)
            if record.get("review_status") != "approved":
                raise ValueError("review is not approved")
            integrated = integrate(record["repo"], record["worktree"], record["base_sha"],
                                   record.get("output_sha", ""), record.get("reviewed_sha", ""),
                                   record.get("tested_sha", ""))
            record["integrated_sha"] = integrated
            save(root, record)
            source = bead(record["source"])
            if source.get("status") != "closed":
                gc("bd", "update", record["source"], "--set-metadata", "gc.outcome=pass",
                   "--set-metadata", "gc.delivery.integrated_sha=" + integrated)
                gc("bd", "close", record["source"], "--reason", "Integrated reviewed and tested commit " + integrated)
            source = bead(record["source"])
            if source.get("status") != "closed" or source.get("metadata", {}).get("gc.delivery.integrated_sha") != integrated:
                raise ValueError("source closure does not match integrated evidence")
        elif args.action == "cleanup":
            if not record.get("integrated_sha"):
                raise ValueError("unintegrated work must be retained")
            if git(record["repo"], "merge-base", "--is-ancestor", record["integrated_sha"], "HEAD"):
                raise ValueError("integrated output no longer reachable")
            gc("worktree", "cleanup", *workspace_args(record), "--attempt-id", record["attempt_id"], json_output=True)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.SubprocessError) as exc:
        import sys
        print(f"source delivery: {exc}", file=sys.stderr)
        sys.exit(1)

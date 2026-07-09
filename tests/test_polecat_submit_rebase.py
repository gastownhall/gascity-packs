from __future__ import annotations

import subprocess
from pathlib import Path


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
    )


def git_logs(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


def git_ok(cwd: Path, *args: str) -> None:
    git(cwd, *args)


def git_out(cwd: Path, *args: str) -> str:
    return git(cwd, *args).stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit_all(repo: Path, message: str) -> str:
    git_ok(repo, "add", "-A")
    git_ok(repo, "commit", "-m", message)
    return git_out(repo, "rev-parse", "HEAD")


def clone_repo(src: Path, dest: Path) -> Path:
    git_ok(dest.parent, "clone", str(src), str(dest))
    git_ok(dest, "config", "user.name", "Test User")
    git_ok(dest, "config", "user.email", "test@example.com")
    return dest


def init_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    git_ok(tmp_path, "init", "--bare", str(remote))
    clone_repo(remote, seed)
    return remote, seed


def create_initial_main(seed: Path) -> str:
    write(seed / "app.txt", "base\n")
    write(seed / "obsolete.txt", "legacy\n")
    git_ok(seed, "checkout", "-b", "main")
    sha = commit_all(seed, "base")
    git_ok(seed, "push", "-u", "origin", "main")
    return sha


def clone_branch_worker(remote: Path, tmp_path: Path) -> Path:
    worker = clone_repo(remote, tmp_path / "worker")
    git_ok(worker, "checkout", "-b", "polecat/stale-base", "origin/main")
    return worker


def advance_main(remote: Path, tmp_path: Path, update: callable[[Path], None]) -> str:
    maintainer = clone_repo(remote, tmp_path / "maintainer")
    git_ok(maintainer, "checkout", "main")
    update(maintainer)
    sha = commit_all(maintainer, "advance main")
    git_ok(maintainer, "push", "origin", "main")
    return sha


def old_submit_push(worker: Path) -> str:
    git_ok(worker, "push", "-u", "origin", "HEAD")
    return git_out(worker, "rev-parse", "HEAD")


def final_submit_rebase(worker: Path, target_branch: str = "main") -> str:
    git_ok(
        worker,
        "fetch",
        "origin",
        f"+refs/heads/{target_branch}:refs/remotes/origin/{target_branch}",
    )
    git_ok(worker, "rebase", f"origin/{target_branch}")
    return git_out(worker, "rev-parse", "HEAD")


def refinery_rebase(remote: Path, tmp_path: Path, branch: str, target_branch: str = "main") -> subprocess.CompletedProcess[str]:
    refinery = clone_repo(remote, tmp_path / f"refinery-{branch.replace('/', '-')}")
    git_ok(refinery, "checkout", "-b", "temp", f"origin/{branch}")
    git_ok(
        refinery,
        "fetch",
        "origin",
        f"+refs/heads/{target_branch}:refs/remotes/origin/{target_branch}",
    )
    return git(refinery, "rebase", f"origin/{target_branch}", check=False)


def diff_names(worker: Path, target_branch: str = "main") -> list[str]:
    output = git_out(worker, "diff", "--name-only", f"origin/{target_branch}...HEAD")
    return [line for line in output.splitlines() if line]


def test_stale_submit_without_final_rebase_hits_refinery_conflict(tmp_path: Path) -> None:
    remote, seed = init_remote(tmp_path)
    create_initial_main(seed)
    worker = clone_branch_worker(remote, tmp_path)

    write(worker / "app.txt", "branch change\n")
    commit_all(worker, "branch change")

    advance_main(
        remote,
        tmp_path,
        lambda repo: write(repo / "app.txt", "target change\n"),
    )

    old_submit_push(worker)
    result = refinery_rebase(remote, tmp_path, "polecat/stale-base")

    assert result.returncode != 0
    assert "CONFLICT" in git_logs(result)


def test_final_submit_rebase_drops_already_merged_deletions_and_merges_cleanly(tmp_path: Path) -> None:
    remote, seed = init_remote(tmp_path)
    create_initial_main(seed)
    worker = clone_branch_worker(remote, tmp_path)

    (worker / "obsolete.txt").unlink()
    write(worker / "feature.txt", "new work\n")
    commit_all(worker, "branch work")

    target_head = advance_main(
        remote,
        tmp_path,
        lambda repo: (repo / "obsolete.txt").unlink(),
    )

    old_submit_push(worker)
    assert "obsolete.txt" in diff_names(worker)

    git_ok(worker, "reset", "--hard", "HEAD")
    rebased_head = final_submit_rebase(worker)

    assert git_out(worker, "rev-parse", "origin/main") == target_head
    assert rebased_head != git_out(worker, "rev-parse", "origin/polecat/stale-base")
    assert "obsolete.txt" not in diff_names(worker)

    git_ok(worker, "push", "--force-with-lease", "-u", "origin", "HEAD")
    result = refinery_rebase(remote, tmp_path, "polecat/stale-base")
    assert result.returncode == 0


def test_final_submit_rebase_surfaces_genuine_conflicts_locally(tmp_path: Path) -> None:
    remote, seed = init_remote(tmp_path)
    create_initial_main(seed)
    worker = clone_branch_worker(remote, tmp_path)

    write(worker / "app.txt", "branch change\n")
    commit_all(worker, "branch change")

    advance_main(
        remote,
        tmp_path,
        lambda repo: write(repo / "app.txt", "target change\n"),
    )

    result = git(
        worker,
        "fetch",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        check=False,
    )
    assert result.returncode == 0

    rebase = git(worker, "rebase", "origin/main", check=False)
    assert rebase.returncode != 0
    assert "CONFLICT" in git_logs(rebase)


def test_final_submit_rebase_is_noop_when_branch_is_current(tmp_path: Path) -> None:
    remote, seed = init_remote(tmp_path)
    create_initial_main(seed)
    worker = clone_branch_worker(remote, tmp_path)

    write(worker / "feature.txt", "current work\n")
    commit_all(worker, "current branch work")
    before = git_out(worker, "rev-parse", "HEAD")

    after = final_submit_rebase(worker)

    assert after == before

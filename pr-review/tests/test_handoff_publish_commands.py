"""The publish commands a pool hand-off records must run as written, later,
from the publisher's own checkout (dr-zn9fq).

mol-pr-from-issue lives in the pr-pipeline pack; its cases are in
pr-pipeline/tests/test_from_issue_handoff.py. Each check reads the formula
step text itself, so a formula edit that drops the quoting, the --repo or the
molecule-keyed path turns a case red.
"""
from __future__ import annotations

import json
import pathlib
import shlex
import subprocess
import tomllib

import pytest

FORMULAS = pathlib.Path(__file__).resolve().parent.parent / "formulas"


def formula_path(name: str) -> pathlib.Path:
    return FORMULAS / f"{name}.formula.toml"
TITLE = "Revert PR #12: user's login fails"
BODY = "/tmp/city dir/x/pr-body.md"


def step(name: str, step_id: str) -> str:
    doc = tomllib.loads(formula_path(name).read_text(encoding="utf-8"))
    return next(s["description"] for s in doc["steps"] if s["id"] == step_id)


def assignment(text: str, var: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(var + "="))


def render(assign_line: str, env: dict[str, str]) -> str:
    """Evaluate the formula's own assignment in bash and return the recorded command."""
    var = assign_line.split("=", 1)[0]
    script = "\n".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    script += f'\n{assign_line}\nprintf "%s" "${{{var}}}"'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout


@pytest.mark.parametrize(
    ("name", "env", "title_var"),
    [
        ("mol-pr-revert",
         {"UPSTREAM_REPO": "o/r", "DEFAULT_BRANCH": "main", "FORK_OWNER": "me",
          "BRANCH": "revert-12", "BODY_FILE": BODY}, "REVERT_TITLE"),
    ],
)
def test_create_command_survives_an_apostrophe_and_a_space(name, env, title_var):
    recorded = render(assignment(step(name, "hand-off-publish"), "PUBLISH_CREATE"),
                      {**env, title_var: TITLE})
    assert subprocess.run(["bash", "-n", "-c", recorded]).returncode == 0, recorded
    argv = shlex.split(recorded)
    assert argv[argv.index("--title") + 1] == TITLE
    assert argv[argv.index("--body-file") + 1] == BODY


@pytest.mark.parametrize(
    ("name", "step_id"),
    [("mol-pr-revert", "hand-off-publish"),
     ("mol-pr-merge-only", "intake"), ("mol-pr-merge-only", "rebase-check"),
     ("mol-pr-merge-only", "finalize")],
)
def test_staged_paths_are_keyed_by_the_molecule(name, step_id):
    paths = [l for l in step(name, step_id).splitlines() if ".gc/staged-gh/" in l]
    assert paths, f"{name}.{step_id} stages nothing"
    for line in paths:
        assert "/.gc/staged-gh/$ROOT_ID-" in line, line


def test_merge_only_commands_name_their_target():
    text = step("mol-pr-merge-only", "finalize")
    for var in ("POST_ACK_CMD", "MERGE_CMD"):
        assert "--repo " in assignment(text, var), var
    assert "--match-head-commit" in assignment(text, "MERGE_CMD")
    push = assignment(text, "PUSH_CMD")
    for part in ("--git-dir=", "--force-with-lease=refs/heads/", "$HEAD_URL",
                 "$REBASED_SHA:refs/heads/"):
        assert part in push, part
    assert 'git update-ref "refs/staged-gh/$ROOT_ID" "$REBASED_SHA"' in text


@pytest.mark.parametrize(
    ("name", "env", "sha_var"),
    [
        ("mol-pr-revert",
         {"GIT_DIR_ABS": "/r/.git", "LOCAL_REPO": "me/r", "BRANCH": "revert-12",
          "REVERT_SHA": "abc123"}, "REVERT_SHA"),
    ],
)
def test_push_command_names_repo_url_and_exact_sha(name, env, sha_var):
    """A remote or branch name means nothing in the publisher's checkout."""
    text = step(name, "hand-off-publish")
    argv = shlex.split(render(assignment(text, "PUBLISH_PUSH"), env))
    assert argv[:3] == ["git", "--git-dir=/r/.git", "push"], argv
    assert "https://github.com/me/r.git" in argv, argv
    assert argv[-1] == "abc123:refs/heads/" + env["BRANCH"], argv
    assert f'git update-ref "refs/staged-gh/$ROOT_ID" "${sha_var}"' in text


@pytest.mark.parametrize("step_id", ["intake", "rebase-check"])
def test_merge_only_staged_gh_commands_name_the_repo(step_id):
    lines = [l for l in step("mol-pr-merge-only", step_id).splitlines()
             if "gh pr comment" in l or "gh pr review" in l or "gh pr edit" in l]
    assert lines, step_id
    for line in lines:
        assert "--repo " in line, line


def test_no_stale_prose_promises_a_pool_write():
    merge_only = tomllib.loads(formula_path("mol-pr-merge-only").read_text())
    header = merge_only["description"]
    assert "finalizes via Path A: squash merge" not in header
    assert "Abort rebase, post comment" not in header
    assert "revert_pr_url" not in step("mol-pr-revert", "report")


def replay(recorded: str) -> list[str]:
    """Run a recorded command through bash word-splitting the way a publisher would."""
    out = subprocess.run(["bash", "-c", "args() { printf '%s\\0' \"$@\"; }; args " + recorded],
                         capture_output=True, text=True, check=True,
                         env={"USER": "publisher", "PATH": "/usr/bin:/bin"}).stdout
    return out.split("\0")[:-1]


SPECIAL_BRANCH = "fix/$USER x"


@pytest.mark.parametrize(
    ("name", "env"),
    [
        ("mol-pr-revert",
         {"GIT_DIR_ABS": "/r/.git", "LOCAL_REPO": "me/r", "REVERT_SHA": "abc123",
          "UPSTREAM_REPO": "o/r", "DEFAULT_BRANCH": "main", "FORK_OWNER": "me",
          "REVERT_TITLE": TITLE, "BODY_FILE": BODY}),
    ],
)
def test_recorded_commands_replay_a_shell_special_branch_verbatim(name, env):
    text = step(name, "hand-off-publish")
    env = {**env, "BRANCH": SPECIAL_BRANCH}
    push = replay(render(assignment(text, "PUBLISH_PUSH"), env))
    assert push[-1] == "abc123:refs/heads/" + SPECIAL_BRANCH, push
    create = replay(render(assignment(text, "PUBLISH_CREATE"), env))
    assert create[create.index("--head") + 1] == "me:" + SPECIAL_BRANCH, create
    assert create[create.index("--title") + 1] == TITLE, create
    assert create[create.index("--body-file") + 1] == BODY, create


@pytest.mark.parametrize("step_id", ["intake", "rebase-check"])
def test_merge_only_staged_comment_paths_replay_with_a_space(step_id):
    lines = [l for l in step("mol-pr-merge-only", step_id).splitlines()
             if "gh pr comment" in l]
    assert lines, step_id
    for line in lines:
        cmd = line.split(": ", 1)[1].replace("<number>", "12").replace("<owner>/<repo>", "o/r")
        recorded = subprocess.run(
            ["bash", "-c", f'STAGED_DIR="/tmp/city dir/x"; printf "%s" "{cmd}"'],
            capture_output=True, text=True, check=True).stdout
        argv = replay(recorded)
        assert argv[argv.index("--body-file") + 1].startswith("/tmp/city dir/x/"), argv


def test_merge_only_finalize_push_replays_a_shell_special_head_ref():
    text = step("mol-pr-merge-only", "finalize")
    push = replay(render(assignment(text, "PUSH_CMD"),
                         {"GIT_DIR_ABS": "/r/.git", "PRE_REBASE_HEAD": "old1",
                          "HEAD_URL": "https://github.com/c/r.git", "REBASED_SHA": "new2",
                          "HEAD_REF": SPECIAL_BRANCH}))
    assert push == ["git", "--git-dir=/r/.git", "push",
                    f"--force-with-lease=refs/heads/{SPECIAL_BRANCH}:old1",
                    "https://github.com/c/r.git", f"new2:refs/heads/{SPECIAL_BRANCH}"], push
    assert "HEAD_REF=$(gh pr view" in text


HOSTILE = "keep $USER and $(printf CHANGED) and `id` literal"


def title_block(text: str, first: str, last: str) -> str:
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(first))
    end = next(i for i, l in enumerate(lines) if i >= start and l.startswith(last))
    return "\n".join(lines[start:end + 1])


@pytest.mark.parametrize(
    ("name", "first", "last", "placeholder", "var", "expected"),
    [
        ("mol-pr-revert", "REVERT_REASON=", "REVERT_TITLE=", "{{reason}}", "REVERT_TITLE",
         "Revert PR #12: " + HOSTILE),
    ],
)
def test_title_text_enters_as_data(name, first, last, placeholder, var, expected):
    block = title_block(step(name, "hand-off-publish"), first, last)
    block = block.replace(placeholder, HOSTILE).replace("{{pr}}", "12")
    out = subprocess.run(["bash", "-c", f'{block}\nprintf "%s" "${var}"'],
                         capture_output=True, text=True, check=True,
                         env={"USER": "pool", "PATH": "/usr/bin:/bin"}).stdout
    assert out == expected, out


OURS = {"url": "https://github.com/o/r/pull/99", "headRefOid": "abc123",
        "headRepositoryOwner": {"login": "me"}, "baseRefName": "main"}
OTHER_FORK = {"url": "https://github.com/o/r/pull/98", "headRefOid": "fff000",
              "headRepositoryOwner": {"login": "someone"}, "baseRefName": "main"}


def run_revert_comment(tmp_path, prs):
    """Replay the recorded comment command against a stub gh that applies --jq."""
    body = tmp_path / "city dir" / "revert-comment.md"
    body.parent.mkdir()
    body.write_text("This PR has been reverted: <REVERT_PR_URL>\n")
    posted = tmp_path / "posted.md"
    listing = tmp_path / "prs.json"
    listing.write_text(json.dumps(prs))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(
        "#!/bin/bash\n"
        'if [ "$1 $2" = "pr list" ]; then\n'
        '  while [ $# -gt 0 ]; do [ "$1" = --jq ] && prog=$2; shift; done\n'
        f'  jq -r "$prog" {shlex.quote(str(listing))}; exit\n'
        "fi\n"
        'if [ "$1 $2" = "pr comment" ]; then\n'
        f'  echo "$@" > {shlex.quote(str(posted))}.argv; cat > {shlex.quote(str(posted))}; exit\n'
        "fi\n"
        "exit 9\n")
    (bindir / "gh").chmod(0o755)
    text = step("mol-pr-revert", "hand-off-publish").replace("{{pr}}", "12")
    env = {"UPSTREAM_REPO": "o/r", "BRANCH": SPECIAL_BRANCH, "COMMENT_FILE": str(body),
           "FORK_OWNER": "me", "REVERT_SHA": "abc123", "DEFAULT_BRANCH": "main"}
    script = "\n".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    script += "\n" + assignment(text, "REVERT_URL_JQ")
    script += "\n" + assignment(text, "PUBLISH_COMMENT") + '\nprintf "%s" "$PUBLISH_COMMENT"'
    recorded = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                              check=True, env={"PATH": "/usr/bin:/bin"}).stdout
    result = subprocess.run(["bash", "-c", recorded],
                            env={"PATH": f"{bindir}:/usr/bin:/bin", "USER": "publisher"})
    return result.returncode, posted


def test_revert_comment_command_fills_the_revert_pr_url_itself(tmp_path):
    """The publisher replays the comment as written; nothing is edited by hand."""
    code, posted = run_revert_comment(tmp_path, [OTHER_FORK, OURS])
    assert code == 0
    assert posted.read_text() == "This PR has been reverted: https://github.com/o/r/pull/99\n"
    assert "--repo o/r" in posted.with_name("posted.md.argv").read_text()


@pytest.mark.parametrize("prs", [
    [OTHER_FORK],
    [OURS, {**OURS, "url": "https://github.com/o/r/pull/97"}],
    [{**OURS, "headRepositoryOwner": {"login": "someone"}}],
    [{**OURS, "headRefOid": "fff000"}],
    [{**OURS, "baseRefName": "release"}],
], ids=["other-fork", "ambiguous", "owner-only-differs", "sha-only-differs",
        "base-only-differs"])
def test_revert_comment_refuses_a_missing_or_ambiguous_revert_pr(tmp_path, prs):
    code, posted = run_revert_comment(tmp_path, prs)
    assert code != 0
    assert not posted.exists()


def test_merge_only_header_promises_no_pool_merge():
    header = tomllib.loads(formula_path("mol-pr-merge-only").read_text())["description"]
    assert "intake through merge" not in header
    assert "| CI fails | Report failure, stop, wait for nudge |" not in header


def test_readme_documents_the_publish_hand_off():
    readme = (FORMULAS.parent / "README.md").read_text()
    for needle in ("mol-pr-from-issue", "mol-pr-revert", "mol-pr-merge-only",
                   "evidence.publish_push_cmd", "evidence.publish_create_cmd",
                   "evidence.publish_comment_cmd", "branch-ready"):
        assert needle in readme, needle

OWNER_LOADER = "PUBLISH_OWNER=$(cat <<'OWNER'\n{{publish_owner}}\nOWNER\n)"
HOSTILE_OWNER = "$(printf INJECTED) O'Brien `id`"
# Every line that names who publishes. Each must read the loaded value.
NAMES_PUBLISHER = ("evidence.publish_owner=", "publish_owner: ", "'s step, from its own login",
                   "posted by ", "stays $PUBLISH_OWNER")


def check_publisher(doc: dict, step_ids: list[str]) -> None:
    assert doc["vars"]["publish_owner"]["default"] == "maintainer"
    for step_id in step_ids:
        text = next(s["description"] for s in doc["steps"] if s["id"] == step_id)
        # The placeholder appears only inside the quoted-heredoc loader, so no
        # owner value is ever parsed as shell.
        assert text.count("{{publish_owner}}") == text.count(OWNER_LOADER) > 0, step_id
        loader = OWNER_LOADER.replace("{{publish_owner}}", HOSTILE_OWNER)
        out = subprocess.run(["bash", "-c", loader + '\nprintf "%s" "$PUBLISH_OWNER"'],
                             capture_output=True, text=True, check=True).stdout
        assert out == HOSTILE_OWNER, out
        naming = [l for l in text.splitlines() if any(n in l for n in NAMES_PUBLISHER)]
        assert naming, f"{step_id} never names its publisher"
        for line in naming:
            assert "$PUBLISH_OWNER" in line, line


@pytest.mark.parametrize(("name", "step_ids"), [("mol-pr-revert", ["hand-off-publish", "report"]),
                                                ("mol-pr-merge-only", ["finalize"])])
def test_publisher_is_loaded_as_data_and_never_hard_coded(name, step_ids):
    check_publisher(tomllib.loads(formula_path(name).read_text()), step_ids)

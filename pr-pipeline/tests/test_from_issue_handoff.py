"""mol-pr-from-issue ends at a publish hand-off whose recorded commands must run
as written, later, from the publisher's own checkout (dr-zn9fq).

The pr-review pack holds the same checks for mol-pr-revert and
mol-pr-merge-only in pr-review/tests/test_handoff_publish_commands.py. Each
check reads the formula step text itself, so a formula edit that drops the
quoting, the --repo or the molecule-keyed path turns a case red.
"""
from __future__ import annotations

import pathlib
import shlex
import subprocess
import tomllib

import pytest

FORMULA = pathlib.Path(__file__).resolve().parent.parent / "formulas" / "mol-pr-from-issue.formula.toml"
README = pathlib.Path(__file__).resolve().parent.parent / "README.md"
TITLE = "Revert PR #12: user's login fails"
BODY = "/tmp/city dir/x/pr-body.md"
SPECIAL_BRANCH = "fix/$USER x"
HOSTILE = "keep $USER and $(printf CHANGED) and `id` literal"


def formula() -> dict:
    return tomllib.loads(FORMULA.read_text(encoding="utf-8"))


def step(step_id: str) -> str:
    return next(s["description"] for s in formula()["steps"] if s["id"] == step_id)


def assignment(text: str, var: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(var + "="))


def render(assign_line: str, env: dict[str, str]) -> str:
    """Evaluate the formula's own assignment in bash and return the recorded command."""
    var = assign_line.split("=", 1)[0]
    script = "\n".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    script += f'\n{assign_line}\nprintf "%s" "${{{var}}}"'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout


def replay(recorded: str) -> list[str]:
    """Run a recorded command through bash word-splitting the way a publisher would."""
    out = subprocess.run(["bash", "-c", "args() { printf '%s\\0' \"$@\"; }; args " + recorded],
                         capture_output=True, text=True, check=True,
                         env={"USER": "publisher", "PATH": "/usr/bin:/bin"}).stdout
    return out.split("\0")[:-1]


def test_create_command_survives_an_apostrophe_and_a_space():
    env = {"UPSTREAM_REPO": "o/r", "UPSTREAM_BASE": "main", "FORK_OWNER": "me",
           "BRANCH": "b", "PR_BODY_PATH": BODY, "PR_TITLE": TITLE}
    recorded = render(assignment(step("hand-off-publish"), "PUBLISH_CREATE"), env)
    assert subprocess.run(["bash", "-n", "-c", recorded]).returncode == 0, recorded
    argv = shlex.split(recorded)
    assert argv[argv.index("--title") + 1] == TITLE
    assert argv[argv.index("--body-file") + 1] == BODY


def test_staged_paths_are_keyed_by_the_molecule():
    paths = [l for l in step("hand-off-publish").splitlines() if ".gc/staged-gh/" in l]
    assert paths, "hand-off-publish stages nothing"
    for line in paths:
        assert "/.gc/staged-gh/$ROOT_ID-" in line, line


def test_push_command_names_repo_url_and_exact_sha():
    """A remote or branch name means nothing in the publisher's checkout."""
    text = step("hand-off-publish")
    env = {"GIT_DIR_ABS": "/r/.git", "FORK_REPO": "me/r", "BRANCH": "b", "COMMIT_SHA": "abc123"}
    argv = shlex.split(render(assignment(text, "PUBLISH_PUSH"), env))
    assert argv[:3] == ["git", "--git-dir=/r/.git", "push"], argv
    assert "https://github.com/me/r.git" in argv, argv
    assert argv[-1] == "abc123:refs/heads/b", argv
    assert 'git update-ref "refs/staged-gh/$ROOT_ID" "$COMMIT_SHA"' in text


def test_recorded_commands_replay_a_shell_special_branch_verbatim():
    text = step("hand-off-publish")
    env = {"GIT_DIR_ABS": "/r/.git", "FORK_REPO": "me/r", "COMMIT_SHA": "abc123",
           "UPSTREAM_REPO": "o/r", "UPSTREAM_BASE": "main", "FORK_OWNER": "me",
           "PR_TITLE": TITLE, "PR_BODY_PATH": BODY, "BRANCH": SPECIAL_BRANCH}
    push = replay(render(assignment(text, "PUBLISH_PUSH"), env))
    assert push[-1] == "abc123:refs/heads/" + SPECIAL_BRANCH, push
    create = replay(render(assignment(text, "PUBLISH_CREATE"), env))
    assert create[create.index("--head") + 1] == "me:" + SPECIAL_BRANCH, create
    assert create[create.index("--title") + 1] == TITLE, create
    assert create[create.index("--body-file") + 1] == BODY, create


def test_title_text_enters_as_data():
    lines = step("hand-off-publish").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("PR_TITLE="))
    end = next(i for i, l in enumerate(lines) if i >= start and l.startswith(")"))
    block = "\n".join(lines[start:end + 1]).replace("<conventional commit summary>", HOSTILE)
    out = subprocess.run(["bash", "-c", f'{block}\nprintf "%s" "$PR_TITLE"'],
                         capture_output=True, text=True, check=True,
                         env={"USER": "pool", "PATH": "/usr/bin:/bin"}).stdout
    assert out == HOSTILE, out


def test_no_prose_promises_a_pool_write():
    text = FORMULA.read_text()
    assert "authorize the polecat to push" not in text
    assert "ends with an opened PR" not in text
    assert "before any auto-push proceeds" not in text
    gate = step("gate-publish-readiness")
    assert "actually push" not in gate
    assert "arm the bypass token" not in gate


def test_readme_describes_publish_handoff_not_pool_write():
    text = README.read_text(encoding="utf-8")
    assert "(optional) open PR" not in text
    assert "authorize the\neligibility-gated push" not in text
    assert "authorizes no push and no PR open" in text


def gate_skip_block() -> str:
    lines = step("gate-publish-readiness").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("if ") and "AUTO_PUSH" in l)
    end = next(i for i, l in enumerate(lines) if i > start and l == "fi")
    return "\n".join(lines[start:end + 1])


@pytest.mark.parametrize(
    ("auto_push", "skip_open_pr", "skips"),
    [("true", "true", True), ("false", "false", True), ("false", "true", True),
     ("true", "false", False)],
)
def test_readiness_gate_skips_whenever_skip_open_pr_is_set(auto_push, skip_open_pr, skips):
    """hand-off-publish says skip_open_pr=true means the gate was not consulted; make it so."""
    script = (f"AUTO_PUSH={auto_push}\nSKIP_OPEN_PR={skip_open_pr}\n"
              f"{gate_skip_block()}\necho GATE_RAN")
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
    assert ("GATE_RAN" not in out) == skips, out


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


def test_publisher_is_loaded_as_data_and_never_hard_coded():
    check_publisher(formula(), ["gate-publish-readiness", "hand-off-publish"])

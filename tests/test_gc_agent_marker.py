#!/usr/bin/env python3
"""Every factory post on GitHub carries the universal `<!-- gc-agent:v1 -->` marker.

Mirrors gastownhall/workflows scripts/gc_agent_marker_test.py. Covers the
helper copies vendored into each pack that posts, every deterministic emitter,
and a repo-wide guard so new posting scripts and new comment templates cannot
ship without the marker.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GASCITY_SCRIPTS = REPO_ROOT / "gascity" / "assets" / "scripts"
GITHUB_SCRIPTS = REPO_ROOT / "github" / "scripts"
for _path in (GASCITY_SCRIPTS, GITHUB_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import github_api  # noqa: E402
import github_intake_common  # noqa: E402
import github_reports  # noqa: E402

MARKER_LITERAL = "<!-- gc-agent:v1 -->"

# Packs are imported independently, so each pack that posts carries its own
# copy of the helper. The copies must stay byte-identical.
HELPER_COPIES = (
    GASCITY_SCRIPTS / "gc_agent_marker.py",
    GITHUB_SCRIPTS / "gc_agent_marker.py",
)

# Packs whose agent-facing text instructs posting on GitHub.
POSTING_PACKS = ("gascity", "github", "pr-review", "pr-pipeline")
INSTRUCTION_GLOBS = (
    "formulas/**/*.toml",
    "assets/workflows/**/*.md",
    "commands/**/*.md",
    "commands/**/*.toml",
    "templates/**/*.md",
    "overlay/**/*.md",
    "skills/**/*.md",
    "prompts/**/*.md",
    "orders/**/*.toml",
)

POSTING_INSTRUCTION_RE = re.compile(
    r"\b(post|posts|posted|posting|publish|update|create|edit)\b[^\n]{0,60}\bcomments?\b"
    r"|\bcomment on the (pr|issue)\b"
    r"|\bgh (pr|issue) (comment|review|close)\b"
    r"|\bgh pr review\b"
    r"|/comments\b"
    r"|comment-(create|update|issue)\b",
    re.IGNORECASE,
)

# Files whose matches are not GitHub posts. Adding an entry needs a reason.
NON_POSTING_FILES = {
    "pr-pipeline/formulas/mol-pr-triage.formula.toml": "read-only triage; states that no comments are applied",
    "pr-pipeline/formulas/mol-pr-review.formula.toml": "local self-review report; only points at templates/adoption-review-comment.md",
    "github/commands/comment-issue/command.toml": "one-line command description; the script and help.md carry the marker",
}

# Fenced blocks near the word "comment" that are not posted bodies.
NON_TEMPLATE_BLOCKS = {
    ("pr-pipeline/templates/adoption-review-comment.md", "_Adopted via `/adopt-pr` workflow. Contributor commits preserved._"):
        "quotes the literal footer line of an already-marked template",
    ("pr-review/overlay/.claude/skills/review-pr/SKILL.md", "# PR Review: <title> (#<number>)"):
        "pre-comment decision stanza shown to the user, never posted",
    ("pr-review/overlay/.claude/skills/review-pr/SKILL.md", "[review-pr] Phase 1/4: Gathering PR context..."):
        "terminal progress output",
}

FENCE_RE = re.compile(r"^\s*```(\S*)\s*$")
METADATA_LINE_RE = re.compile(r"^\s*[\w.\-/<>]+=")

# Deterministic GitHub comment/review writers in scripts: `gh pr comment`
# argv lists, `gh api -X POST repos/.../comments`, and direct REST calls such
# as github_api_request("POST", f"/repos/.../comments").
PY_POSTING_RE = re.compile(
    r'"gh",\s*"(pr|issue)",\s*"(comment|review|close)"'
    r'|"(POST|PATCH)",\s*f?"/?repos/[^"]*/(comments|reviews)'
)
SH_POSTING_RE = re.compile(r"\bgh (pr|issue) (comment|review|close)\b|\brepos/\S*/(comments|reviews)\b")
SKIP_DIR_PARTS = {".git", "vendor", "node_modules", "tests", "__pycache__"}


def repo_files(suffix: str) -> list[pathlib.Path]:
    return sorted(
        p
        for p in REPO_ROOT.rglob(f"*{suffix}")
        if p.is_file() and not (SKIP_DIR_PARTS & set(p.relative_to(REPO_ROOT).parts))
    )


def instruction_files() -> list[pathlib.Path]:
    found = set()
    for pack in POSTING_PACKS:
        for pattern in INSTRUCTION_GLOBS:
            found.update(p for p in (REPO_ROOT / pack).glob(pattern) if p.is_file())
    return sorted(found)


def effective_text(path: pathlib.Path) -> str:
    """File text plus any `description_file` it embeds (formula steps)."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".toml":
        return text
    parts = [text]
    for ref in re.findall(r'description_file\s*=\s*"([^"]+)"', text):
        target = (path.parent / ref).resolve()
        if target.is_file():
            parts.append(target.read_text(encoding="utf-8"))
    return "\n".join(parts)


def comment_template_blocks(path: pathlib.Path) -> list[tuple[int, list[str]]]:
    """Fenced prose blocks introduced by text that talks about a comment."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[int, list[str]]] = []
    i = 0
    last_close = 0
    while i < len(lines):
        match = FENCE_RE.match(lines[i])
        if not match:
            i += 1
            continue
        lang = match.group(1)
        j = i + 1
        while j < len(lines) and not FENCE_RE.match(lines[j]):
            j += 1
        body = [line for line in lines[i + 1 : j] if line.strip()]
        context = "\n".join(lines[max(last_close, i - 20) : i])
        if (
            lang in ("", "text", "markdown", "md")
            and re.search(r"\bcomment", context, re.IGNORECASE)
            and body
            and body != [MARKER_LITERAL]
            and not (len(body) == 1 and not re.search(r"\s", body[0].strip()))
            and not all(METADATA_LINE_RE.match(line) for line in body)
        ):
            blocks.append((i + 1, body))
        last_close = j + 1
        i = j + 1
    return blocks


def load_helper(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"gc_agent_marker_{path.parent.parent.name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HelperTest(unittest.TestCase):
    def test_helper_copies_are_identical(self) -> None:
        texts = {path.read_text(encoding="utf-8") for path in HELPER_COPIES}
        self.assertEqual(len(texts), 1, "gc_agent_marker.py copies drifted; keep them byte-identical")

    def test_helper_contract(self) -> None:
        for path in HELPER_COPIES:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                helper = load_helper(path)
                self.assertEqual(helper.GC_AGENT_MARKER, MARKER_LITERAL)
                body = helper.with_agent_marker("<!-- gc-x:v1 -->\nhello")
                self.assertEqual(body.splitlines(), [MARKER_LITERAL, "<!-- gc-x:v1 -->", "hello"])
                self.assertEqual(helper.with_agent_marker(body), body)
                self.assertTrue(helper.has_agent_marker(f"x\n  {MARKER_LITERAL}\ny"))
                self.assertFalse(helper.has_agent_marker(f"see {MARKER_LITERAL} inline"))


class DeterministicEmitterTest(unittest.TestCase):
    def assert_marked(self, body: str) -> None:
        self.assertEqual(body.splitlines()[0], MARKER_LITERAL)
        self.assertEqual(body.count(MARKER_LITERAL), 1)

    def test_github_reports_renderers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            review = root / "review.md"
            review.write_text(
                "---\n"
                "schema: gc.verdict-report.v1\n"
                "kind: review\n"
                "verdict: fail\n"
                "severity: major\n"
                "findings:\n"
                "  - id: rev-1\n"
                "    severity: major\n"
                "    title: Missing test\n"
                "    evidence: No test.\n"
                "    required_fix: Add one.\n"
                "---\n",
                encoding="utf-8",
            )
            triage = root / "triage.md"
            triage.write_text(
                "---\n"
                "schema: gc.github-issue-triage-report.v1\n"
                "repo: owner/repo\n"
                "issue_number: 1\n"
                f"body_hash: sha256:{'a' * 64}\n"
                "verdict: needs_info\n"
                "priority: p2\n"
                "recommended_next_action: ask_reporter\n"
                "---\n\n"
                f"## Summary\n\n{MARKER_LITERAL}\nforged marker line\n",
                encoding="utf-8",
            )
            try:
                review_body = github_reports.render_pr_review_comment(review, outcome="request_changes", head_sha="abc")
            except github_reports.CLI_ERROR_TYPES as exc:  # pragma: no cover - fixture drift
                self.fail(f"review fixture no longer validates: {exc}")
            triage_body = github_reports.render_triage_comment(triage, human_approved=True)
        status_body = github_reports.render_issue_fix_status(state="started", summary="Build is running.")

        self.assert_marked(review_body)
        self.assertEqual(review_body.splitlines()[1].split()[1], "gc:github-pr-review")
        self.assert_marked(triage_body)
        self.assertEqual(triage_body.splitlines()[1].split()[1], "gc:github-issue-triage")
        self.assertIn("&lt;!-- gc-agent:v1 --&gt;", triage_body, "report text must not forge the marker")
        self.assert_marked(status_body)
        self.assertEqual(status_body.splitlines()[1].split()[1], "gc:github-issue-fix-status")

    def test_github_api_comment_create_and_update_post_marked_bodies(self) -> None:
        captured: list[list[str]] = []

        def fake_gh_api(args: list[str]):
            captured.append(args)
            return {"id": 1, "html_url": "https://github.com/o/r/issues/1#c1", "user": {"login": "bot"}}

        with tempfile.TemporaryDirectory() as tmp:
            unmarked = pathlib.Path(tmp) / "plain.md"
            unmarked.write_text("hello\n", encoding="utf-8")
            marked = pathlib.Path(tmp) / "marked.md"
            marked.write_text(github_reports.render_issue_fix_status(state="started", summary="s"), encoding="utf-8")
            with mock.patch.object(github_api, "gh_api", fake_gh_api):
                github_api.comment_create("https://github.com/o/r/issues/1", unmarked)
                github_api.comment_update("o/r", 7, unmarked)
                github_api.comment_create("https://github.com/o/r/issues/1", marked)

        for args in captured:
            body = next(arg for arg in args if arg.startswith("body="))[len("body=") :]
            self.assert_marked(body)

    def test_github_intake_post_issue_comment_is_marked(self) -> None:
        with mock.patch.object(github_intake_common, "create_installation_token", return_value="tok"), mock.patch.object(
            github_intake_common, "github_api_request", return_value={"id": 1}
        ) as request:
            github_intake_common.post_issue_comment({}, "inst", "o", "r", "5", "ack")
            github_intake_common.post_issue_comment({}, "inst", "o", "r", "5", f"{MARKER_LITERAL}\nack")
        for call in request.call_args_list:
            self.assert_marked(call.kwargs["payload"]["body"])

    def test_every_script_that_posts_comments_uses_the_helper(self) -> None:
        offenders = []
        for path in repo_files(".py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if PY_POSTING_RE.search(text) and "with_agent_marker" not in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        for path in repo_files(".sh"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if SH_POSTING_RE.search(text) and MARKER_LITERAL not in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], "scripts post GitHub comments/reviews without the gc-agent marker")

    def test_guard_regex_still_sees_the_known_emitters(self) -> None:
        for path in (GASCITY_SCRIPTS / "github_api.py", GITHUB_SCRIPTS / "github_intake_common.py"):
            self.assertRegex(path.read_text(encoding="utf-8"), PY_POSTING_RE, str(path))


class PromptTemplateTest(unittest.TestCase):
    def test_files_that_instruct_github_posts_require_the_marker(self) -> None:
        offenders = []
        for path in instruction_files():
            rel = str(path.relative_to(REPO_ROOT))
            if rel in NON_POSTING_FILES:
                continue
            if not POSTING_INSTRUCTION_RE.search(path.read_text(encoding="utf-8")):
                continue
            if MARKER_LITERAL not in effective_text(path):
                offenders.append(rel)
        self.assertEqual(offenders, [], "instruct GitHub comment posting without the gc-agent marker literal")

    def test_non_posting_exemptions_are_still_needed(self) -> None:
        for rel in NON_POSTING_FILES:
            path = REPO_ROOT / rel
            self.assertTrue(path.is_file(), f"stale exemption: {rel}")
            self.assertRegex(path.read_text(encoding="utf-8"), POSTING_INSTRUCTION_RE, f"stale exemption: {rel}")

    def test_non_template_exemptions_are_still_needed(self) -> None:
        seen = {
            (str(path.relative_to(REPO_ROOT)), body[0].strip())
            for path in instruction_files()
            for _, body in comment_template_blocks(path)
        }
        for key in NON_TEMPLATE_BLOCKS:
            self.assertIn(key, seen, f"stale template exemption: {key}")

    def test_comment_templates_start_with_the_marker(self) -> None:
        offenders = []
        found = 0
        for path in instruction_files():
            rel = str(path.relative_to(REPO_ROOT))
            if rel in NON_POSTING_FILES:
                continue
            for line_no, body in comment_template_blocks(path):
                found += 1
                if (rel, body[0].strip()) in NON_TEMPLATE_BLOCKS:
                    continue
                if body[0].strip() != MARKER_LITERAL:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {body[0].strip()[:60]}")
        self.assertGreaterEqual(found, 3, "template scan found too few comment templates; the heuristic broke")
        self.assertEqual(offenders, [], "comment templates must start with the gc-agent marker line")


if __name__ == "__main__":
    unittest.main()

---
name: review-pr
description: >-
  Multi-model code review for gastown. Reviews GitHub PRs (by URL or number)
  or local branches (by branch name). Spawns parallel Claude, Codex, and
  (optionally) Gemini reviewers with specialized prompts optimized for
  regression prevention, then synthesizes findings into a single
  maintainer-grade decision report. Use --skip-gemini for dual-model mode
  when Gemini quota is exhausted. Invoke with /review-pr <pr-url|number|branch>.
---

# Review PR Orchestrator

You are the **Review PR Orchestrator**. When the user invokes `/review-pr <arg>`, you execute a multi-phase pipeline that produces a thorough, multi-model code review focused on **preventing regressions** in the gastown codebase. You coordinate parallel Claude, Codex, and (unless `--skip-gemini`) Gemini reviewers, merge their findings, and present a single actionable report. All reviewers get full codebase access via temporary worktrees to ensure accurate caller/callee tracing. You never delegate orchestration to a spawned agent -- you are the single controller.

### Mode Detection

`/review-pr <arg>` auto-detects the review mode from `<arg>`:

| Pattern | Mode | Example |
|---------|------|---------|
| `https://github.com/.*/pull/\d+` | PR mode | `/review-pr https://github.com/org/gastown/pull/123` |
| Bare integer | PR mode | `/review-pr 123` |
| Anything else | Local branch mode | `/review-pr ci/close-stale-needs` |

- **PR mode**: Fetches context from GitHub, posts comment after review (4 phases).
- **Local branch mode**: Computes diff from local git refs, skips GitHub posting (3 phases).

---

## Pipeline Overview

| Phase | Name | Agents | Modes | Description |
|-------|------|--------|-------|-------------|
| 1 | Context Gathering | Orchestrator | Both | Gather metadata + diff; create worktrees for codebase access |
| 2 | Parallel Review | Claude ∥ Codex ∥ Gemini | Both | Independent reviews with role-specialized prompts |
| 3 | Synthesis | Orchestrator | Both | Merge, deduplicate, resolve disagreements, produce final report |
| 4 | Post to GitHub | Orchestrator | PR only | Format compact comment, present for user approval, post via `gh pr comment` on confirmation |

---

## Critical Rules

1. **Claude and Codex are always required.** Both must succeed (non-empty output) or the pipeline stops. **Gemini is required unless `--skip-gemini` is set.** When `--skip-gemini` is active, the pipeline runs in dual-model mode (Claude + Codex only) — Gemini preflight, prompt, invocation, and output validation are all skipped. There is no single-model fallback.
2. **Prompts saved first.** Before every agent invocation, save the full prompt to `<run_dir>/prompts/`. This is the audit trail.
3. **Parallel execution.** Phase 2 spawns Claude and Codex in parallel. Neither depends on the other's output.
4. **Worktree-based review.** Two temporary worktrees are created from the upstream repo: a **base worktree** (upstream main) for Claude, and a **PR head worktree** for Codex (and Gemini, unless `--skip-gemini`). Claude receives the diff in its prompt and uses the base worktree for caller/callee tracing. Codex and Gemini receive the diff in their prompts and run from the PR head worktree so they can read files for additional context.
5. **Working directory conventions:**
   - `run_dir` = `/tmp/review-pr/<run_id>/`
   - `run_id` format: `YYYYMMDDTHHMMSSZ-<8-hex>`
6. **All artifacts under `run_dir`.** Prompts, reviewer outputs, synthesis -- everything goes under `run_dir`.
7. **Fail closed.** On agent failure, empty output, or malformed results, stop and report the failure. Do not attempt to interpret broken output.
8. **North star: regression prevention.** Every decision in this pipeline optimizes for catching changes that break existing behavior, violate contracts, or corrupt state.

---

## CLI Interface

```
/review-pr <arg> [options]
```

### Arguments

- `<arg>` (required): One of:
  - **PR URL** — `https://github.com/org/gastown/pull/123` → PR mode
  - **Bare integer** — `123` → PR mode (uses current repo)
  - **Branch name** — `ci/close-stale-needs` → Local branch mode

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--base <branch>` | auto-detect | Base branch for local branch mode. Auto-detects the best base by finding the most recent merge-base across `main`, `upstream/main`, and `origin/main`. Override with an explicit branch name. Ignored in PR mode. |
| `--skip-gemini` | false | Run dual-model review (Claude + Codex only). Use when Gemini quota is exhausted. |
| `--skip-synthesis` | false | Output raw reviewer findings without synthesis |
| `--claude-only` | false | Run only Claude reviewer (degrades quality) |
| `--codex-only` | false | Run only Codex reviewer (degrades quality) |
| `--gemini-only` | false | Run only Gemini reviewer (degrades quality) |

---

## Phase 1: Context Gathering

Gather all context needed to build self-contained prompts. Steps 1, 3, 4, and 5 are shared across both modes. Step 2 is mode-specific.

### Step 1: Set up run directory

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$(openssl rand -hex 4)"
RUN_DIR="/tmp/review-pr/$RUN_ID"
mkdir -p "$RUN_DIR"/{prompts,outputs,context,scripts}
```

### Step 2: Gather context (mode-specific)

#### PR Mode

1. **Parse PR identifier** from `<arg>`. Extract owner, repo, and PR number.

2. **Fetch PR metadata, diff, and file list in parallel:**
   These three `gh` calls are independent — run them concurrently to save ~5-10s:
   ```bash
   gh pr view <number> --repo <owner>/<repo> \
     --json title,body,author,baseRefName,headRefName,number,additions,deletions,changedFiles \
     > "$RUN_DIR/context/metadata.json" &
   METADATA_PID=$!

   gh pr diff <number> --repo <owner>/<repo> \
     > "$RUN_DIR/context/diff.patch" &
   DIFF_PID=$!

   gh pr view <number> --repo <owner>/<repo> \
     --json files --jq '.files[].path' \
     > "$RUN_DIR/context/files.txt" &
   FILES_PID=$!

   wait $METADATA_PID $DIFF_PID $FILES_PID
   ```
   If any fetch fails, stop with the appropriate error.

3. **Build the PR context block** (injected into all reviewer prompts):

   ```
   ## PR Context

   PR #<number>: <title>
   Author: <author>
   Base: <baseRefName> <- Head: <headRefName>
   Stats: +<additions> -<deletions> across <changedFiles> files

   ### Description
   <body>

   ### Changed Files
   <file list>

   ### Full Diff
   <diff>
   ```

4. **Create upstream worktrees (CRITICAL for accurate reviews):**

   Fetch both the base branch and PR head from the upstream repo. Create two worktrees:
   - **Base worktree** (`<run_dir>/worktree/`): For Claude reviewer — checked out at base branch (upstream main). Claude gets the diff in its prompt and uses the worktree to trace callers/callees.
   - **PR head worktree** (`<run_dir>/worktree-pr/`): For Codex and Gemini reviewers — checked out at PR head. Both receive the diff in their prompts and can read files from this worktree for additional tracing.

   ```bash
   # Base worktree (for Claude)
   # IMPORTANT: Do NOT use --depth=1. The local clone may already be shallow.
   git fetch https://github.com/<owner>/<repo>.git <baseRefName>
   git worktree add <run_dir>/worktree FETCH_HEAD --detach

   # PR head worktree (for Codex and Gemini)
   git fetch https://github.com/<owner>/<repo>.git +pull/<number>/head:refs/tmp/review-pr-head
   git worktree add <run_dir>/worktree-pr refs/tmp/review-pr-head --detach
   ```

   - Both worktrees are cleaned up after synthesis.
   - **Why this matters:** In PR #1288, reviewers flagged `router.go` sites as unmigrated because they were reading the local checkout, which was behind upstream main. The upstream worktree eliminates this class of false positive entirely.
   - **Premise validation lesson (PR #1648, reverted in #1656):** Both Claude and Codex validated PR #1648's fix without verifying the bug existed. The PR claimed `ForceCloseWithReason` writing to a polecat branch would cause stuck HOOKED beads via merge conflicts. In reality, `MergePolecatBranch` already handles this conflict via `--theirs` resolution (polecat wins). The fix was reverted because it bypassed branch isolation unnecessarily. **Root cause:** reviewers validated the solution's internal consistency without tracing the existing conflict resolution path. All reviewer prompts now include explicit premise-validation guidance.
   - If `git worktree add` fails (e.g., FETCH_HEAD conflict), fall back to:
     ```bash
     git fetch https://github.com/<owner>/<repo>.git +<baseRefName>:refs/tmp/review-base
     git worktree add <run_dir>/worktree refs/tmp/review-base --detach
     # Cleanup ref after worktree removal: git update-ref -d refs/tmp/review-base
     ```

#### Local Branch Mode

1. **Verify branch exists:**
   ```bash
   git rev-parse --verify <branch>
   ```
   If this fails, stop: `"Branch '<branch>' not found in local repository."`

2. **Resolve the effective base (CRITICAL for fork-based workflows):**

   When working in a fork, the local `main` branch tracks `origin/main` (the fork), not `upstream/main` (the source repo). If the feature branch was created from `upstream/main`, using local `main` as the base produces a massive diff with hundreds of unrelated files from the fork's divergence.

   **If `--base` was explicitly provided**, use it directly — the user knows what they want.

   **If `--base` was NOT provided (auto-detect mode)**, find the best base automatically:

   ```bash
   # Fetch upstream to ensure refs are current
   git fetch upstream main 2>/dev/null || true

   # Collect candidate base refs
   CANDIDATES=""
   for ref in main upstream/main origin/main; do
     if git rev-parse --verify "$ref" >/dev/null 2>&1; then
       CANDIDATES="$CANDIDATES $ref"
     fi
   done

   if [ -z "$CANDIDATES" ]; then
     echo "ERROR: No base branch found. Tried: main, upstream/main, origin/main"
     exit 1
   fi

   # Find the most recent merge-base (closest ancestor to the branch).
   # The right base is the one whose merge-base with the branch is most recent,
   # because that's where the branch actually diverged from.
   BEST_BASE=""
   BEST_MB=""
   BEST_MB_TIME=0
   for ref in $CANDIDATES; do
     MB=$(git merge-base "$ref" <branch> 2>/dev/null) || continue
     MB_TIME=$(git log -1 --format=%ct "$MB")
     if [ "$MB_TIME" -gt "$BEST_MB_TIME" ]; then
       BEST_MB_TIME=$MB_TIME
       BEST_MB=$MB
       BEST_BASE=$ref
     fi
   done

   EFFECTIVE_BASE="$BEST_BASE"
   ```

   Report which base was selected:
   ```
   [review-pr]   Auto-detected base: <EFFECTIVE_BASE> (merge-base: <BEST_MB short>)
   ```

   If the auto-detected base differs from `main`, this means the branch was forked from a different ref (typically `upstream/main` in a fork workflow).

3. **Verify commits exist between base and branch:**
   ```bash
   git log --oneline <EFFECTIVE_BASE>..<branch>
   ```
   If empty, stop: `"No commits between '<EFFECTIVE_BASE>' and '<branch>'. Nothing to review."`

4. **Compute context locally:**
   ```bash
   # Full diff (three-dot uses merge-base automatically)
   git diff <EFFECTIVE_BASE>...<branch>

   # Diff stats
   git diff --stat <EFFECTIVE_BASE>...<branch>

   # Changed file list
   git diff --name-only <EFFECTIVE_BASE>...<branch>

   # Title (last commit subject)
   git log -1 --format=%s <branch>

   # Description (all commit messages between base and branch)
   git log --reverse --format="* %s%n%n%b" <EFFECTIVE_BASE>..<branch>

   # Author
   git log -1 --format="%an" <branch>
   ```

5. **Build the context block** (same structure, different header):

   ```
   ## Review Context

   Branch: <branch> (vs <EFFECTIVE_BASE>)
   Author: <author>
   Stats: +<additions> -<deletions> across <changedFiles> files

   ### Description
   <commit messages>

   ### Changed Files
   <file list>

   ### Full Diff
   <diff>
   ```

6. **Create local worktrees** (no fetch needed):
   ```bash
   # Base worktree (for Claude) — use the merge-base commit for the most accurate "before" state
   git worktree add <run_dir>/worktree <EFFECTIVE_BASE> --detach

   # Branch head worktree (for Codex and Gemini)
   git worktree add <run_dir>/worktree-pr <branch> --detach
   ```
   - If `git worktree add` fails, report error — review cannot proceed without accurate codebase access.

### Step 3: Save context

Save the context block to `<run_dir>/context/pr-context.md`.

### Step 4: Write PTY wrapper scripts

Write to `<run_dir>/scripts/` (see Agent Invocations below):
- `aimux-claude.sh` — PTY wrapper for Claude invocations
- `aimux-codex.sh` — PTY wrapper for Codex invocations
- `aimux-gemini.sh` — PTY wrapper for Gemini invocations (skip if `--skip-gemini`)

### Step 5: Pre-flight check (parallel)

Verify required agents are available. All preflight checks are independent — run them concurrently to save ~20-30s:
```bash
echo "Reply ONLY with: ok" > <run_dir>/prompts/preflight_claude.md
echo "Reply ONLY with: ok" > <run_dir>/prompts/preflight_codex.md

bash <run_dir>/scripts/aimux-claude.sh <run_dir>/prompts/preflight_claude.md /tmp/claude_preflight.txt &
CLAUDE_PF=$!

bash <run_dir>/scripts/aimux-codex.sh <run_dir>/prompts/preflight_codex.md /tmp/codex_preflight.txt &
CODEX_PF=$!

# Skip Gemini preflight if --skip-gemini
if [ "$SKIP_GEMINI" != "true" ]; then
  echo "Reply ONLY with: ok" > <run_dir>/prompts/preflight_gemini.md
  bash <run_dir>/scripts/aimux-gemini.sh <run_dir>/prompts/preflight_gemini.md /tmp/gemini_preflight.txt &
  GEMINI_PF=$!
fi

# Wait for all preflight checks
if [ "$SKIP_GEMINI" = "true" ]; then
  wait $CLAUDE_PF $CODEX_PF
else
  wait $CLAUDE_PF $CODEX_PF $GEMINI_PF
fi

# Validate all required preflights succeeded (non-empty output)
cat /tmp/claude_preflight.txt
cat /tmp/codex_preflight.txt
if [ "$SKIP_GEMINI" != "true" ]; then
  cat /tmp/gemini_preflight.txt
fi
```
If any required agent fails, stop: `"Required agent <name> is not available. Check aimux status."`

---

## Phase 2: Parallel Review

Build prompts, save them, then invoke all three reviewers in parallel. The process is identical for both modes — only the context block header differs (PR mode: `PR #<number>: <title>`, local branch mode: `Branch: <branch> (vs <base>)`).

### Step 2a: Build Prompts

**Claude prompt** — full context including diff (Claude receives the diff in-prompt):
1. The claude-reviewer role prompt (see Reviewer Prompts below)
2. The full PR context block from Phase 1 (metadata + diff)
Save to: `<run_dir>/prompts/claude-reviewer.md`

**Codex prompt** — full context including diff (same as Claude):
1. The codex-reviewer role prompt (see Reviewer Prompts below)
2. The full PR context block from Phase 1 (metadata + diff)
Save to: `<run_dir>/prompts/codex-reviewer.md`

**Gemini prompt** (skip if `--skip-gemini`) — full context including diff (same as Claude/Codex):
1. The gemini-reviewer role prompt (see Reviewer Prompts below)
2. The full PR context block from Phase 1 (metadata + diff)
Save to: `<run_dir>/prompts/gemini-reviewer.md`

> **Why `exec` with prompt, not `exec review --base`?** (Updated 2026-02-13):
> - `--base` and `[PROMPT]` are **mutually exclusive** (confirmed: Codex returns error `the argument '--base <BRANCH>' cannot be used with '[PROMPT]'`).
> - `exec review --base` consistently spends all capacity on codebase research (reading files, tracing callers) without producing a final review. The diff is included in the prompt so Codex doesn't need to compute it.
> - This also eliminates the shallow clone / `git merge-base` failure that plagued `--base`.

### Step 2b: Invoke in Parallel

All reviewers use PTY wrapper scripts for output capture. Claude runs from the base worktree. Codex (and Gemini, unless `--skip-gemini`) run from the PR head worktree. All can read files from their respective worktrees for caller/callee tracing.

```bash
BASE_WORKTREE="<run_dir>/worktree"
PR_WORKTREE="<run_dir>/worktree-pr"

# Claude (via PTY wrapper) -- run in background from BASE worktree
cd "$BASE_WORKTREE" && bash <run_dir>/scripts/aimux-claude.sh \
  <run_dir>/prompts/claude-reviewer.md \
  <run_dir>/outputs/claude-review.md &
CLAUDE_PID=$!

# Codex (via PTY wrapper) -- run in background from PR HEAD worktree.
cd "$PR_WORKTREE" && bash <run_dir>/scripts/aimux-codex.sh \
  <run_dir>/prompts/codex-reviewer.md \
  <run_dir>/outputs/codex-review.md &
CODEX_PID=$!

# Gemini (via PTY wrapper) -- skip if --skip-gemini
if [ "$SKIP_GEMINI" != "true" ]; then
  cd "$PR_WORKTREE" && bash <run_dir>/scripts/aimux-gemini.sh \
    <run_dir>/prompts/gemini-reviewer.md \
    <run_dir>/outputs/gemini-review.md &
  GEMINI_PID=$!
fi

# Wait for all reviewers
if [ "$SKIP_GEMINI" = "true" ]; then
  wait $CLAUDE_PID $CODEX_PID
else
  wait $CLAUDE_PID $CODEX_PID $GEMINI_PID
fi
```

### Step 2c: Validate Outputs

- `<run_dir>/outputs/claude-review.md` must be non-empty.
- `<run_dir>/outputs/codex-review.md` must be non-empty.
- `<run_dir>/outputs/gemini-review.md` must be non-empty (skip check if `--skip-gemini`).
- If any required output is empty, report failure and stop.

---

## Phase 3: Synthesis

Read all three review outputs and produce the final report.

### Steps

1. **Read** all reviewer outputs (2 if `--skip-gemini`, otherwise 3).
2. **Build synthesis prompt** by concatenating:
   - The synthesizer prompt (see below). If `--skip-gemini`, use the dual-model variant (see [Dual-Model Synthesizer Adjustments](#dual-model-synthesizer-adjustments) below).
   - The PR context block **without the diff** — only metadata (title, author, base/head, stats, description) and the changed file list. The synthesizer merges findings; it doesn't need the raw diff.
   - All reviewer outputs (labeled: "## Codex Reviewer Findings", "## Claude Reviewer Findings", and — unless `--skip-gemini` — "## Gemini Reviewer Findings")
3. **Save** to `<run_dir>/prompts/synthesizer.md`.
4. **Invoke Claude** for synthesis (Claude is better at reasoning-heavy merge tasks):
   ```bash
   bash <run_dir>/scripts/aimux-claude.sh \
     <run_dir>/prompts/synthesizer.md \
     <run_dir>/outputs/synthesis.md
   ```
5. **Clean up worktrees:**
   ```bash
   git worktree remove <run_dir>/worktree --force 2>/dev/null || true
   git worktree remove <run_dir>/worktree-pr --force 2>/dev/null || true
   # Clean up temporary refs (PR mode only — local branch mode has no temp refs):
   git update-ref -d refs/tmp/review-base 2>/dev/null || true
   git update-ref -d refs/tmp/review-pr-head 2>/dev/null || true
   ```
6. **Present** the synthesis to the user.

---

## Phase 4: Post to GitHub (PR Mode Only)

**Local branch mode: Phase 4 is skipped entirely. Present the synthesis directly as the final output.**

After presenting the synthesis to the user (PR mode), **format the GitHub comment and present it for user approval before posting**.

### Pre-Comment Presentation

Before showing the formatted comment, present a concise decision stanza:

```
# PR Review: <title> (#<number>)

## Decision: <approve|request_changes|block>

<1-3 sentence plain-English summary of the PR quality and key takeaways from the review. State the decision rationale.>

**Fixes Validated:** [if applicable]
- <fix description>: correct/incomplete/wrong

**New Findings:** [only issues WITH the PR, not bugs the PR fixes]
1. **<Severity> (<confidence> confidence, <source(s)>):** <one-line summary>
[repeat for each NEW finding]
```

**IMPORTANT:** Do NOT list pre-existing bugs that the PR fixes as "findings." Those are fix validations — they confirm the PR is doing its job correctly. Only list issues that the PR introduces or leaves unaddressed as findings.

Then show the full formatted GitHub comment (below) in a blockquote so the user can read exactly what will be posted.

End with: `Want me to post this as-is, or would you like to edit anything first?`

Only post via `gh pr comment` after the user explicitly confirms. If the user requests edits, incorporate them and re-present for approval.

### GitHub Comment Format

The comment must follow this exact structure. The tone is **friendly, inclusive, and encouraging** — we want contributors to feel appreciated and motivated to iterate.

```markdown
## Automated PR Review — <MODE_LABEL>

Where `<MODE_LABEL>` is:
- Triple-model: `Triple-Model (Claude + Codex + Gemini)`
- Dual-model (`--skip-gemini`): `Dual-Model (Claude + Codex)`

### Decision: <approve | request_changes | block>

<opening paragraph: 2-3 sentences thanking the contributor for the work, acknowledging the problem is real and worth solving, and noting what's good about the approach. Then 1-2 sentences summarizing the key takeaways from the review — the decision rationale. Be genuine, not formulaic.>

[If there are new findings that need response:]
Please address the items below and re-submit — not all may require changes depending on your read of the severity.

---

[For bug-fix PRs, optionally include a brief validation section:]
### Fixes Validated
- **<fix description>:** Confirmed correct. <1-sentence explanation of why the fix is right.>
[repeat for each validated fix — keep these brief, 1-2 lines each]

---

[Then list ONLY new findings — issues with the PR itself, NOT pre-existing bugs it fixes:]

### <Severity>: <One-line title>
**Source:** <codex|claude|gemini|claude+codex|claude+gemini|codex+gemini|all>, <confidence> confidence

<2-4 sentence explanation of the issue in plain language. No jargon walls. Explain the concrete failure scenario.>

**Suggested fix:** <concrete action>

[repeat for each NEW finding, ordered by severity: blocker → major → minor → nit]

---

### Pre-Merge Checklist
- [ ] <derived from NEW findings only>

---
_🤖 Generated by automated review pipeline (<MODEL_LIST>)_

Where `<MODEL_LIST>` is:
- Triple-model: `Claude Opus 4.6 + GPT-5.3 Codex + Gemini 3 Pro`
- Dual-model (`--skip-gemini`): `Claude Opus 4.6 + GPT-5.3 Codex`
```

### Format Rules

1. **Compact, not verbose.** Each finding is one `###` heading + a short paragraph + suggested fix. No nested bullet lists or taxonomy tables in the comment — those stay in the raw synthesis.
2. **Severity in the heading.** Use `Blocker:`, `Major:`, `Minor:`, or `Nit:` as the heading prefix so the contributor can quickly scan priority.
3. **Source and confidence inline.** Put `**Source:** all, high confidence` on a single line under the heading — no taxonomy IDs or category numbers.
4. **Plain language.** Explain *what breaks* and *when*, not abstract category names. The contributor may not know gastown internals.
5. **No "No Finding" sections.** Only list things that need attention. Clean categories are omitted.
6. **Encourage response.** The opening paragraph must ask the contributor to respond with their intention (fix/defer/disagree) for each item. Not all findings are necessarily blocking — the contributor's judgment matters.
7. **Friendly closer.** End with the robot emoji footer attributing the pipeline.
8. **Fix validations are NOT findings.** For bug-fix PRs, pre-existing bugs that the PR correctly fixes go in a brief "Fixes Validated" section — NOT as severity-tagged findings. This prevents the confusing situation where a bug-fix PR appears to have "blockers" that are actually the bugs it's fixing. Only list new issues (things the PR introduces or leaves unaddressed) as findings.

### Tone Guidelines

- **Thank first.** Always open by thanking the contributor and acknowledging the value of their work.
- **Affirm the approach.** Note what's good about the direction before listing concerns.
- **Collaborative, not gatekeeping.** Frame findings as "things to consider" not "things you got wrong." Use "suggested fix" not "required fix" in the comment (even if the synthesis says "required").
- **Invite dialogue.** Make it clear the contributor can push back — severity ratings are the reviewers' judgment, not gospel.
- **Encourage future contributions.** The tone should make someone want to come back and submit more PRs, not dread the review process.

---

## Agent Invocations

### Claude PTY Wrapper (REQUIRED)

**Claude CLI requires a TTY** to produce output. When stdout is a plain file or pipe, it hangs silently with 0 bytes. All Claude invocations MUST use the PTY wrapper script.

**Critical environment fixes (learned 2026-02-13):**
- **`unset CLAUDECODE`** — Claude Code refuses to launch inside another Claude Code session (detects via `CLAUDECODE` env var). The `script` PTY inherits the parent environment, so nested invocations fail with "cannot be launched inside another Claude Code session." Unsetting this var in the `script -c` command fixes it.
- **`command cat`** — On some systems `cat` is aliased to `bat`, which adds ANSI formatting that corrupts the pipe to aimux. Using `command cat` bypasses aliases.

**Stream-JSON output format (learned 2026-02-13):**
- Claude's `--output-format stream-json` produces TWO different event formats depending on whether Claude uses tools:
  - **No tool use:** `stream_event` events with `content_block_delta` / `text_delta` — the original parser handled this.
  - **Multi-turn with tool use:** `assistant` events with `message.content[].text` — each assistant turn is a separate event containing the full text for that turn. The review content is in the longest text block that contains `##` markers.
- The parser MUST handle both formats. Extract text from `assistant` events as a fallback when `stream_event` deltas are empty.

Write this to `<run_dir>/scripts/aimux-claude.sh` during Phase 1:

```bash
#!/usr/bin/env bash
# aimux-claude.sh — PTY-wrapped Claude invocation via aimux
# Usage: aimux-claude.sh <prompt_file> <output_file> [timeout_seconds]
set -euo pipefail

PROMPT_FILE="$1"
OUTPUT_FILE="$2"
TIMEOUT="${3:-600}"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

LOG_FILE=$(mktemp /tmp/claude-pty-XXXXXX.log)
trap 'rm -f "$LOG_FILE"' EXIT

timeout "$TIMEOUT" script -q -e -f -c \
  "unset CLAUDECODE; command cat '$PROMPT_FILE' | aimux run claude -p --verbose --model opus --output-format stream-json -- -" \
  "$LOG_FILE" > /dev/null 2>&1 || true

python3 -c '
import json, re, sys

text = open(sys.argv[1], "r", errors="replace").read()
text = re.sub(r"^Script (started|done) on .*\n?", "", text, flags=re.MULTILINE)
text = re.sub(r"\x1bP[^\x1b]*\x1b\\\\", "", text)
text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\\\)", "", text)
text = re.sub(r"\x1b\[[\x20-\x3f]*[\x40-\x7e]", "", text)
text = re.sub(r"\x1b[()][A-Za-z0-9]", "", text)
text = re.sub(r"\x1b[\x40-\x7e]", "", text)
text = text.replace("\r", "")

result = None
content_deltas = []
assistant_texts = []

for line in text.splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        event = json.loads(line)
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        if etype == "result":
            result = event.get("result", "")
        elif etype == "stream_event":
            inner = event.get("event", {})
            if inner.get("type") == "content_block_delta":
                delta = inner.get("delta", {})
                if delta.get("type") == "text_delta":
                    content_deltas.append(delta.get("text", ""))
        elif etype == "assistant":
            msg = event.get("message", {})
            if isinstance(msg, dict):
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            t = block.get("text", "")
                            if t:
                                assistant_texts.append(t)
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass

# Priority: stream deltas > assistant text blocks > result > raw text
all_deltas = "".join(content_deltas)
if all_deltas:
    out = all_deltas
elif assistant_texts:
    # Use the longest assistant text block containing review markers
    review_blocks = [t for t in assistant_texts if "##" in t and len(t) > 500]
    if review_blocks:
        out = max(review_blocks, key=len)
    else:
        out = max(assistant_texts, key=len)
elif result is not None:
    out = result
else:
    out = text
sys.stdout.write(out)
' "$LOG_FILE" > "$OUTPUT_FILE"

if [[ ! -s "$OUTPUT_FILE" ]]; then
  echo "ERROR: Claude produced empty output. Check aimux status." >&2
  tail -50 "$LOG_FILE" >&2 || true
  exit 1
fi
```

Make executable: `chmod +x <run_dir>/scripts/aimux-claude.sh`

### Codex PTY Wrapper (REQUIRED)

**Codex `exec -o` does NOT work for large review prompts.** Codex spends its capacity on file reads and reasoning, then exits without producing a final agent message — so the `-o` file is never written. This was verified across multiple runs on PR #1226 (83KB+ prompt). The fix is PTY capture via `script`, same pattern as Claude.

**Key design decisions (verified 2026-02-13):**
- Use `exec` (not `exec review --base`). The `--base` subcommand spends all capacity on codebase research without producing a final review.
- **Must use `--dangerously-bypass-approvals-and-sandbox`** — without this, Codex runs in read-only sandbox and cannot execute commands for caller/callee tracing.
- **Must use PTY capture** (not `-o` flag) — the `-o` flag only captures the "last agent message", but Codex never produces one for large prompts. PTY capture gets all output including intermediate "codex" blocks.
- Include the full diff in the prompt so Codex doesn't need to compute it.
- Use `-c model_reasoning_effort='"xhigh"'` for maximum reasoning depth.
- Pipe the prompt via `cat <file> | ... -- -` (not stdin redirect `-- - < file`).

Write this to `<run_dir>/scripts/aimux-codex.sh` during Phase 1:

```bash
#!/usr/bin/env bash
# aimux-codex.sh — PTY-wrapped Codex invocation via aimux
# Usage: aimux-codex.sh <prompt_file> <output_file> [timeout_seconds]
set -euo pipefail

PROMPT_FILE="$1"
OUTPUT_FILE="$2"
TIMEOUT="${3:-600}"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

LOG_FILE=$(mktemp /tmp/codex-pty-XXXXXX.log)
trap 'rm -f "$LOG_FILE"' EXIT

# Build the command in a temp file (avoids quoting issues with script -c)
CMD_FILE=$(mktemp /tmp/codex-cmd-XXXXXX.sh)
printf 'unset CLAUDECODE; command cat %q | aimux run codex -m gpt-5.3-codex exec --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort='"'"'"xhigh"'"'"' -- -\n' "$PROMPT_FILE" > "$CMD_FILE"
chmod +x "$CMD_FILE"

timeout "$TIMEOUT" script -q -e -f -c "bash '$CMD_FILE'" "$LOG_FILE" > /dev/null 2>&1 || true

rm -f "$CMD_FILE"

# Extract "codex" blocks (agent messages) from the PTY log.
# The longest block is the actual review content.
# Note: Codex sometimes outputs the review twice (with a "tokens used" separator).
# The "longest block" heuristic deduplicates this automatically.
python3 -c '
import re, sys

text = open(sys.argv[1], "r", errors="replace").read()

# Strip script header/footer
text = re.sub(r"^Script (started|done) on .*\n?", "", text, flags=re.MULTILINE)

# Strip ANSI escape sequences
text = re.sub(r"\x1bP[^\x1b]*\x1b\\\\", "", text)
text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\\\)", "", text)
text = re.sub(r"\x1b\[[\x20-\x3f]*[\x40-\x7e]", "", text)
text = re.sub(r"\x1b[()][A-Za-z0-9]", "", text)
text = re.sub(r"\x1b[\x40-\x7e]", "", text)
text = text.replace("\r", "")

# Find all "codex" blocks — these are agent messages
blocks = []
lines = text.split("\n")
in_codex_block = False
current_block = []

for line in lines:
    stripped = line.strip()
    if stripped == "codex":
        if current_block and in_codex_block:
            blocks.append("\n".join(current_block))
        in_codex_block = True
        current_block = []
    elif in_codex_block and stripped in ("thinking", "exec", "user"):
        blocks.append("\n".join(current_block))
        in_codex_block = False
        current_block = []
    elif in_codex_block:
        current_block.append(line)

if in_codex_block and current_block:
    blocks.append("\n".join(current_block))

if blocks:
    # Output the longest codex block (the actual review)
    longest = max(blocks, key=len)
    sys.stdout.write(longest.strip() + "\n")
else:
    # Fallback: output everything
    sys.stdout.write(text)
' "$LOG_FILE" > "$OUTPUT_FILE"

if [[ ! -s "$OUTPUT_FILE" ]]; then
  echo "ERROR: Codex produced empty output. Check aimux status." >&2
  tail -50 "$LOG_FILE" >&2 || true
  exit 1
fi
```

Make executable: `chmod +x <run_dir>/scripts/aimux-codex.sh`

> **Historical note (2026-02-13):** The original approach used `codex exec -o <file>` to capture the last agent message. This worked for small prompts but consistently failed for large review prompts (83KB+). Codex would read 6+ files, produce brief progress messages, and exit (code 0) without a final agent message — so `-o` never wrote the file. The PTY capture approach (matching Forge's `agent-wrapper.sh` pattern) captures all output and extracts the review from "codex" blocks. The `--dangerously-bypass-approvals-and-sandbox` flag is required for Codex to execute commands for caller/callee tracing.

### Gemini PTY Wrapper (REQUIRED)

**Gemini is invoked via `aimux run gemini`**, matching the pattern used for Claude and Codex. Aimux handles account selection and sets `GEMINI_CLI_HOME` for credential isolation. The Gemini CLI uses `--yolo` for auto-approving tool use (file reads for tracing), `-p ''` for headless (non-interactive) mode with stdin as input, and `-o text` for plain text output. The output extraction is simpler than Claude/Codex — just strip ANSI and script chrome (no JSON parsing, no "codex block" extraction).

Write this to `<run_dir>/scripts/aimux-gemini.sh` during Phase 1:

```bash
#!/usr/bin/env bash
# aimux-gemini.sh — PTY-wrapped Gemini invocation via aimux
# Usage: aimux-gemini.sh <prompt_file> <output_file> [timeout_seconds]
set -euo pipefail

PROMPT_FILE="$1"
OUTPUT_FILE="$2"
TIMEOUT="${3:-600}"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

LOG_FILE=$(mktemp /tmp/gemini-pty-XXXXXX.log)
trap 'rm -f "$LOG_FILE"' EXIT

timeout "$TIMEOUT" script -q -e -f -c \
  "command cat '$PROMPT_FILE' | aimux run gemini -- -m gemini-3-pro-preview --yolo -o text -p ''" \
  "$LOG_FILE" > /dev/null 2>&1 || true

# Extract clean text from PTY log (strip ANSI + script chrome)
python3 -c '
import re, sys

text = open(sys.argv[1], "r", errors="replace").read()
text = re.sub(r"^Script (started|done) on .*\n?", "", text, flags=re.MULTILINE)
text = re.sub(r"\x1bP[^\x1b]*\x1b\\\\", "", text)
text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\\\)", "", text)
text = re.sub(r"\x1b\[[\x20-\x3f]*[\x40-\x7e]", "", text)
text = re.sub(r"\x1b[()][A-Za-z0-9]", "", text)
text = re.sub(r"\x1b[\x40-\x7e]", "", text)
text = text.replace("\r", "")
sys.stdout.write(text.strip() + "\n")
' "$LOG_FILE" > "$OUTPUT_FILE"

if [[ ! -s "$OUTPUT_FILE" ]]; then
  echo "ERROR: Gemini produced empty output. Check aimux status." >&2
  tail -50 "$LOG_FILE" >&2 || true
  exit 1
fi
```

Make executable: `chmod +x <run_dir>/scripts/aimux-gemini.sh`

---

## Shared Taxonomy

All three reviewers use this exact category taxonomy and priority ranking:

| Priority | # | Category | Why it catches regressions |
|----------|---|----------|---------------------------|
| P0 | 1 | Behavioral Correctness | Logic bugs, edge cases, off-by-ones, nil derefs |
| P0 | 2 | Contract & Interface Fidelity | Broken caller expectations, schema violations |
| P0 | 3 | Change Impact / Blast Radius | Incomplete updates across callsites |
| P0 | 4 | Concurrency, Ordering & State Safety | Races, deadlocks, ordering violations |
| P1 | 5 | Error Handling & Resilience | Swallowed errors, missing retries/timeouts |
| P1 | 6 | Security Surface | Injection, path traversal, secret leakage |
| P1 | 7 | Resource Lifecycle & Cleanup | Leaked files, sessions, goroutines, worktrees |
| P1 | 8 | Release Safety | Migration risk, rollback blockers, state corruption |
| P2 | 9 | Test Evidence Quality | Changed behavior without test coverage |
| P2 | 10 | Architectural Consistency | Pattern drift, role boundary violations |
| P2 | 11 | Debuggability & Operability | Missing diagnostic output for failure investigation |

### Severity Scale

| Severity | Meaning | Action |
|----------|---------|--------|
| `blocker` | Will break existing behavior or corrupt state | Must fix before merge |
| `major` | High risk of regression under realistic conditions | Should fix before merge |
| `minor` | Low probability issue, but real mechanism exists | Fix or explicitly accept |
| `nit` | Improvement opportunity with no regression risk | Optional |

### Confidence Scale

| Confidence | Meaning |
|------------|---------|
| `high` | Concrete evidence in code, reproducible reasoning |
| `medium` | Strong signal but depends on runtime conditions |
| `low` | Plausible concern, needs human verification |

---

## Reviewer Prompts

### codex-reviewer

This prompt is passed to Codex via PTY-wrapped `exec` along with the full context block (metadata + diff). Codex runs from the head worktree (PR head or branch tip) and can read files for additional caller/callee tracing.

```
You are "codex-reviewer" for a code review in the gastown codebase.

Gastown is a Go-based multi-agent orchestration system. It manages concurrent AI agents across tmux sessions, git worktrees, and a bead-based work tracking system. Regressions are hard to catch because the system is difficult to test end-to-end.

## Mission

Produce a high-signal, evidence-first review focused on concrete code impact and repo-wide traceability. Your strength is indexing and tracing -- use it. Find every caller, every test, every contract touchpoint.

IMPORTANT: You MUST produce a final review with findings. Do NOT spend all your time reading files. The diff below contains all changed code. Focus your analysis on the diff itself. Only read files from the worktree if you need to check a specific caller or contract — DO NOT read more than 5 files total.

## Category Taxonomy (use exactly)

1) Behavioral Correctness
2) Contract & Interface Fidelity
3) Change Impact / Blast Radius
4) Concurrency, Ordering & State Safety
5) Error Handling & Resilience
6) Security Surface
7) Resource Lifecycle & Cleanup
8) Release Safety
9) Test Evidence Quality
10) Architectural Consistency
11) Debuggability & Operability

Priority: P0 = categories 1-4 (aggressively check). P1 = 5-8. P2 = 9-11.

## How to Work

### Codebase Access
You are running from a git worktree checked out at the PR head. The full diff is included in this prompt. You may use the codebase to trace callers and verify claims, but **prioritize analyzing the diff directly** over exhaustive codebase research. The diff contains all changed code — focus your analysis there.

### General
- Analyze the diff for logic bugs, edge cases, and incomplete updates.
- Identify contract touchpoints: CLI flags, API signatures, config structs, TOML schemas, hook protocols, bead fields.
- Check that updates are complete across all usage sites visible in the diff.
- Map changed behavior to existing tests and list explicit coverage gaps.
- Check cleanup paths (files, tmux sessions, worktrees, goroutines) on both success AND failure.
- Check that error messages and log output remain useful for debugging.

### Existing Handling Check (CRITICAL for bug-fix PRs)
- When a PR claims to fix a failure mode, **actively search for existing code that already handles that failure.** This is your highest-priority tracing task for bug-fix PRs.
- Specifically search for: error recovery paths, retry logic, conflict resolution, fallback branches, and any multi-phase handling (try → detect failure → resolve) downstream of the "broken" code path.
- If you find an existing handling mechanism, evaluate whether it would resolve the claimed bug WITHOUT the PR's changes. Cite the handler with path:line evidence.
- For Dolt/database operations: always trace merge conflict resolution paths (`--theirs`, `--ours`, `DOLT_CONFLICTS_RESOLVE`). These are specifically designed to handle divergent branch state.
- Include your findings in the Evidence Bundle under a new field: **Existing handlers checked:** [list with path:line, or "none found"]

### Gastown-Specific Invariants
- **Formula TOML contracts:** Step dependencies must form a DAG. No orphan steps. Variable references (Go text/template) must resolve. New steps must appear in TopologicalSort output.
- **Role boundaries:** Polecats never touch main branch. Refinery never creates worktrees. Deacon never merges. Witness never does implementation work. Mayor never spawns polecats directly.
- **Hook/bead protocol:** `bd ready`/`bd close` must be paired. Bead sync must happen before `gt done`. Hook environment variables must be set before agent spawn.
- **Agent preset contracts:** `AgentPresetInfo` fields (SessionIDEnv, ResumeFlag, ResumeStyle, SupportsHooks) must match actual CLI behavior of the agent binary.
- **Self-cleaning contract:** Polecats must call `gt done` which syncs beads, nukes worktree, and exits. No partial cleanup.
- **Tmux session management:** Session names must be deterministic. Pane targeting must handle "no sessions" and "no current target" errors.

## Output Format

**CRITICAL: Separate fix validations from new findings.**

Bug-fix PRs will have two classes of observations:
1. **Fix Validations** — pre-existing bugs that the PR correctly fixes. These are NOT problems with the PR. List them to confirm correctness, but they do NOT count as findings.
2. **New Findings** — issues introduced by the PR itself, or remaining issues that the PR should address. These ARE problems with the PR.

Start with "## Fix Validations" (if the PR fixes bugs):
```
### <what was broken>
- **Status:** correct | incomplete | wrong
- **Evidence:** path:line
- **Assessment:** [1-2 sentences confirming the fix is correct, or explaining why it's incomplete/wrong]
```

Then "## Findings" for NEW issues only:

For each finding:
```
### [Category Name]
- **Severity:** blocker|major|minor|nit
- **Confidence:** high|medium|low
- **Evidence:** path:line[, path:line]
- **Why it matters:** [one sentence]
- **Suggested fix:** [concrete action]
```

Then "## No Finding" for categories with no issues (list them explicitly).

End with:
## Evidence Bundle
- **Changed hot paths:** [list]
- **Impacted callers:** [list with path:line]
- **Impacted tests:** [list with path:line]
- **Unresolved uncertainty:** [list]

## Constraints
- No style/formatting issues unless they create behavioral risk.
- No invented behavior -- cite code evidence for every claim. **Search the codebase** to back up claims about callers, patterns, or missing migrations.
- Prefer precise path:line references over broad claims.
- Fewer high-signal findings >> exhaustive speculative lists.
- **Do NOT list pre-existing bugs that the PR fixes as "findings".** Those go under Fix Validations.
```

### claude-reviewer

```
You are "claude-reviewer" for a code review in the gastown codebase.

Gastown is a Go-based multi-agent orchestration system. It manages concurrent AI agents across tmux sessions, git worktrees, and a bead-based work tracking system. Regressions are hard to catch because the system is difficult to test end-to-end.

## Mission

Produce a high-signal, reasoning-heavy review focused on intent fidelity, invariant safety, and subtle regression risk. Your strength is deep reasoning about correctness under edge conditions -- use it. Think about what happens when things fail halfway, when concurrent operations interleave, when assumptions don't hold.

## Category Taxonomy (use exactly)

1) Behavioral Correctness
2) Contract & Interface Fidelity
3) Change Impact / Blast Radius
4) Concurrency, Ordering & State Safety
5) Error Handling & Resilience
6) Security Surface
7) Resource Lifecycle & Cleanup
8) Release Safety
9) Test Evidence Quality
10) Architectural Consistency
11) Debuggability & Operability

Priority: P0 = categories 1-4 (gatekeepers). P1 = 5-8. P2 = 9-11.

## How to Work

### Codebase Access
You are running from a git worktree checked out at the base branch, which represents the authoritative codebase state before the changes. Use your tools (grep, find, read) freely to trace callers, callees, dependencies, and existing patterns. The diff is included in the prompt below — the worktree shows the codebase *before* the changes.

### General
- Evaluate whether implementation matches claimed PR intent. Flag divergence.
- Check edge cases: empty inputs, nil values, zero-length slices, missing map keys, EOF, partial writes.
- Check negative paths: what happens when the operation fails halfway? Is state left consistent?
- Validate ordering assumptions under concurrent execution. If two goroutines or agents could race on shared state, flag it.
- Inspect contract safety: backward compatibility of exported functions, schema/protocol stability, caller expectations preserved. **Search the codebase** to find callers of changed functions.
- Threat-model trust boundaries: user input → exec.Command, file paths → os.Open, template data → TOML injection.
- Assess rollback safety: could this change be reverted cleanly? Does it introduce persistent state that survives rollback?
- Check operational diagnosability: if this change breaks in production, can you tell what happened from logs and bead state?

### Premise Validation (CRITICAL for bug-fix PRs)
- **Before validating a fix, validate the bug.** If the PR claims "X causes Y failure", trace the full execution path to verify Y actually occurs without this PR. Do NOT take the PR description's failure narrative at face value.
- Search for existing handling mechanisms downstream: error recovery, conflict resolution (e.g., `--theirs` merge strategies), retry logic, fallback paths. The codebase may already handle the failure through a different code path that the PR author missed.
- Ask: "If I remove this entire PR, does the claimed failure actually happen?" Trace end-to-end, across files.
- Flag if the PR bypasses an existing mechanism (e.g., writing directly to a data store instead of going through the established merge/conflict-resolution pipeline). Even if the bypass "works", it breaks architectural contracts.
- When you cannot fully verify the premise, mark the Fix Validation as `incomplete` with a note explaining what you couldn't trace, rather than defaulting to `correct`.

### Gastown-Specific Invariants
- **Formula TOML contracts:** Step dependencies must form a DAG. No orphan steps. Variable references (Go text/template) must resolve. Changed steps must not break TopologicalSort or ReadySteps computation.
- **Role boundaries:** Polecats never touch main. Refinery never creates worktrees. Deacon never merges. Witness never implements. Mayor never spawns polecats directly. Violations are silent and catastrophic.
- **Hook/bead protocol:** `bd ready`/`bd close` pairing. Bead sync before `gt done`. Hook env vars set before agent spawn. Violation means lost work or phantom state.
- **Agent preset contracts:** `AgentPresetInfo` fields must match real CLI behavior. Wrong ResumeStyle = broken session resume. Wrong SupportsHooks = silent hook failure.
- **Self-cleaning contract:** Polecats call `gt done` → sync beads → nuke worktree → exit. Partial cleanup leaves zombie worktrees that corrupt future operations.
- **Tmux session management:** Session names deterministic. Pane targeting handles edge cases. Race between session creation and pane targeting is a known fragile area.
- **Merge queue (Refinery):** Only Refinery merges to main. Merge ordering must respect dependency graph. Conflict resolution spawns fresh polecats, never retries in-place.

## Output Format

**CRITICAL: Separate fix validations from new findings.**

Bug-fix PRs will have two classes of observations:
1. **Fix Validations** — pre-existing bugs that the PR correctly fixes. These are NOT problems with the PR. List them to confirm correctness, but they do NOT count as findings.
2. **New Findings** — issues introduced by the PR itself, or remaining issues that the PR should address. These ARE problems with the PR.

Start with "## Fix Validations" (if the PR fixes bugs):
```
### <what was broken>
- **Status:** correct | incomplete | wrong
- **Evidence:** path:line
- **Assessment:** [1-2 sentences confirming the fix is correct, or explaining why it's incomplete/wrong]
```

Then "## Findings" for NEW issues only:

For each finding:
```
### [Category Name]
- **Severity:** blocker|major|minor|nit
- **Confidence:** high|medium|low
- **Evidence:** path:line[, path:line]
- **Why it matters:** [one sentence]
- **Suggested fix:** [concrete action]
```

Then "## No Finding" for categories with no issues (list them explicitly).

End with:
## Assumptions Checked
[List invariants you verified hold — cite codebase searches you performed]

## Open Risks
[List concerns that need human judgment or runtime verification]

## Constraints
- No style nits unless they hide a correctness/operability problem.
- No speculative concerns without a concrete mechanism and evidence.
- Deep, high-impact findings >> exhaustive low-signal lists.
- If you are uncertain, say so with confidence=low rather than omitting.
- **Search the codebase** to back up claims about callers, patterns, or missing migrations. Do not guess.
- **Do NOT list pre-existing bugs that the PR fixes as "findings".** Those go under Fix Validations.
```

### gemini-reviewer

This prompt is passed to Gemini via PTY-wrapped `aimux run gemini` along with the full context block (metadata + diff). Gemini runs from the PR head worktree and can read files for cross-file pattern analysis.

```
You are "gemini-reviewer" for a code review in the gastown codebase.

Gastown is a Go-based multi-agent orchestration system. It manages concurrent AI agents across tmux sessions, git worktrees, and a bead-based work tracking system. Regressions are hard to catch because the system is difficult to test end-to-end.

## Mission

Produce a high-signal review focused on cross-file consistency, pattern adherence, and architectural coherence. Your strength is analyzing how changes ripple across files and whether the codebase remains internally consistent after the PR. Think holistically — zoom out from individual lines to the structural relationships between components.

Two other reviewers (Claude and Codex) are analyzing this same PR in parallel. Claude focuses on invariant safety and edge-case reasoning. Codex focuses on caller/callee tracing and evidence gathering. Your job is to catch what they'll miss: **pattern drift, incomplete propagation, architectural violations, and cross-cutting inconsistencies.**

## Category Taxonomy (use exactly)

1) Behavioral Correctness
2) Contract & Interface Fidelity
3) Change Impact / Blast Radius
4) Concurrency, Ordering & State Safety
5) Error Handling & Resilience
6) Security Surface
7) Resource Lifecycle & Cleanup
8) Release Safety
9) Test Evidence Quality
10) Architectural Consistency
11) Debuggability & Operability

Priority: Focus heavily on categories 3, 10, and 2. These are where cross-file analysis catches the most regressions. Categories 1 and 4 are well-covered by Claude. Evidence gathering for categories 5-9 is well-covered by Codex.

## How to Work

### Codebase Access
You are running from a git worktree checked out at the PR head — the code as it will look after the change. Use your tools freely to read files, search for patterns, and trace dependencies. The diff is included in the prompt below.

### Your Unique Focus Areas

**Cross-file consistency (your #1 job):**
- When the PR changes a struct, interface, or function signature: search the entire codebase for all usage sites. Are all callers updated? Are there test files, mock implementations, or generated code that need matching changes?
- When the PR adds a new pattern (new helper function, new error type, new config field): does it follow the conventions established by similar existing patterns? Search for 2-3 analogous examples and compare.
- When the PR modifies one file in a group of related files (e.g., one role's manager but not others): check whether sibling files need parallel changes.

**Pattern drift detection:**
- Compare the PR's approach against the dominant pattern in the codebase. If 8 out of 10 similar functions use pattern A and the PR introduces pattern B, flag it — even if B works. Consistency has value.
- Look for copy-paste with incomplete adaptation: when code is clearly modeled on an existing function, check that ALL relevant differences were addressed (not just the obvious ones).

**Dependency chain analysis:**
- Map the chain: what calls the changed code, and what does the changed code call? Follow the chain 2-3 levels deep. Are there intermediate functions that make assumptions the PR violates?
- Check for implicit contracts: does the changed code produce output that downstream consumers parse or depend on? (Log formats, bead field values, tmux session name patterns, file path conventions.)

**Architectural coherence:**
- Does the change respect the system's layering? (e.g., CLI layer should not import internal agent logic; role managers should not reach into each other's state.)
- Does the change create new coupling between modules that were previously independent?
- Does the change duplicate logic that already exists elsewhere? If so, should it call the existing code instead?

**Bypass detection (critical for bug-fix PRs):**
- When a PR changes the ordering or location of an operation to avoid a failure, check whether the existing code path already has a mechanism to handle that failure (conflict resolution, retry, fallback).
- Flag PRs that bypass established data flow (e.g., writing directly to main instead of going through branch merge + conflict resolution). Even if the bypass "works", it violates the system's designed error-handling pipeline.
- Compare the PR's approach against the system's designed multi-phase patterns. If the system has a deliberate try → conflict → resolve pipeline, and the PR avoids the conflict entirely rather than relying on the resolution phase, that's an architectural red flag worth investigating.

### Gastown-Specific Patterns to Check
- **Role boundary compliance:** Polecats never touch main. Refinery never creates worktrees. Deacon never merges. Mayor never spawns polecats directly. Check that the PR doesn't introduce cross-role coupling.
- **Formula consistency:** If a formula TOML is changed, verify step IDs, dependency edges, and description fields are consistent with the formula's Go consumer code.
- **Bead field conventions:** Bead labels follow `key:value` format. Status transitions follow open → closed. Description fields use consistent Markdown structure.
- **Config/flag propagation:** When a new CLI flag or config field is added, check that it's wired through all layers: CLI parsing → config struct → runtime usage → help text → documentation.
- **Error message consistency:** Gastown uses structured error wrapping (`fmt.Errorf("context: %w", err)`). Check that new error messages follow this pattern and don't lose error context.
- **Logging conventions:** Check that new log output includes enough context (session name, bead ID, step ID) to diagnose issues without additional debugging.

## Output Format

**CRITICAL: Separate fix validations from new findings.**

Bug-fix PRs will have two classes of observations:
1. **Fix Validations** — pre-existing bugs that the PR correctly fixes. These are NOT problems with the PR.
2. **New Findings** — issues introduced by the PR itself, or remaining issues the PR should address.

Start with "## Fix Validations" (if the PR fixes bugs):
### <what was broken>
- **Status:** correct | incomplete | wrong
- **Evidence:** path:line
- **Assessment:** [1-2 sentences]

Then "## Findings" for NEW issues only:

### [Category Name]
- **Severity:** blocker|major|minor|nit
- **Confidence:** high|medium|low
- **Evidence:** path:line[, path:line]
- **Pattern comparison:** [cite the existing pattern this deviates from, with path:line]
- **Why it matters:** [one sentence]
- **Suggested fix:** [concrete action]

Then "## No Finding" for categories with no issues.

End with:
## Consistency Report
- **Patterns checked:** [list patterns you searched for and verified]
- **Sibling files checked:** [list related files you compared against]
- **Propagation verified:** [list dependency chains you traced]
- **Drift detected:** [list any pattern deviations, even minor ones]

## Constraints
- No style nits unless they represent pattern drift from an established codebase convention.
- Every finding must cite a **comparison point** — the existing pattern or file it deviates from. No abstract claims.
- Your unique value is breadth of analysis across files. Prioritize findings that span multiple files over single-file issues.
- Do NOT duplicate Claude's edge-case reasoning or Codex's caller tracing. Focus on what only cross-file analysis reveals.
- **Search the codebase** to verify claims. Do not guess about patterns — find examples.
- **Do NOT list pre-existing bugs that the PR fixes as "findings".** Those go under Fix Validations.
```

---

## Synthesizer Prompt

```
You are the "review-synthesizer" combining outputs from codex-reviewer, claude-reviewer, and gemini-reviewer for a gastown code review.

## Inputs

You will receive:
1. The review context (metadata, description, changed file list — NOT the full diff)
2. Codex reviewer findings
3. Claude reviewer findings
4. Gemini reviewer findings

## Task

Create one maintainer-grade decision report. Deduplicated, severity-calibrated, action-oriented.

## Method

1) Normalize all findings into the shared taxonomy:
   1. Behavioral Correctness
   2. Contract & Interface Fidelity
   3. Change Impact / Blast Radius
   4. Concurrency, Ordering & State Safety
   5. Error Handling & Resilience
   6. Security Surface
   7. Resource Lifecycle & Cleanup
   8. Release Safety
   9. Test Evidence Quality
   10. Architectural Consistency
   11. Debuggability & Operability

2) Merge findings that share the same root cause into a single entry.

3) Severity disagreement policy:
   - If multiple reviewers flag the same issue, keep the stricter severity.
   - If one reviewer flags blocker and the others don't mention it at all, mark confidence as "medium" and keep blocker -- this needs human attention.
   - If severity differs by exactly one level (e.g., major vs minor), keep the stricter.

4) Mark each final finding with source attribution: `codex`, `claude`, `gemini`, `claude+codex`, `claude+gemini`, `codex+gemini`, or `all`.

5) Cross-reference Claude's findings against Codex's evidence bundle. Findings that have concrete path:line evidence from the bundle get confidence boosted. Findings with no evidence trail get confidence reduced.

6) **Trust codebase-backed evidence.** All three reviewers had full access to the upstream codebase (via worktree). Findings that cite specific path:line evidence from codebase searches are high-signal. Findings that make claims about "remaining sites" or "missing callers" without citing search evidence should be treated with lower confidence — ask whether the reviewer actually searched.

7) **Gemini cross-file findings are high-signal.** When Gemini flags a cross-file consistency issue that neither Claude nor Codex mentioned, treat it as high-signal — this is Gemini's specialty. Cross-reference Gemini's consistency report against Codex's evidence bundle. Gemini findings that align with Codex-traced callers get confidence boosted.

8) **Premise validation consensus check.** For bug-fix PRs: check whether any reviewer independently verified that the claimed failure actually occurs (by tracing the full execution path including existing handling mechanisms like conflict resolution or retry logic). If ALL reviewers accepted the PR's stated bug at face value without independent verification, add a finding:
   - Category: Behavioral Correctness
   - Severity: major
   - Confidence: medium
   - Source: synthesis
   - Summary: "No reviewer independently verified the claimed failure scenario. Existing handling mechanisms (e.g., [cite if any reviewer mentioned them]) may already resolve this case."
   This is critical because a fix for a non-existent bug adds complexity, may bypass safety mechanisms, and sets incorrect precedents. See PR #1648 (reverted in #1656).

## Output Format

**CRITICAL: Separate fix validations from new findings.**

Reviewers may report two classes of observations:
1. **Fix Validations** — pre-existing bugs the PR correctly fixes. These confirm the fix is correct. They do NOT count toward the merge decision.
2. **New Findings** — issues introduced by or remaining in the PR. These drive the merge decision.

When merging, classify each reviewer observation into one of these two categories. If a reviewer listed a "fix validation" as a "finding" (e.g., severity: blocker with note "this PR fixes it"), reclassify it as a fix validation.

Where `<identifier>` is `#<number>` for PR mode or `<branch> vs <base>` for local branch mode.

```
# Review: <title> (<identifier>)

## Decision: approve | request_changes | block

## Fix Validations
[For bug-fix PRs: brief confirmation that pre-existing bugs are correctly fixed]
- **<what was broken>:** <correct|incomplete|wrong> — <1-sentence assessment>

## Top Risks (max 5, ordered by severity then confidence)
[Only NEW findings — not fix validations]
1. [one-line summary] — severity / confidence / source

## New Findings

### [Category Name]
- **Severity:** blocker|major|minor|nit
- **Confidence:** high|medium|low
- **Source:** codex|claude|gemini|claude+codex|claude+gemini|codex+gemini|all
- **Evidence:** path:line
- **Why it matters:** [one sentence]
- **Required fix:** [concrete action]

[repeat for each NEW finding]

## Category Coverage
[For each of the 11 categories: either a finding reference or "No finding"]

## Pre-Merge Checklist
- [ ] [must-pass items derived from NEW findings only]
```

## Decision Policy

Decision is based ONLY on new findings, NOT on fix validations:
- Any unresolved blocker in categories 1-4 → `block`.
- Any unresolved blocker in categories 5-8 → `request_changes`.
- Major issues in categories 1-8 without mitigation → `request_changes`.
- Purely minor/nit set → `approve`.
- No new findings at all → `approve`.
- Fix validations marked "incomplete" or "wrong" → treat as new findings at appropriate severity.

## Constraints
- No style-only commentary.
- Concise, concrete, evidence-linked.
- The output is for a human maintainer making a merge decision. Respect their time.
```

---

## Dual-Model Synthesizer Adjustments

When `--skip-gemini` is active, apply these adjustments to the synthesizer prompt and process:

1. **Synthesizer prompt header:** Replace "combining outputs from codex-reviewer, claude-reviewer, and gemini-reviewer" with "combining outputs from codex-reviewer and claude-reviewer (dual-model mode, Gemini skipped)".
2. **Inputs section:** Remove "3. Gemini reviewer findings" from the input list.
3. **Method step 4:** Source attribution uses only: `codex`, `claude`, or `claude+codex` (not `gemini`, `claude+gemini`, `codex+gemini`, or `all`).
4. **Method step 7 (Gemini cross-file findings):** Skip entirely — this step is N/A in dual-model mode.
5. **Cross-file coverage gap:** Note in the synthesis output that cross-file consistency analysis (Gemini's specialty) was not performed. Add a line under Category Coverage: `"⚠ Cross-file consistency (category 3, 10) had reduced coverage — Gemini reviewer was skipped."`
6. **GitHub comment heading:** Use `Dual-Model (Claude + Codex)` instead of `Triple-Model (Claude + Codex + Gemini)`.
7. **GitHub comment footer:** Use `Claude Opus 4.6 + GPT-5.3 Codex` instead of the triple-model list.

All other synthesis logic (deduplication, severity policy, decision policy, output format) remains identical.

---

## Progress Reporting

Print phase transitions to terminal.

**PR mode** (4 phases):

```
[review-pr] Phase 1/4: Gathering PR context...
[review-pr]   PR #123: "Add formula validation for orphan steps"
[review-pr]   +142 -38 across 5 files
[review-pr]   Upstream worktrees created at <run_dir>/worktree{,-pr}
[review-pr] Phase 2/4: Running parallel reviews (Claude || Codex [|| Gemini])...
[review-pr]   Claude reviewer started
[review-pr]   Codex reviewer started
[review-pr]   Gemini reviewer started
[review-pr]   Claude reviewer complete (60s)
[review-pr]   Gemini reviewer complete (45s)
[review-pr]   Codex reviewer complete (300s)
[review-pr] Phase 3/4: Synthesizing findings...
[review-pr]   Synthesis complete (90s)
[review-pr]   Decision: request_changes (2 blockers, 1 major)
[review-pr]   Worktrees cleaned up.
[review-pr] Phase 4/4: Awaiting user approval to post to GitHub...
[review-pr]   User approved. Comment posted.
[review-pr] Done. Report at <run_dir>/outputs/synthesis.md
```

**Local branch mode** (3 phases — no Phase 4):

```
[review-pr] Phase 1/3: Gathering branch context...
[review-pr]   Branch: ci/close-stale-needs
[review-pr]   Auto-detected base: upstream/main (merge-base: fd7b5663)
[review-pr]   +85 -12 across 3 files
[review-pr]   Local worktrees created at <run_dir>/worktree{,-pr}
[review-pr] Phase 2/3: Running parallel reviews (Claude || Codex [|| Gemini])...
[review-pr]   Claude reviewer started
[review-pr]   Codex reviewer started
[review-pr]   Gemini reviewer started
[review-pr]   Claude reviewer complete (60s)
[review-pr]   Gemini reviewer complete (45s)
[review-pr]   Codex reviewer complete (300s)
[review-pr] Phase 3/3: Synthesizing findings...
[review-pr]   Synthesis complete (90s)
[review-pr]   Decision: approve (0 blockers, 1 minor)
[review-pr]   Worktrees cleaned up.
[review-pr] Done. Report at <run_dir>/outputs/synthesis.md
```

**Typical timing:** Phase 1: ~30s, Phase 2: ~5 min (Codex is the bottleneck; Claude finishes in ~60s, Gemini in ~45s), Phase 3: ~90s, Phase 4 (PR only): depends on user review.

---

## Error Handling

| Failure | Action |
|---------|--------|
| `gh` command fails | Report error, check auth: `gh auth status` |
| PR not found | Report "PR not found" with URL attempted |
| Branch not found (local mode) | Report "Branch '<branch>' not found in local repository." |
| Base branch not found (local mode) | Report "Base branch '<base>' not found in local repository." |
| No commits between branches (local mode) | Report "No commits between '<base>' and '<branch>'. Nothing to review." |
| `--base` used in PR mode | Ignore silently (base is determined by the PR) |
| Worktree creation fails | Try fallback ref method (PR mode). If still fails, report error — review cannot proceed without accurate codebase access |
| Agent pre-flight fails | Report which agent, suggest `aimux status` |
| Gemini unavailable via aimux | If `--skip-gemini`: N/A. Otherwise: Report "Gemini not available. Check `aimux status` and `aimux verify gemini`.", stop |
| One reviewer produces empty output | Report failure and stop. All required reviewers must succeed — no single-model fallback |
| Gemini produces empty output | If `--skip-gemini`: N/A. Otherwise: Report failure, stop |
| Codex PTY log has no "codex" blocks | Codex may have failed to start or hit an error. Check the PTY log file. Stop pipeline — all reviewers required |
| Codex output is duplicated | Normal behavior — Codex sometimes outputs the review twice with a "tokens used" separator. The PTY parser's "longest block" heuristic handles this automatically |
| Synthesis produces empty output | Present raw reviewer outputs directly |
| Diff too large (>100KB) | All three reviewers get the full diff. No truncation. |
| Worktree cleanup fails | Log warning but don't block. User can clean up manually: `git worktree list` then `git worktree remove` |
| Claude produces tiny output (<500 bytes) | Claude spent all capacity on tool use (reading files) instead of producing a review. **Retry with shorter prompt** that includes explicit "CRITICAL: Do NOT use tools to read files" instruction. See Known Issues below |
| Branch has large merge-base divergence | Should be auto-resolved by the base auto-detection (checks `main`, `upstream/main`, `origin/main` and picks the most recent merge-base). If auto-detection still produces a large diff, the user can override with `--base <ref>` pointing to the correct ancestor. |

---

## Known Issues & Operational Learnings

### Claude reviewer fails on large prompts (>100KB)

**Symptom:** Claude produces 100-300 bytes of output like "I'll start by searching the codebase..." instead of an actual review. This happens consistently when the prompt exceeds ~100KB and Claude has tool access.

**Root cause:** Claude uses all its capacity on tool calls (reading files, grepping) and never produces the final review text.

**Fix:** Use a shorter role prompt (~500 bytes vs ~4KB) with an explicit instruction: `CRITICAL: Do NOT use tools to read files. The diff contains everything you need. Produce your review directly.` This consistently produces 9-12KB reviews in ~60-180s.

**When to retry:** If Claude output is <500 bytes, retry once with the short prompt. If still failing, report failure.

### Local branch mode: fork-based workflows (resolved)

**Symptom:** `git diff main...branch` returns hundreds of files and 70K+ lines when the branch only has ~15 feature commits.

**Root cause:** In fork-based workflows, the local `main` tracks `origin/main` (the fork), not `upstream/main` (the source repo). When the feature branch was forked from `upstream/main`, `git merge-base main branch` returns a very old commit, and the three-dot diff includes all divergence between the fork's main and upstream.

**Fix (implemented):** The local branch mode now auto-detects the best base by checking `main`, `upstream/main`, and `origin/main`, and picking the one with the most recent merge-base with the branch. This handles fork workflows automatically without manual intervention. Users can still override with `--base <branch>` if needed.

### Codex output deduplication

**Behavior:** Codex consistently produces its review output twice in the PTY log, separated by a "tokens used" line. The PTY parser's "longest block" heuristic handles this automatically — no action needed. But be aware that raw output file sizes appear ~2x larger than the actual review content.

### Review iteration convergence

**Pattern observed across 11 review passes:** Each review cycle fixes 3-5 findings but may introduce 1-2 new ones. Findings that persist across reviews fall into two categories:
1. **Architecture limitations** (integration tests, stale snapshots) — these repeat every cycle and should be tracked as follow-ups rather than fixed in-loop.
2. **Genuine new findings** from code changes made to fix previous findings — these are real and should be fixed.

**Recommendation for adopt-pr-auto:** After 2-3 review iterations, categorize remaining findings as "fix now" vs "track as follow-up" rather than continuing to iterate. Convergence typically takes 2 iterations for code fixes and never resolves for architecture-level concerns.

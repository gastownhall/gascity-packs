---
description: Generate a GSL (Generalized Syntax Language) guideline file from a user request
allowed-tools: Read, Write, Bash, Glob, Grep, AskUserQuestion, WebFetch
---

# GSL Guideline File Generator

GSL = Generalized Syntax Language. A single-line, LLM-ingestible, densely-packed encoding of technical guidelines. It trades human readability for maximum information density while preserving enforceability — one physical line, structured sections, symbolic operators, and optional CJK ideographs for recurring concepts.

## Purpose

Given a user request for a new guideline topic, this skill:
1. Evaluates whether the request is suitable for GSL encoding.
2. Asks clarifying questions if scope, destination, or content is ambiguous.
3. Produces a single-line GSL file conforming to the format below.
4. Writes the file to a location the user chooses.
5. Reports the path, character count, and a one-line summary of what was produced.

This skill is environment-agnostic: it works on macOS, Linux, and Windows, and runs inside Claude Code, Claude Cowork, or any client that supports slash-command skills. It does not assume any specific directory layout, MCP server, or memory system.

## GSL Format Specification (STRICT)

### Physical form
- **Single line.** The entire guideline sits on ONE physical line. Exactly one trailing newline. No `\n`, `\r`, `<br>`, or wrapping anywhere inside the content.
- **UTF-8 encoding.** Emoji shortcodes (`:shield:`), CJK characters, and symbolic operators are expected.
- **No XML, no JSON, no markdown headings, no bullets, no code fences.** GSL is not a markup language; it is a packed spec.

### Line anatomy
```
<HEADER>|<SECTION1>.<SECTION2>.<SECTION3>....:white_check_mark:<label>:<required-checklist>.
```

- HEADER: language/context + version markers, pipe-separated. Examples: `PY3.14+|`, `BASH5+|`, `C#12|net8.0|nullable strict|`, `AUTO|`, `META/29rules/zero-tolerance|`.
- Sections are separated by a literal `.` immediately followed by the next section's `:emoji:label:` opener.
- Each section opens with `:emoji_shortcode:<label>:` where `<label>` is a short ASCII or CJK tag (`core`, `format`, `err`, `禁`, `必`, etc.).
- The final section is ALWAYS a required-checklist under `:white_check_mark:` — it lists non-negotiables that summarize the whole document.

### In-section operators
| Symbol | Meaning |
|---|---|
| `/` | Sibling rule separator within a section |
| `+` | AND / conjunction / "with" |
| `\|` | OR / alternative / variant separator |
| `(...)` | Example, detail, or sub-rule expansion |
| `→` | Transition, consequence, or flow |
| `=` | Definition or equivalence |
| `>` | Precedence (`A > B` = A overrides B) |
| `:no_entry_sign:` | Inline "prohibited" marker |
| `:heavy_check_mark:` | Inline "required/correct" marker, usually paired after a prohibition |

### Standard section emoji vocabulary
Use these consistently. Prefer an existing emoji over inventing a new one.

| Emoji | Typical label | Domain |
|---|---|---|
| `:shield:` | core / 核心 | Core principles, invariants |
| `:classical_building:` | class / 类 | OO structure, types, constructors |
| `:building_construction:` | arch | High-level architecture |
| `:triangular_ruler:` | format / 格 | Formatting, indentation, line limits |
| `:package:` | deps / 导 | Imports, dependencies, packaging |
| `:jigsaw:` | types / 型 | Type system, generics, protocols |
| `:zap:` | async / 异 | Concurrency, parallelism |
| `:warning:` | err / 错 | Error handling, exceptions |
| `:wood:` | log / 志 | Logging, tracing |
| `:open_file_folder:` | io / fs | Filesystem I/O |
| `:lock:` | sec / 安 | Security, secrets, input validation |
| `:test_tube:` | test / 测 | Testing, coverage |
| `:rocket:` | perf OR shakedown / 摇 | Performance; if both needed, use two `:rocket:` sections with distinct labels |
| `:books:` | docs / 文档 | Documentation |
| `:hammer_and_wrench:` | build | Build system, tooling |
| `:gear:` | tech / config | Generic technical or configuration |
| `:repeat:` | idempotent / 幂等 | Idempotency |
| `:syringe:` | self-heal / 自愈 | Self-healing automation |
| `:hourglass:` | retry / 重试 | Retry, backoff |
| `:hospital:` | health / 健康 | Health checks |
| `:ship:` | deploy / 部署 | Deployment strategies |
| `:rewind:` | rollback / 回滚 | Rollback |
| `:triangular_flag_on_post:` | flags | Feature flags |
| `:key:` | secrets | Secret rotation |
| `:alarm_clock:` | sched | Scheduled tasks |
| `:globe_with_meridians:` | net / 网络 | Networking, HTTP |
| `:earth_americas:` | xplat / 跨 | Cross-platform |
| `:ci:` | CI/CD | Pipelines |
| `:input_numbers:` | codes | Numeric/exit codes |
| `:art:` | output / 输 | Terminal output, colors |
| `:abc:` | vars / 变 | Variables, naming |
| `:wrench:` | funcs / 函 | Functions, subroutines |
| `:control_knobs:` | ctrl / 控 | Control flow, config hierarchy |
| `:link:` | source / 源 | Sourcing, module loading |
| `:page_facing_up:` | header / 头 | File headers |
| `:speech_balloon:` | comm | Communication conventions |
| `:mega:` | enforce / 执行 | Enforcement |
| `:memo:` | audit / 监 | Monitoring, audit |
| `:scroll:` | tpl / 模板 | Templates, boilerplate |
| `:bell:` | nullable / alert | Nullability, alerts |
| `:floppy_disk:` | persist / 存 | Database, persistence |
| `:airplane_departure:` | preflight | Preflight validation |
| `:file_folder:` | dirs | Directory layout |
| `:satellite:` | remote / 远 | Remote execution |
| `:cyclone:` | recover | Context recovery |
| `:high_brightness:` | parallel / 并行 | Parallel execution |
| `:counterclockwise_arrows_button:` | err-recover / 错恢 | Error recovery |
| `:robot:` | agents | Agent routing |
| `:scale:` | ambig | Ambiguity resolution |
| `:no_entry_sign:` | prohibited / 禁 | **Almost always include** — enumerated prohibitions |
| `:white_check_mark:` | required / 必 | **Always the final section** — required checklist |

### Lexical compression rules
Apply aggressively. The goal is maximum density without losing enforceability.

- **Drop English articles and copulas** ("the", "a", "is", "are") when unambiguous.
- **CJK ideographs for recurring concepts** are optional but encouraged when the document is long or repeats the same concept many times. Examples: core=核心, type=型, required=必, forbidden=禁, error=错, class=类, format=格, source=源, test=测, log=志, security=安, cross=跨, remote=远, idempotent=幂等, self-heal=自愈, variable=变, function=函, control=控, import=导, deploy=部署, shakedown=摇, health=健康, rollback=回滚, parallel=并行, verify=验. If the author prefers ASCII-only for the whole document, that is also valid — pick one mode and stay consistent.
- **Use operator symbols over words**: `>=` not "at least", `→` not "leads to", `+` not "and".
- **Remove whitespace** around `|`, `/`, `+`, `=`, `→`.
- **Parenthetical packing**: `rule(detail1/detail2/detail3)` — one label, parenthesized enumeration.
- **Rule IDs inline** when referenced elsewhere in the same file: `(cp-001)`, `SHAKEDOWN-001`.
- **No sentence case. No trailing punctuation** inside a section except the `.` that terminates the section.

### Common patterns to emulate
- `:no_entry_sign:X/Y/Z/...` — flat list of prohibitions.
- `:no_entry_sign:X(reason)/:heavy_check_mark:Y(correct)` — paired prohibition + correction.
- `pattern(subrule1/subrule2/...)` — compact expansion.
- `triggers(A/B/C)/non-triggers(X/Y/Z)` — trigger enumeration (common in shakedown/release sections).
- Trailing `:white_check_mark:required:item1/item2/item3/.` — the required checklist always closes the line.

## Suitability evaluation

**SUITABLE for GSL**:
- Programming language conventions (style, typing, error handling, async).
- Framework or library rules (React, Angular, FastAPI, EF Core, etc.).
- Infrastructure standards (Docker, Kubernetes, Terraform, Bicep, etc.).
- API design rules, security policies, deployment checklists.
- Prohibited-behavior lists, deterministic enforcement rules.
- Anything enumerable, stable, and phrased as rules or constraints.

**UNSUITABLE for GSL** — reject with a short explanation and suggest markdown or another format instead:
- Narrative tutorials or conceptual explainers.
- Rapidly-evolving content that changes weekly.
- Content requiring long code examples.
- Creative writing, user-facing documentation, onboarding docs.
- Anything a human must read directly.
- Content that cannot be expressed as enumerable rules.

If the request is borderline (e.g., "guidelines for writing blog posts"), ask the user whether they want rule-style enforcement (GSL) or prose guidance (markdown).

## Workflow

### Step 1 — Parse and evaluate the request
- Extract topic, scope, and target language/domain from the user's message (passed as the skill argument, if any).
- Classify as SUITABLE, UNSUITABLE, or BORDERLINE.
- If UNSUITABLE: state the reason in one sentence, suggest an alternative format, and stop.
- If BORDERLINE or missing details: use `AskUserQuestion` (single call, multiple questions at once) to clarify.

### Step 2 — Ask for destination and filename

Always confirm output location with the user. Do NOT assume any particular directory, convention, or runtime layout. Use `AskUserQuestion` to gather:

1. **Destination directory** (absolute or relative path). Offer a sensible default based on the user's current working directory (e.g., `./guidelines/` or `./GSL/`) but let the user override.
2. **Filename** (without extension). Suggest `<topic>_guidelines`, `<topic>_principles`, or just `<topic>`. Extension is always `.gsl`.
3. **Overwrite policy** if the target file already exists.
4. **Optional: ASCII-only mode** — ask whether CJK compression is acceptable or whether the user prefers ASCII-only section labels (useful for teams whose tooling or review process struggles with non-ASCII).

Resolve the path using forward slashes; on Windows the runtime accepts either separator. Do not hardcode `~/`, `%USERPROFILE%`, or `$HOME` anywhere — always use the path the user supplied.

### Step 3 — Gather content
- If the user supplied source material (a URL, a paste, a file path): fetch via `WebFetch` or read via `Read`.
- If the user pointed at a directory of existing GSL files as a style reference: `Glob` for `*.gsl`, then `Read` 1–2 of the closest-domain files. Copy only section-emoji choices and operator density — never copy content.
- Otherwise, build the content from the user's stated requirements plus established best practices for the domain.
- Ask clarifying questions as needed for scope, severity, target audience (humans vs LLMs), and any existing standards to align with.

### Step 4 — Construct the GSL line
- Start with the HEADER (language+version or context marker).
- Order sections logically: core principles first, specific domains in the middle, prohibitions near the end, required-checklist last.
- Apply every lexical compression rule.
- Keep each section focused — one concern per section.
- Validate mentally before writing: no `\n` mid-line, every section opens with `:emoji:label:`, every section ends with `.`, line terminates with exactly one `\n`.

### Step 5 — Write the file
- Ensure the destination directory exists. If it does not, ask the user whether to create it.
- Write via the `Write` tool to the full path the user chose, with extension `.gsl`.
- Do NOT create an XML or markdown counterpart unless the user explicitly asked for one.
- Do NOT modify any other file (no auto-registration in a CLAUDE.md, no MCP config changes, no memory writes). If the user wants the file registered elsewhere, that is a separate request.

### Step 6 — Validate

Perform these checks. Report any failure before declaring success.

Cross-platform validation approach: use the `Read` tool on the written file and verify:
- The file has exactly one line of content plus a trailing newline.
- The first character is NOT `:` (the header comes before any section).
- The content contains `:white_check_mark:` (required-checklist section present).
- The content contains at least one `:no_entry_sign:` (prohibitions present); if none are appropriate, confirm with the user before accepting.
- No literal `\n`, `<br>`, `<?xml`, markdown `#`, or triple-backtick fences appear.
- Character count is sensible: typical GSL files are 500–8000 characters. Flag if under 300 (likely too thin) or over 15000 (likely insufficiently compressed).

If a shell is available and the user has not restricted Bash, these quick checks work on macOS, Linux, and Windows (Git Bash / WSL / PowerShell via `wc`/`Measure-Object` equivalents):

- macOS / Linux / Git Bash: `awk 'END{print NR}' <file>` should print `1`.
- PowerShell: `(Get-Content <file>).Count` should print `1`.

Prefer the `Read`-based checks when uncertain about the shell — they are universal.

### Step 7 — Report

Print a short report:
- Absolute path of the written file.
- Character count.
- Approximate section count (count `.:` occurrences + 1).
- One-line list of the standard sections included.
- A plain-text note: "To have this loaded automatically as a guideline, reference it from whatever instruction file your client uses (for example a CLAUDE.md, a project rules file, or a system prompt). This skill did not modify any such file."

Do not offer to register, install, or link the file anywhere. That is a separate, user-initiated step.

## Execution

Parse `$ARGUMENTS` from the invocation. If the user invoked `/gsl <topic or paragraph>`, treat the argument as the initial request. If invoked with no argument, ask the user what topic they want encoded.

Begin the workflow now.

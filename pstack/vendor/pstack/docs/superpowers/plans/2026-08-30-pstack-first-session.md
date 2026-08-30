# pstack First session box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put host-contract caveats in a First session box on both READMEs and 01-setup. No `commands/`.

**Architecture:** Docs only. Tests lock the strings.

**Tech Stack:** Markdown, existing `python3 tests/test_verify_harness.py`.

## Global Constraints

- No `commands/` directory.
- Switcher and CJK rules unchanged.
- Do not document `grok plugin install pstack --trust` as the default.

### Task 1: First session copy + tests

**Files:** `README.md`, `README.zh-CN.md`, `docs/guide/01-setup.md`, `tests/test_verify_harness.py`

- [x] Failing test for First session strings
- [x] English + Chinese README section
- [x] 01-setup mirror
- [x] Tests pass

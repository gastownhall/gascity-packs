---
schema: gc.build.requirements.v1
workflow: {id: fi-vtt, formula: build-basic}
methodology: {pack: gascity, name: build-basic}
producer: {formula: build-basic, stage: requirements, attempt: 2}
status: approved
trace:
  upstream:
    - path: beads/fi-0j7
      hash: bead:fi-0j7
    - path: slugger.py
      hash: git:HEAD
    - path: tests/test_slugger.py
      hash: git:HEAD
  coverage:
    - id: REQ-001
      status: covered
    - id: REQ-002
      status: covered
    - id: REQ-003
      status: covered
---

# Requirements

## Problem Statement

`slugger.py` defines a `slugify(value: str) -> str` function that currently
raises `NotImplementedError`. The test suite in `tests/test_slugger.py`
already specifies the expected behavior. The function must be implemented so
that arbitrary input strings are converted into URL-safe slugs.

## W6H

- **Who**: Callers of `slugger.slugify`, exercised by `tests/test_slugger.py`.
- **What**: Implement `slugify` to convert a string into a lowercase,
  hyphen-separated URL slug.
- **When**: This factory run.
- **Where**: `slugger.py`.
- **Why**: The function is a stub (`raise NotImplementedError`) and blocks
  any caller or test that depends on it.
- **How**: Lowercase the input, replace runs of non-alphanumeric characters
  with a single hyphen, and strip leading/trailing hyphens.

## User Stories

- As a caller of `slugger.slugify`, I want a normalized slug returned for any
  input string so that I can use it safely in URLs.

## Technical Stories

- As a maintainer, I want `slugify` implemented with no external
  dependencies so that the module stays a lightweight, dependency-free
  fixture.

## Behavior Requirements

- REQ-001: `slugify` lowercases all alphabetic characters in the input.
- REQ-002: `slugify` collapses any run of one or more non-alphanumeric
  characters (spaces, punctuation, repeated separators) into a single
  hyphen, and strips leading/trailing hyphens from the result.
- REQ-003: `slugify` returns an empty string when the input contains no
  alphanumeric characters.

## Example Mapping

| Rule | Example Input | Expected Output |
| --- | --- | --- |
| REQ-001 + REQ-002 | `"Hello, World!"` | `"hello-world"` |
| REQ-002 | `"  Multiple---spaces___OK  "` | `"multiple-spaces-ok"` |
| REQ-003 | `"!!!"` | `""` |

## Coverage

| ID | Status |
| --- | --- |
| REQ-001 | covered |
| REQ-002 | covered |
| REQ-003 | covered |

## Acceptance Criteria

- Given `"Hello, World!"`, `slugify` returns `"hello-world"`.
- Given `"  Multiple---spaces___OK  "`, `slugify` returns
  `"multiple-spaces-ok"`.
- Given `"!!!"`, `slugify` returns `""`.
- All tests in `tests/test_slugger.py` pass.
- `slugify` no longer raises `NotImplementedError`.

## Out Of Scope

- Unicode transliteration (e.g., converting accented characters to ASCII
  equivalents).
- Length limiting or truncation of the resulting slug.
- Any change to the public signature of `slugify`.

## Open Questions

- None blocking. This is a headless, autonomous run; the existing test suite
  fully specifies the expected behavior, so no clarification is required to
  proceed.

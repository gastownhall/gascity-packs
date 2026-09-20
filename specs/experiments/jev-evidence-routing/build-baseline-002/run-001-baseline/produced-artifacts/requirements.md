---
schema: gc.build.requirements.v1
workflow:
  id: fi-vrx
  formula: build-basic
methodology:
  pack: gascity
  name: build-basic
producer:
  formula: build-basic
  stage: requirements
  attempt: 1
status: approved
trace:
  upstream:
    - path: beads/fi-69e
      hash: bead:fi-69e
    - path: slugger.py
      hash: sha256:9d7ea153a02d2847d334f0d7eb66f111ba6faaeff63018b99d1d9b0660576cf9
    - path: tests/test_slugger.py
      hash: sha256:148afb6a5de401b3930b293c5e5d5d093bf25f16c36f2886ed1bd01351ed164c
      ids:
        - REQ-001
        - REQ-002
        - REQ-003
  coverage:
    - id: REQ-001
      status: covered
    - id: REQ-002
      status: covered
    - id: REQ-003
      status: covered
---

## Problem Statement

`slugger.py` exposes a `slugify(value: str) -> str` function that is
intentionally unimplemented (it raises `NotImplementedError`). The project's
test suite (`tests/test_slugger.py`) already encodes the expected behavior.
The goal of this build is to implement `slugify` so it satisfies the existing
tests without changing the function's public signature or the test file.

## W6H

- **Who**: Callers within this fixture project that need a URL-safe slug from
  an arbitrary string (currently only exercised by the test suite).
- **What**: Implement `slugify(value: str) -> str` in `slugger.py`.
- **When**: This build-basic factory run, prior to review and publish.
- **Where**: `slugger.py` at the repository root.
- **Why**: The function currently raises `NotImplementedError`, so any code
  depending on it fails; the tests define the contract it must meet.
- **How**: Normalize the input to lowercase, replace runs of non-alphanumeric
  characters with a single hyphen, and strip leading/trailing hyphens.

## User Stories

- As a developer calling `slugify`, I want a lowercase, hyphen-separated slug
  from a human-readable string so I can use it in URLs or identifiers.
- As a maintainer, I want `slugify` to handle messy input (mixed separators,
  punctuation, no alphanumeric characters) predictably so downstream code
  doesn't need to special-case those inputs.

## Technical Stories

- Replace the `raise NotImplementedError(...)` body of `slugify` in
  `slugger.py` with an implementation, preserving the existing signature
  `slugify(value: str) -> str`.
- Do not modify `tests/test_slugger.py`; it is the acceptance contract.
- Keep the implementation dependency-free (standard library only), consistent
  with the current minimal `slugger.py` module.

## Behavior Requirements

- REQ-001: Given a phrase with punctuation and spaces (e.g. `"Hello, World!"`),
  `slugify` returns the lowercase words joined by single hyphens, with
  punctuation removed (e.g. `"hello-world"`).
- REQ-002: Given input with multiple consecutive separators of mixed kinds
  (spaces, hyphens, underscores) and leading/trailing whitespace (e.g.
  `"  Multiple---spaces___OK  "`), `slugify` collapses each run of separators
  into a single hyphen and trims leading/trailing hyphens, returning
  `"multiple-spaces-ok"`.
- REQ-003: Given input with no alphanumeric characters (e.g. `"!!!"`),
  `slugify` returns an empty string rather than raising or returning stray
  hyphens.

## Example Mapping

| Rule | Example Input | Example Output |
| --- | --- | --- |
| REQ-001 | `Hello, World!` | `hello-world` |
| REQ-002 | `  Multiple---spaces___OK  ` | `multiple-spaces-ok` |
| REQ-003 | `!!!` | `` (empty string) |

## Acceptance Criteria

Coverage of the behavior requirements above:

| ID | Status |
| --- | --- |
| REQ-001 | covered |
| REQ-002 | covered |
| REQ-003 | covered |

- `tests/test_slugger.py::test_slugify_basic_phrase` passes.
- `tests/test_slugger.py::test_slugify_collapses_separators` passes.
- `tests/test_slugger.py::test_slugify_handles_no_alphanumerics` passes.
- `slugify` no longer raises `NotImplementedError` under any input covered by
  the test suite.
- No changes are made to `tests/test_slugger.py` or the function signature of
  `slugify`.

## Out Of Scope

- Unicode transliteration (e.g. accented characters to ASCII) is not
  addressed; only the three existing test cases define the required behavior.
- Configurable separators, maximum length truncation, or collision handling
  for slugs are not required.
- Changes to `pyproject.toml`, packaging, or CI configuration are not part of
  this build.

## Open Questions

- Should `slugify` support non-ASCII/Unicode input beyond what the current
  tests exercise? No test covers this, so the implementation should default
  to stripping non-ASCII-alphanumeric characters unless a stakeholder
  clarifies otherwise. Recorded here rather than blocking, per headless
  interaction mode.

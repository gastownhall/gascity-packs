---
schema: gc.build.plan.v1
workflow: {id: fi-vtt, formula: build-basic}
methodology: {pack: gascity, name: build-basic}
producer: {formula: build-basic, stage: plan, attempt: 1}
status: approved
trace:
  upstream:
    - path: /private/tmp/gcja-4r1pdmmv/w/fixture/.gc/inference-gate/build-basic/requirements.md
      hash: sha256:0000000000000000000000000000000000000000000000000000000000000
      ids: [REQ-001, REQ-002, REQ-003]
  coverage:
    - id: REQ-001
      status: covered
    - id: REQ-002
      status: covered
    - id: REQ-003
      status: covered
---

# Implementation Plan

## Summary

Implement `slugify(value: str) -> str` in `slugger.py` so it converts an
arbitrary input string into a lowercase, hyphen-separated, URL-safe slug,
satisfying `tests/test_slugger.py` and the approved requirements.

## Current System

`slugger.py` defines the `slugify` function signature but its body
unconditionally raises `NotImplementedError`. `tests/test_slugger.py`
already contains the executable specification for the expected behavior;
no other module depends on `slugify` and it has no external dependencies.

## Proposed Implementation

- In `slugger.py`, replace the `NotImplementedError` body with logic that:
  1. Lowercases the input string (REQ-001).
  2. Uses a regular expression (`re.sub`) to replace every run of one or
     more characters that are not ASCII letters or digits with a single
     hyphen (REQ-002).
  3. Strips any leading/trailing hyphens from the result via `str.strip("-")`
     (REQ-002).
  4. Returns the resulting string as-is, including the empty string when no
     alphanumeric characters were present (REQ-003).
- Add `import re` at the top of `slugger.py`.
- No changes to the public signature `slugify(value: str) -> str` and no new
  external dependencies, per the requirements' Out Of Scope section.

## Non-Goals

- Unicode transliteration of accented or non-ASCII characters.
- Length limiting or truncation of the resulting slug.
- Any change to the public signature of `slugify`.

## Verification

- Run `python -m pytest tests/test_slugger.py` and confirm all tests pass.
- Manually confirm the Example Mapping cases from the requirements:
  - `"Hello, World!"` -> `"hello-world"`
  - `"  Multiple---spaces___OK  "` -> `"multiple-spaces-ok"`
  - `"!!!"` -> `""`

## Coverage

| ID | Status |
| --- | --- |
| REQ-001 | covered |
| REQ-002 | covered |
| REQ-003 | covered |

# Evidence and verification

## Establish the evidence base

Use this hierarchy, stopping when the claim is established:

1. Current implementation, public types, and tests.
2. Current CLI help, command implementation, and configuration schema.
3. Existing published documentation and examples.
4. Release notes, changelog, and the latest released artifact.
5. Accepted design documents only as intent, never as shipped behavior.
6. Issues, support reports, or conversations only to understand the reader problem.

For docs-only changes, compare the branch with the latest public release before describing availability. For docs shipped alongside code, state that the documentation depends on the accompanying change.

## Keep a claim ledger while working

For each material claim, record the claim, its evidence, and release scope. Material claims include commands, flags, parameters, defaults, permissions, limits, compatibility, error behavior, and prerequisites. Remove claims that do not have support.

Verify examples by running them when practical. Verify a CLI command from `--help` and the command implementation. Verify an API example from exported types and tests. Never repair an example by guessing an argument or output.

## Run repository-native documentation checks

Inspect the repository before selecting checks:

- Read contributor documentation and docs-specific instructions.
- Inspect package scripts, build configuration, and CI workflows.
- Search for documentation build, link, lint, spelling, formatting, snippet, or example-validation commands.

Run the relevant commands for changed documentation. If no dedicated documentation check exists, run the closest available repository validation and say that no docs-specific check was available. Do not add a toolchain merely to complete a documentation edit.

## Final verification record

In the handoff, state:

- Claims verified and their evidence class.
- Commands or examples exercised.
- Documentation checks run and their results.
- Any unavailable evidence, unrun check, or release-scope limitation.

## Primary references

- [Eve technical-writing workflow](https://github.com/vercel/eve/blob/main/.agents/skills/technical-writing/SKILL.md)
- [Write the Docs: docs as code](https://www.writethedocs.org/guide/docs-as-code/)
- [Write the Docs: testing documentation](https://www.writethedocs.org/guide/tools/testing/)

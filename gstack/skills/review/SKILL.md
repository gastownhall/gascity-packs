---
name: review
description: Review a code change before landing, with concrete evidence, severity, and a clear approve-or-iterate verdict. Use for pull requests, exact diffs, self-review, pre-landing review, and the one independent Gstack Lite review pass.
---

# Review

Perform one evidence-driven review of the requested change. Find defects that
would matter after landing, verify each finding against the code, and finish
with an unambiguous verdict. The skill is self-contained: it requires no
provider-specific runtime, external review bot, helper binary, or agent fanout.

## Review boundary

Review the working tree, branch, commit range, or PR
the user named. Review is read-only by default. Do not edit code, commit, push,
post replies, resolve threads, or change PR state unless the user explicitly
requests those actions.

## Establish the review boundary

Before judging the change:

1. Identify the repository, current head, intended base, and merge base. Include
   tracked and untracked working-tree changes when the working tree is the
   target.
2. Read the available intent: requirements, plan, bead, issue, PR description,
   acceptance criteria, commit messages, and relevant documentation.
3. Inspect the exact diff and changed-file list. Read enough unchanged code to
   verify callers, sibling consumers, schemas, enums, persistence, and cleanup
   paths.
4. Note anything that prevents an exact review, such as a missing base,
   inaccessible generated artifact, or incomplete requirements. Continue with
   the reviewable surface and report the limitation explicitly.

GitHub metadata may help establish intent and check status, but it is optional.
The code and repository-native evidence are sufficient to run this skill.

## Load the bundled review guidance

Read `checklist.md` completely for every review. It is the canonical general
checklist and severity guide.

Then load only the adjacent specialist references that match the change:

- Always read `specialists/testing.md` and
  `specialists/maintainability.md`.
- Read `specialists/security.md` for authentication, authorization, secrets,
  parsing, shell/SQL/path/URL handling, deserialization, or other trust
  boundaries.
- Read `specialists/performance.md` for database access, loops over remote
  work, hot paths, rendering, bundles, pagination, or async code.
- Read `specialists/data-migration.md` for schema changes, backfills, data
  conversions, indexes, or migration sequencing.
- Read `specialists/api-contract.md` for public APIs, events, schemas,
  persistence formats, CLI contracts, or compatibility-sensitive changes.
- Read `design-checklist.md` for user-interface or visual changes.
- Read `specialists/red-team.md` for high-risk authentication, security,
  destructive operations, money movement, external side effects, or recovery
  logic.
- Read `greptile-triage.md` only when the task includes existing Greptile
  comments that need classification. Greptile is optional input, never a
  prerequisite for review or delivery.

These files are methodology, not separate review agents. Apply their relevant
checks within this one pass. Historical instructions inside the pinned
references to dispatch parallel subagents or specialist agents are overridden
by this adapter and must not be followed.

## Review the change

Review semantic intent before style. Trace values and state across boundaries,
not just within each changed hunk. At minimum, verify:

1. correctness, control flow, error handling, cleanup, and data integrity;
2. concurrency, transactions, retries, idempotency, timeouts, and partial
   failure behavior;
3. validation and trust boundaries for every externally controlled value;
4. completeness across enum members, statuses, modes, tiers, types, and sibling
   consumers;
5. API, schema, storage, CLI, and backward-compatibility contracts;
6. acceptance criteria and promised behavior, including negative and boundary
   cases;
7. test quality: whether tests can fail for the intended defect and cover the
   changed behavior rather than only the happy path;
8. scope integrity: missing required work, unrelated work, accidental generated
   output, or unsafe migration/deployment ordering; and
9. concrete maintainability or performance risks with production impact.

Use repository-native tests and static checks when they materially verify a
finding or verdict and are safe to run. Record the exact commands and results.
Do not manufacture a clean result when a check was not run or could not finish.

## Verify every finding

Report a finding only when all of the following are present:

- an exact file, line, symbol, artifact, or contract reference;
- the motivating code or reproducible evidence;
- a concrete failure mode and user, security, data, or operational impact;
- the smallest required correction; and
- calibrated confidence.

Check surrounding code and existing tests before reporting it. Suppress
speculation, generic hardening advice, pure preference, pre-existing defects
unrelated to the change, and claims contradicted by repository evidence.

Use these priorities:

- **P0** — active catastrophe: severe security exposure, irreversible data loss,
  or a change that must not ship under any condition.
- **P1** — likely production breakage, security bypass, corruption, or failure
  of a core requirement; blocks landing.
- **P2** — real correctness, compatibility, reliability, or material test gap;
  normally blocks landing.
- **P3** — bounded non-critical defect or follow-up with concrete value; state
  whether it blocks under the repository's policy.

## Produce the result

Lead with findings in descending priority. For each finding include priority,
confidence, location, evidence, impact, and smallest fix. Then include:

1. **Coverage** — the exact diff or head reviewed, intent sources, specialist
   references used, and checks run.
2. **Open limitations** — any surface that could not be verified.
3. **Verdict** — exactly one of:
   - `approve`: no required finding remains;
   - `iterate`: one or more required findings must be fixed; or
   - `blocked`: the review boundary or evidence is too incomplete for a safe
     verdict.

An approval must say why the inspected change is safe enough to land; “looks
good” is not evidence. Bind the verdict to the exact immutable candidate head.

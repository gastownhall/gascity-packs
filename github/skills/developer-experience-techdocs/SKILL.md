---
name: developer-experience-techdocs
description: Create, edit, review, or audit developer-facing technical documentation. Use when documentation must explain APIs, CLIs, SDKs, integrations, configuration, troubleshooting, or developer workflows with verified claims and repository-native docs-as-code checks.
---

# Developer-experience technical documentation

Write documentation that lets a developer complete a real task with confidence. Treat both developers and agents as readers: make the outcome, evidence, prerequisites, and next action easy to find without unstated context.

## Choose the workflow

- For a new page or substantial rewrite, read [page workflows](references/page-workflows.md).
- For a focused edit, read the targeted-edit workflow in [page workflows](references/page-workflows.md).
- For a review or audit, read the review workflow there.
- When an audit finding may require a tracker issue, read [finding triage](references/finding-triage.md).
- Before finalizing any documentation change, read [evidence and verification](references/evidence-and-verification.md).
- For terminology, voice, structure, accessibility, or prose quality, read [editorial standard](references/editorial-standard.md).

## Non-negotiable rules

- Verify technical claims before writing them. Do not rely on training data for repository behavior.
- Treat an issue, support thread, design, or request as evidence of a reader problem, not evidence that a behavior shipped.
- Use exact public names for APIs, commands, flags, defaults, limits, and diagnostic surfaces.
- If a claim cannot be verified, omit it or report the missing evidence or owner. Do not leave verification markers in completed docs.
- Write for one primary reader task. Lead with the outcome and the supported happy path, then cover alternatives and failure modes that affect that task.
- Preserve existing routes, anchors, terminology, and strong prose unless changing them solves a verified reader problem.
- State unsupported boundaries directly. Do not present proposed, branch-only, or inferred behavior as released.
- Classify every issue created from a documentation finding with exactly one controlled-vocabulary tag. Do not add severity labels.

## Finish every change

1. Re-read every changed page in full.
2. Verify each new claim, command, example, default, and limitation against evidence.
3. Search for affected links, terminology, and contradictory instructions.
4. Discover and run the host repository's actual documentation checks.
5. Report which checks passed and which verification could not be performed.

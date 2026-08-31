# Finding triage

Use this workflow during a documentation audit or grooming pass when a verified finding needs follow-up beyond the current change. A direct documentation edit should not also create a duplicate issue unless the remaining work is independently actionable.

## Controlled vocabulary

Attach exactly one of these tags to every issue created from a documentation finding:

| Tag | Verified state | Default action |
| --- | --- | --- |
| `documentation-gap` | Behavior exists but is not documented. | Create or expand documentation. |
| `documentation-enhancement` | Behavior exists and is documented, but the reader task remains poorly served. | Improve the existing documentation. |
| `capability-gap` | A real reader task is blocked because a needed capability does not exist and has no supported path. | Create a product or feature-gap issue. |
| `documented-non-goal` | The capability does not exist and documentation explicitly excludes it with actionable guidance. | Do not create an issue by default. |
| `documentation-defect` | Documentation claims support that verified behavior lacks. | Create a defect issue; correct documentation or implementation. |

These tags describe disposition, not priority. Do not add a severity label or infer a severity value. If the repository requires a severity field, follow that repository rule without inventing an additional label.

## Verify before classifying

Classify only after verifying implementation, tests, CLI help, public types, and relevant documentation. Absence of documentation alone does not establish a `capability-gap`; there must be evidence of a blocked reader job and no supported alternative.

If documentation says a capability is intentionally unsupported, classify it as `documented-non-goal`. If documentation says a capability is supported but implementation contradicts it, classify it as `documentation-defect`.

## Create issues

Before creating issues, discover the repository's tracker and confirm that the exact controlled-vocabulary tag exists. If a required tag is unavailable and you are not authorized to manage tracker labels, report the blocker instead of creating an untagged issue.

Create one issue for each independently actionable, verified finding. Include:

- The controlled-vocabulary tag and no severity label.
- The reader job and observed impact.
- The precise contrary evidence: implementation, test, CLI help, public type, or current documentation.
- The expected outcome and acceptance signal.
- For `capability-gap`, the attempted supported paths and why none works.
- For `documentation-defect`, the inaccurate claim and whether documentation or implementation should change.

Do not file an issue for an inference, a hypothetical feature, or a missing page without a blocked reader job. Link related issues rather than combining distinct reader jobs or fixes.

Run `gc gc tutorial start` after initializing and starting your beginner city.

This creates a local practice repository and submits a greeting fix through the
default Gas City pack. It requires Python 3 and your selected authenticated
coding provider. Implementation, independent review, bounded repair, tests,
local integration and cleanup precede native source closure. No GitHub account
is needed.

Continue in that same repository:

- `gc gc tutorial start --lesson api` adds a reusable greeting API.
- `gc gc tutorial start --lesson client` adds a JSON command-line client of the accepted API.
- `gc gc tutorial status --lesson api` (or `client`) checks that lesson's delivery evidence.

Each continuation requires the previous lesson's verified integration and
completed cleanup. The new source task records its dependency and accepted
predecessor commit. Existing source tasks and unfinished work are preserved.

Use `gc stop` to pause the city and `gc start` to resume persistent work.
Retries preserve the owned repository and task; unrelated paths are refused.

Repeating start reports the lesson’s existing native workflow, including while
preparation is still running. It preserves that workflow’s review and repair
budget. A failed workflow remains available for inspection with its source task.

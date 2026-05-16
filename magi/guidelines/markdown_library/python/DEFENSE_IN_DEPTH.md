# Defense in Depth

Multiple, independent layers protect Python code from a single failure. Every step has a fallback, every assumption is independently verified, every action is reversible.

### Independent Layers of Defense
1. **Static typing** — `mypy --strict` MUST run before commit and in CI.
2. **Linting and formatting** — `ruff` MUST run on every save and in CI.
3. **Runtime validation** — Pydantic models MUST validate every external boundary.
4. **Automated tests** — `pytest` MUST cover happy paths, error paths, and edge cases.
5. **CI gate** — PR checks for typing, linting, and testing.
6. **Runtime observability** — structured logging and metrics.

### The Rule of Three — Majority Wins
- **One is a claim** — one green local test run.
- **Two is a tie** — mypy passes but tests fail (or vice versa).
- **Three is a quorum** — static typing + tests + production observability. When all three agree, the change is releasable.

Example: a refactor that passes mypy and ruff but fails one pytest case is overrides the other two.

---
[Back to Overview](./OVERVIEW.md)

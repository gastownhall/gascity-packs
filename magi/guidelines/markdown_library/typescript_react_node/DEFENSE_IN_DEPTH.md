# Defense in Depth

Multiple, independent layers protect TypeScript / React / Node code from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Strict tsc** — `strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `exactOptionalPropertyTypes` MUST all be enabled in `tsconfig.json`. The type system is the first wall.
2. **ESLint and Prettier** — ESLint with `@typescript-eslint/strict` + Prettier MUST pass on every commit. Lint catches what tsc does not express.
3. **Runtime validation** — Zod (or io-ts / valibot) MUST validate every fetch response, form submission, env var, queue message. **tsc trusts the caller; runtime validation does not.**
4. **Unit and component tests** — Vitest/Jest unit tests + React Testing Library component tests MUST cover business logic and rendered states.
5. **E2E browser tests** — Playwright (or Cypress) E2E tests MUST exercise the critical user flows in a real browser.
6. **CI and preview deploys** — CI MUST run typecheck + lint + unit + E2E + a preview deploy that smoke-checks the live URL before merge.
7. **Shakedown** — A §11 shakedown MUST pass after every triggering change before promotion.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — `tsc` clean is one signal; it proves shapes line up at compile time, **NOT** that runtime data matches those shapes.
- **Two is a tie** — Tests passing in jsdom but a Playwright run failing in a real browser is two-versus-one against the green light; **the browser run wins** because it sees the actual platform.
- **Three is a quorum** — `tsc` + runtime schema validation (zod) + browser-driven E2E form the canonical triple. **Majority MUST agree the feature works before declaring done.**

**Example:** A response typed as `{ id: number }` but actually returning `{ id: '7' }` passes `tsc` and component tests; only the zod boundary plus the E2E run catch it — the third signal.

---
[Back to Overview](./OVERVIEW.md)

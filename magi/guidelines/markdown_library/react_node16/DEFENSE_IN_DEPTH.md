# Defense in Depth

Multiple, independent layers protect React on Node 16 code from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

Every change in this domain MUST pass through the following independent failure-prevention layers. They are independent on purpose: a bug or outage in one MUST NOT mask the failure for another.

1. **Strict tsc** — `strict` and `noUncheckedIndexedAccess` MUST be on. The type system is layer one.
2. **ESLint** — ESLint with `react-hooks/exhaustive-deps` and `react/jsx-no-leaked-render` MUST pass. Lint catches bugs the type system does not encode.
3. **React Testing Library** — Component tests MUST exercise user-visible behavior, not implementation details.
4. **Runtime schema validation** — All API responses MUST be validated at the boundary (zod or equivalent). **No `as Foo` casts on untrusted JSON.**
5. **E2E browser tests** — Playwright or Cypress MUST exercise the primary flows.
6. **CI with coverage floor** — CI MUST enforce coverage thresholds and block merges below the floor.
7. **Shakedown** — A §13 shakedown MUST follow every change to the SSR entry, client hydration entry, QueryClient configuration, build config, or pinned-dependency upgrade.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — A passing component test is one signal; it does NOT prove the integrated app renders correctly with real data.
- **Two is a tie** — If component tests pass but Playwright fails on the same flow, treat the disagreement as a freeze, **not** a flaky-test waiver.
- **Three is a quorum** — Type checker + component tests + browser E2E form the triple. **All three MUST agree before declaring a feature done.**

**Example:** An optional prop typed correctly and tested in isolation still crashes when the parent passes `undefined`; the parent-mounted Playwright run is the third witness.

---
[Back to Overview](./OVERVIEW.md)

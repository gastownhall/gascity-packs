# Defense in Depth

Multiple, independent layers protect any frontend / SPA code from a single failure. This is failure-mode defense in depth (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Independent Layers of Defense

1. **Type checker** — Strict TypeScript MUST pass.
2. **Linter** — ESLint + Stylelint with strict configs MUST pass.
3. **Unit and component tests** — MUST cover business logic and rendered component states.
4. **Runtime schema validation** — All API responses MUST be validated at the boundary (Zod or equivalent).
5. **E2E browser tests** — Playwright or Cypress MUST drive the real browser end-to-end.
6. **Accessibility audit** — `axe-core` (automated) + a manual keyboard pass MUST run before declaring a UI feature done.
7. **Preview deploy smoke** — A deployed preview URL MUST be smoke-tested before merge; only the preview catches build/runtime drift.

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority.

- **One is a claim** — A green local dev server is one signal; production build, deployed bundle, and real-browser rendering still fail independently.
- **Two is a tie** — Type checker green + unit tests green + Playwright failing means the rendered app is broken; the browser is the deciding voter — never override it with the other two.
- **Three is a quorum** — Type checker + tests + real-browser E2E on a deployed preview form the canonical triple. All three MUST agree before declaring a UI feature done.

Example: a component that renders fine in jsdom but white-screens in Chrome (e.g., `import.meta` misuse) — only the browser surfaces the failure.

---
[Back to Overview](./OVERVIEW.md)

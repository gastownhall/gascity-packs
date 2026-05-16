# Defense in Depth

Multiple, independent layers protect Vue/Nuxt code from a single failure. This is **failure-mode defense in depth** (not security defense in depth): every step has a fallback, every assumption is independently verified, every action is reversible. If any one layer breaks, silently degrades, or returns the wrong answer, at least two other layers MUST still catch the failure before it reaches production.

**Intent:** No single check, person, tool, or system is trusted to be the only safeguard.

### Six Independent Layers of Defense

| Layer | Validation |
|:-----:|:-----------|
| 1 | **Strict TypeScript** — `vue-tsc` with `strict` + Volar MUST pass; `<script setup>` with TypeScript on every component |
| 2 | **ESLint + Stylelint** — `eslint-plugin-vue` and Stylelint MUST pass on every commit |
| 3 | **Vitest unit/component** — `@vue/test-utils` + Vitest MUST cover rendered states |
| 4 | **Runtime validation** — zod or valibot MUST validate every API response and form submission at the boundary |
| 5 | **Playwright E2E** — Nuxt's e2e harness or Playwright MUST exercise primary flows on the dev server |
| 6 | **Nuxt build validation** — `nuxt build` + `nuxt preview` MUST succeed in CI on a clean image; **SSR/CSR drift only surfaces on the preview server** |

### The Rule of Three — Majority Wins

One signal is unverifiable. Two signals disagree with no tiebreaker. Three independent signals always produce a majority. Apply this rule whenever a decision in this domain depends on a check, a copy, a vote, or an actor that fails, drifts, or disagrees.

- **One is a claim** — `vue-tsc` passing is one signal; it does **not** prove SSR matches CSR.
- **Two is a tie** — Unit tests passing in jsdom but Playwright failing on the SSR-rendered page is the SSR/CSR mismatch dissent; **the browser is the deciding voter**.
- **Three is a quorum** — Type checking + component tests + browser-driven E2E on a Nuxt preview are the canonical triple.

**Example:** Hydration mismatches surface only when SSR HTML and CSR DOM disagree; the only signal that catches them is the rendered browser run.

---
[Back to Overview](./OVERVIEW.md)

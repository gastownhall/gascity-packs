# Defense in Depth

Multiple, independent layers protect Angular code from a single failure. Every step has a fallback, every assumption is verified, every action is reversible.

### Independent Layers of Defense

1. **Strict mode**: `tsconfig` `strict` + `strictTemplates` + `strictInjectionParameters`. Template checking is layer one.
2. **Linting**: `@angular-eslint` and Stylelint MUST pass with zero warnings.
3. **Unit tests**: Karma/Jest with `TestBed` covering components, services, pipes, and guards.
4. **Schema validation at boundaries**: All HTTP responses validated with `zod` before typing.
5. **E2E tests**: Cypress/Playwright exercising primary user flows against built artifact.
6. **Production AOT build**: `ng build --configuration production` MUST pass in CI (catches JIT-masked errors).
7. **Shakedown**: Bundle integrity and runtime smoke against real backend (§18).

### The Rule of Three — Majority Wins

- **One is a claim**: `ng serve` running locally.
- **Two is a tie**: Units pass but AOT build fails. AOT is the deciding voter.
- **Three is a quorum**: Strict TS + unit tests + production AOT build + E2E. Majority MUST agree before merge.

**Intent: No single check, person, tool, or system is trusted to be the only safeguard.**

---
[Back to Overview](./OVERVIEW.md)

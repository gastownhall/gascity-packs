# Prohibited Practices (Absolute Blacklist)

### Never Do

- Use `ChangeDetectionStrategy.Default` (OnPush is mandatory).
- Subscribe without an unsubscription strategy (leaks).
- Import `HttpClient` directly in components (use services).
- Use `any` type anywhere (codebase or templates).
- Disable strict template checking.
- Use `ngOnChanges` in new components (use signals).
- Create new NgModules for application code.
- Use legacy structural directives (`*ngIf`, `*ngFor`).
- Bypass sanitization without documentation.
- Store auth tokens in `localStorage`.
- Use `setTimeout` for Angular-relevant timing (use RxJS/signals).
- Chain more than three nested subscribes.
- Create circular dependencies between features.
- Commit `// TODO` or disabled tests.
- Use `index` for tracking in mutable collections.
- Mutate input values.
- Embed business logic in components.
- Create components exceeding 150 lines.
- Use `ViewEncapsulation.None` without justification.
- Expose writable signals from services publicly.
- Skip schema validation on HTTP responses.
- Run shakedown against mocked backends.

### Always Do

- Enable `strictTemplates` and strict injection parameters.
- Use OnPush on every component.
- Use signal-based `input()`, `output()`, and `model()`.
- Use built-in control flow (@if, @for, etc.).
- Use `inject()` for dependency acquisition.
- Use `takeUntilDestroyed()` for component subscriptions.
- Lazy load every feature route.
- Enforce bundle budgets in CI.
- Use `NonNullableFormBuilder` with typed forms.
- Handle loading/error/empty states in templates.
- Run `ng lint` with zero warnings in CI.
- Validate HTTP responses with `zod` at the service boundary.
- Run shakedown after every trigger condition (§18).

---
[Back to Overview](./OVERVIEW.md)

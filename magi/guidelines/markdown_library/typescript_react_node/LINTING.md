# Linting and Formatting

### ESLint with `typescript-eslint`

Use ESLint with `typescript-eslint` for TypeScript-aware linting. Enable the **`strict-type-checked`** and **`stylistic-type-checked`** configuration presets. These catch:

- Unsafe `any` usage.
- Floating promises (promises without `await` or `.catch`).
- Unnecessary type assertions.
- Inconsistent type imports.

Use the flat config format (`eslint.config.ts`) for ESLint 9+.

### Prettier (or Biome)

Use Prettier for code formatting:

- Configure once.
- Run on save and in CI.
- **Do not debate formatting in code review** — Prettier's output is the format.
- Integrate with ESLint via `eslint-config-prettier`.

Alternatively, use **Biome** as a combined linter + formatter for faster execution.

### React Compiler ESLint Plugin

Enable `eslint-plugin-react-compiler` to catch patterns incompatible with automatic memoization:

- Mutating values during render.
- Using refs incorrectly.
- Other patterns that prevent the Compiler from optimizing.

Fixing these warnings makes the codebase Compiler-ready.

### Pre-commit and CI

| Tool | Where |
|:-----|:------|
| `lint-staged` + Husky/lefthook | Pre-commit — ESLint + Prettier on staged files only (fast feedback) |
| `tsc --noEmit` | CI — full project type check (requires complete project) |

Pre-commit hooks catch formatting and lint errors. **CI catches type errors that span multiple files.**

---
[Back to Overview](./OVERVIEW.md)

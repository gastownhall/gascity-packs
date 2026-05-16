# React Component Patterns

React component design determines reusability, testability, and rendering performance. TypeScript integration enforces prop contracts and enables IDE-driven development with auto-complete and inline documentation.

### Typing Props

Type component props with an `interface`. Define the interface above the component or in a co-located types file. **Do not use `React.FC` or `React.FunctionComponent`** — they add implicit `children` (pre-React 18), obscure the return type, and provide no benefit over a plain typed function. Export the props interface when consumers need to extend or reference it.

```typescript
export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick: (event: React.MouseEvent<HTMLButtonElement>) => void;
  children: React.ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  onClick,
  children,
}: ButtonProps): JSX.Element {
  return (
    <button
      type="button"
      className={`btn btn-${variant} btn-${size}`}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
```

### Children

Declare `children` explicitly when a component accepts them: `interface Props { children: React.ReactNode }`. `ReactNode` is the correct type for renderable content (elements, strings, numbers, fragments, `null`).

| Type | Use |
|:-----|:----|
| `React.ReactNode` | **Correct** — anything React can render |
| `JSX.Element` | Too narrow; excludes strings, numbers, `null` |
| `React.ReactElement` | Excludes strings and `null` |
| `React.ReactChild` | **Deprecated** |

### Default Values

Use destructuring with default values **in the function signature** for optional props. Defaults are visible at the component definition site, not buried in the component body. **Do not use `defaultProps`** — deprecated for function components and does not integrate with TypeScript's type inference.

### Single Responsibility

Keep components focused on a single responsibility. A component that fetches data, transforms it, manages form state, handles validation, and renders a complex UI is doing five things:

- Extract data fetching into a custom hook.
- Extract form logic into a form hook or component.
- Extract complex rendering into sub-components.

A component that exceeds **200 lines of JSX + logic** is a decomposition candidate.

### Feature Co-Location

Organize components by feature, not by type:

```text
components/auth/LoginForm.tsx      # not components/forms/LoginForm.tsx
components/product/ProductCard.tsx # not components/cards/ProductCard.tsx
```

Feature co-location keeps related code together: the component, its styles, its tests, its types, and its hooks live in the same directory.

### Code Splitting with Lazy + Suspense

Use `React.lazy()` and `Suspense` for code-splitting non-critical components: modals, below-the-fold content, admin panels, feature-flagged UI. Lazy loading reduces the initial bundle size and improves Time to Interactive. **Provide a meaningful fallback** in the Suspense boundary — a skeleton, spinner, or layout placeholder that matches the expected component dimensions to prevent CLS.

### Event Handler Typing

Type event handlers with React's event types:

| Type | Event |
|:-----|:------|
| `React.MouseEvent<HTMLButtonElement>` | Click on button |
| `React.ChangeEvent<HTMLInputElement>` | Input value change |
| `React.FormEvent<HTMLFormElement>` | Form submission |
| `React.KeyboardEvent` | Keyboard interaction |

Do not use `any` for event parameters. The generic parameter specifies the element type, enabling access to element-specific properties (`event.target.value` on `ChangeEvent<HTMLInputElement>`) with type safety.

### Extending Native HTML Element Props

Use `React.ComponentPropsWithoutRef<'button'>` (or `ComponentPropsWithRef` for forwarded refs) to extend native HTML element props in wrapper components. This provides all standard HTML attributes (`onClick`, `className`, `aria-*`, `data-*`) without manually redeclaring them:

```typescript
interface ButtonProps extends React.ComponentPropsWithoutRef<'button'> {
  variant: 'primary' | 'secondary';
}
```

---
[Back to Overview](./OVERVIEW.md)

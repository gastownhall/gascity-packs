# Accessibility

Accessibility (a11y) ensures applications are usable by people with disabilities. TypeScript enforces ARIA attribute types. React provides the JSX structure. Discipline fills the gaps.

### Semantic HTML

Use semantic HTML elements:

| Element | Use |
|:--------|:----|
| `<button>` | Clickable actions (not `<div>` with `onClick`) |
| `<a>` | Navigation links |
| `<nav>` | Navigation regions |
| `<main>` | Primary content |
| `<header>`, `<footer>` | Landmarks |
| `<ul>`, `<ol>` | Lists |
| `<table>` | Tabular data |

Semantic elements provide built-in keyboard handling, screen reader announcements, and focus management that `<div>`-based implementations must reimplement manually and usually get wrong.

### Keyboard Accessibility

Every interactive element is keyboard-accessible. Buttons and links are keyboard-accessible by default. Custom interactive widgets (dropdowns, modals, tabs, accordions) must implement keyboard patterns from the **WAI-ARIA Authoring Practices Guide**. Prefer headless UI libraries — **Radix UI**, **React Aria**, **Headless UI** — that implement these patterns correctly over building custom keyboard handling.

### Images and Labels

- All images have `alt` text.
- Decorative images use `alt=""`.
- Meaningful images describe the content.
- Icon buttons use `aria-label`.
- Form inputs have associated labels (`htmlFor` on `<label>` matching `id` on input, or wrap input in `<label>`).

`eslint-plugin-jsx-a11y` catches common violations — install and enable it.

### Focus Management

Manage focus intentionally in SPAs:

- When navigation occurs, move focus to the main content area or a heading.
- When a modal opens, trap focus inside the modal.
- When a modal closes, return focus to the trigger element.
- When content loads asynchronously, announce it to screen readers via `aria-live` regions.

Focus management is invisible to sighted mouse users and critical for keyboard and screen reader users.

---
[Back to Overview](./OVERVIEW.md)

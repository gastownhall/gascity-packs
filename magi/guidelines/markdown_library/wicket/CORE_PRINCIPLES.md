# Core Principles

### Component-Oriented Architecture

Web pages are object hierarchies, not templates with embedded code. Every visual element is a reusable Java component with explicit lifecycle, state, and behavior. Components bind to HTML elements via `wicket:id`. Complex pages compose from simple, tested components. **Think Swing for the web, not MVC request handlers.**

### Server-Side State Management

Wicket manages page state on the server. Components are stateful objects that survive across requests within a session. Pages serialize to a page store for back-button support and session replication. This eliminates manual `HttpSession` manipulation but demands proper serialization discipline. **Non-serializable fields break clustering and back-button navigation.**

### Strict HTML/Java Separation

HTML templates contain **zero logic** — no conditionals, no loops, no expressions. Templates define structure and `wicket:id` bindings; Java code defines all behavior. Designers edit HTML; developers edit Java. **The boundary is absolute.** Templates must be valid HTML previewable in browsers without Wicket processing.

### Model-Driven Components

Every component reads and writes data through `IModel` abstractions. Models decouple components from data sources, enable lazy loading, support proper detachment for serialization, and make components reusable across different data contexts. **Passing raw objects instead of models creates stale data, serialization bloat, and tight coupling.**

### Type Safety Throughout

Wicket leverages Java's type system extensively. Generic components, typed models, and compile-time verification catch errors before runtime. Use generic `IModel<T>` properly. Avoid raw types and string-based property access where type-safe alternatives exist.

### Components Own Their Markup

Every Wicket component binds to **exactly one** HTML element via `wicket:id`. The component renders that element and its children. **Components do not reach outside their markup boundary.** A `Panel` packages its HTML, CSS, and JavaScript together as a self-contained unit. This encapsulation enables composition — complex pages assemble from simple, tested components.

### Models Are Not Optional

Every component that displays or edits data uses an `IModel`, never raw object references. Passing raw objects creates:

- **Stale data** — the object reference never updates.
- **Serialization bloat** — the entire object graph serializes with the page.
- **Tight coupling** — the component cannot be reused with different data sources.

---
[Back to Overview](./OVERVIEW.md)

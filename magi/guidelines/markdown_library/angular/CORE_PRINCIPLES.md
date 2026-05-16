# Core Principles

These guidelines define strict, scalable, and maintainable patterns for Angular application development, optimizing for:

- **Standalone by Default**: Every component, directive, and pipe is standalone; NgModules exist only for third-party interop and legacy migration paths—never as the organizational primitive for new code.
- **Signal-First Reactivity**: Signals are the primary reactive primitive for synchronous state; RxJS is reserved for asynchronous streams, event composition, and complex temporal operations where Signals lack expressiveness.
- **Strict Type Safety**: TypeScript strict mode with zero `any` types, strict template checking enabled, and compile-time validation of bindings, route parameters, and form controls.
- **Unidirectional Data Flow**: Data flows down through inputs; events flow up through outputs; cross-cutting state lives in injectable services—never in component trees through shared mutable references.
- **Change Detection Awareness**: Every component and binding decision acknowledges the change detection cost; OnPush is the default strategy, and zone-free operation is the architectural target.

### Primary Rule: Components Are Thin Shells

A component's job is to bind a template to state and delegate behavior to services. Business logic in components is an architectural defect. Components that exceed 150 lines indicate missing service abstractions, improper concern distribution, or template logic that belongs in pipes or directives. The template renders; the component coordinates; services execute.

### Secondary Rule: Observable Streams Are Pipelines, Not Storage

RxJS observables describe data transformations over time. They are pipelines—declared once, subscribed to as needed, and completed when no longer relevant. Storing intermediate state in BehaviorSubjects as a poor substitute for proper state management creates memory leaks, stale data, and subscription management nightmares. Use Signals for synchronous state. Use dedicated state management for complex shared state. Use RxJS for what it was designed for: composing asynchronous event streams.

### Version and Platform Strategy

These guidelines target Angular 17+ with the modern compilation and rendering pipeline. Key platform capabilities assumed:

- **Standalone APIs**: Components, directives, and pipes default to `standalone: true`.
- **Built-in control flow**: `@if`, `@for`, `@switch`, `@defer` blocks replace structural directives.
- **Signal primitives**: `signal()`, `computed()`, `linkedSignal()`, `effect()`, `input()`, `output()`, `model()` provide fine-grained reactive state management.
- **ESBuild/Vite**: The application builder uses ESBuild for development and Vite for dev server.
- **Functional APIs**: `inject()`, functional guards, functional resolvers, and functional interceptors.

Applications on Angular 16 or earlier should prioritize migration to standalone and signals before adopting these guidelines wholesale.

---
[Back to Overview](./OVERVIEW.md)

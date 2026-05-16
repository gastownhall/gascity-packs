# Unified Rust Coding Style Guidelines Library

This directory contains an expanded, modularized version of the Unified Rust Coding Style Guidelines. These guidelines are mandatory for all Rust source files (`*.rs`), library crates, binary crates, and build scripts.

## Table of Contents

1.  [Core Principles](./CORE_PRINCIPLES.md) - Non-negotiable philosophical foundations.
2.  [Line Length and Formatting](./LINE_LENGTH_FORMATTING.md) - Horizontal density and `rustfmt` configuration.
3.  [Import Style](./IMPORT_STYLE.md) - Organization, grouping, and compact formats.
4.  [Function Definitions](./FUNCTION_DEFINITIONS.md) - Signatures, compact functions, and ordering.
5.  [Structural Elements](./STRUCTURAL_ELEMENTS.md) - Structs, Enums, and collection literals.
6.  [Method Chaining](./METHOD_CHAINING.md) - Multi-line vs. compact chains and builder patterns.
7.  [Error Handling](./ERROR_HANDLING.md) - Result types, propagation, and custom error types.
8.  [Pattern Matching](./PATTERN_MATCHING.md) - Match arms, destructuring, and match guards.
9.  [Conditionals and Expressions](./CONDITIONALS_EXPRESSIONS.md) - Inline conditionals and let-else patterns.
10. [Async/Await Patterns](./ASYNC_AWAIT_PATTERNS.md) - Concurrency, timeouts, and cancellation safety.
11. [Memory and Ownership](./MEMORY_OWNERSHIP.md) - Borrowing rules, preference order, and interior mutability.
12. [Concurrency Patterns](./CONCURRENCY_PATTERNS.md) - Synchronization primitives, channels, and atomics.
13. [Type System Patterns](./TYPE_SYSTEM_PATTERNS.md) - Newtypes, trait bounds, and associated types.
14. [Logging and Diagnostics](./LOGGING_DIAGNOSTICS.md) - Structured logging and instrumentation with `tracing`.
15. [Testing Patterns](./TESTING_PATTERNS.md) - Module structure, async tests, and property-based testing.
16. [Macros](./MACROS.md) - Declarative and derive macros.
17. [Comments and Documentation](./COMMENTS_DOCUMENTATION.md) - Documentation comments and module-level docs.
18. [Indentation and Spacing](./INDENTATION_SPACING.md) - 4-space rule and vertical space management.
19. [Performance Considerations](./PERFORMANCE_CONSIDERATIONS.md) - Allocation avoidance and zero-copy patterns.
20. [Security Considerations](./SECURITY_CONSIDERATIONS.md) - Input validation, secret handling, and SQL injection prevention.
21. [Prohibited Practices](./PROHIBITED_PRACTICES.md) - The absolute "Never Do" and "Always Do" lists.
22. [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md) - Common compiler errors and solutions.
23. [Minimum Viable Templates](./MINIMUM_VIABLE_TEMPLATES.md) - Boilerplate for crates and services.
24. [Style Summary](./STYLE_SUMMARY.md) - Quick reference for style requirements.

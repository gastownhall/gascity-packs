# Python Development Guidelines Library

This directory contains an expanded, modularized version of the Python Development Guidelines. These guidelines are mandatory for all Python application code, libraries, and services.

## Critical Mandates (Read First)
- **Target Version**: Python 3.14+ for new projects; 3.11+ minimum for existing.
- **Tools**: Code must pass `mypy --strict` and `ruff check`.
- **Absolute Bans**:
    - **NEVER** use `TYPE_CHECKING` in Python code.
    - **NEVER** use `TypedDict`, bare classes, or anything else instead of a Pydantic model.
    - **NEVER** put production logic outside `src/` or tests outside `tests/`.

## Table of Contents

1.  [Core Principles](./CORE_PRINCIPLES.md) - Non-negotiable philosophical foundations.
2.  [Project Structure](./PROJECT_STRUCTURE.md) - Standard layout, `src/` vs `tests/`, and `typings/`.
3.  [Boundaries and Validation](./BOUNDARIES_AND_VALIDATION.md) - Pydantic at the perimeter, trusted internals.
4.  [Naming and API Design](./NAMING_AND_API_DESIGN.md) - Verbs, nouns, and public surface requirements.
5.  [Type System](./TYPE_SYSTEM.md) - Mandatory typing, `Any` ban, and built-in generics.
6.  [Type Organization](./TYPE_ORGANIZATION.md) - The `typings/` directory and symbol centralization.
7.  [Imports](./IMPORTS.md) - Sorting, grouping, and predictability.
8.  [Pydantic Models](./PYDANTIC_MODELS.md) - Configuration, field descriptors, and V2 syntax.
9.  [Classes and Objects](./CLASSES_AND_OBJECTS.md) - Dataclasses, Protocols, and Properties.
10. [Methods and Visibility](./METHODS_AND_VISIBILITY.md) - Decorators, guard clauses, and private members.
11. [Formatting](./FORMATTING.md) - Indentation, blank lines, and the 200-character line limit.
12. [Code Patterns](./CODE_PATTERNS.md) - Context managers, comprehensions, and pattern matching.
13. [Error Handling](./ERROR_HANDLING.md) - Domain hierarchies and exception context.
14. [Logging](./LOGGING.md) - Lazy formatting, log levels, and security.
15. [Async Patterns](./ASYNC_PATTERNS.md) - Non-blocking I/O and loop ownership.
16. [File I/O and Subprocess](./FILE_IO_AND_SUBPROCESS.md) - `pathlib.Path`, encoding, and safe execution.
17. [Documentation](./DOCUMENTATION.md) - Google-style docstrings and the ban on inline comments.
18. [Circular Imports](./CIRCULAR_IMPORTS.md) - High-priority resolution strategies.
19. [Operational Standards](./OPERATIONAL_STANDARDS.md) - Timeouts, retries, and resource ownership.
20. [Security](./SECURITY.md) - Validation, secret management, and injection prevention.
21. [Performance](./PERFORMANCE.md) - Measurement, generators, and caching.
22. [Testing](./TESTING.md) - Structure, categories, and async verification.
23. [Shakedown](./SHAKEDOWN.md) - Integrated end-to-end async validation.
24. [Modern Python Features](./MODERN_PYTHON.md) - Type parameter syntax and `Self`.
25. [Dependency Management](./DEPENDENCY_MANAGEMENT.md) - Venvs, `pyproject.toml`, and `uv`.
26. [Defense in Depth](./DEFENSE_IN_DEPTH.md) - Independent layers and the Rule of Three.
27. [Linter Configuration](./LINTER_CONFIG.md) - Standard `mypy` and `ruff` settings.
28. [Prohibited Practices](./PROHIBITED_PRACTICES.md) - The absolute "Never Do" list.
29. [Style Summary](./STYLE_SUMMARY.md) - Quick reference for style requirements.

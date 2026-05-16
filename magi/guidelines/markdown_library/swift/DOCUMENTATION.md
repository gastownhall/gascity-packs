# Documentation

### Documentation Comments

- Use `///` for documentation comments on public APIs.
- Include `- Parameters:`, `- Returns:`, `- Throws:` sections for functions.
- Document preconditions, postconditions, and complexity when non-obvious.
- Link related symbols with double backticks: `` See ``RelatedType`` for more details. ``

### Inline Comments

- **Avoid explaining what code does** — the code should be self-explanatory.
- Use comments to explain **why** unusual approaches were necessary.
- Mark non-obvious invariants or constraints that the type system cannot express.
- TODO and FIXME comments require linked issue numbers; **orphan TODOs are prohibited**.

### README and Module Documentation

- Each module or package includes a README explaining purpose, usage, architecture.
- Document build requirements, environment setup, test execution.
- Maintain a CHANGELOG for versioned libraries.

---
[Back to Overview](./OVERVIEW.md)

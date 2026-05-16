# Prohibited Practices

### Never Do

- Break query folding unnecessarily; pushing computation to source is always preferable.
- Use implicit typing; every column must have explicit type declaration.
- Embed credentials in queries; use parameters and managed credentials.
- Create circular references; M prohibits them, but designs should never approach them.
- Use `Table.Buffer` indiscriminately; buffering consumes memory and should be intentional.
- Ignore privacy levels; Formula.Firewall errors indicate real security boundary violations.
- Name queries with spaces; reference syntax becomes cumbersome.
- Load staging queries; intermediate queries waste memory and clutter models.
- Use `each _` without understanding; it is a function shorthand, not magic.
- Disable query folding verification; always confirm folding for performance.
- Hardcode file paths; use parameters for all environment-specific values.
- Ignore error handling; try-otherwise patterns are required for risky operations.
- Create monolithic queries; decompose into reusable staging, transform, and output layers.
- Skip testing; validate schema, row counts, and data quality programmatically.
- Use `type number` for currency; `Decimal.Type` prevents floating-point errors.
- Rely on default step names; rename steps to describe their action.
- Mix transformation and loading logic; separation enables maintenance.
- Deploy untested to production; use staging workspace validation.

---
[Back to Overview](./OVERVIEW.md)

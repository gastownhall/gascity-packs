# Required Practices

### Always Do

- Verify query folding on every source-connected step.
- Declare types explicitly at point of ingestion.
- Use parameters for environment-specific configuration.
- Structure queries into staging, transform, and output tiers.
- Disable load on intermediate queries.
- Apply consistent naming conventions with prefixes.
- Handle errors with try-otherwise patterns.
- Document functions with metadata.
- Validate schema before processing.
- Use `Table.Buffer` only when repeated access is confirmed.
- Set privacy levels explicitly on all data sources.
- Profile large queries with diagnostics before deployment.
- Version control queries using PBIP format.
- Test functions with known inputs.
- Rename steps to describe their transformation.
- Use `Decimal.Type` for all monetary values.
- Reference queries instead of duplicating.
- Filter and select columns as early as possible in query chain.
- Run a §18 shakedown after every M query rewrite, data source swap, or Power BI/Fabric dataset modification.

---
[Back to Overview](./OVERVIEW.md)

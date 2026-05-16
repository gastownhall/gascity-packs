# Security and Data Privacy

### Privacy Levels

| Level | Description | Combines With |
|:------|:------------|:--------------|
| None | No privacy level set | Inherits from context |
| Public | Data can be shared freely | All levels |
| Organizational | Data stays within organization | Organizational, Public |
| Private | Data never leaves local context | Private only |

**Privacy level mismatches cause Formula.Firewall errors.** Set levels explicitly on all data sources.

### Privacy Level Configuration

| Method | Path |
|:-------|:-----|
| Query-level | Right-click query → Properties → Privacy Level |
| Data-source-level | File → Options → Data source settings → Edit Permissions |
| Programmatic | `Value.ReplaceType(Source, Value.Type(Source) meta [Privacy = "Organizational"])` |

### Credential Security

- **Never embed credentials** — use parameters; credentials managed externally.
- **Service principal for automation** — Azure AD service principals for scheduled refresh.
- **Scope permissions minimally** — request only required access from source systems.
- **Rotate credentials regularly.**

### Sensitive Data Handling

```powerquery
// Masking during development
Table.TransformColumns(Source, {
    {"SSN", each Text.Repeat("*", Text.Length(_) - 4) & Text.End(_, 4), type text},
    {"CreditCard", each Text.Repeat("*", 12) & Text.End(_, 4), type text}
})
```

Power Query does not encrypt data natively; rely on source system encryption and Power BI sensitivity labels. Enable diagnostic logging for compliance — track query execution and data access patterns.

### Formula.Firewall Mitigation

When privacy levels conflict:

1. Set all sources to the same privacy level (if appropriate).
2. Disable privacy level checks for development (never in production).
3. Restructure queries to avoid cross-privacy-level operations.
4. Use staging tables in a single privacy context.

---
[Back to Overview](./OVERVIEW.md)

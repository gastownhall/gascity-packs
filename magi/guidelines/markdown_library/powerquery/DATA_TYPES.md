# Data Type System

### Primitive Types

| Type | M Type Name | Example | Notes |
|:-----|:------------|:--------|:------|
| Text | `type text` | `"hello"` | Unicode strings |
| Number | `type number` | `42`, `3.14` | 64-bit floating point; precision limits apply |
| Integer | `Int64.Type` | `42` | **Use for IDs and counts** |
| Decimal | `Decimal.Type` | `123.45` | Fixed-point; **use for currency** |
| Boolean | `type logical` | `true`, `false` | |
| Date | `type date` | `#date(2025, 1, 15)` | Date without time |
| Time | `type time` | `#time(14, 30, 0)` | Time without date |
| DateTime | `type datetime` | `#datetime(2025, 1, 15, 14, 30, 0)` | Combined |
| DateTimeZone | `type datetimezone` | `#datetimezone(...)` | DateTime with timezone offset |
| Duration | `type duration` | `#duration(1, 2, 30, 0)` | Days, hours, minutes, seconds |
| Binary | `type binary` | Binary data | Byte sequences |
| Null | `type null` | `null` | Absence of value |

### Complex Types

- **List** — ordered collection, zero-indexed: `{1, 2, 3}` or `{"a", "b", "c"}`. Homogeneous lists perform better.
- **Record** — named field-value pairs: `[Name = "John", Age = 30]`. Field names are case-sensitive.
- **Table** — rows with consistent column schema. Primary data structure for query outputs.
- **Function** — first-class values: `(x) => x * 2`.
- **Type** — types themselves are values. Used for schema enforcement and documentation.

### Type Declaration Patterns

Column typing at source:

```powerquery
Table.TransformColumnTypes(Source, {
    {"CustomerID", Int64.Type},
    {"CustomerName", type text},
    {"CreatedDate", type date},
    {"Revenue", Decimal.Type},
    {"IsActive", type logical}
})
```

Function parameter types:

```powerquery
(inputDate as date, multiplier as number) as number =>
    Date.DayOfYear(inputDate) * multiplier
```

Table type definition:

```powerquery
type table [
    CustomerID = Int64.Type,
    CustomerName = text,
    CreatedDate = date,
    Revenue = Decimal.Type
]
```

### Type Coercion and Safety

- **Explicit over implicit** — always declare types; don't rely on inference.
- **Type at ingestion** — apply `Table.TransformColumnTypes` immediately after source connection.
- **Handle nullability** — M types are nullable by default; `non-nullable` modifier available but rarely needed.
- **Validate before transform** — type errors cascade; catch early.
- **Currency as `Decimal.Type`** — never use `type number` for monetary values; floating-point imprecision causes accounting errors.

### Schema Enforcement

```powerquery
let
    ExpectedSchema = type table [ID = Int64.Type, Name = text, Amount = Decimal.Type],
    ActualSchema = Value.Type(SourceTable),
    IsValid = Type.Is(ActualSchema, ExpectedSchema)
in
    if IsValid then SourceTable else error "Schema mismatch detected"
```

### Null-Safe Conversion

```powerquery
(value as any, targetType as type) as any =>
    try
        if value = null then null
        else Value.As(value, targetType)
    otherwise null
```

---
[Back to Overview](./OVERVIEW.md)

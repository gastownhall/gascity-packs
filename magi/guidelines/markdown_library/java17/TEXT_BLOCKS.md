# Text Blocks and String Handling

Text blocks (JEP 378) provide multi-line string literals with automatic indentation management.

### Use Text Blocks for Multi-Line Literals

```java
String sql = """
    SELECT id, name, email
    FROM users
    WHERE tenant_id = ?
      AND status = 'ACTIVE'
    ORDER BY created_at DESC
    """;
```

Text blocks start with `"""` followed by a line terminator and end with `"""`. The compiler strips common leading whitespace, preserving intended indentation relative to the closing delimiter.

### Closing Delimiter Controls Indentation

```java
// Closing """ aligned with leftmost content → zero-indent output
String json = """
{
  "name": "value"
}
""";

// Content indented relative to closing """ → indentation preserved
String yaml = """
  name: value
  list:
    - item1
    - item2
  """;
```

### Never Embed User Input in Text Blocks for SQL/HTML

Text blocks are compile-time string literals — they do not provide parameterization or escaping. Use:

- `PreparedStatement` for SQL.
- Template engines for HTML.
- Parameterized builders for JSON.

String interpolation of untrusted input into text blocks is an injection vulnerability regardless of the string format.

---
[Back to Overview](./OVERVIEW.md)

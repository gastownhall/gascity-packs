# Line Length and Formatting

### Maximum Line Length

- **Hard limit:** 200 characters per line.
- **Philosophy:** horizontal density reduces cognitive load from vertical scanning.

### Single-line Preference

Keep on one line when under 200 characters:

- Function signatures (parameters, generics, return types).
- Guard statements with single conditions.
- Simple closures passed as trailing arguments.
- Property declarations with default values.
- Short switch cases with single expressions.

### Multi-line Formatting

Break across lines when:

- Generic where clauses exceed comfortable reading.
- Closure bodies contain multiple statements.
- Function calls have more than four arguments or complex argument expressions.
- Chained method calls exceed the line limit.

### Trailing Commas (Required in multi-line)

- Array and dictionary literals.
- Function parameter lists (Swift 5.9+).
- Enum case associated value declarations.

### Indentation and Spacing

- 4 spaces per indentation level; **tabs prohibited**.
- Single blank line between type members.
- Single blank line between import groups.
- No trailing whitespace on any line.
- Opening braces on the same line as the declaration.
- Closing braces on their own line for multi-line blocks.

```swift
func processData(items: [Item]) {
    items.forEach { item in
        process(item)
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

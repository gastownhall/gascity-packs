# Pattern Matching and Switch Expressions

Pattern matching for `instanceof` (JEP 394) eliminates the cast-after-instanceof pattern. Switch expressions (JEP 361) replace verbose switch statements with concise, exhaustive expressions.

### Pattern Matching for instanceof

```java
// CORRECT
if (obj instanceof String s) {
    System.out.println(s.toUpperCase());
}

// FORBIDDEN — traditional cast-after-check
if (obj instanceof String) {
    String s = (String) obj;
    System.out.println(s.toUpperCase());
}
```

The pattern variable `s` is scoped to the true branch and is automatically cast.

### Switch Expressions with Arrow Syntax

```java
String label = switch (status) {
    case PENDING   -> "Awaiting approval";
    case APPROVED  -> "Approved";
    case REJECTED  -> "Rejected";
    case CANCELLED -> "Cancelled";
};
```

Switch expressions are exhaustive (compiler enforces all cases), prevent fall-through bugs, and return values directly. Use `yield` for multi-statement case bodies that must return a value:

```java
String description = switch (level) {
    case 1 -> "novice";
    case 2 -> "intermediate";
    default -> {
        log.debug("custom level {}", level);
        yield "level-" + level;
    }
};
```

### Omit Default on Sealed Types

```java
double area = switch (shape) {
    case Shape.Circle c    -> Math.PI * c.radius() * c.radius();
    case Shape.Rectangle r -> r.width() * r.height();
    case Shape.Triangle t  -> heronArea(t.a(), t.b(), t.c());
    // No default — compiler verifies exhaustiveness
};
```

A `default` case on a sealed-type switch hides the compiler's exhaustiveness check. If a new permitted subtype is added, `default` silently handles it instead of generating compilation errors at every switch site that needs updating.

### Switch Pattern Matching Note

Type patterns in `switch` cases (e.g., `case Circle c ->`) is a **preview** feature in Java 17 (JEP 406). Standard from Java 21. In Java 17 production code without `--enable-preview`, use pattern matching for `instanceof` with if-else chains as the alternative. Refactor to switch pattern matching when the codebase migrates to Java 21.

---
[Back to Overview](./OVERVIEW.md)

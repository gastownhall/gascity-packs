# Required Document Structure

### Opening Section: Core Principles
Every guideline document opens with a Core Principles section containing:
1. **Primary Rule**: The single most important principle that guides all decisions in this domain. Everything else is subordinate to this.
2. **Secondary Rule**: The second-order principle that shapes default behaviors.
3. **Tertiary Rule**: The third-order principle that resolves ambiguity when the first two don't apply.
- These rules establish the mental model readers use to evaluate situations the document doesn't explicitly cover. They must be specific enough to provide real guidance, not platitudes.
- Example of insufficient specificity: "Write good code" — useless.
- Example of sufficient specificity: "The database is the last line of defense; if a constraint can be expressed in DDL, it belongs in DDL" — actionable.
### Part-Based Organization
- Organize content into logical Parts that follow a natural workflow or progression. Common organizational patterns:
    - **Lifecycle-based**: Design → Implementation → Execution → Operations
    - **Abstraction-based**: Fundamentals → Patterns → Advanced Topics → Reference
    - **Decision-based**: Requirements Analysis → Technology Selection → Implementation → Validation
- **Each Part should be self-contained enough that a reader working on that phase can focus there, while cross-referencing other Parts as needed.**
### Section Depth Requirements
Within each Part, provide multi-level depth:
1. **H2 headers**: Major topic areas within the Part
2. **H3 headers**: Specific subjects within each topic
3. **H4 headers** (sparingly): Detailed breakdowns when a subject has distinct sub-components
- **Each section must answer:**
    - What is this? (Definition)
    - When does it apply? (Scope)
    - How do you do it correctly? (Guidance)
    - What goes wrong if you don't? (Consequences)
    - What are common mistakes? (Anti-patterns)
### Required Closing Section: Style Summary
Every guideline document ends with a Style Summary section containing:
1. A table summarizing key standards in scannable format
2. A reinforcing statement of the document's purpose
3. A directive for universal application

---
[Back to Overview](./OVERVIEW.md)

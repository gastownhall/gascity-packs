# Power Query (M Language) Library

These guidelines define strict, performant, and maintainable patterns for Power Query (M language) implementations across Power BI, Excel, and Dataflows.

## Critical Mandates (Read First)
- **Query Folding Is Performance** — every transformation considers whether operations push to the source.
- **Explicit Over Implicit** — every column has explicit type declaration; never rely on inference.
- **Decimal.Type for Currency** — never `type number` for monetary values.
- **Staging/Transform/Output Tiers** — only output queries load; intermediates disabled.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Query Architecture and Organization](./QUERY_ARCHITECTURE.md)
3. [Data Source Connectivity](./DATA_SOURCES.md)
4. [Query Folding](./QUERY_FOLDING.md)
5. [Data Type System](./DATA_TYPES.md)
6. [Transformation Patterns](./TRANSFORMATIONS.md)
7. [Function Design](./FUNCTION_DESIGN.md)
8. [Error Handling](./ERROR_HANDLING.md)
9. [Parameter Management](./PARAMETERS.md)
10. [Custom Connectors](./CUSTOM_CONNECTORS.md)
11. [Security and Data Privacy](./SECURITY_PRIVACY.md)
12. [Performance Optimization](./PERFORMANCE.md)
13. [Incremental Refresh](./INCREMENTAL_REFRESH.md)
14. [Dataflow Patterns](./DATAFLOWS.md)
15. [Testing and Validation](./TESTING.md)
16. [Integration Patterns](./INTEGRATION.md)
17. [Development Workflow](./DEVELOPMENT_WORKFLOW.md)
18. [Post-Rebuild Shakedown](./SHAKEDOWN.md)
19. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
20. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
21. [Required Practices](./REQUIRED_PRACTICES.md)
22. [Style Summary](./STYLE_SUMMARY.md)

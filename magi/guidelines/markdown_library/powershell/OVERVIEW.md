# PowerShell Library

These guidelines define strict, maintainable, and enterprise-ready patterns for all PowerShell development.

## Critical Mandates (Read First)
- **PowerShell Is Not Batch Scripting** — operate on objects, not text streams.
- **Verb-Noun Discipline** — every function uses approved verbs from `Get-Verb`.
- **Discoverability Is Non-Negotiable** — comment-based help mandatory on every public function.
- **Strict Mode + ErrorActionPreference=Stop** at the top of every script.

## Table of Contents

1. [Core Principles](./CORE_PRINCIPLES.md)
2. [Script Structure and Requirements](./SCRIPT_STRUCTURE.md)
3. [Comment-Based Help](./COMMENT_BASED_HELP.md)
4. [Naming Conventions](./NAMING_CONVENTIONS.md)
5. [Parameter Design](./PARAMETER_DESIGN.md)
6. [Error Handling](./ERROR_HANDLING.md)
7. [Type System and Output](./TYPE_SYSTEM.md)
8. [Pipeline and Object Orientation](./PIPELINE.md)
9. [Module Architecture](./MODULE_ARCHITECTURE.md)
10. [Security Practices](./SECURITY.md)
11. [Performance Optimization](./PERFORMANCE.md)
12. [Cross-Platform Considerations](./CROSS_PLATFORM.md)
13. [Testing Strategy](./TESTING.md)
14. [Logging and Observability](./LOGGING.md)
15. [Remote Execution and Sessions](./REMOTE_EXECUTION.md)
16. [Desired State Configuration (DSC)](./DSC.md)
17. [PSScriptAnalyzer](./PSSCRIPT_ANALYZER.md)
18. [Advanced Function Patterns](./ADVANCED_FUNCTIONS.md)
19. [PowerShell 7+ Features](./PS7_FEATURES.md)
20. [Common Patterns and Idioms](./COMMON_PATTERNS.md)
21. [Shakedown — Integration Validation](./SHAKEDOWN.md)
22. [Defense in Depth](./DEFENSE_IN_DEPTH.md)
23. [Prohibited Practices](./PROHIBITED_PRACTICES.md)
24. [Required Practices](./REQUIRED_PRACTICES.md)
25. [Style Summary](./STYLE_SUMMARY.md)

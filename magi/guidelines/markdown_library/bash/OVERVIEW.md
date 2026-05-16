# Bash Scripting Standard Library

This directory contains an expanded, modularized version of the Bash Scripting Standard. These guidelines are mandatory for all executable/library Bash scripts, `.utilities/` files, and automation/deployment/provisioning scripts.

## Table of Contents

1.  [Core Principles](./CORE_PRINCIPLES.md) - Non-negotiable philosophical foundations.
2.  [Execution Model](./EXECUTION_MODEL.md) - Shebang, strict mode, and environment initialization.
3.  [Header Block](./HEADER_BLOCK.md) - Required documentation structure.
4.  [Section Ordering](./SECTION_ORDERING.md) - Fixed sequence of script components.
5.  [Color and Output](./COLOR_AND_OUTPUT.md) - Semantic color usage and output formatting.
6.  [Logging](./LOGGING.md) - Mandatory logging requirements and patterns.
7.  [Debugging](./DEBUGGING.md) - Tracing and debug mode activation.
8.  [Pre-flight and Shakedown](./PRE_FLIGHT_AND_SHAKEDOWN.md) - Verification before and during execution.
9.  [Source Management](./SOURCE_MANAGEMENT.md) - Shared libraries and source guards.
10. [Resilience](./RESILIENCE.md) - Idempotency, self-healing, and retries.
11. [Safe Destruction](./SAFE_DESTRUCTION.md) - Safe `rm` and backup patterns.
12. [Control Flow](./CONTROL_FLOW.md) - Guard patterns and branching style.
13. [Variables and Constants](./VARIABLES_AND_CONSTANTS.md) - Naming and declaration rules.
14. [Functions](./FUNCTIONS.md) - Declaration, length, and documentation.
15. [Dependency Management](./DEPENDENCY_MANAGEMENT.md) - Auto-installation and privilege handling.
16. [Privileged Execution](./PRIVILEGED_EXECUTION.md) - Sudo and root handling.
17. [OS Detection](./OS_DETECTION.md) - Cross-platform and distribution helpers.
18. [macOS Specifics](./MACOS_SPECIFICS.md) - Homebrew preferences and tool versions.
19. [Remote and Embedded](./REMOTE_AND_EMBEDDED.md) - Heredocs and remote execution.
20. [Filesystem Operations](./FILESYSTEM_OPERATIONS.md) - Paths, globs, and atomic writes.
21. [Concurrency](./CONCURRENCY.md) - Lock files and background processes.
22. [Argument Parsing](./ARGUMENT_PARSING.md) - Shift-based parsing and validation.
23. [Configuration Management](./CONFIGURATION_MANAGEMENT.md) - Precedence and validation.
24. [CI Detection](./CI_DETECTION.md) - Adapting to automated environments.
25. [Testing](./TESTING.md) - Dry-runs, isolation, and validation utilities.
26. [Cleanup and Traps](./CLEANUP_AND_TRAPS.md) - EXIT and ERR traps.
27. [Utilities Contract](./UTILITIES_CONTRACT.md) - Rules for `.utilities/` files.
28. [Error Messages and Exit Codes](./ERROR_MESSAGES_AND_EXIT_CODES.md) - Semantic errors and codes.
29. [Scheduled Tasks](./SCHEDULED_TASKS.md) - Cron-safe script requirements.
30. [Best Practices](./BEST_PRACTICES.md) - Arrays, quoting, and arithmetic.
31. [Anti-Patterns](./ANTI_PATTERNS.md) - The absolute blacklist.
32. [Security](./SECURITY.md) - Input validation and credential handling.
33. [Defense in Depth](./DEFENSE_IN_DEPTH.md) - Failure-mode defense layers.
34. [Templates](./TEMPLATES.md) - Boilerplate for new scripts.
35. [Troubleshooting](./TROUBLESHOOTING.md) - Common issues and solutions.

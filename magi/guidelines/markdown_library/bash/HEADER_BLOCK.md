# Header Block

The only permitted comment region. All documentation lives here.

### Structure (exact order)
1. Title line
2. 78-char `=` separator
3. Description (purpose, side effects, target environments)
4. Usage (invocation examples, option syntax)
5. Interface (OPTIONS + ENVIRONMENT VARIABLES for executables; EXPORTED FUNCTIONS for libraries)
6. Dependencies (internal files, external commands)
7. Closing `=` separator

### Example
```bash
#!/usr/bin/env bash
#
# Docker Build Orchestration
# ==============================================================================
# Orchestrates Docker build: env loading, arg parsing, caching, tagging, push.
#
# USAGE:
#   ./build.sh [OPTIONS]
#
# OPTIONS:
#   --name NAME    Image name (required if not in .env)
#   --tag TAG      Image tag (default: 'latest')
#   --push         Push to registry after build
#   -h, --help     Show help
#
# ENVIRONMENT VARIABLES:
#   IMAGE_NAME     Default image name
#   REGISTRY_URL   Registry URL
#
# DEPENDENCIES:
#   Internal: utils.sh
#   External: docker, git, jq
# ==============================================================================
```

### Post-Header Rule (Zero Tolerance)
After the header: **NO comments, NO blank lines, NO inline comments.** Code begins immediately and remains contiguous. Structure is expressed through indentation and function boundaries only. Use `#` lines as visual section dividers within otherwise contiguous code (not free prose).

---
[Back to Overview](./OVERVIEW.md)

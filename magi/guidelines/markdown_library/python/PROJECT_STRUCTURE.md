# Project Structure

### Standard Layout
```
project-name/
├── pyproject.toml
├── requirements.txt
├── src/
│   ├── main.py
│   ├── config.py
│   ├── typings/
│   │   ├── {PROJECT_NAME}_models/
│   │   ├── {PROJECT_NAME}_enums/
│   │   ├── {PROJECT_NAME}_constants/
│   │   └── stubs/
│   ├── services/
│   ├── repositories/
│   ├── api/
│   └── utils/
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/
```
**If the project has a frontend and a backend**, the Python directories become `backend/src/` and `backend/tests/` respectively.

### Directory Responsibilities
| Directory | Responsibility |
|:----------|:---------------|
| `typings/` | All type definitions: `{PROJECT_NAME}_models/` (Pydantic), `{PROJECT_NAME}_enums/` (Enums), `{PROJECT_NAME}_constants/` (constants and type aliases), `stubs/` (`.pyi` files for external libs only) |
| `services/` | Stateless business logic; returns domain models |
| `repositories/` | Data access; encapsulates DB, API, file operations |
| `api/` | HTTP routes; thin layer — validates input, calls services, formats output |
| `utils/` | Pure functions; no side effects, no external dependencies |

### Source Layout Rules
- All production logic lives in `src/`. No production logic in ad-hoc scripts outside `src/`.
- All test code lives in `tests/`. **NO test files outside `tests/` — ever.** No test files in the project root.
- Type definitions live in `src/typings/`.

### File Size Limits
- Standard limit: 1000 lines per file.
- Hard limit with justification: 1200 lines.
- Prefer modules and classes over dumping logic into one oversized file.

---
[Back to Overview](./OVERVIEW.md)

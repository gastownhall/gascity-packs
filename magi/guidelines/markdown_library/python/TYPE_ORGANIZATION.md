# Type Organization

### The `typings/` Directory
All type definitions live in `src/{package_name}/typings/`:
```
typings/
├── {PROJECT_NAME}_models/   # All Pydantic models
│   ├── user_models.py
│   ├── order_models.py
│   └── common_models.py
├── {PROJECT_NAME}_enums/    # All enumerations
│   ├── status_enums.py
│   └── category_enums.py
├── {PROJECT_NAME}_constants/  # Constants and type aliases
│   ├── api_constants.py
│   └── type_aliases.py
└── stubs/                   # .pyi for external libs only
    └── untyped_lib.pyi
```

### Rules
- **No Pydantic models outside `{PROJECT_NAME}_models/`.** Services and repositories import from there.
- **No enums outside `{PROJECT_NAME}_enums/`.** If two modules need the same states, they share one enum. Never duplicate enum meanings with a second enum type.
- **No constants outside `{PROJECT_NAME}_constants/`.** Magic numbers, defaults, and type aliases live here.
- **No stub files for internal code.** Internal code must have inline annotations.
- **Never create duplicate symbol types** (models, enums, constants, type aliases) that overlap meaning. Extend the existing symbol or introduce one shared replacement; do not fork types.

### Importing
Always use full paths to specific files. Directory-level imports are forbidden:
```python
# Correct
from typings.project_models.user_models import User
from typings.project_enums.status_enums import UserStatus
from typings.project_constants.api_constants import DEFAULT_PAGE_SIZE
# Wrong
from typings.project_models import User
from typings import UserStatus
```

---
[Back to Overview](./OVERVIEW.md)

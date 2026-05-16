# Imports

### Top of File Only
All imports belong at the top of the file. No local imports inside functions, methods, or blocks. No lazy imports. Resolve circular imports via architecture, not import hacks.

### Explicit and Predictable
- Prefer importing the exact symbol used (`from x import y`) over module-level imports when it improves clarity.
- Never use star imports (`from x import *`).
- Never rely on directory-level re-exports as a convenience surface.

### `__init__.py` Rules
- `__init__.py` is empty or contains only `__all__`.
- `__all__` is forbidden outside `__init__.py`.
- **Never use `__init__.py` for re-exports.**

### Group Ordering
Three groups separated by single blank lines: stdlib, third-party, internal.
Within each group, place imports on consecutive lines with no extra blank lines between individual statements.

### Sorting Within Groups
- Sort imports alphabetically within each group.
- Sort by import type first: plain `import x` before `from x import y` within each group.

### From-Import Always Split
Each `from`-import statement stands alone. Never merge multiple `from`-imports from the same source into one statement:
```python
# Correct
from pathlib import Path
from typing import Protocol
from typing import Self
# Wrong
from typing import Protocol, Self
```

### Sort Names Within From-Imports
When a single `from`-import imports multiple names, sort them alphabetically:
```python
from pydantic import BaseModel, ConfigDict, Field
```

### Multi-Line Imports
Multi-line only when a single import statement exceeds 200 characters.

---
[Back to Overview](./OVERVIEW.md)

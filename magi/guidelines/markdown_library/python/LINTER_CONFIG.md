# Linter Configuration

**Never modify linter configuration to bypass errors or warnings.** Fix the code or adjust the design.

```toml
# pyproject.toml
[tool.mypy]
strict = true

[tool.ruff]
line-length = 200
select = ["ALL"]
ignore = ["D203", "D213"]

[tool.ruff.lint]
extend-select = [
    "PYI041",  # Disallow Any in function signatures
    "PGH003",  # Disallow unnecessary variadics
    "ANN401"   # Disallow untyped arguments returning Any
]
```

Apply universally to all `*.py` files and Python projects.

---
[Back to Overview](./OVERVIEW.md)

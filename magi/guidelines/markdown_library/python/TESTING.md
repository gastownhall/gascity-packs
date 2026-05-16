# Testing

**Do not add tests unless the user explicitly asks for tests to be added.**

### Test Location
- Tests go in `tests/`. **No exceptions.**
- Mirror `src/` layout inside `tests/` for discovery.
- Frontend/backend projects use `backend/tests/`.

### Test Structure
```
tests/
├── conftest.py
├── unit/
│   └── test_services.py
└── integration/
    └── test_api.py
```
Test files named `test_{module}.py`. Shared fixtures in `conftest.py`.

### Test Categories
- **Unit tests:** pure logic.
- **Integration tests:** boundaries (DB, net), timeouts mandatory.
- **Contract tests:** validate model schemas and boundary parsing.

### Test Naming
Test functions describe scenario and expected outcome:
```python
def test_create_user_with_valid_data_returns_user() -> None:
```

### Async Tests
Use `pytest-asyncio`:
```python
@pytest.mark.asyncio
async def test_fetch_user_returns_data() -> None:
    # ...
```

### Mocking External Boundaries
Use `unittest.mock.AsyncMock` or `patch` to mock external boundaries.

### Rules
- Prefer behavior over implementation.
- Keep tests deterministic.
- **Anti-patterns:** sleeping for "eventual consistency," hidden host-state dependencies.

---
[Back to Overview](./OVERVIEW.md)

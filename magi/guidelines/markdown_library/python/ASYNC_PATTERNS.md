# Async Patterns

### No Blocking I/O in Async Functions
Use async libraries for HTTP, DB, Files, and Redis. When forced to call blocking code, use a thread executor.

### Always Use `async with` for Resources
```python
async def fetch_user(user_id: str) -> UserData:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{API_BASE}/users/{user_id}")
        return UserData.model_validate(response.json())
```

### Timeouts Are Mandatory
Every async function that touches network/file/DB takes a timeout parameter or uses a configured timeout from a typed config object:
```python
async def fetch_data(url: str) -> dict[str, str]:
    async with asyncio.timeout(10.0):
        # ...
```

### Concurrent Execution
Use `asyncio.gather` or `asyncio.TaskGroup` for concurrent execution.

### Retry with Backoff
Implement retries with exponential backoff for transient failures.

### Cancellation and Cleanup
- If a task owns a resource, it must clean it up on cancellation.
- Use context managers to enforce cleanup semantics.
- **Anti-pattern:** Fire-and-forget tasks without tracking.

### Event Loop Ownership
- Only application entry points call `asyncio.run()`.
- Libraries return coroutines; libraries never own the loop.

---
[Back to Overview](./OVERVIEW.md)

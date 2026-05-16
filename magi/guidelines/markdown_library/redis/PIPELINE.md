# Pipeline Optimization

### Optimal Pipeline Batching

| Rule | Guidance |
|:-----|:---------|
| Batch size | 100–1000 commands |
| Memory | Monitor client output buffer limits; keep pipeline under 1MB total |
| Network | Consider MTU for packet efficiency |
| Async | Use async pipeline execution when possible |

```python
def bulk_set_with_pipeline(redis, data, batch_size=1000):
    pipeline = redis.pipeline(transaction=False)
    count = 0
    for key, value in data.items():
        pipeline.set(key, value, ex=3600)
        count += 1
        if count % batch_size == 0:
            pipeline.execute()
            pipeline = redis.pipeline(transaction=False)
    # Execute remaining commands
    if count % batch_size != 0:
        pipeline.execute()
```

### Anti-Pattern: Dependent Commands in a Pipeline

```python
# WRONG: second command depends on first
pipeline = redis.pipeline()
pipeline.incr('counter')
pipeline.get('counter')  # Won't see the incremented value
results = pipeline.execute()
```

Pipelines are batched but **not interactive** within the batch. Use a Lua script for true atomic chained operations.

---
[Back to Overview](./OVERVIEW.md)

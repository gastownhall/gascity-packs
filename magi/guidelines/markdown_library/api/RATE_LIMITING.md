# Rate Limiting and Throttling

### Rate Limit Design

- Define limits per client (API key, user, or IP)
- Express limits as requests per time window (e.g., 1000/hour)
- Apply different limits to different endpoints based on cost
- Implement tiered limits for different client plans

### Rate Limit Headers

Include rate limit status in every response:

```
RateLimit-Limit: 1000
RateLimit-Remaining: 847
RateLimit-Reset: 1705312800
```

- `RateLimit-Limit`: Maximum requests in current window
- `RateLimit-Remaining`: Requests remaining in current window
- `RateLimit-Reset`: Unix timestamp when window resets

### Exceeded Limit Response

Return **429 Too Many Requests** with retry information:

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "\nRate limit exceeded. Try again in 45 seconds.",
    "retryAfter": 45
  }
}
```

Include `Retry-After` header with seconds until retry is allowed.

### Throttling Strategies

| Strategy | Description | Trade-off |
|:---------|:------------|:----------|
| Fixed Window | Reset at fixed intervals | Burst at window boundaries |
| Sliding Window | Rolling window | Smoother limiting, no boundary bursts |
| Token Bucket | Allows controlled bursting | Maintains average rate with burst capacity |
| Leaky Bucket | Processes at constant rate | Smooth traffic flow; queues excess |

Choose based on traffic patterns and user-experience requirements.

---
[Back to Overview](./OVERVIEW.md)

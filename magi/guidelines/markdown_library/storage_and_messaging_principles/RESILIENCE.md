# Resilience Patterns

### Retry with Exponential Backoff

```csharp
public static class RetryPolicy
{
    public static async Task<T> ExecuteWithRetryAsync<T>(
        Func<CancellationToken, Task<T>> operation,
        int maxRetries = 3,
        CancellationToken ct = default)
    {
        var delay = TimeSpan.FromMilliseconds(100);

        for (int attempt = 0; attempt <= maxRetries; attempt++)
        {
            try
            {
                return await operation(ct);
            }
            catch (Exception ex) when (IsTransient(ex) && attempt < maxRetries)
            {
                await Task.Delay(delay, ct);
                delay *= 2; // Exponential backoff
                delay = TimeSpan.FromMilliseconds(Math.Min(delay.TotalMilliseconds, 30000)); // Cap at 30s
            }
        }

        throw new InvalidOperationException("Should not reach here");
    }

    private static bool IsTransient(Exception ex) =>
        ex is TimeoutException or
        HttpRequestException or
        TaskCanceledException { CancellationToken.IsCancellationRequested: false };
}
```

### Circuit Breaker

```csharp
public class CircuitBreaker
{
    private readonly int _failureThreshold;
    private readonly TimeSpan _openDuration;
    private int _failureCount;
    private DateTimeOffset _lastFailure;
    private CircuitState _state = CircuitState.Closed;
    private readonly object _lock = new();

    public async Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken ct)
    {
        lock (_lock)
        {
            if (_state == CircuitState.Open)
            {
                if (DateTimeOffset.UtcNow - _lastFailure > _openDuration)
                {
                    _state = CircuitState.HalfOpen;
                }
                else
                {
                    throw new CircuitOpenException();
                }
            }
        }

        try
        {
            var result = await operation(ct);

            lock (_lock)
            {
                _failureCount = 0;
                _state = CircuitState.Closed;
            }

            return result;
        }
        catch (Exception ex) when (IsFailure(ex))
        {
            lock (_lock)
            {
                _failureCount++;
                _lastFailure = DateTimeOffset.UtcNow;

                if (_failureCount >= _failureThreshold)
                {
                    _state = CircuitState.Open;
                }
            }

            throw;
        }
    }
}
```

### Bulkhead Isolation

```csharp
public class BulkheadPolicy
{
    private readonly SemaphoreSlim _semaphore;
    private readonly TimeSpan _timeout;

    public BulkheadPolicy(int maxConcurrency, TimeSpan timeout)
    {
        _semaphore = new SemaphoreSlim(maxConcurrency, maxConcurrency);
        _timeout = timeout;
    }

    public async Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken ct)
    {
        if (!await _semaphore.WaitAsync(_timeout, ct))
        {
            throw new BulkheadRejectedException();
        }

        try
        {
            return await operation(ct);
        }
        finally
        {
            _semaphore.Release();
        }
    }
}

// Usage: Isolate external service calls
private readonly BulkheadPolicy _paymentBulkhead = new(maxConcurrency: 10, timeout: TimeSpan.FromSeconds(5));
private readonly BulkheadPolicy _inventoryBulkhead = new(maxConcurrency: 20, timeout: TimeSpan.FromSeconds(5));

await _paymentBulkhead.ExecuteAsync(ct => _paymentService.ChargeAsync(payment, ct), ct);
```

---
[Back to Overview](./OVERVIEW.md)

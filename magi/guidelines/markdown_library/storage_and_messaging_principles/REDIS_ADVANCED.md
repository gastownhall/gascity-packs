# Redis Advanced Patterns

### Rate Limiting with Sliding Window

```csharp
public class SlidingWindowRateLimiter
{
    private readonly IDatabase _redis;

    public async Task<bool> IsAllowedAsync(string key, int limit, TimeSpan window)
    {
        var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        var windowStart = now - (long)window.TotalMilliseconds;

        var script = @"
            redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
            local count = redis.call('ZCARD', KEYS[1])
            if count < tonumber(ARGV[2]) then
                redis.call('ZADD', KEYS[1], ARGV[3], ARGV[3])
                redis.call('PEXPIRE', KEYS[1], ARGV[4])
                return 1
            else
                return 0
            end";

        var result = await _redis.ScriptEvaluateAsync(
            script,
            new RedisKey[] { key },
            new RedisValue[] { windowStart, limit, now, (long)window.TotalMilliseconds });

        return (int)result == 1;
    }
}
```

### Distributed Lock with Fencing Token

```csharp
public class FencedLock
{
    private readonly IDatabase _redis;

    public async Task<(bool Acquired, long FencingToken)> AcquireAsync(string resource, TimeSpan expiry)
    {
        var fencingToken = await _redis.StringIncrementAsync($"fence:{resource}");

        var acquired = await _redis.StringSetAsync(
            $"lock:{resource}",
            fencingToken.ToString(),
            expiry,
            When.NotExists);

        if (!acquired)
        {
            return (false, 0);
        }

        return (true, fencingToken);
    }

    // Storage must check fencing token
    public async Task WriteWithFenceAsync(string resource, long fencingToken, object data)
    {
        // Include fencing token in write; storage rejects if token is stale
        await _storage.WriteAsync(resource, data, expectedFencingToken: fencingToken);
    }
}
```

### Leaderboard with Scores

```csharp
public class LeaderboardService
{
    private readonly IDatabase _redis;
    private const string LeaderboardKey = "game:leaderboard";

    public async Task UpdateScoreAsync(string userId, double score)
    {
        await _redis.SortedSetAddAsync(LeaderboardKey, userId, score);
    }

    public async Task<long?> GetRankAsync(string userId)
    {
        // Ranks are 0-based, reverse order (highest score = rank 0)
        return await _redis.SortedSetRankAsync(LeaderboardKey, userId, Order.Descending);
    }

    public async Task<List<LeaderboardEntry>> GetTopAsync(int count)
    {
        var entries = await _redis.SortedSetRangeByRankWithScoresAsync(
            LeaderboardKey, 0, count - 1, Order.Descending);

        return entries.Select((e, i) => new LeaderboardEntry
        {
            Rank = i + 1,
            UserId = e.Element.ToString(),
            Score = e.Score
        }).ToList();
    }
}
```

### Pub/Sub for Real-Time Notifications

```csharp
public class NotificationService
{
    private readonly ISubscriber _subscriber;
    private readonly IDatabase _database;

    public async Task PublishAsync(string userId, Notification notification)
    {
        var channel = $"notifications:{userId}";
        var message = JsonSerializer.Serialize(notification);
        await _subscriber.PublishAsync(channel, message);
    }

    public async Task SubscribeAsync(string userId, Action<Notification> handler, CancellationToken ct)
    {
        var channel = $"notifications:{userId}";

        await _subscriber.SubscribeAsync(channel, (_, message) =>
        {
            var notification = JsonSerializer.Deserialize<Notification>(message!);
            handler(notification!);
        });

        // Unsubscribe on cancellation
        ct.Register(() => _subscriber.Unsubscribe(channel));
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

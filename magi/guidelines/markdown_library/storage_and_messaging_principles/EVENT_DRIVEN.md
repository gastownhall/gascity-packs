# Event-Driven Patterns

### Outbox Pattern

Ensure events are published reliably alongside database changes:

```csharp
public class OrderService
{
    public async Task CreateOrderAsync(Order order, CancellationToken ct)
    {
        await using var transaction = await _dbContext.Database.BeginTransactionAsync(ct);

        try
        {
            // 1. Write business data
            _dbContext.Orders.Add(order);

            // 2. Write event to outbox table (same transaction)
            var outboxMessage = new OutboxMessage
            {
                Id = Guid.NewGuid(),
                EventType = "OrderCreated",
                Payload = JsonSerializer.Serialize(new OrderCreatedEvent(order)),
                CreatedAt = DateTimeOffset.UtcNow
            };
            _dbContext.OutboxMessages.Add(outboxMessage);

            await _dbContext.SaveChangesAsync(ct);
            await transaction.CommitAsync(ct);
        }
        catch
        {
            await transaction.RollbackAsync(ct);
            throw;
        }
    }
}

// Separate worker polls outbox and publishes events
public class OutboxPublisher : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            var messages = await GetUnpublishedMessagesAsync(ct);

            foreach (var message in messages)
            {
                try
                {
                    await PublishToServiceBusAsync(message, ct);
                    await MarkAsPublishedAsync(message.Id, ct);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to publish outbox message {MessageId}", message.Id);
                    await MarkAsFailedAsync(message.Id, ct);
                }
            }

            await Task.Delay(TimeSpan.FromSeconds(1), ct);
        }
    }
}
```

### Inbox Pattern (Idempotent Message Processing)

The complement to the Outbox pattern: ensure consumed messages are not processed twice.

```csharp
public class InboxPattern
{
    public async Task<bool> HandleMessageAsync(Message message)
    {
        // Check if already processed
        var exists = await _dbContext.InboxMessages
            .AnyAsync(m => m.MessageId == message.Id);

        if (exists)
        {
            _logger.LogInformation("Message {MessageId} already processed", message.Id);
            return true; // Idempotent success
        }

        using var transaction = await _dbContext.Database.BeginTransactionAsync();
        try
        {
            // Record message as processed
            _dbContext.InboxMessages.Add(new InboxMessage
            {
                MessageId = message.Id,
                MessageType = message.Type,
                ProcessedAt = DateTimeOffset.UtcNow
            });

            // Process business logic
            await ProcessBusinessLogicAsync(message);

            await _dbContext.SaveChangesAsync();
            await transaction.CommitAsync();
            return true;
        }
        catch
        {
            await transaction.RollbackAsync();
            throw;
        }
    }
}
```

### Idempotency Patterns

#### Idempotency Key Middleware

```csharp
public class IdempotencyMiddleware
{
    private readonly IDistributedCache _cache;

    public async Task InvokeAsync(HttpContext context, RequestDelegate next)
    {
        if (context.Request.Method == "POST" || context.Request.Method == "PUT")
        {
            var idempotencyKey = context.Request.Headers["Idempotency-Key"].FirstOrDefault();
            if (string.IsNullOrEmpty(idempotencyKey))
            {
                context.Response.StatusCode = 400;
                await context.Response.WriteAsync("Idempotency-Key header required");
                return;
            }

            var cacheKey = $"idempotency:{idempotencyKey}";

            // Check if already processed
            var cached = await _cache.GetAsync(cacheKey);
            if (cached != null)
            {
                var cachedResponse = JsonSerializer.Deserialize<CachedResponse>(cached);
                context.Response.StatusCode = cachedResponse.StatusCode;
                await context.Response.WriteAsync(cachedResponse.Body);
                return;
            }

            // Process request
            var originalBody = context.Response.Body;
            using var responseBody = new MemoryStream();
            context.Response.Body = responseBody;

            await next(context);

            // Cache response
            responseBody.Seek(0, SeekOrigin.Begin);
            var responseText = await new StreamReader(responseBody).ReadToEndAsync();
            var cacheEntry = new CachedResponse
            {
                StatusCode = context.Response.StatusCode,
                Body = responseText
            };

            await _cache.SetAsync(
                cacheKey,
                JsonSerializer.SerializeToUtf8Bytes(cacheEntry),
                new DistributedCacheEntryOptions
                {
                    AbsoluteExpirationRelativeToNow = TimeSpan.FromHours(24)
                });

            responseBody.Seek(0, SeekOrigin.Begin);
            await responseBody.CopyToAsync(originalBody);
        }
        else
        {
            await next(context);
        }
    }
}
```

#### Natural Idempotency

Design operations to be naturally idempotent — set a target value, don't increment relative to current state:

```csharp
// Instead of: IncrementBalance(amount)
// Use: SetBalance(newBalance, expectedVersion)
public async Task<bool> UpdateBalanceAsync(
    Guid accountId,
    decimal newBalance,
    int expectedVersion)
{
    var account = await _repository.GetAsync(accountId);
    if (account.Version != expectedVersion)
        return false; // Concurrent modification

    account.Balance = newBalance;
    account.Version++;
    await _repository.UpdateAsync(account);
    return true;
}
```

#### Message Deduplication with Process-Once Lock

```csharp
public class MessageDeduplicator
{
    private readonly IDistributedCache _cache;
    private readonly TimeSpan _deduplicationWindow = TimeSpan.FromHours(1);

    public async Task<T> ProcessOnceAsync<T>(
        string messageId,
        Func<Task<T>> processor)
    {
        var resultKey = $"msg:result:{messageId}";

        // Check for cached result
        var cached = await _cache.GetAsync(resultKey);
        if (cached != null)
        {
            return JsonSerializer.Deserialize<T>(cached);
        }

        // Distributed lock to prevent concurrent processing
        await using var lockHandle = await _lockManager.AcquireAsync(
            $"msg:lock:{messageId}",
            TimeSpan.FromSeconds(30));

        if (!lockHandle.Acquired)
        {
            throw new ProcessingInProgressException(messageId);
        }

        // Double-check after acquiring lock
        cached = await _cache.GetAsync(resultKey);
        if (cached != null)
        {
            return JsonSerializer.Deserialize<T>(cached);
        }

        // Process and cache result
        var result = await processor();
        await _cache.SetAsync(
            resultKey,
            JsonSerializer.SerializeToUtf8Bytes(result),
            new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = _deduplicationWindow
            });

        return result;
    }
}
```

### Saga Pattern — Orchestration vs Choreography

**Orchestration**: central orchestrator coordinates all steps. Centralized business logic, easier to understand and test, but creates a single point of failure and a potential bottleneck.

**Choreography**: services coordinate through events without a central orchestrator. No single point of failure, better scalability, looser coupling — but harder to understand the flow, distributed logic, and complex testing.

#### Orchestration Saga (full implementation)

```csharp
public class OrderSagaOrchestrator
{
    private readonly IServiceBus _bus;

    public async Task<SagaResult> ProcessOrderAsync(OrderSagaData data)
    {
        var sagaId = Guid.NewGuid();
        var state = new SagaState(sagaId);

        try
        {
            // Step 1: Reserve inventory
            state.InventoryReservation = await ExecuteStepAsync<ReserveInventoryCommand, InventoryReservation>(
                new ReserveInventoryCommand(data.Items),
                TimeSpan.FromSeconds(30));

            // Step 2: Process payment
            state.PaymentAuth = await ExecuteStepAsync<AuthorizePaymentCommand, PaymentAuthorization>(
                new AuthorizePaymentCommand(data.Payment),
                TimeSpan.FromSeconds(30));

            // Step 3: Create shipment
            state.ShipmentId = await ExecuteStepAsync<CreateShipmentCommand, string>(
                new CreateShipmentCommand(data.ShippingAddress),
                TimeSpan.FromSeconds(30));

            // Step 4: Confirm order
            state.OrderId = await ExecuteStepAsync<ConfirmOrderCommand, Guid>(
                new ConfirmOrderCommand(data),
                TimeSpan.FromSeconds(30));

            await MarkSagaCompleteAsync(sagaId, state);
            return SagaResult.Success(state.OrderId);
        }
        catch (SagaStepException ex)
        {
            await CompensateAsync(state, ex.FailedStep);
            await MarkSagaFailedAsync(sagaId, ex);
            return SagaResult.Failure(ex.Message);
        }
    }

    private async Task CompensateAsync(SagaState state, int failedStep)
    {
        // Compensate in reverse order from failure point
        var compensations = new List<Func<Task>>();

        if (failedStep > 3 && state.OrderId != null)
            compensations.Add(() => ExecuteCompensationAsync(new CancelOrderCommand(state.OrderId.Value)));
        if (failedStep > 2 && state.ShipmentId != null)
            compensations.Add(() => ExecuteCompensationAsync(new CancelShipmentCommand(state.ShipmentId)));
        if (failedStep > 1 && state.PaymentAuth != null)
            compensations.Add(() => ExecuteCompensationAsync(new ReversePaymentCommand(state.PaymentAuth)));
        if (failedStep > 0 && state.InventoryReservation != null)
            compensations.Add(() => ExecuteCompensationAsync(new ReleaseInventoryCommand(state.InventoryReservation)));

        // Execute compensations in parallel
        await Task.WhenAll(compensations.Select(c => c()));
    }
}
```

#### Choreography Saga (event-driven)

Each service handles its part and emits events. There is no orchestrator.

```csharp
public class InventoryService
{
    public async Task HandleAsync(OrderCreatedEvent @event)
    {
        try
        {
            var reservation = await ReserveInventoryAsync(@event.Items);
            await _bus.PublishAsync(new InventoryReservedEvent
            {
                SagaId = @event.SagaId,
                OrderId = @event.OrderId,
                ReservationId = reservation.Id
            });
        }
        catch (InsufficientInventoryException ex)
        {
            await _bus.PublishAsync(new SagaFailedEvent
            {
                SagaId = @event.SagaId,
                Reason = ex.Message,
                FailedService = "Inventory"
            });
        }
    }

    public async Task HandleAsync(SagaFailedEvent @event)
    {
        if (@event.FailedService != "Inventory")
        {
            // Compensate our successful operation
            await ReleaseReservationAsync(@event.SagaId);
        }
    }
}
```

### Saga Pattern (Simple Inline Form)

Coordinate multi-step distributed transactions with compensating actions:

```csharp
public class OrderSaga
{
    public async Task<SagaResult> ExecuteAsync(CreateOrderRequest request, CancellationToken ct)
    {
        var context = new SagaContext();

        try
        {
            // Step 1: Reserve inventory
            context.InventoryReservationId = await _inventoryService.ReserveAsync(request.Items, ct);

            // Step 2: Process payment
            context.PaymentId = await _paymentService.ChargeAsync(request.Payment, ct);

            // Step 3: Create order
            context.OrderId = await _orderService.CreateAsync(request, ct);

            // Step 4: Confirm inventory
            await _inventoryService.ConfirmReservationAsync(context.InventoryReservationId, ct);

            return SagaResult.Success(context.OrderId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Saga failed, executing compensation");
            await CompensateAsync(context, ct);
            return SagaResult.Failure(ex.Message);
        }
    }

    private async Task CompensateAsync(SagaContext context, CancellationToken ct)
    {
        // Compensate in reverse order
        if (context.PaymentId != null)
        {
            try { await _paymentService.RefundAsync(context.PaymentId, ct); }
            catch (Exception ex) { _logger.LogError(ex, "Failed to refund payment"); }
        }

        if (context.InventoryReservationId != null)
        {
            try { await _inventoryService.CancelReservationAsync(context.InventoryReservationId, ct); }
            catch (Exception ex) { _logger.LogError(ex, "Failed to cancel inventory reservation"); }
        }
    }
}
```

### Cosmos Event Store with Optimistic Concurrency

```csharp
public interface IEventStore
{
    Task<long> AppendEventsAsync(string streamId, long expectedVersion, IEnumerable<Event> events);
    Task<IReadOnlyList<Event>> GetEventsAsync(string streamId, long fromVersion = 0);
    IAsyncEnumerable<Event> SubscribeToStream(string streamId, long fromVersion = 0);
}

public class CosmosEventStore : IEventStore
{
    public async Task<long> AppendEventsAsync(string streamId, long expectedVersion, IEnumerable<Event> events)
    {
        var batch = _container.CreateTransactionalBatch(new PartitionKey(streamId));

        // Optimistic concurrency check
        var streamHeader = await GetStreamHeaderAsync(streamId);
        if (streamHeader.Version != expectedVersion)
            throw new ConcurrencyException();

        long version = expectedVersion;
        foreach (var @event in events)
        {
            version++;
            var eventDoc = new EventDocument
            {
                Id = $"{streamId}:{version:D10}",
                StreamId = streamId,
                Version = version,
                EventType = @event.GetType().Name,
                EventData = JsonSerializer.Serialize(@event),
                Timestamp = DateTimeOffset.UtcNow
            };
            batch.CreateItem(eventDoc);
        }

        // Update stream header
        streamHeader.Version = version;
        batch.UpsertItem(streamHeader);

        var response = await batch.ExecuteAsync();
        if (!response.IsSuccessStatusCode)
            throw new EventStoreException(response.StatusCode);

        return version;
    }
}
```

### Event Projection

Build read models from events:

```csharp
public class OrderProjection : IEventProjection
{
    private readonly IReadModelStore _store;

    public async Task HandleAsync(Event @event, EventMetadata metadata)
    {
        switch (@event)
        {
            case OrderCreated e:
                await _store.CreateAsync(new OrderReadModel
                {
                    OrderId = e.OrderId,
                    CustomerId = e.CustomerId,
                    Status = "Created",
                    Items = e.Items,
                    CreatedAt = metadata.Timestamp
                });
                break;
            case OrderShipped e:
                await _store.UpdateAsync(e.OrderId, order =>
                {
                    order.Status = "Shipped";
                    order.ShippedAt = e.ShippedAt;
                });
                break;
            case OrderCancelled e:
                await _store.UpdateAsync(e.OrderId, order =>
                {
                    order.Status = "Cancelled";
                    order.CancelledAt = e.CancelledAt;
                    order.CancellationReason = e.Reason;
                });
                break;
        }
    }
}
```

### Snapshot Strategy

Optimize replay by storing periodic snapshots:

```csharp
public class SnapshotStore
{
    private const int SnapshotFrequency = 100;

    public async Task<T> LoadAggregateAsync<T>(string aggregateId) where T : AggregateRoot, new()
    {
        // Try to load from snapshot
        var snapshot = await GetLatestSnapshotAsync<T>(aggregateId);
        var aggregate = snapshot?.Aggregate ?? new T();
        var fromVersion = snapshot?.Version ?? 0;

        // Replay events since snapshot
        var events = await _eventStore.GetEventsAsync(aggregateId, fromVersion);
        foreach (var @event in events)
        {
            aggregate.Apply(@event);
        }

        // Create new snapshot if needed
        if (aggregate.Version - fromVersion >= SnapshotFrequency)
        {
            await SaveSnapshotAsync(aggregateId, aggregate);
        }

        return aggregate;
    }
}
```

### Event Sourcing — Aggregate Root Pattern

Store state as sequence of events:

```csharp
public abstract class AggregateRoot
{
    private readonly List<DomainEvent> _uncommittedEvents = new();
    public int Version { get; private set; }

    protected void ApplyEvent(DomainEvent @event)
    {
        When(@event);
        Version++;
        _uncommittedEvents.Add(@event);
    }

    protected abstract void When(DomainEvent @event);

    public IReadOnlyList<DomainEvent> GetUncommittedEvents() => _uncommittedEvents.AsReadOnly();
    public void ClearUncommittedEvents() => _uncommittedEvents.Clear();
}

public class Order : AggregateRoot
{
    public Guid Id { get; private set; }
    public OrderStatus Status { get; private set; }
    public List<OrderItem> Items { get; private set; } = new();

    public void Create(Guid orderId, List<OrderItem> items)
    {
        ApplyEvent(new OrderCreatedEvent(orderId, items));
    }

    public void Ship()
    {
        if (Status != OrderStatus.Confirmed)
            throw new InvalidOperationException("Cannot ship unconfirmed order");

        ApplyEvent(new OrderShippedEvent(Id, DateTimeOffset.UtcNow));
    }

    protected override void When(DomainEvent @event)
    {
        switch (@event)
        {
            case OrderCreatedEvent e:
                Id = e.OrderId;
                Items = e.Items;
                Status = OrderStatus.Created;
                break;
            case OrderShippedEvent e:
                Status = OrderStatus.Shipped;
                break;
        }
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

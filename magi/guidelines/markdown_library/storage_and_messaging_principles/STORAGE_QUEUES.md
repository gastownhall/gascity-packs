# Azure Storage Queues

### What It Are

Azure Storage Queues provide simple, reliable message queuing for asynchronous communication between components. Messages are stored persistently and can be consumed by one or more receivers.

### Core Strengths

- **Simplicity**: Minimal configuration; part of storage account
- **Cost-Effective**: Very cheap for moderate volumes
- **Reliability**: Messages persisted; survive receiver failures
- **Scale**: Handles millions of messages
- **Visibility Timeout**: Messages invisible during processing; reappear if not deleted
- **Large Messages**: Up to 64KB per message (or use claim check pattern for larger)

### Core Weaknesses

- **At-Least-Once Delivery**: Duplicates possible; consumers must be idempotent
- **No Ordering Guarantee**: FIFO not guaranteed under load
- **Limited Features**: No dead-letter queue, no scheduling, no topics/subscriptions
- **Polling Required**: Receivers must poll; no push-based delivery
- **No Message Priority**: All messages treated equally

### Ideal Use Cases

- Simple decoupling of application components
- Work queues for background processing
- Load leveling for spiky workloads
- Lightweight async communication within single application
- Cost-sensitive scenarios with moderate requirements

### Avoid When

- Message ordering is required (use Service Bus)
- Complex routing, topics, subscriptions needed (use Service Bus or RabbitMQ)
- Dead-letter queue or scheduled delivery required
- At-most-once delivery semantics needed
- High throughput with strict latency requirements

### Message Lifecycle

```
1. Sender: Add message to queue
2. Message: Visible in queue
3. Receiver: Get message (visibility timeout starts)
4. Message: Invisible to other receivers
5. Receiver: Process message
6. Receiver: Delete message (success) OR timeout expires (failure)
7. If timeout: Message becomes visible again (retry)
```

### Visibility Timeout

- Default: 30 seconds
- Maximum: 7 days
- Set based on expected processing time plus margin
- Update timeout during long processing to prevent duplicate delivery

### Claim Check Pattern

For messages larger than 64KB:
1. Store payload in Blob Storage
2. Put blob reference in queue message
3. Receiver retrieves blob, processes, deletes blob and message

```json
{
  "blobContainer": "payloads",
  "blobName": "messages/2024/06/20/abc123.json",
  "contentType": "application/json"
}
```

### Code Pattern

```csharp
// Producer
await queueClient.SendMessageAsync(JsonSerializer.Serialize(order));

// Consumer (polling)
while (true)
{
    var messages = await queueClient.ReceiveMessagesAsync(maxMessages: 10, visibilityTimeout: TimeSpan.FromMinutes(5));

    foreach (var message in messages.Value)
    {
        try
        {
            var order = JsonSerializer.Deserialize<Order>(message.Body.ToString());
            await ProcessOrder(order);
            await queueClient.DeleteMessageAsync(message.MessageId, message.PopReceipt);
        }
        catch (Exception ex)
        {
            // Log error; message will reappear after visibility timeout
            logger.LogError(ex, "Failed to process message {MessageId}", message.MessageId);
        }
    }

    if (messages.Value.Length == 0)
        await Task.Delay(TimeSpan.FromSeconds(1)); // Backoff when empty
}
```

### Comparison: Storage Queues vs Service Bus

| Feature                  | Storage Queues | Service Bus                  |
|--------------------------|----------------|------------------------------|
| **Max Message Size**     | 64 KB          | 256 KB - 100 MB              |
| **Max Queue Size**       | 500 TB         | 1-80 GB                      |
| **Delivery**             | At-least-once  | At-least-once / At-most-once |
| **Ordering**             | No guarantee   | FIFO with sessions           |
| **Dead Letter**          | No             | Yes                          |
| **Scheduled Delivery**   | No             | Yes                          |
| **Topics/Subscriptions** | No             | Yes                          |
| **Transactions**         | No             | Yes                          |
| **Duplicate Detection**  | No             | Yes                          |
| **Cost**                 | Very low       | Higher                       |

Use Storage Queues for simple scenarios. Use Service Bus when you need advanced features.

---
[Back to Overview](./OVERVIEW.md)

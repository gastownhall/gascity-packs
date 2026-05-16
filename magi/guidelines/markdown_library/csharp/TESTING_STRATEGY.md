# Testing Strategy

### Test Project Structure

Mirror source structure in test projects:

```
Company.Product.Core.Tests/
├── Services/
│   └── OrderServiceTests.cs
├── ValueObjects/
│   └── MoneyTests.cs
└── Entities/
    └── OrderTests.cs
```

### Test Naming

`MethodName_Scenario_ExpectedResult`:

```csharp
[Fact]
public async Task CreateOrder_WithValidCommand_ReturnsSuccessResult() { }

[Fact]
public async Task CreateOrder_WithEmptyLines_ReturnsFailureResult() { }

[Fact]
public async Task CreateOrder_WhenRepositoryThrows_PropagatesException() { }
```

### Arrange-Act-Assert Structure

```csharp
[Fact]
public async Task ProcessOrder_WithValidPayment_UpdatesOrderStatus() {
    // Arrange
    var order = new Order { Id = Guid.NewGuid(), Total = 100m, Status = OrderStatus.Pending };
    var paymentGateway = Substitute.For<IPaymentGateway>();
    paymentGateway.ChargeAsync(Arg.Any<decimal>(), Arg.Any<PaymentMethod>(), Arg.Any<CancellationToken>())
        .Returns(Task.FromResult(PaymentResult.Success));
    var sut = new OrderService(_repository, paymentGateway, _logger);

    // Act
    var result = await sut.ProcessAsync(order, CancellationToken.None);

    // Assert
    Assert.Equal(OrderStatus.Confirmed, result.Status);
    await paymentGateway.Received(1).ChargeAsync(100m, Arg.Any<PaymentMethod>(), Arg.Any<CancellationToken>());
}
```

### Test Data Builders

```csharp
public sealed class OrderBuilder {
    private Guid _id = Guid.NewGuid();
    private string _customerId = "customer-1";
    private decimal _total = 100m;
    private OrderStatus _status = OrderStatus.Pending;

    public OrderBuilder WithId(Guid id) { _id = id; return this; }
    public OrderBuilder WithCustomerId(string customerId) { _customerId = customerId; return this; }
    public OrderBuilder WithTotal(decimal total) { _total = total; return this; }
    public OrderBuilder WithStatus(OrderStatus status) { _status = status; return this; }
    public Order Build() => new() { Id = _id, CustomerId = _customerId, Total = _total, Status = _status };
}
```

### Integration Testing

```csharp
public sealed class OrderApiTests : IClassFixture<WebApplicationFactory<Program>> {
    private readonly HttpClient _client;

    public OrderApiTests(WebApplicationFactory<Program> factory) {
        _client = factory.WithWebHostBuilder(builder => {
            builder.ConfigureServices(services => {
                services.RemoveAll<IOrderRepository>();
                services.AddSingleton<IOrderRepository, InMemoryOrderRepository>();
            });
        }).CreateClient();
    }

    [Fact]
    public async Task GetOrder_WhenExists_ReturnsOrder() {
        var response = await _client.GetAsync("/api/orders/123");
        response.EnsureSuccessStatusCode();
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

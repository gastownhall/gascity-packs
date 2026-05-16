# HTTP Client and API Integration

### HttpClient Configuration

Configure through `provideHttpClient()` with functional interceptors and `withFetch()`:

```typescript
provideHttpClient(
    withInterceptors([authInterceptor, errorInterceptor]),
    withFetch(),
)
```

### Service-Level API Encapsulation

Components never call `HttpClient` directly. Services own URL construction, transformations, and error handling:

```typescript
@Injectable({ providedIn: 'root' })
export class OrderApiService {
    private readonly http = inject(HttpClient);
    private readonly baseUrl = inject(API_BASE_URL);

    getOrders(filters: OrderFilters): Observable<Order[]> {
        return this.http.get<Order[]>(`${this.baseUrl}/orders`, { params });
    }
}
```

### Functional Interceptors

Interceptors transform requests and responses globally. Ordering matters—register in the sequence they should wrap requests.

### Retry and Timeout Strategy

- `retry()`: Use exponential backoff for server errors (5xx). **Never retry 4xx errors.**
- `timeout()`: Hard timeout for unresponsive endpoints.

### Response Typing

Always provide a type parameter to `HttpClient` methods. Never consume `any`-typed responses. Define DTOs matching the API contract; transform to domain models at the service boundary if needed.

### Boundary Schema Validation

Validate response payloads with `zod` or `class-validator` before passing into typed code. The compiler trusts your DTOs; the network does not.

### Cancellation

Navigating away from a component mid-request should cancel in-flight requests. The `async` pipe and `takeUntilDestroyed()` handle this. `switchMap` in search patterns cancels prior requests automatically.

---
[Back to Overview](./OVERVIEW.md)

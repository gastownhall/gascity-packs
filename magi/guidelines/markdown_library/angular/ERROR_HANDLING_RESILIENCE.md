# Error Handling and Resilience

### Global Error Handler

Implement `ErrorHandler` to catch unhandled exceptions globally:

```typescript
@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
    handleError(error: unknown): void {
        const normalized = this.normalizeError(error);
        this.logger.error(normalized);
        this.notification.showError('An unexpected error occurred');
    }
}
```
Register in `app.config.ts`: `providers: [{ provide: ErrorHandler, useClass: GlobalErrorHandler }]`.

### HTTP Error Classification

Classify by status code:
- **401 Unauthorized**: Attempt token refresh or redirect to login.
- **403 Forbidden**: Display access denied message.
- **404 Not Found**: Navigate to not-found view or show empty state.
- **409 Conflict**: Reload data and prompt user to retry.
- **422 Unprocessable**: Map server errors to form control errors.
- **5xx Server Errors**: Retry with exponential backoff.

### Component-Level Error Boundaries

Wrap feature sections in error boundary components to catch rendering errors and display fallback UI without crashing the whole application.

### Loading and Error State Pattern

Templates always account for all three states: loading, error, and success.

```html
@if (store.loading()) {
    <app-skeleton-loader />
} @else if (store.error(); as error) {
    <app-error-message [message]="error" (retry)="store.loadOrders()" />
} @else {
    @for (order of store.orders(); track order.id) {
        <app-order-card [order]="order" />
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

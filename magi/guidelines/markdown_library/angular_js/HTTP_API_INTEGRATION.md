# HTTP and API Integration

### `$http` Service

All communication flows through `$http`. Raw `XMLHttpRequest` or `fetch()` bypasses the digest cycle and interceptors.

### Service Encapsulation

**Components never call `$http` directly.** Encapsulate in dedicated services:

```javascript
function OrderService($http, API_BASE_URL) {
    return {
        getAll: function() {
            return $http.get(API_BASE_URL + '/orders').then(extractData);
        }
    };
    function extractData(response) { return response.data; }
}
```

### Interceptors

Modify requests/responses globally (e.g., auth, error normalization, loading indicators). Register in `.config()` via `$httpProvider.interceptors`.

### Promise Handling

Always handle success (`.then()`) and failure (`.catch()`). Empty `.catch()` blocks are **prohibited**. Return the promise chain from service methods. `.success()` and `.error()` are **forbidden**.

### Response Caching

Use `{ cache: true }` for stable data. Invalidate manually via `$cacheFactory` if needed.

---
[Back to Overview](./OVERVIEW.md)

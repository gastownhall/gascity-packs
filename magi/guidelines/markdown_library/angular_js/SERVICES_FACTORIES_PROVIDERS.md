# Services, Factories, and Providers

### Service Type Selection

- **`.service()`**: Instantiated with `new`. Use for constructor functions.
- **`.factory()`**: Invoked as a function. Returns an API object. **Default choice.**
- **`.provider()`**: Configurable during `.config()`. Use only when pre-instantiation configuration is required.

### Service Design

- **Single responsibility**: One service does one thing.
- **Stateless by default**: Prefer stateless services.
- **Return promises**: All async operations must return a `$q` promise.
- **Minimal API**: Expose only what is necessary.

### Reference Factory Implementation

```javascript
OrderService.$inject = ['$http', 'API_BASE'];
function OrderService($http, API_BASE) {
    return {
        getAll: getAll
    };

    function getAll() {
        return $http.get(API_BASE + '/orders').then(extractData).catch(handleError);
    }
    function extractData(response) { return response.data; }
    function handleError(error) { return $q.reject(error); }
}
```

### Shared State Patterns

- Exactly one service owns each piece of state.
- Access state through getters, never direct mutation by consumers.
- Use explicit setter methods for mutations.

---
[Back to Overview](./OVERVIEW.md)

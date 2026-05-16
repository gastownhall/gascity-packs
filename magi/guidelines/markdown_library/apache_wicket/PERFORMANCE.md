# Performance

### Session Size Optimization

Minimize serialized page size by:
- Using `LoadableDetachableModel` consistently
- Limiting page history via page-store configuration
- Marking non-essential fields as `transient`
- Using stateless pages where possible

### Component Tree Optimization

- Use lazy loading for heavy panels.
- Limit repeater sizes with pagination.
- Physically `remove()` invisible components when they won't be shown again rather than just hiding them.
- Keep component hierarchies shallow where possible.

### Repeater Optimization

For large lists use `DataView` with `IDataProvider` for pagination and efficient data access. The provider's `iterator()` loads only visible items; `size()` provides total count for paging. Each item gets `LoadableDetachableModel` for efficient serialization:

```java
add(new DataView<Order>("orders", new OrderDataProvider()) {
    @Override
    protected void populateItem(Item<Order> item) {
        item.add(new Label("number", new PropertyModel<>(item.getModel(), "number")));
    }
});
add(new PagingNavigator("navigator", dataView));
```

`ListView` is forbidden for large datasets — use `DataView` + `IDataProvider`.

---
[Back to Overview](./OVERVIEW.md)

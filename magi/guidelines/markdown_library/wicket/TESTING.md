# Testing

### WicketTester

`WicketTester` simulates requests and verifies responses without a servlet container.

| Method | Verifies |
|:-------|:---------|
| `startPage()` | Start a page |
| `assertRenderedPage()` | Verify rendering |
| `assertComponent()` | Check components |
| `assertLabel()` | Verify labels |

**No web server required for comprehensive component testing.**

### Form Testing

Use `FormTester` from `tester.newFormTester()` to simulate form submission. Set values with `setValue()`, submit with `submit()`. Verify error messages with `assertErrorMessages()`. Verify successful submission by checking rendered page or model state.

### Ajax Testing

Click Ajax links with `clickLink(path, true)` where `true` indicates Ajax. Execute Ajax events with `executeAjaxEvent()`. Verify Ajax response targets with `assertComponentOnAjaxResponse()`. Test behavior attachment and event handling.

### Mocking Dependencies

Mock services using standard mocking frameworks. Create test application subclass that overrides service resolution. With Spring, configure test application context with mock beans. Verify component behavior with mocked data sources.

---
[Back to Overview](./OVERVIEW.md)

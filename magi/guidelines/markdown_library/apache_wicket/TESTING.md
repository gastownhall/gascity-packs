# Testing

### WicketTester

`WicketTester` simulates requests and verifies responses without a servlet container. No web server required for comprehensive component testing:

```java
@Test
void homePage_renders_label() {
    WicketTester tester = new WicketTester(new MyWicketApplication());
    tester.startPage(HomePage.class);
    tester.assertRenderedPage(HomePage.class);
    tester.assertLabel("welcomeLabel", "Welcome");
    tester.assertNoErrorMessage();
}
```

### Form Testing

Use `FormTester` from `tester.newFormTester()` to simulate form submission. Set values with `setValue()`, submit with `submit()`. Verify error messages with `assertErrorMessages()`. Verify successful submission by checking rendered page or model state:

```java
FormTester form = tester.newFormTester("orderForm");
form.setValue("customerName", "Acme Corp");
form.setValue("email", "buyer@acme.example");
form.setValue("quantity", "5");
form.submit();
tester.assertNoErrorMessage();
```

### Ajax Testing

Click Ajax links with `clickLink(path, true)` where `true` indicates Ajax. Execute Ajax events with `executeAjaxEvent()`. Verify Ajax response targets with `assertComponentOnAjaxResponse()`. Test behavior attachment and event handling.

### Mocking Dependencies

Mock services using standard mocking frameworks. Create a test application subclass that overrides service resolution. With Spring, configure a test application context with mock beans. Verify component behavior with mocked data sources.

---
[Back to Overview](./OVERVIEW.md)

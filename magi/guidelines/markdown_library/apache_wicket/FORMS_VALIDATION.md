# Forms and Validation

### Form Structure

Wicket forms bind to HTML form elements and manage child `FormComponent` validation and submission. Use `CompoundPropertyModel` on the form for automatic property binding. Override `onSubmit()` for success handling and `onError()` for validation-failure handling. Add a `FeedbackPanel` to display validation messages:

```java
public class OrderForm extends Form<Order> {

    public OrderForm(String id, IModel<Order> orderModel) {
        super(id, new CompoundPropertyModel<>(orderModel));
        add(new TextField<>("customerName").setRequired(true));
        add(new EmailTextField("email").setRequired(true));
        add(new NumberTextField<>("quantity", Integer.class)
                .setMinimum(1)
                .setMaximum(1000)
                .setRequired(true));
        add(new FeedbackPanel("feedback"));
    }

    @Override
    protected void onSubmit() {
        super.onSubmit();
        // persist via injected service
    }

    @Override
    protected void onError() {
        super.onError();
        // log or surface validation failure
    }
}
```

### Form Components

| Component | Purpose |
|:----------|:--------|
| `TextField<T>` | Single-line text |
| `TextArea<T>` | Multi-line text |
| `PasswordTextField` | Password input |
| `EmailTextField` | Email with built-in validation |
| `NumberTextField<T>` | Type-safe numeric input with `min`/`max` |
| `DropDownChoice<T>` | Select dropdown |
| `CheckBox` | Boolean |
| `RadioChoice<T>` | Radio group |
| `CheckBoxMultipleChoice<T>` | Multiple-select |
| `FileUploadField` | File upload |

### Validation

Validators attach to `FormComponent`s and execute during form processing. Built-in validators include `StringValidator` (length), `PatternValidator` (regex), `RangeValidator` (numeric range), and `EmailAddressValidator` (email format). Create custom validators implementing `IValidator`. Override the form's `onValidate()` for cross-field validation.

**Always validate input on the server side regardless of any client-side validation.** Client-side validation is a convenience for users; server-side validation is the security gate.

---
[Back to Overview](./OVERVIEW.md)

# Forms and Validation

### Form Structure

Wicket forms bind to HTML form elements and manage child `FormComponent` validation and submission. Use `CompoundPropertyModel` on the form for automatic property binding. Override `onSubmit()` for success handling and `onError()` for validation failure handling. Add `FeedbackPanel` to display validation messages.

### Form Components

| Component | Use |
|:----------|:----|
| `TextField` | Single-line text |
| `TextArea` | Multi-line text |
| `PasswordTextField` | Passwords |
| `EmailTextField` | Built-in email validation |
| `NumberTextField` | Type-safe min/max |
| `DropDownChoice` | Select dropdowns |
| `CheckBox` | Boolean |
| `RadioChoice` | Radio groups |
| `CheckBoxMultipleChoice` | Multiple selection |
| `FileUploadField` | File uploads |

### Validation

Validators attach to `FormComponent`s and execute during form processing.

| Built-in validator | Validates |
|:-------------------|:----------|
| `StringValidator` | Length |
| `PatternValidator` | Regex |
| `RangeValidator` | Numeric range |
| `EmailAddressValidator` | Email format |

Create custom validators implementing `IValidator` interface. Override form's `onValidate()` for cross-field validation.

**Always validate input on the server side regardless of any client-side validation.** Client-side validation is a convenience for users; server-side validation is the security gate.

---
[Back to Overview](./OVERVIEW.md)

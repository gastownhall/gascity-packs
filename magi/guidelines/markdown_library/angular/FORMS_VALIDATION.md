# Forms and Validation

### Reactive Forms as Default

Reactive forms are the standard for all implementations. Template-driven forms lack type safety and are harder to test.

### Typed Form Groups

Angular's typed reactive forms enforce type safety at the control level. Use `NonNullableFormBuilder` to create forms where controls reset to initial values rather than `null`:

```typescript
private readonly fb = inject(NonNullableFormBuilder);

readonly form = this.fb.group<OrderForm>({
    customerId: this.fb.control('', [Validators.required]),
    lineItems: this.fb.array<FormGroup<LineItemForm>>([]),
    priority: this.fb.control(Priority.Normal),
});
```

### Validation Strategy

- **Built-in validators**: `required`, `minLength`, `pattern`, `email`, etc.
- **Custom validators**: Pure functions returning `ValidationErrors | null`.
- **Cross-field validation**: Applies at the `FormGroup` level (e.g., matching passwords).
- **Display validation errors**: Only after `touched` or `dirty`. Premature errors degrade UX.

```html
@if (control.invalid && (control.dirty || control.touched)) {
    <span class="error">{{ errorMessage() }}</span>
}
```

### Dynamic Forms

Use `FormArray` for collections that users add to/remove from. Track by index or unique identifier in the template `@for` block.

### Form Submission

Disable the submit button while the form is invalid or submission is in progress. Handle submission through a service method accepting the strongly-typed form value. Use `form.getRawValue()` for a complete snapshot.

---
[Back to Overview](./OVERVIEW.md)

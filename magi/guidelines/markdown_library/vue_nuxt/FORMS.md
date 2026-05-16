# Form Handling and Validation

### VeeValidate Setup

VeeValidate 4.x integrates with the Composition API via `useForm` and `useField` composables. Use zod or yup for validation schema definitions — schema-based validation provides TypeScript type inference for form values, centralizes validation rules, and enables server-side schema reuse. **Define the schema once, use it for both client-side validation and server-side request validation in Nitro routes.**

### Form Composition Patterns

`useForm` accepts a `validationSchema` and returns `handleSubmit`, `errors`, `values`, `resetForm`, `setFieldValue`, and `meta` (`dirty`, `valid`, `touched`). Use `useField` for individual fields that need independent validation state or custom input components. Define initial values via `useForm`'s `initialValues` option — never leave form state uninitialized, as `undefined` initial values cause hydration mismatches when the form renders differently on server and client.

| Constraint | Required |
|:-----------|:---------|
| Submission | `handleSubmit` wraps the submit handler with validation. The handler receives typed, validated values. **Never access form values directly in the submit handler** — use the `values` argument provided by `handleSubmit` |
| Server validation | Server validation errors map to field-level errors via `setErrors()` or `setFieldError()`. Display server errors alongside client errors in the same UI |
| Dirty tracking | Use `meta.dirty` to enable/disable submit buttons and prompt users about unsaved changes on navigation. Combine with `onBeforeRouteLeave` guard to prevent accidental data loss |

### Validation Schema Patterns

Define schemas in a shared location (e.g., `shared/schemas/` or a dedicated validation composable) when the same schema validates both client-side forms and server-side request bodies. zod schemas double as TypeScript type sources via `z.infer`. Compose complex schemas from reusable parts: a `baseAddressSchema` extends into `shippingAddressSchema` and `billingAddressSchema`. **Custom validation messages must be user-friendly, not developer-facing.** "Email is required" — not "string.required validation failed".

### Form SSR Considerations

Forms render on the server with their initial values. Ensure initial values are deterministic and available server-side. Client-only validation (password strength meters, real-time availability checks) wraps in `onMounted` or `<ClientOnly>`. Form submission handlers (`$fetch` calls, store actions) execute only on the client — they do not need SSR guards. Focus management and scroll-to-error behavior belongs in `onMounted` since it requires DOM access.

---
[Back to Overview](./OVERVIEW.md)

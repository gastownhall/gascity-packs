# Forms

Form handling in React with TypeScript requires typed form values, typed validation, and integration with the component's state management and submission logic.

### Form Libraries

Use a form library (**React Hook Form**, **Formik**, or **TanStack Form**) for forms with more than 2–3 fields. Form libraries provide:

- Validation integration
- Dirty tracking
- Submission handling
- Field-level error state
- Performance optimization (React Hook Form uses uncontrolled components by default, reducing re-renders)

Define form values as a TypeScript interface and pass it as the generic parameter to `useForm<FormValues>()`.

### Schema-Driven Validation

Integrate form validation with **zod** or **yup** schemas. React Hook Form's `@hookform/resolvers` provides `zodResolver` for seamless integration. The schema defines validation rules and the TypeScript type simultaneously:

```typescript
const formSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

type FormValues = z.infer<typeof formSchema>;
```

Changes to the schema automatically update both the runtime validation and the compile-time type.

### Server-Side Validation

**Validate on the server regardless of client-side validation.** Client-side validation improves UX by providing immediate feedback. Server-side validation enforces business rules. A user with browser DevTools can bypass any client-side validation. Map server validation errors to form field errors for consistent error display.

---
[Back to Overview](./OVERVIEW.md)

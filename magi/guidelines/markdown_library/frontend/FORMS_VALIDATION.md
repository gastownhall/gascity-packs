# Form Handling and Validation

### Schema-First Forms with Zod + React Hook Form

```typescript
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

// Advanced Zod schema patterns
const userSchema = z.object({
  email: z.string().email().toLowerCase().trim(),
  age: z.coerce.number().min(18).max(100),
  password: z.string()
    .min(8)
    .regex(/[A-Z]/, 'Must contain uppercase')
    .regex(/[a-z]/, 'Must contain lowercase')
    .regex(/[0-9]/, 'Must contain number'),
  confirmPassword: z.string(),
  role: z.enum(['admin', 'user', 'guest']),
  preferences: z.object({
    newsletter: z.boolean(),
    notifications: z.boolean()
  }).optional(),
  tags: z.array(z.string()).min(1).max(5)
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ['confirmPassword']
})

type UserFormData = z.infer<typeof userSchema>

function UserForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isDirty },
    watch,
    setValue,
    reset
  } = useForm<UserFormData>({
    resolver: zodResolver(userSchema),
    defaultValues: {
      role: 'user',
      preferences: {
        newsletter: false,
        notifications: true
      }
    }
  })

  const watchRole = watch('role')

  return (/* form JSX */)
}
```

### Field Arrays

```typescript
import { useFieldArray, useForm } from 'react-hook-form'

function DynamicForm() {
  const { control, register } = useForm()
  const { fields, append, remove, move } = useFieldArray({
    control,
    name: 'items'
  })

  return (
    <div>
      {fields.map((field, index) => (
        <div key={field.id}>
          <input {...register(`items.${index}.name`)} />
          <button onClick={() => remove(index)}>Remove</button>
        </div>
      ))}
      <button onClick={() => append({ name: '' })}>Add Item</button>
    </div>
  )
}
```

### Practical Contact Form

```tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import type { FC } from 'react'

const contactSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  phone: z.string().regex(/^\d{10}$/, 'Phone must be 10 digits').optional().or(z.literal('')),
  message: z.string().min(10, 'Message must be at least 10 characters'),
})

type ContactFormData = z.infer<typeof contactSchema>

const ContactForm: FC = () => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
  })

  const onSubmit = async (data: ContactFormData) => {
    try {
      await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      reset()
    } catch (error) {
      console.error('Form submission failed:', error)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-gray-700">Name</label>
        <input {...register('name')} type="text" id="name" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm" />
        {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name.message}</p>}
      </div>
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
        <input {...register('email')} type="email" id="email" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm" />
        {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>}
      </div>
      <div>
        <label htmlFor="phone" className="block text-sm font-medium text-gray-700">Phone (Optional)</label>
        <input {...register('phone')} type="tel" id="phone" className="mt-1 block w-full rounded-md border-gray-300 shadow-sm" />
        {errors.phone && <p className="mt-1 text-sm text-red-600">{errors.phone.message}</p>}
      </div>
      <div>
        <label htmlFor="message" className="block text-sm font-medium text-gray-700">Message</label>
        <textarea {...register('message')} id="message" rows={4} className="mt-1 block w-full rounded-md border-gray-300 shadow-sm" />
        {errors.message && <p className="mt-1 text-sm text-red-600">{errors.message.message}</p>}
      </div>
      <button type="submit" disabled={isSubmitting} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
        {isSubmitting ? 'Sending...' : 'Send Message'}
      </button>
    </form>
  )
}

export default ContactForm
```

**Form Rules:**

- Always use React Hook Form for forms with more than 2 fields.
- Always validate with Zod schemas for type safety and runtime validation.
- Extract form schemas to separate files if used in multiple places.
- Use `zodResolver` to connect Zod schemas with React Hook Form.
- Display validation errors inline near their fields.
- Use `aria-invalid` and `role="alert"` on error messages.
- Disable submit button during submission.
- Reset form after successful submission.
- Handle server errors explicitly with user-friendly messages.

---
[Back to Overview](./OVERVIEW.md)

# Styling and Theme System

### Centralized Theme Configuration

```typescript
export const theme = {
  colors: {
    primary: {
      50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
      500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
    },
    neutral: {
      50: '#f9fafb', 100: '#f3f4f6', 200: '#e5e7eb', 300: '#d1d5db', 400: '#9ca3af',
      500: '#6b7280', 600: '#4b5563', 700: '#374151', 800: '#1f2937', 900: '#111827',
    },
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  },
  spacing: {
    xs: '0.25rem', sm: '0.5rem', md: '1rem', lg: '1.5rem', xl: '2rem',
    '2xl': '3rem', '3xl': '4rem',
  },
  fontSize: {
    xs: '0.75rem', sm: '0.875rem', base: '1rem', lg: '1.125rem', xl: '1.25rem',
    '2xl': '1.5rem', '3xl': '1.875rem', '4xl': '2.25rem',
  },
  fontWeight: { normal: '400', medium: '500', semibold: '600', bold: '700' },
  borderRadius: {
    none: '0', sm: '0.125rem', md: '0.375rem', lg: '0.5rem', xl: '0.75rem', full: '9999px',
  },
  breakpoints: { sm: '640px', md: '768px', lg: '1024px', xl: '1280px', '2xl': '1536px' },
}

export type Theme = typeof theme
```

### Tailwind Configuration

```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
          500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
```

### Conditional Classes

Forbidden — string concatenation defeats JIT:

```tsx
<div className={`text-${size} bg-${color}-500`} />
```

Correct — complete class names + lookup map:

```tsx
const sizeClasses = {
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg'
}
const colorClasses = {
  red: 'bg-red-500',
  blue: 'bg-blue-500'
}

<div className={`${sizeClasses[size]} ${colorClasses[color]}`} />
```

Or use `clsx`:

```tsx
import { clsx } from 'clsx'

<div className={clsx(
  'base-styles',
  {
    'text-sm': size === 'sm',
    'text-lg': size === 'lg',
    'bg-red-500': color === 'red',
    'opacity-50': disabled
  }
)} />
```

### Component Variants with `cva`

```typescript
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input hover:bg-accent hover:text-accent-foreground',
        ghost: 'hover:bg-accent hover:text-accent-foreground'
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10'
      }
    },
    defaultVariants: {
      variant: 'default',
      size: 'default'
    }
  }
)

interface ButtonProps extends VariantProps<typeof buttonVariants> {
  children: React.ReactNode
}

function Button({ variant, size, children }: ButtonProps) {
  return (
    <button className={buttonVariants({ variant, size })}>
      {children}
    </button>
  )
}
```

**Styling Rules:**

- Use Tailwind CSS for all styling.
- Define theme values in centralized configuration.
- Use utility classes directly in components.
- Extract repeated patterns to reusable components or `cva` variants, not utility class strings.
- Use arbitrary values sparingly only when theme values are insufficient.
- Use responsive modifiers (`sm:`, `md:`, `lg:`) for adaptive layouts.
- Use `hover:`, `focus:`, `active:` states for interactive elements.

Forbidden:

- Dynamic class name construction (`text-${size}`).
- Arbitrary values when theme values exist.
- Inline styles for static values (only for truly dynamic values from props/state).
- `@apply` in component files.

---
[Back to Overview](./OVERVIEW.md)

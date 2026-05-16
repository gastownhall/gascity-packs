# Component Design Patterns

### Component Structure

Hard limits: **150 lines max per component**, **cyclomatic complexity max 10**.

```tsx
import { memo } from 'react'
import type { FC } from 'react'

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  onClick?: () => void
  children: React.ReactNode
}

const Button: FC<ButtonProps> = memo(({ variant = 'primary', size = 'md', disabled = false, onClick, children }) => {
  const baseStyles = 'font-semibold rounded-md transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2'
  const variantStyles = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500',
    outline: 'border-2 border-blue-600 text-blue-600 hover:bg-blue-50 focus:ring-blue-500',
  }
  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg',
  }

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </button>
  )
})

Button.displayName = 'Button'
export default Button
```

**Component Rules:**

- Always use functional components with TypeScript.
- Use `memo()` for components that receive stable props to prevent unnecessary re-renders.
- Define explicit interfaces for all props.
- Set `displayName` for debugging.
- Default export for single component, named exports for utilities/types.
- Keep component logic under 150 lines; extract to custom hooks if larger.

### Composition Over Configuration

Prefer composition patterns over complex prop APIs:

```tsx
import type { FC, ReactNode } from 'react'

interface CardProps { children: ReactNode }
interface CardHeaderProps { children: ReactNode }
interface CardBodyProps { children: ReactNode }
interface CardFooterProps { children: ReactNode }

const Card: FC<CardProps> & {
  Header: FC<CardHeaderProps>
  Body: FC<CardBodyProps>
  Footer: FC<CardFooterProps>
} = ({ children }) => {
  return <div className="bg-white rounded-lg shadow-md overflow-hidden">{children}</div>
}

Card.Header = ({ children }) => <div className="px-6 py-4 border-b border-gray-200">{children}</div>
Card.Body = ({ children }) => <div className="px-6 py-4">{children}</div>
Card.Footer = ({ children }) => <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">{children}</div>

export default Card
```

Usage:

```tsx
<Card>
  <Card.Header>
    <h3 className="text-lg font-semibold">Title</h3>
  </Card.Header>
  <Card.Body>
    <p>Content goes here</p>
  </Card.Body>
  <Card.Footer>
    <Button>Action</Button>
  </Card.Footer>
</Card>
```

---
[Back to Overview](./OVERVIEW.md)

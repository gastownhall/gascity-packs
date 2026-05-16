# Testing Strategy

**NOTE:** Most applications should have a `.utilities/.frontend/` folder with test scripts:

1. `.utilities/.frontend/local/_frontend_preCheck.sh` — local pre-check; logs to `{PROJECT_ROOT}/.utilities/_logs/*-frontend_preCheck.log`.
2. `.utilities/.frontend/deployed/_evaluate_frontend.sh` — wrapper for `evaluate_frontend.py` against a deployed instance; screenshots in `{PROJECT_ROOT}/screenshots`; logs in `{PROJECT_ROOT}/.utilities/_logs/*-evaluate_frontend.log`. Triggers `check_frontend_screenshots.sh`.
3. `.utilities/.frontend/deployed/check_frontend_screenshots.sh` — passes screenshots through an AI assistant that summarizes them as markdown.

These scripts in `.utilities/` are configured via the project's `.env` file at `{PROJECT_ROOT}/.env`.

### Vitest Configuration

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/', '*.config.ts'],
      thresholds: {
        branches: 90,
        functions: 90,
        lines: 90,
        statements: 90
      }
    }
  }
})
```

### Unit Tests

```typescript
import { describe, it, expect } from 'vitest'
import { formatDate, validateEmail } from '@utils/format'

describe('formatDate', () => {
  it('formats ISO string to readable date', () => {
    expect(formatDate('2025-10-07T10:00:00Z')).toBe('October 7, 2025')
  })
  it('handles invalid date gracefully', () => {
    expect(formatDate('invalid')).toBe('Invalid date')
  })
})

describe('validateEmail', () => {
  it('validates correct email', () => {
    expect(validateEmail('test@example.com')).toBe(true)
  })
  it('rejects invalid email', () => {
    expect(validateEmail('invalid')).toBe(false)
  })
})
```

### Component Tests — User-Centric Queries

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect } from 'vitest'

describe('UserForm', () => {
  const user = userEvent.setup()

  it('submits form with valid data', async () => {
    const onSubmit = vi.fn()
    render(<UserForm onSubmit={onSubmit} />)

    // Query by accessible names
    const nameInput = screen.getByRole('textbox', { name: /name/i })
    const emailInput = screen.getByRole('textbox', { name: /email/i })
    const submitButton = screen.getByRole('button', { name: /submit/i })

    await user.type(nameInput, 'John Doe')
    await user.type(emailInput, 'john@example.com')
    await user.click(submitButton)

    // Assert behavior, not implementation
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'John Doe',
        email: 'john@example.com'
      })
    })
  })

  it('shows validation errors', async () => {
    render(<UserForm onSubmit={vi.fn()} />)
    const submitButton = screen.getByRole('button', { name: /submit/i })
    await user.click(submitButton)

    expect(screen.getByRole('alert')).toHaveTextContent(/required/i)
    const form = screen.getByRole('form')
    expect(form).toHaveAttribute('aria-invalid', 'true')
  })
})
```

### Custom Render with Providers

```typescript
import { render as rtlRender } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'

function render(ui: React.ReactElement, options = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  return rtlRender(ui, { wrapper: Wrapper, ...options })
}
```

### MSW for API Mocking

```typescript
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

const server = setupServer(
  http.get('/api/users/:id', ({ params }) => {
    return HttpResponse.json({ id: params.id, name: 'Test User' })
  }),
  http.post('/api/users', async ({ request }) => {
    const data = await request.json()
    return HttpResponse.json({ ...data, id: '123' }, { status: 201 })
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// Override in specific tests
it('handles server error', async () => {
  server.use(
    http.get('/api/users/:id', () => HttpResponse.error())
  )
  render(<UserProfile userId="1" />)
  await waitFor(() => {
    expect(screen.getByText(/error/i)).toBeInTheDocument()
  })
})
```

### E2E Tests with Playwright

```typescript
import { test, expect } from '@playwright/test'

test.describe('Events Page', () => {
  test('displays events list', async ({ page }) => {
    await page.goto('/events')
    await expect(page.locator('h1')).toContainText('Events')
    await expect(page.locator('[data-testid="event-card"]')).toHaveCount(3)
  })

  test('filters events by sport', async ({ page }) => {
    await page.goto('/events')
    await page.selectOption('[data-testid="sport-filter"]', 'football')
    await expect(page.locator('[data-testid="event-card"]')).toHaveCount(1)
  })
})
```

### Coverage Requirements

| Metric | Minimum |
|:-------|:--------|
| Branches | 90% |
| Functions | 90% |
| Lines | 90% |
| Statements | 90% |

**Testing Rules:**

- Achieve 90%+ code coverage for utils, hooks, and core logic.
- Test components by user behavior, not implementation details.
- Use `data-testid` attributes sparingly only when necessary.
- Mock API calls with MSW for consistent component tests.
- Test error states and edge cases explicitly.
- Run E2E tests for critical user paths.
- Test accessibility in component tests with `jest-axe` / `@axe-core/playwright`.

---
[Back to Overview](./OVERVIEW.md)

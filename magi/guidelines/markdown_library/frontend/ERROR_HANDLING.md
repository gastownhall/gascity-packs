# Error Handling and Loading States

### Granular Error Boundaries

```tsx
import { Component, type ReactNode } from 'react'
import type { ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

// App-level boundary
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log to error service
    console.error('App error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-900 mb-4">Something went wrong</h1>
              <p className="text-gray-600 mb-4">{this.state.error?.message}</p>
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="px-4 py-2 bg-blue-600 text-white rounded-md"
              >
                Try again
              </button>
            </div>
          </div>
        )
      )
    }
    return this.props.children
  }
}

// Feature-level boundary
function FeatureErrorBoundary({ children, fallback }) {
  return (
    <ErrorBoundary
      fallback={fallback || <FeatureErrorFallback />}
      onError={(error, info) => {
        console.error('Feature error:', error)
      }}
    >
      {children}
    </ErrorBoundary>
  )
}

// Usage
<AppErrorBoundary>
  <Router>
    <FeatureErrorBoundary>
      <Dashboard />
    </FeatureErrorBoundary>
  </Router>
</AppErrorBoundary>
```

### Async Error Boundary

```tsx
function AsyncBoundary({ children }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<Loading />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  )
}

function RecoverableError({ error, retry }) {
  return (
    <div className="error-container">
      <h2>Something went wrong</h2>
      <details>
        <summary>Error details</summary>
        <pre>{error.message}</pre>
      </details>
      <button onClick={retry}>Try Again</button>
    </div>
  )
}
```

### Loading and Error States in Data Components

```tsx
import { useEvents } from '@hooks/useEvents'
import LoadingSpinner from '@components/shared/LoadingSpinner'
import ErrorMessage from '@components/shared/ErrorMessage'

export const EventsList = () => {
  const { data, isLoading, error } = useEvents({ status: 'available' })

  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorMessage message={error.message} />
  if (!data || data.length === 0) return <EmptyState message="No events found" />

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {data.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  )
}
```

**Error Handling Rules:**

- Wrap root app in `AppErrorBoundary`; wrap feature areas in `FeatureErrorBoundary`.
- Handle loading, error, and empty states explicitly in all data-fetching components.
- Never show raw error messages to users; format appropriately.
- Log errors to a real reporting service (Sentry, Datadog) — `console.error` only in dev.
- Provide actionable recovery options (retry, go back, contact support).
- Use optimistic updates for mutations with rollback on error.
- Display toast notifications for transient errors.
- Validate user input before submission to prevent avoidable errors.

---
[Back to Overview](./OVERVIEW.md)

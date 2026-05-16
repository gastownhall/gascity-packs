# Routing and Navigation

### React Router v6

```tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Layout from '@components/layout/Layout'
import LoadingSpinner from '@components/shared/LoadingSpinner'

const Home = lazy(() => import('@pages/Home'))
const Events = lazy(() => import('@pages/Events'))
const EventDetail = lazy(() => import('@pages/EventDetail'))
const About = lazy(() => import('@pages/About'))
const Contact = lazy(() => import('@pages/Contact'))
const NotFound = lazy(() => import('@pages/NotFound'))

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'events', element: <Events /> },
      { path: 'events/:id', element: <EventDetail /> },
      { path: 'about', element: <About /> },
      { path: 'contact', element: <Contact /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

export const App = () => {
  return (
    <Suspense fallback={<LoadingSpinner fullScreen />}>
      <RouterProvider router={router} />
    </Suspense>
  )
}
```

**Routing Rules:**

- Use lazy loading for all route components to enable code splitting.
- Wrap lazy routes in `Suspense` with appropriate loading fallback.
- Use nested routes with `Layout` component for consistent page structure.
- Always define a catch-all route for 404 handling.
- Use relative paths in `Link` components.
- Extract route params with `useParams` and validate them.
- Use `navigate` programmatically only after user actions.
- Define route constants file for type-safe navigation.

---
[Back to Overview](./OVERVIEW.md)

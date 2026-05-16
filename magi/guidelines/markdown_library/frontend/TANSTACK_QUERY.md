# Data Fetching with TanStack Query

### Query Hook Pattern

```typescript
export const useUser = (userId: string) => {
  return useQuery({
    queryKey: ['users', userId] as const,
    queryFn: () => userApi.getUser(userId),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    enabled: !!userId,
    select: (data) => ({
      ...data,
      fullName: `${data.firstName} ${data.lastName}`
    })
  })
}
```

### Mutation Hook with Optimistic Updates

```typescript
export const useUpdateUser = () => {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: userApi.updateUser,
    onMutate: async (newUser) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ['users', newUser.id] })
      const previousUser = queryClient.getQueryData(['users', newUser.id])
      queryClient.setQueryData(['users', newUser.id], newUser)
      return { previousUser }
    },
    onError: (err, newUser, context) => {
      // Rollback on error
      if (context?.previousUser) {
        queryClient.setQueryData(['users', newUser.id], context.previousUser)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    }
  })
}
```

### Infinite Queries

```typescript
export const useInfinitePosts = () => {
  return useInfiniteQuery({
    queryKey: ['posts'],
    queryFn: ({ pageParam }) => postApi.getPosts({ page: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => lastPage.nextPage,
    getPreviousPageParam: (firstPage) => firstPage.previousPage
  })
}
```

### Practical Event Hooks

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { eventsApi } from '@services/api/events'
import type { Event, EventFilters } from '@types/events'

export const useEvents = (filters: EventFilters) => {
  return useQuery({
    queryKey: ['events', filters],
    queryFn: () => eventsApi.getEvents(filters),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })
}

export const useEvent = (id: string) => {
  return useQuery({
    queryKey: ['events', id],
    queryFn: () => eventsApi.getEvent(id),
    enabled: !!id,
  })
}

export const useCreateEvent = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: eventsApi.createEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
    },
  })
}
```

### Query Provider Setup

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 60 * 1000,
    },
  },
})

export const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <Router />
      {import.meta.env.DEV && <ReactQueryDevtools />}
    </QueryClientProvider>
  )
}
```

### API Layer

```typescript
import type { Event, EventFilters, CreateEventDto } from '@types/events'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api'

const handleResponse = async <T,>(response: Response): Promise<T> => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Unknown error' }))
    throw new Error(error.message || `HTTP ${response.status}`)
  }
  return response.json()
}

export const eventsApi = {
  getEvents: async (filters: EventFilters): Promise<Event[]> => {
    const params = new URLSearchParams()
    if (filters.sport) params.append('sport', filters.sport)
    if (filters.date) params.append('date', filters.date.toISOString())
    const response = await fetch(`${BASE_URL}/events?${params}`)
    return handleResponse<Event[]>(response)
  },
  getEvent: async (id: string): Promise<Event> => {
    const response = await fetch(`${BASE_URL}/events/${id}`)
    return handleResponse<Event>(response)
  },
  createEvent: async (event: CreateEventDto): Promise<Event> => {
    const response = await fetch(`${BASE_URL}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    })
    return handleResponse<Event>(response)
  },
}
```

**TanStack Query Rules:**

- All server state managed exclusively through TanStack Query.
- Define custom hooks for each query/mutation.
- Use `queryKey` arrays with all dependencies for proper cache management.
- Set appropriate `staleTime` and `gcTime` based on data volatility.
- Invalidate queries after mutations to trigger refetches.
- Use `select` to derive shaped data without re-fetching.
- Use `enabled` to control when queries run.
- Use optimistic updates with `onMutate` / `onError` rollback / `onSettled` invalidation.
- Validate all API responses at the boundary with Zod.
- Never store fetched data in component state or Zustand.

---
[Back to Overview](./OVERVIEW.md)

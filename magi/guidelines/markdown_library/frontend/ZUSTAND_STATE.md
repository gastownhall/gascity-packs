# State Management with Zustand

### Store Slices Pattern

```typescript
// Slices for separation of concerns
interface AuthSlice {
  user: User | null
  setUser: (user: User | null) => void
  logout: () => void
}

interface UISlice {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark') => void
}

const createAuthSlice: StateCreator<AuthSlice> = (set) => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null })
})

const createUISlice: StateCreator<UISlice> = (set) => ({
  theme: 'light',
  sidebarOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme })
})
```

### Middleware Composition

```typescript
import { create } from 'zustand'
import { devtools, persist, subscribeWithSelector } from 'zustand/middleware'
import { immer } from 'zustand/middleware/immer'

const useStore = create<StoreState>()(
  devtools(
    persist(
      subscribeWithSelector(
        immer((set) => ({
          // Immer allows direct-style mutations
          items: [],
          addItem: (item) => set((state) => {
            state.items.push(item)
          })
        }))
      ),
      {
        name: 'app-storage',
        partialize: (state) => ({ items: state.items })
      }
    )
  )
)
```

### Computed Values via Selectors

```typescript
const useFilteredItems = () => {
  const items = useStore((state) => state.items)
  const filter = useStore((state) => state.filter)

  return useMemo(
    () => items.filter(item => item.name.includes(filter)),
    [items, filter]
  )
}
```

### Selective Persistence

```typescript
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

persist(
  (set) => ({ /* store */ }),
  {
    name: 'user-preferences',
    storage: createJSONStorage(() => localStorage),
    partialize: (state) => ({
      // Only persist specific fields
      theme: state.theme,
      language: state.language
    }),
    onRehydrateStorage: () => (state) => {
      console.log('State rehydrated:', state)
    }
  }
)
```

### Practical Filter Store

```typescript
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface FilterState {
  searchQuery: string
  selectedSport: string | null
  selectedDate: Date | null
  setSearchQuery: (query: string) => void
  setSelectedSport: (sport: string | null) => void
  setSelectedDate: (date: Date | null) => void
  clearFilters: () => void
}

export const useFilterStore = create<FilterState>()(
  devtools(
    persist(
      (set) => ({
        searchQuery: '',
        selectedSport: null,
        selectedDate: null,
        setSearchQuery: (query) => set({ searchQuery: query }),
        setSelectedSport: (sport) => set({ selectedSport: sport }),
        setSelectedDate: (date) => set({ selectedDate: date }),
        clearFilters: () => set({ searchQuery: '', selectedSport: null, selectedDate: null }),
      }),
      {
        name: 'filter-storage',
        partialize: (state) => ({ searchQuery: state.searchQuery }),
      }
    )
  )
)
```

**Zustand Rules:**

- One store per domain or feature (filters, user preferences, UI state).
- Use `devtools` middleware in development for debugging.
- Use `persist` middleware for state that should survive refreshes.
- `partialize` persist to only save specific fields.
- Use `immer` middleware for nested state updates.
- Use `subscribeWithSelector` when fine-grained subscriptions are needed.
- Compute derived values via selectors with `useMemo`, not inside the store.
- **Never store server state in Zustand; use TanStack Query instead.**

---
[Back to Overview](./OVERVIEW.md)

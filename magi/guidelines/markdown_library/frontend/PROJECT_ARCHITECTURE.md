# Project Architecture

### Directory Structure

Standard layout for scalable SPAs:

```
src/
├── components/
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   └── Layout.tsx
│   ├── navigation/
│   │   ├── MainNav.tsx
│   │   └── MobileNav.tsx
│   ├── events/
│   │   ├── EventCard.tsx
│   │   ├── EventFilters.tsx
│   │   └── EventGallery.tsx
│   └── shared/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Modal.tsx
│       └── LoadingSpinner.tsx
├── pages/
│   ├── Home.tsx
│   ├── Events.tsx
│   ├── Services/
│   │   ├── Sports.tsx
│   │   ├── Graduations.tsx
│   │   └── Headshots.tsx
│   ├── About.tsx
│   ├── FAQ.tsx
│   ├── Contact.tsx
│   └── FindYourPhotos.tsx
├── hooks/
│   ├── useDebounce.ts
│   ├── useMediaQuery.ts
│   └── useLocalStorage.ts
├── services/
│   ├── api/
│   │   ├── events.ts
│   │   ├── contacts.ts
│   │   └── photos.ts
│   └── mock/
│       ├── mockApi.ts
│       └── fixtures/
├── store/
│   ├── userStore.ts
│   └── filterStore.ts
├── types/
│   ├── events.ts
│   ├── api.ts
│   └── index.ts
├── utils/
│   ├── format.ts
│   ├── validation.ts
│   └── constants.ts
├── styles/
│   ├── theme.ts
│   ├── globals.css
│   └── tailwind.config.js
├── App.tsx
├── main.tsx
└── vite-env.d.ts
```

**Organizational Rules:**

- `components/` — reusable UI components grouped by domain or function.
- `pages/` — route-level components that compose smaller components.
- `hooks/` — custom React hooks for shared logic.
- `services/` — API layer and data fetching logic.
- `store/` — Zustand stores for client-side state.
- `types/` — TypeScript interfaces and type definitions.
- `utils/` — pure functions with zero side effects.
- `styles/` — theme configuration and global styles.

### File Naming

- **Components**: PascalCase (`Button.tsx`, `EventCard.tsx`).
- **Hooks**: camelCase with `use` prefix (`useDebounce.ts`).
- **Utilities**: camelCase (`format.ts`, `validation.ts`).
- **Types**: camelCase (`events.ts`, `api.ts`).

---
[Back to Overview](./OVERVIEW.md)

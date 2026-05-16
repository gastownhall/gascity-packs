# Accessibility (WCAG 2.1 AA)

### Semantic HTML

```tsx
<main>
  <article>
    <header>
      <h1>Page Title</h1>
      <nav aria-label="Breadcrumb">
        <ol>
          <li><a href="/">Home</a></li>
          <li aria-current="page">Current</li>
        </ol>
      </nav>
    </header>
    <section aria-labelledby="section-title">
      <h2 id="section-title">Section Title</h2>
      <p>Content</p>
    </section>
  </article>
</main>
```

### ARIA Attributes

```tsx
<button
  aria-label="Close dialog"
  aria-pressed={isPressed}
  aria-expanded={isExpanded}
  aria-controls="menu-id"
  aria-describedby="helper-text"
>
  <CloseIcon aria-hidden="true" />
</button>

// Live regions
<div aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>

// Skip links
<a href="#main-content" className="sr-only focus:not-sr-only">
  Skip to main content
</a>
```

### Keyboard Navigation and Focus Trap

```tsx
function Dialog({ isOpen, onClose }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      const focusableElements = ref.current?.querySelectorAll(
        'a, button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
      )
      const firstElement = focusableElements?.[0] as HTMLElement
      const lastElement = focusableElements?.[focusableElements.length - 1] as HTMLElement
      firstElement?.focus()

      const handleTab = (e: KeyboardEvent) => {
        if (e.key === 'Tab') {
          if (e.shiftKey && document.activeElement === firstElement) {
            e.preventDefault()
            lastElement?.focus()
          } else if (!e.shiftKey && document.activeElement === lastElement) {
            e.preventDefault()
            firstElement?.focus()
          }
        }
        if (e.key === 'Escape') {
          onClose()
        }
      }
      document.addEventListener('keydown', handleTab)
      return () => document.removeEventListener('keydown', handleTab)
    }
  }, [isOpen, onClose])

  return (/* dialog JSX */)
}
```

### Color Contrast (WCAG 2.1 AA)

| Content | Minimum Ratio |
|:--------|:--------------|
| Normal text | 4.5:1 |
| Large text (18pt+ or 14pt bold) | 3:1 |
| Non-text (icons, borders for input identification) | 3:1 |

### Practical Semantic Card

```tsx
export const EventCard: FC<EventCardProps> = ({ event }) => {
  return (
    <article className="bg-white rounded-lg shadow-md overflow-hidden">
      <img src={event.thumbnailUrl} alt={`${event.title} event photo`} className="w-full h-48 object-cover" />
      <div className="p-4">
        <header>
          <h3 className="text-xl font-semibold text-gray-900">{event.title}</h3>
          <time dateTime={event.date} className="text-sm text-gray-600">
            {formatDate(event.date)}
          </time>
        </header>
        <p className="mt-2 text-gray-700">{event.location.venue}</p>
        <footer className="mt-4">
          <Link to={`/events/${event.id}`} className="text-blue-600 hover:text-blue-700 font-medium">
            View Photos
          </Link>
        </footer>
      </div>
    </article>
  )
}
```

**Accessibility Rules:**

- Use semantic HTML elements (`article`, `section`, `nav`, `header`, `footer`, `main`).
- Provide alt text for all images.
- Use proper heading hierarchy (`h1`, `h2`, `h3`).
- Add `aria-label` when text content is insufficient.
- Ensure keyboard navigation works for all interactive elements.
- Use `<button>` for actions, `<a>` for navigation.
- Provide focus indicators for keyboard users.
- Use `aria-live` regions for dynamic content updates.
- Trap focus inside modal dialogs; restore on close.
- Test with screen readers and run `axe-core` automated audits.

---
[Back to Overview](./OVERVIEW.md)

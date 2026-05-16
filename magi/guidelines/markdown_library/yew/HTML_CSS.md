# HTML, CSS, and Assets

- Use `class="..."` for static classes; use `classes!` macro for conditional sets.
- Copy static assets with `<link data-trunk rel="copy-dir" href="assets">`.
- Prefer **semantic HTML**; wire `aria-*` attributes for interactive elements.

### CSS and Tailwind Integration

Two primary styling approaches:

| Approach | Use |
|:---------|:----|
| **Direct CSS** (small projects) | Co-locate small, component-specific CSS files (`style/mod.css`); include via `<link data-trunk rel="css">` |
| **Tailwind CSS** (larger projects) | Utility-first scalable styling; integrates with Trunk via PostCSS |

#### Tailwind Setup Steps

1. **Initialize Node.js project** in `ui/`:

```bash
npm init -y
```

2. **Install Tailwind and PostCSS**:

```bash
npm install -D tailwindcss postcss autoprefixer
```

3. **Initialize Tailwind**:

```bash
npx tailwindcss init -p
```

4. **Configure `tailwind.config.js`** to scan Rust template files:

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./index.html",
        "./src/**/*.{rs,html}", // Scan Rust files and HTML templates
    ],
    theme: {
        extend: {},
    },
    plugins: [],
}
```

5. **Create Tailwind input CSS** (`src/style/tailwind.css`):

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

6. **Configure `Trunk.toml`** PostCSS processor pointing `source` to `src/style/tailwind.css`.
7. **Link in `index.html`** the processed CSS output.

With this setup, `trunk build` or `trunk serve` automatically processes `tailwind.css` through PostCSS, generating a lean `app.css` containing only the utility classes used.

### classes! Macro

```rust
let is_active = true;
let is_disabled = false;
html! {
    <button class={classes!(
        "btn",
        "px-4",
        "py-2",
        is_active.then_some("bg-blue-500"),
        is_disabled.then_some("opacity-50 cursor-not-allowed")
    )}>
        {"Click me"}
    </button>
}
```

### Stylist (CSS-in-Rust)

```rust
use stylist::{yew::styled_component, css};

#[styled_component(StyledButton)]
pub fn styled_button() -> Html {
    let stylesheet = css!(
        r#"
        button {
            background-color: #4CAF50;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            &:hover {
                background-color: #45a049;
            }
            &:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
        }
        "#
    );
    html! {
        <div class={stylesheet}>
            <button>{"Styled Button"}</button>
        </div>
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

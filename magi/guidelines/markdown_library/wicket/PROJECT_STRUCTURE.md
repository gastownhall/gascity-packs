# Project Structure

### Standard Directory Layout

Organize by component type at the top level:

| Directory | Contents |
|:----------|:---------|
| `page/` | `WebPage` subclasses |
| `panel/` | Reusable `Panel` components |
| `component/` | Custom `FormComponent` subclasses |
| `model/` | `IModel` implementations |
| `behavior/` | `Behavior` classes |
| `validator/` | `IValidator` implementations |

For large applications, introduce feature packages beneath these.

### HTML Template Co-location

HTML templates **must reside in the same package** as their Java class — either in the same source folder or in a parallel resources folder. Wicket locates templates by class name and package. A class `com.company.app.page.HomePage` expects its template at `com/company/app/page/HomePage.html`. **Choose one co-location pattern and apply it consistently across the project.**

### Application Class Configuration

The `WebApplication` subclass is the entry point. Configure home page, security settings, page mounting, and development vs production behavior in `init()`. Register custom session class via `newSession()`. Configure request cycle listeners for CSRF protection. Set appropriate exception display modes for development vs deployment.

---
[Back to Overview](./OVERVIEW.md)

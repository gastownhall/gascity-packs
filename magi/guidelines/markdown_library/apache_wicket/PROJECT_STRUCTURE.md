# Project Structure

### Standard Directory Layout

Organize by component type at the top level. For large applications, introduce feature packages beneath these:

```
src/main/java/com/company/app/
├── MyWicketApplication.java
├── page/        # WebPage subclasses
├── panel/       # Reusable Panels
├── component/   # Custom FormComponents
├── model/       # IModel implementations
├── behavior/    # Behavior classes
├── validator/   # IValidator implementations
└── service/     # Domain services (DI-injected)

src/main/resources/com/company/app/   # parallel to source for HTML co-location
├── page/HomePage.html
└── panel/UserPanel.html
```

### HTML Template Co-location

HTML templates must reside in the same package as their Java class, either in the same source folder or in a parallel `resources` folder. Wicket locates templates by class name and package — `com.company.app.page.HomePage` expects its template at `com/company/app/page/HomePage.html`. Choose one co-location pattern (alongside Java vs. parallel `resources`) and apply it consistently across the project.

### Application Class Configuration

The `WebApplication` subclass is the entry point. Configure home page, security settings, page mounting, and development vs. production behavior in `init()`. Register a custom session class via `newSession()`. Configure request cycle listeners for CSRF protection. Set appropriate exception display modes for development vs. deployment:

```java
public class MyWicketApplication extends WebApplication {

    @Override
    public Class<? extends WebPage> getHomePage() {
        return HomePage.class;
    }

    @Override
    protected void init() {
        super.init();
        getComponentInstantiationListeners().add(new SpringComponentInjector(this));
        getRequestCycleListeners().add(new ResourceIsolationRequestCycleListener());
        getCspSettings().blocking().strict();
        mountPage("/login", LoginPage.class);
        mountPage("/orders/${id}", OrderDetailPage.class);
    }

    @Override
    public Session newSession(Request request, Response response) {
        return new MyWebSession(request);
    }
}
```

---
[Back to Overview](./OVERVIEW.md)

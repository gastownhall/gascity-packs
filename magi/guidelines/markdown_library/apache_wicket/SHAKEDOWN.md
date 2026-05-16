# Shakedown

### Definition

A Wicket shakedown is the first controlled, end-to-end exercise of an assembled Wicket application under real framework wiring. It exists to prove that:

- The `WebApplication` subclass initializes
- Page classes mount
- The component tree renders against real markup files
- The page store persists and reconstitutes stateful pages
- `wicket-spring` injects every `@SpringBean`

…all before live traffic touches the filter.

Shakedown runs in two complementary forms:
1. An in-process `WicketTester` pass against a real H2 or PostgreSQL instance executed in the verify phase.
2. A live servlet-container mount sequence executed against the deployed WAR after Tomcat or Jetty starts.

### Shakedown vs Preflight vs Unit Testing

- **Preflight** is static: the WAR exists, the JDBC URL is set, `wicket.configuration` is `deployment`, the servlet container is up.
- **Shakedown** is integration: `WebApplication.init()` actually runs, pages actually mount, `@SpringBean` injections actually resolve, forms actually round-trip.
- **Unit testing** with `WicketTester` in isolated test application subclasses with mocked services is **not** shakedown — it is component-level testing.

Shakedown uses the production `WebApplication` subclass with a real Spring context, real database, real `wicket-spring` wiring, and real page serialization through the page store.

### Mandatory Triggers

Shakedown is required after:
- First deployment of a new Wicket application
- Wicket framework upgrade (9.x → 10.x; minor bumps that touch component rendering or serialization)
- Spring context restructure affecting `@SpringBean` resolution
- Addition or removal of mounted page classes
- Changes to `CryptoMapper` configuration or CSRF protection wiring
- Page store or `IPageManager` replacement
- Session class (`newSession()`) modifications
- Servlet container replacement or Jakarta Servlet API version change
- Switching between development and deployment `wicket.configuration` modes for the first time
- Addition of resource bundles (CSS/JS aggregation) to `Application.init()`

### Non-Triggers

- Pure HTML template markup changes within an already-mounted page that do not alter `wicket:id` bindings
- Property file edits for existing i18n keys
- CSS-only visual changes
- Javadoc updates
- Unit test additions that exercise `WicketTester` only

### Validation Categories (Six Failure Surfaces)

1. **Application wiring** — `WebApplication.init()` completes without exception, `SpringComponentInjector` is installed, `CryptoMapper` or `ResourceIsolationRequestCycleListener` is registered, custom session class is set.
2. **Page mounting and URL resolution** — every `mountPage()` call resolves to a reachable URL, `PageParameters` construct without NPE, bookmarkable page links render.
3. **Component tree construction** — every page under shakedown instantiates its full component hierarchy, `onInitialize` chains complete, no `NotSerializableException` fires against the page store.
4. **Form round-trip** — a representative form submits with valid data, `CompoundPropertyModel` updates the backing bean, `onSubmit()` executes, validators fire on invalid data and `FeedbackPanel` captures messages.
5. **AJAX wiring** — `AjaxLink`, `AjaxButton`, and `AjaxFormComponentUpdatingBehavior` each produce an `AjaxRequestTarget` response with the expected component re-render markup.
6. **Resource and DI integration** — `@SpringBean` proxies resolve to concrete beans, `PackageResourceReference` URLs return 200, CSS/JS resource bundles aggregate and serve.

### Execution Principles

- **Conservative inputs** — representative sample data, a single test user, no load generation.
- **Progressive stress** — start with `HomePage` render, then login form submission, then one AJAX-heavy panel, then one `DataView` with a small paged dataset.
- **Controlled environment** — isolated H2 or dedicated PostgreSQL schema; sandbox Spring profile; real page store (`DiskPageStore`) backed by a temp work directory cleaned between runs.
- **Observable execution** — `wicket.configuration=development` during the `WicketTester` shakedown to activate `CheckingObjectOutputStream`, then a second pass with `deployment` to surface production-only behavior.
- **Known-good inputs** — fixture users, fixture form payloads with pre-computed expected HTML assertions.
- **No optimization during shakedown** — if a page renders slowly, log it and continue.

### Execution Sequence

```text
1.  Confirm preflight: WAR exists, database reachable, Spring context profile set
2.  Construct the production WebApplication subclass inside WicketTester with the real Spring ApplicationContext
3.  Assert tester.startPage(HomePage.class) yields assertRenderedPage(HomePage.class) with zero feedback errors
4.  Exercise every mounted page class through startPage with representative PageParameters; verify assertRenderedPage for each
5.  Round-trip a login form via FormTester; assert successful authentication state transition in the session
6.  Exercise an AJAX path with tester.executeAjaxEvent and assert assertComponentOnAjaxResponse
7.  Force a page store round-trip by calling tester.startPage then navigating away and back; verify no NotSerializableException
8.  After the in-process pass, hit the deployed WAR via HTTP against mounted page URLs and verify 200 responses with expected HTML fragments
9.  Record all observations
10. Classify results
```

### Reference Harness

```java
@SpringBootTest
@ActiveProfiles("shakedown")
class WicketShakedownIT {

    @Autowired
    private ApplicationContext springContext;

    private WicketTester tester;

    @BeforeEach
    void bootRealApplication() {
        WebApplication application = new MyWicketApplication();
        application.setServletContext(new MockServletContext(application, null));
        tester = new WicketTester(application);
        application.getComponentInstantiationListeners().add(
            new SpringComponentInjector(application, springContext)
        );
    }

    @Test
    void homePage_renders_against_real_wiring() {
        tester.startPage(HomePage.class);
        tester.assertRenderedPage(HomePage.class);
        tester.assertNoErrorMessage();
    }

    @Test
    void loginForm_roundTrips_with_real_auth_service() {
        tester.startPage(LoginPage.class);
        FormTester form = tester.newFormTester("loginForm");
        form.setValue("username", "shakedown.user@example.com");
        form.setValue("password", "shakedown-fixture-pw");
        form.submit("submit");
        tester.assertRenderedPage(DashboardPage.class);
        tester.assertNoErrorMessage();
    }

    @Test
    void ajaxLink_produces_request_target() {
        tester.startPage(DashboardPage.class);
        tester.clickLink("refreshPanelLink", true);
        tester.assertComponentOnAjaxResponse("refreshPanel");
    }

    @Test
    void pageStore_roundTrips_every_mounted_page_without_serialization_failure() {
        for (Class<? extends Page> pageClass : MountedPages.ALL) {
            tester.startPage(pageClass);
            tester.assertRenderedPage(pageClass);
            tester.startPage(HomePage.class);
            tester.startPage(pageClass);
            tester.assertRenderedPage(pageClass);
        }
    }

    @AfterEach
    void teardown() {
        if (tester != null) tester.destroy();
    }
}
```

### Result Classification

- **Pass** — Every mounted page renders, every form round-trips, every AJAX path returns the expected target, every `@SpringBean` resolves, the page store accepts and reconstitutes every page without `NotSerializableException`.
- **Fail (blocking)** — Any `NotSerializableException`, any `SpringBean` that cannot resolve, any NPE in `onInitialize` or `onConfigure`, any mounted page returning 500, any CSRF protection misconfiguration.
- **Fail (non-blocking)** — Slow page render above an advisory threshold, excessive page-store size for a single page, noisy feedback warnings on a valid submission.
- **Inconclusive** — Infrastructure unreachable (database down, Spring context refused to start). Fix the environment and re-run the specific validation.

### Required Artifacts

- Execution log with full `WicketTester` output
- Wicket debug logging at `DEBUG` for `org.apache.wicket`
- `CheckingObjectOutputStream` reports for the development-mode pass
- HTTP response captures from the live-container pass
- Result summary classifying each mounted page as pass/fail
- Issue list keyed by page class and component path
- Environment snapshot: Wicket version, Jakarta Servlet version, Spring version, database version, `wicket.configuration` mode, deployed WAR digest, active Spring profiles

### Anti-Patterns (Forbidden)

- Skipping shakedown after "just a markup tweak" that silently changed a `wicket:id` binding
- Running shakedown with a `TestApplication` subclass that mocks Spring beans (validates the mock wiring, not production wiring)
- Running shakedown against an in-memory `HashMapPageStore` when production uses `DiskPageStore` or a clustered session-replication store
- Treating `WicketTester` assertions as a full test suite instead of a small set of representative page flows
- Fixing a serialization bug mid-shakedown by adding `transient` to a field without re-running the full sequence
- Shipping without any recorded shakedown artifacts

---
[Back to Overview](./OVERVIEW.md)

# Page-Flow Shakedown

### Definition

A page-flow shakedown exercises a Wicket page through **one complete request cycle and one AJAX re-render cycle under real framework conditions**. It validates the full path from incoming `HttpServletRequest` through page mount, session attach, model resolution, component render, HTML output, and page detach. The complementary framework-wiring shakedown (covered in `apache_wicket_guidelines`) focuses on `Application.init()` and `@SpringBean` resolution; this section focuses on **what happens once a mounted page receives a request**. **Both shakedown passes are required before production traffic.**

### WicketTester Unit Pages vs Servlet Container Shakedown

`WicketTester` unit pages mock the servlet environment — no real `HttpSession`, no real HTTP request, no real servlet filter chain, no real page store persistence path. A unit page test validates component logic in isolation.

A **servlet container shakedown** deploys the WAR to a real Tomcat or Jetty, fires real HTTP requests, and observes:

- Real session creation.
- Real cookie handshakes.
- Real CSRF token round-trips.
- Real page store writes.

**The difference matters:** Wicket bugs around session serialization, `CryptoMapper` URL encoding, and request cycle listener ordering only surface in the real container path. **Shakedown must exercise both.**

### Mandatory Triggers

Page-flow shakedown is required after:

- Any change to a mounted page's component hierarchy construction (new child components, new behaviors, new `LoadableDetachableModel` wiring).
- Modification of a page's request cycle listener stack.
- Form validation pipeline changes affecting `onSubmit`/`onError` flow.
- Addition or removal of an AJAX behavior.
- Session attach/detach logic modification.
- Page serialization contract changes (new field in `WebSession` subclass, new serializable field in a page).
- Switching between `DiskPageStore` and an alternate `IPageManager` implementation.
- `CryptoMapper` or URL coding strategy changes that affect bookmarkable page URLs.

### Non-Triggers

- Pure CSS changes.
- Changes to a property file for existing keys.
- Changes confined to a reusable `Panel` already covered by a prior shakedown.
- Markup whitespace cleanup.
- Javadoc updates.
- Routine form component label adjustments that do not alter `wicket:id`, model expression, or validator chain.

### Validation Categories

| Category | What is verified |
|:---------|:-----------------|
| Request-to-render integrity | Request arrives, `WebApplication` locates the mounted class, page instantiates, `onInitialize` completes, `onConfigure` runs, render produces the expected HTML, `wicket:id` bindings appear in the DOM |
| Session attach/detach correctness | `WebSession` subclass attaches on first request, session state mutations mark `dirty()`, detach releases transient state, subsequent requests reattach the same session |
| Component tree stability across request cycles | Page survives a serialization/deserialization round-trip through the page store and renders identically on back-button navigation |
| Form validation pipeline | Invalid submissions trigger `onError` with populated `FeedbackPanel`, valid submissions trigger `onSubmit` with `CompoundPropertyModel`-populated bean, validators fire in declared order, cross-field validation on the form executes |
| AJAX re-render path | `AjaxRequestTarget` receives the target components, response contains the expected wicket-ajax-response XML, `setOutputMarkupId` is honored, `setOutputMarkupPlaceholderTag` maintains placeholders for invisible components |
| Behavior attachment and cleanup | Behaviors added in `onInitialize` are attached on render, detached on detach, and do not leak across page instances |

### Execution Principles

- **Conservative** — One representative user path per page, one valid form submission, one invalid form submission, one AJAX interaction.
- **Progressive** — Exercise the simplest stateless page first, then a `CompoundPropertyModel` form page, then a page with a `DataView`, then a page with stacked AJAX behaviors.
- **Controlled** — Production `wicket.configuration=deployment` mode in the real container, production `CryptoMapper`, production CSRF listener, production page store.
- **Observable** — Enable TRACE logging on `org.apache.wicket.request.cycle` and `org.apache.wicket.pageStore` during the shakedown pass; capture full HTML responses; capture AJAX response XML.
- **Known-good inputs** — Fixture bean instances with predetermined assertable field values.
- **No optimization** — Note any latency observations as non-blocking findings and continue.

### Execution Pattern

1. Confirm preflight: WAR is deployed, servlet container is running, database is reachable, fixture data is seeded.
2. Initiate an HTTP session against the deployed WAR with a clean cookie jar.
3. `GET` the simplest mounted page, assert 200, assert expected `wicket:id` elements in the DOM, assert no console errors in the response's rendered JavaScript, assert a `JSESSIONID` cookie is set.
4. Follow the request cycle through the second request to verify session reattach.
5. `POST` an invalid form submission, assert `onError` path, assert `FeedbackPanel` contains the expected message, assert the page redisplays with the same component state.
6. `POST` a valid form submission, assert `onSubmit` path, assert redirect to the expected destination page.
7. Issue an AJAX request to an `AjaxLink` endpoint, assert the response is valid wicket-ajax-response XML and contains the expected component re-render.
8. Trigger back-button navigation (page store reconstitution) and verify the page renders identically.
9. Record observations.
10. Classify results.

### Reference Harness — Live Container Page-Flow Shakedown

```java
package com.company.app.shakedown;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.ActiveProfiles;

import java.net.CookieManager;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpResponse.BodyHandlers;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("shakedown")
class PageFlowShakedownIT {

    @LocalServerPort
    private int port;

    private final HttpClient client = HttpClient.newBuilder()
        .cookieHandler(new CookieManager())
        .followRedirects(HttpClient.Redirect.NORMAL)
        .build();

    @Test
    void homePage_requestCycle_completes_and_session_attaches() throws Exception {
        HttpResponse<String> response = get("/home");

        assertEquals(200, response.statusCode());
        assertTrue(response.headers().firstValue("set-cookie").orElse("").contains("JSESSIONID"));

        Document dom = Jsoup.parse(response.body());
        assertNotNull(dom.selectFirst("[wicket\\:id=feedbackPanel]"));
        assertNotNull(dom.selectFirst("[wicket\\:id=mainNavigation]"));
    }

    @Test
    void loginForm_invalidSubmission_triggers_onError_path() throws Exception {
        HttpResponse<String> initial = get("/login");
        Document form = Jsoup.parse(initial.body());
        String action = form.selectFirst("form[wicket\\:id=loginForm]").attr("action");

        HttpResponse<String> submit = postForm(action, "username=&password=");
        assertEquals(200, submit.statusCode());

        Document result = Jsoup.parse(submit.body());
        assertTrue(result.select(".feedbackPanelERROR").size() > 0,
            "onError path must populate FeedbackPanel");
    }

    @Test
    void loginForm_validSubmission_triggers_onSubmit_and_redirects() throws Exception {
        HttpResponse<String> initial = get("/login");
        Document form = Jsoup.parse(initial.body());
        String action = form.selectFirst("form[wicket\\:id=loginForm]").attr("action");

        HttpResponse<String> submit = postForm(action,
            "username=shakedown.user%40example.com&password=shakedown-fixture-pw");
        assertEquals(200, submit.statusCode());
        assertTrue(submit.uri().getPath().endsWith("/dashboard"),
            "onSubmit path must redirect to dashboard");
    }

    @Test
    void ajaxLink_produces_wicket_ajax_response_xml() throws Exception {
        HttpResponse<String> page = get("/dashboard");
        Document dom = Jsoup.parse(page.body());
        String ajaxUrl = dom.selectFirst("[wicket\\:id=refreshPanelLink]").attr("href");

        HttpResponse<String> ajax = HttpRequest.newBuilder()
            .uri(URI.create("http://localhost:" + port + ajaxUrl))
            .header("Wicket-Ajax", "true")
            .header("Wicket-Ajax-BaseURL", "dashboard")
            .GET()
            .build()
            .let(req -> client.send(req, BodyHandlers.ofString()));

        assertEquals(200, ajax.statusCode());
        assertTrue(ajax.body().startsWith("<?xml"));
        assertTrue(ajax.body().contains("<ajax-response>"));
        assertTrue(ajax.body().contains("id=\"refreshPanel\""));
    }

    @Test
    void pageStore_reconstitutes_on_back_button_navigation() throws Exception {
        HttpResponse<String> first = get("/dashboard");
        String firstBodyHash = hashWicketPaths(first.body());

        get("/home");

        // Back-button navigation reuses the prior page ID from page store
        HttpResponse<String> back = get(first.uri().getPath() + "?" + first.uri().getQuery());
        String backBodyHash = hashWicketPaths(back.body());

        assertEquals(firstBodyHash, backBodyHash,
            "Page store reconstitution must produce identical component tree");
    }

    private HttpResponse<String> get(String path) throws Exception {
        return client.send(
            HttpRequest.newBuilder(URI.create("http://localhost:" + port + path)).GET().build(),
            BodyHandlers.ofString()
        );
    }

    private HttpResponse<String> postForm(String action, String body) throws Exception {
        return client.send(
            HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/" + action))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build(),
            BodyHandlers.ofString()
        );
    }

    private String hashWicketPaths(String html) {
        Document dom = Jsoup.parse(html);
        StringBuilder paths = new StringBuilder();
        dom.select("[wicket\\:id]").forEach(el -> paths.append(el.attr("wicket:id")).append(";"));
        return Integer.toHexString(paths.toString().hashCode());
    }
}
```

### Result Classification

| Outcome | Trigger |
|:--------|:--------|
| **Pass** | Every exercised page returns 200, every form round-trips correctly, every AJAX response validates, page store reconstitution produces identical HTML, session lifecycle attach/detach fires correctly |
| **Fail-blocking** | Any 500 response, any `NotSerializableException` logged during page store write, any component tree divergence on back-button navigation, any `onSubmit` failure for a valid submission, any validator firing in the wrong order, any missing CSRF token |
| **Fail-nonblocking** | Spurious feedback warnings on valid submissions, excessive HTML output size relative to prior shakedown baseline, non-critical JavaScript warnings in the rendered response |
| **Inconclusive** | Servlet container misconfiguration, fixture data missing — correct and re-run the specific validation |

### Required Artifacts

- **Execution log** with full HTTP request/response captures for each exercised page, `org.apache.wicket` TRACE logs, page store write/read events, session lifecycle events.
- **Result summary** per mounted page covering request cycle, form round-trip, AJAX path, page store round-trip, and session attach/detach.
- **Issue list** keyed by page class and request cycle phase.
- **Environment snapshot** — deployed WAR digest, servlet container version, Wicket version, `wicket.configuration` mode, `IPageManager` implementation, active Spring profiles, JDBC driver version.

### Anti-Patterns

- Running page-flow shakedown entirely inside `WicketTester` and declaring success — **the real servlet container path is the whole point**.
- Skipping the back-button navigation step because "the page already rendered once" — page store reconstitution is a distinct failure surface.
- Asserting only HTTP status codes without verifying the HTML body contains expected `wicket:id` bindings.
- Treating a single form submission as adequate coverage — **both the `onSubmit` and `onError` paths must be exercised**.
- Running shakedown against a page whose `@SpringBean` dependencies are mocked — the proxy resolution path is part of the request cycle and must run against real beans.
- Discarding captured HTTP responses after the run — **the HTML is the evidence**.

---
[Back to Overview](./OVERVIEW.md)

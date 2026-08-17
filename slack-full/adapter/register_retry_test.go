package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// cityNotReadyBody is the exact JSON gc's per-city bindCity gate returns
// while the city is still booting — a 404 carrying the structured
// "city-not-found" code (urn:gascity:error:city-not-found). Reproduced from
// the live incident log (sc-vr3ygj): every supervisor restart 404'd the
// adapter's registration POST with this body until the city finished coming
// up.
const cityNotReadyBody = `{"type":"urn:gascity:error:city-not-found","title":"City Not Found","status":404,"detail":"not_found: city not found or not running: sct-city","code":"city-not-found"}`

// TestRegisterAdapter_RetriesCityNotReadyThenSucceeds is the core regression:
// registration survives the boot-ordering race. gc 404s "city-not-found"
// while the city is still booting, then accepts once it is up; registration
// must retry through the 404s and end REGISTERED without manual intervention.
// Before the fix registerAdapter was one-shot and the first 404 was fatal.
func TestRegisterAdapter_RetriesCityNotReadyThenSucceeds(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if attempt := atomic.AddInt32(&n, 1); attempt < 3 {
			// City still booting: bindCity gate 404s with city-not-found.
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(cityNotReadyBody))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), fastRetry(5), sleep)
	if err != nil {
		t.Fatalf("registration should recover once the city is up, got: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 3 {
		t.Errorf("requests = %d, want 3 (2 city-not-ready 404s + 1 success)", got)
	}
	if len(*slept) != 2 {
		t.Errorf("sleeps = %d, want 2 (between the 3 attempts)", len(*slept))
	}
}

// TestRegisterAdapter_SucceedsFirstTryNoRetry: the common case — the city is
// already up — registers on the first attempt with no backoff, so the fix
// adds no latency to a normal boot.
func TestRegisterAdapter_SucceedsFirstTryNoRetry(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	if err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), bootRegisterRetryConfig(), sleep); err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want 1 (city already up)", got)
	}
	if len(*slept) != 0 {
		t.Errorf("slept %v, want none on first-try success", *slept)
	}
}

// TestRegisterAdapter_RetriesTransportErrorThenSucceeds covers the other
// boot-race face: the gc API process is not yet listening, so the POST fails
// in transport (connection refused) before any HTTP status. Registration
// must retry these too.
func TestRegisterAdapter_RetriesTransportErrorThenSucceeds(t *testing.T) {
	var served int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&served, 1)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	client := &http.Client{Transport: &flakyTransport{failN: 2, inner: srv.Client().Transport}}
	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", srv.URL), client, fastRetry(5), sleep)
	if err != nil {
		t.Fatalf("registration should recover once gc is listening, got: %v", err)
	}
	if got := atomic.LoadInt32(&served); got != 1 {
		t.Errorf("server served %d, want 1 (first 2 died in transport)", got)
	}
	if len(*slept) != 2 {
		t.Errorf("sleeps = %d, want 2 (two transport failures retried)", len(*slept))
	}
}

// TestRegisterAdapter_Retries5xxThenSucceeds: a city mid-boot may briefly
// 5xx; that is transient and reuses the inbound path's retryableStatus.
func TestRegisterAdapter_Retries5xxThenSucceeds(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if atomic.AddInt32(&n, 1) < 2 {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte("gc still starting"))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	if err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), fastRetry(5), sleep); err != nil {
		t.Fatalf("registration should retry a transient 5xx, got: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 2 {
		t.Errorf("requests = %d, want 2 (1 5xx + 1 success)", got)
	}
	if len(*slept) != 1 {
		t.Errorf("sleeps = %d, want 1", len(*slept))
	}
}

// TestRegisterAdapter_ExhaustsWhenCityNeverReady: if the city genuinely never
// comes up (or GC_CITY_NAME is wrong — indistinguishable at the wire, both
// are city-not-found), the retry budget is bounded, not infinite, and the
// final error names the city and attempt count so the caller's fatal log is
// actionable.
func TestRegisterAdapter_ExhaustsWhenCityNeverReady(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(cityNotReadyBody))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), fastRetry(4), sleep)
	if err == nil {
		t.Fatal("expected exhaustion error when the city never comes up, got nil")
	}
	if !strings.Contains(err.Error(), "after 4 attempts") {
		t.Errorf("error should report the attempt count: %v", err)
	}
	if !strings.Contains(err.Error(), "sct-city") {
		t.Errorf("error should name the city for an actionable fatal log: %v", err)
	}
	if !strings.Contains(err.Error(), "GC_CITY_NAME") {
		t.Errorf("error should hint at the likely misconfiguration: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 4 {
		t.Errorf("requests = %d, want 4 (all attempts made)", got)
	}
	if len(*slept) != 3 {
		t.Errorf("sleeps = %d, want 3 (between 4 attempts)", len(*slept))
	}
}

// TestRegisterAdapter_PermanentBadRequestFailsFast: a real 4xx that is not
// city-not-found (a malformed request, an auth failure) is permanent — the
// same request will keep failing, so it returns immediately rather than
// burning the whole boot budget masking a genuine misconfiguration.
func TestRegisterAdapter_PermanentBadRequestFailsFast(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte("malformed register request"))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), fastRetry(5), sleep)
	if err == nil {
		t.Fatal("expected a terminal error on a permanent 4xx, got nil")
	}
	if !strings.Contains(err.Error(), "400") {
		t.Errorf("error should name the status: %v", err)
	}
	if strings.Contains(err.Error(), "after") {
		t.Errorf("a permanent 4xx should be terminal, not an exhaustion error: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want 1 (permanent 4xx is not retried)", got)
	}
	if len(*slept) != 0 {
		t.Errorf("slept %v, want none on a terminal 4xx", *slept)
	}
}

// TestRegisterAdapter_GenericNotFoundFailsFast: a 404 that is NOT the
// city-not-found gate (e.g. a genuinely wrong route / gc version skew) is
// terminal. Only the precise city-not-found marker is treated as a boot race;
// a bare 404 must not spin for the whole budget.
func TestRegisterAdapter_GenericNotFoundFailsFast(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"code":"not-found","detail":"no such route"}`))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), fastRetry(5), sleep)
	if err == nil {
		t.Fatal("expected a terminal error on a non-city-not-found 404, got nil")
	}
	if strings.Contains(err.Error(), "after") {
		t.Errorf("a generic 404 should be terminal, not an exhaustion error: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want 1 (a generic 404 is not retried)", got)
	}
	if len(*slept) != 0 {
		t.Errorf("slept %v, want none on a terminal 404", *slept)
	}
}

// TestRegisterAdapter_SingleAttemptFloor: maxAttempts <= 0 is floored to a
// single attempt, never a zero- or infinite-attempt loop.
func TestRegisterAdapter_SingleAttemptFloor(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	rc := gcRetryConfig{maxAttempts: 0, baseBackoff: time.Millisecond, maxBackoff: time.Millisecond}
	if err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), rc, noSleep); err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want exactly 1", got)
	}
}

// TestRegisterAdapter_SendsCorrectRequest confirms the retry refactor
// preserved the full wire contract: POST to the city-escaped adapters route,
// the gc CSRF + content-type + Idempotency-Key headers, and the register body
// carrying provider/account/callback/name/capabilities.
func TestRegisterAdapter_SendsCorrectRequest(t *testing.T) {
	type captured struct {
		method, path, csrf, ctype, idem string
		body                            adapterRegisterRequest
	}
	got := make(chan captured, 1)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var body adapterRegisterRequest
		_ = json.Unmarshal(raw, &body)
		got <- captured{
			method: r.Method,
			path:   r.URL.Path,
			csrf:   r.Header.Get("X-GC-Request"),
			ctype:  r.Header.Get("Content-Type"),
			idem:   r.Header.Get("Idempotency-Key"),
			body:   body,
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	cfg := config{
		gcAPIBase:           srv.URL,
		cityName:            "sct-city",
		provider:            "slack",
		accountID:           "T0BF5GQ0DNU",
		internalCallbackURL: "http://127.0.0.1:8372/v0/city/sct-city/svc/slack",
	}
	if err := registerAdapterWith(cfg, srv.Client(), fastRetry(2), noSleep); err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	c := <-got
	if c.method != http.MethodPost {
		t.Errorf("method = %s, want POST", c.method)
	}
	if c.path != "/v0/city/sct-city/extmsg/adapters" {
		t.Errorf("path = %s, want /v0/city/sct-city/extmsg/adapters", c.path)
	}
	if c.csrf != "gc-slack-adapter" {
		t.Errorf("X-GC-Request = %q, want gc-slack-adapter", c.csrf)
	}
	if c.ctype != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", c.ctype)
	}
	if c.idem == "" {
		t.Error("Idempotency-Key header missing; retries would double-emit gc's ExtMsgAdapterAdded event")
	}
	if c.body.Provider != "slack" || c.body.AccountID != "T0BF5GQ0DNU" {
		t.Errorf("register body provider/account = %q/%q, want slack/T0BF5GQ0DNU", c.body.Provider, c.body.AccountID)
	}
	if c.body.CallbackURL != cfg.internalCallbackURL {
		t.Errorf("register body callback = %q, want %q", c.body.CallbackURL, cfg.internalCallbackURL)
	}
	if c.body.Name != "slack-adapter" {
		t.Errorf("register body name = %q, want slack-adapter", c.body.Name)
	}
	if !c.body.Capabilities.SupportsAttachments || c.body.Capabilities.MaxMessageLength != 40000 {
		t.Errorf("register body capabilities = %+v, want attachments + 40000 max", c.body.Capabilities)
	}
}

// TestRegisterAdapter_SameIdempotencyKeyAcrossRetries: a boot's registration
// retries must carry ONE stable Idempotency-Key so gc dedups the
// ExtMsgAdapterAdded event if an earlier attempt committed but its response
// was lost; a distinct boot gets a distinct key (verified separately by the
// value being non-empty and per-call).
func TestRegisterAdapter_SameIdempotencyKeyAcrossRetries(t *testing.T) {
	var mu sync.Mutex
	var keys []string
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		keys = append(keys, r.Header.Get("Idempotency-Key"))
		mu.Unlock()
		if atomic.AddInt32(&n, 1) < 3 {
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(cityNotReadyBody))
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	if err := registerAdapterWith(testConfig("", srv.URL), srv.Client(), fastRetry(5), noSleep); err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	mu.Lock()
	defer mu.Unlock()
	if len(keys) != 3 {
		t.Fatalf("server saw %d requests, want 3", len(keys))
	}
	if keys[0] == "" {
		t.Fatal("Idempotency-Key was empty")
	}
	for i, k := range keys {
		if k != keys[0] {
			t.Errorf("Idempotency-Key[%d] = %q, want stable %q across the boot's retries", i, k, keys[0])
		}
	}
}

// TestRegisterAdapter_TransportErrorExhausts covers the transport-error arm on
// the FINAL attempt (the break path + lastErr wrapping): gc never becomes
// reachable, so every attempt dies in transport and the budget exhausts.
func TestRegisterAdapter_TransportErrorExhausts(t *testing.T) {
	// A transport that always fails the dial — gc never comes up.
	client := &http.Client{Transport: &flakyTransport{failN: 1 << 30, inner: http.DefaultTransport}}
	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", "http://127.0.0.1:0"), client, fastRetry(3), sleep)
	if err == nil {
		t.Fatal("expected exhaustion error when gc never becomes reachable, got nil")
	}
	if !strings.Contains(err.Error(), "after 3 attempts") {
		t.Errorf("error should report the attempt count: %v", err)
	}
	if !strings.Contains(err.Error(), "connection refused") {
		t.Errorf("error should wrap the last transport failure: %v", err)
	}
	if len(*slept) != 2 {
		t.Errorf("sleeps = %d, want 2 (between 3 attempts)", len(*slept))
	}
}

// TestRegisterAdapter_RedirectFailsFast: the production client does not follow
// redirects, so a 3xx (e.g. a misconfigured base URL that 302s to a login) is
// surfaced and must be treated as a permanent failure — never a false success.
func TestRegisterAdapter_RedirectFailsFast(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		http.Redirect(w, r, "https://example.invalid/login", http.StatusFound)
	}))
	defer srv.Close()

	// Mirror the production no-follow client.
	client := &http.Client{
		Timeout:       5 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	sleep, slept := recordingSleep()
	err := registerAdapterWith(testConfig("", srv.URL), client, fastRetry(5), sleep)
	if err == nil {
		t.Fatal("expected a terminal error on a 3xx redirect, got nil (false success)")
	}
	if strings.Contains(err.Error(), "after") {
		t.Errorf("a redirect should be terminal, not an exhaustion error: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want 1 (redirect is not retried)", got)
	}
	if len(*slept) != 0 {
		t.Errorf("slept %v, want none on a terminal redirect", *slept)
	}
}

// TestRegisterAdapter_BodyReadErrorRetries: a response whose body errors
// mid-read (truncated mid-boot) classifies transient-vs-permanent, so it must
// be retried like a transport failure, not misread as a permanent rejection.
func TestRegisterAdapter_BodyReadErrorRetries(t *testing.T) {
	var n int32
	client := &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
		if atomic.AddInt32(&n, 1) < 2 {
			return &http.Response{
				StatusCode: http.StatusNotFound,
				Status:     "404 Not Found",
				Body:       io.NopCloser(errReader{}),
				Header:     make(http.Header),
				Request:    r,
			}, nil
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Status:     "200 OK",
			Body:       io.NopCloser(strings.NewReader(`{"ok":true}`)),
			Header:     make(http.Header),
			Request:    r,
		}, nil
	})}
	sleep, slept := recordingSleep()
	if err := registerAdapterWith(testConfig("", "http://gc.invalid"), client, fastRetry(5), sleep); err != nil {
		t.Fatalf("a mid-read body error should be retried, got: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 2 {
		t.Errorf("requests = %d, want 2 (1 read-error retry + 1 success)", got)
	}
	if len(*slept) != 1 {
		t.Errorf("sleeps = %d, want 1", len(*slept))
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

// errReader fails on the first Read, simulating a connection dropped after
// the response headers but before the body is fully delivered.
type errReader struct{}

func (errReader) Read([]byte) (int, error) { return 0, io.ErrUnexpectedEOF }

func TestIsCityNotReady(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
		want   bool
	}{
		{"boot-race 404 city-not-found", http.StatusNotFound, cityNotReadyBody, true},
		// A 404 that decodes to a DIFFERENT code is a genuine permanent
		// rejection (wrong route / version skew) — fail fast, not the gate.
		{"404 explicit different code", http.StatusNotFound, `{"code":"route-not-found"}`, false},
		// codex-flagged false positive: "city-not-found" appears in a non-code
		// field but the code is something else — must NOT be treated as the gate.
		{"404 marker only in detail field", http.StatusNotFound, `{"code":"route-not-found","detail":"upstream said city-not-found"}`, false},
		// Lean toward "not ready" when the body cannot pin down a different
		// code: on this route the only 404 source is the boot gate, and a
		// truncated/odd body mid-boot must retry, not strand.
		{"empty 404 (truncated mid-boot)", http.StatusNotFound, "", true},
		{"non-JSON 404 body", http.StatusNotFound, "not found", true},
		{"404 JSON with no code field", http.StatusNotFound, `{"detail":"nope"}`, true},
		// Status gating: 5xx/2xx/other are not this predicate's job.
		{"503 with marker is not 404", http.StatusServiceUnavailable, cityNotReadyBody, false},
		{"200 ok", http.StatusOK, `{"ok":true}`, false},
		{"400 bad request", http.StatusBadRequest, `{"code":"city-not-found"}`, false},
	}
	for _, c := range cases {
		if got := isCityNotReady(c.status, []byte(c.body)); got != c.want {
			t.Errorf("%s: isCityNotReady(%d, %q) = %v, want %v", c.name, c.status, c.body, got, c.want)
		}
	}
}

// TestBootRegisterRetryConfig documents the boot budget: it must outlast a
// real city boot (well over the inbound path's few seconds) yet stay bounded.
func TestBootRegisterRetryConfig(t *testing.T) {
	rc := bootRegisterRetryConfig()
	if rc.maxAttempts < 20 {
		t.Errorf("maxAttempts = %d, want >= 20 to outlast a slow boot", rc.maxAttempts)
	}
	// Sum the backoff schedule to assert the wall-clock budget spans minutes,
	// not the inbound path's seconds.
	var total time.Duration
	for attempt := 1; attempt < rc.maxAttempts; attempt++ {
		total += rc.backoffFor(attempt)
	}
	if total < 90*time.Second {
		t.Errorf("worst-case budget = %s, want >= 90s to cover an unhurried boot", total)
	}
}

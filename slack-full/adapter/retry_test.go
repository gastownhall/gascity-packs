package main

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestBackoffFor(t *testing.T) {
	rc := gcRetryConfig{maxAttempts: 5, baseBackoff: 250 * time.Millisecond, maxBackoff: 3 * time.Second}
	cases := []struct {
		attempt int
		want    time.Duration
	}{
		{1, 250 * time.Millisecond},
		{2, 500 * time.Millisecond},
		{3, 1 * time.Second},
		{4, 2 * time.Second},
		{5, 3 * time.Second}, // 4s capped to 3s
		{6, 3 * time.Second}, // stays capped
	}
	for _, c := range cases {
		if got := rc.backoffFor(c.attempt); got != c.want {
			t.Errorf("backoffFor(%d) = %s, want %s", c.attempt, got, c.want)
		}
	}
}

func TestRetryableStatus(t *testing.T) {
	for code, want := range map[int]bool{
		200: false, 201: false, 400: false, 401: false, 404: false,
		409: false, 422: false, 499: false, 500: true, 502: true, 503: true, 504: true,
	} {
		if got := retryableStatus(code); got != want {
			t.Errorf("retryableStatus(%d) = %v, want %v", code, got, want)
		}
	}
}

// fastRetry keeps the backoff loop bounded but non-zero so tests exercise
// the sleep path without real latency (the injected sleep is a no-op).
func fastRetry(maxAttempts int) gcRetryConfig {
	return gcRetryConfig{maxAttempts: maxAttempts, baseBackoff: time.Millisecond, maxBackoff: 4 * time.Millisecond}
}

func recordingSleep() (func(time.Duration), *[]time.Duration) {
	var slept []time.Duration
	return func(d time.Duration) { slept = append(slept, d) }, &slept
}

func TestGCPostWithRetry_SuccessFirstTry(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		if r.Header.Get("X-GC-Request") != "gc-slack-adapter" {
			t.Errorf("missing/wrong CSRF header: %q", r.Header.Get("X-GC-Request"))
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/json" {
			t.Errorf("Content-Type = %q, want application/json", ct)
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	body, err := gcPostWithRetry(srv.Client(), defaultGCRetryConfig(), sleep, srv.URL, "inbound", []byte(`{"x":1}`))
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if string(body) != `{"ok":true}` {
		t.Errorf("body = %s, want {\"ok\":true}", body)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want 1", got)
	}
	if len(*slept) != 0 {
		t.Errorf("slept %v, want no sleeps on first-try success", *slept)
	}
}

func TestGCPostWithRetry_RetriesOn5xxThenSucceeds(t *testing.T) {
	var n int32
	var mu sync.Mutex
	var gotBodies []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		mu.Lock()
		gotBodies = append(gotBodies, string(b))
		mu.Unlock()
		if atomic.AddInt32(&n, 1) < 3 {
			// Emulate the live dolt transient that caused silent drops.
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = w.Write([]byte("resolving binding ... begin read tx: invalid connection"))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	body, err := gcPostWithRetry(srv.Client(), fastRetry(5), sleep, srv.URL, "inbound", []byte(`{"x":1}`))
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if string(body) != `{"ok":true}` {
		t.Errorf("body = %s, want success body", body)
	}
	if got := atomic.LoadInt32(&n); got != 3 {
		t.Errorf("requests = %d, want 3 (2 fails + 1 success)", got)
	}
	if len(*slept) != 2 {
		t.Errorf("sleeps = %d, want 2 (between the 3 attempts)", len(*slept))
	}
	// Idempotency: the retried request body must be byte-identical each time
	// (so gc's DedupKey dedups a delivered-but-500'd POST).
	mu.Lock()
	defer mu.Unlock()
	if len(gotBodies) != 3 {
		t.Fatalf("server saw %d bodies, want 3", len(gotBodies))
	}
	for i, b := range gotBodies {
		if b != `{"x":1}` {
			t.Errorf("body[%d] = %q, want identical resend {\"x\":1}", i, b)
		}
	}
}

func TestGCPostWithRetry_NoRetryOn4xx(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte("malformed"))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	_, err := gcPostWithRetry(srv.Client(), fastRetry(5), sleep, srv.URL, "inbound", []byte(`{"x":1}`))
	if err == nil {
		t.Fatal("expected terminal error on 4xx, got nil")
	}
	if !strings.Contains(err.Error(), "400") {
		t.Errorf("error should name the status: %v", err)
	}
	if strings.Contains(err.Error(), "after") {
		t.Errorf("4xx should be terminal, not an exhaustion error: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want 1 (4xx is terminal, no retry)", got)
	}
	if len(*slept) != 0 {
		t.Errorf("slept %v, want none on terminal 4xx", *slept)
	}
}

func TestGCPostWithRetry_ExhaustsOnPersistent5xx(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusBadGateway)
		_, _ = w.Write([]byte("gc down"))
	}))
	defer srv.Close()

	sleep, slept := recordingSleep()
	_, err := gcPostWithRetry(srv.Client(), fastRetry(4), sleep, srv.URL, "inbound", []byte(`{"x":1}`))
	if err == nil {
		t.Fatal("expected exhaustion error, got nil")
	}
	if !strings.Contains(err.Error(), "after 4 attempts") {
		t.Errorf("error should report attempt count: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 4 {
		t.Errorf("requests = %d, want 4 (all attempts made)", got)
	}
	if len(*slept) != 3 {
		t.Errorf("sleeps = %d, want 3 (between 4 attempts)", len(*slept))
	}
}

// flakyTransport returns a transport error the first failN calls, then
// delegates to inner — models gc being briefly unreachable.
type flakyTransport struct {
	failN int32
	calls int32
	inner http.RoundTripper
}

func (f *flakyTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	if atomic.AddInt32(&f.calls, 1) <= f.failN {
		return nil, fmt.Errorf("dial tcp 127.0.0.1: connect: connection refused")
	}
	return f.inner.RoundTrip(r)
}

func TestGCPostWithRetry_RetriesOnTransportError(t *testing.T) {
	var served int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&served, 1)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer srv.Close()

	client := &http.Client{Transport: &flakyTransport{failN: 2, inner: srv.Client().Transport}}
	sleep, slept := recordingSleep()
	body, err := gcPostWithRetry(client, fastRetry(5), sleep, srv.URL, "inbound", []byte(`{"x":1}`))
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if string(body) != `{"ok":true}` {
		t.Errorf("body = %s, want success", body)
	}
	if got := atomic.LoadInt32(&served); got != 1 {
		t.Errorf("server served %d, want 1 (first 2 died in transport)", got)
	}
	if len(*slept) != 2 {
		t.Errorf("sleeps = %d, want 2 (two transport failures retried)", len(*slept))
	}
}

func TestGCPostWithRetry_SingleAttemptFloor(t *testing.T) {
	var n int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&n, 1)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	sleep, _ := recordingSleep()
	// maxAttempts <= 0 must be floored to a single attempt, not an infinite
	// or zero-attempt loop.
	rc := gcRetryConfig{maxAttempts: 0, baseBackoff: time.Millisecond, maxBackoff: time.Millisecond}
	if _, err := gcPostWithRetry(srv.Client(), rc, sleep, srv.URL, "inbound", []byte(`{}`)); err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got := atomic.LoadInt32(&n); got != 1 {
		t.Errorf("requests = %d, want exactly 1", got)
	}
}

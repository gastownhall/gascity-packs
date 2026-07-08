package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// fastRetry is a retryPolicy with sub-millisecond backoff so registration
// retry tests exercise the loop without real waits.
var fastRetry = retryPolicy{initialBackoff: time.Millisecond, maxBackoff: 5 * time.Millisecond}

func TestRegisterAdapter(t *testing.T) {
	srv := newTestServer(t)
	var got adapterRegisterRequest
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/extmsg/adapters") {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		_ = json.NewDecoder(r.Body).Decode(&got)
		w.WriteHeader(http.StatusOK)
	}))
	defer gc.Close()
	srv.cfg.gcAPIBase = gc.URL

	if err := srv.registerAdapter(context.Background()); err != nil {
		t.Fatalf("registerAdapter: %v", err)
	}
	if got.Provider != "slack" || got.AccountID != "T123" {
		t.Errorf("register payload = %+v", got)
	}
	if got.Capabilities.SupportsChildConversations {
		t.Error("Tier 2 must not advertise child conversations")
	}
}

// TestRegisterAdapterWithRetry404ThenSuccess is the registration-race
// regression: the city returns 404 "city not found" while it is still
// starting, then 200 once adoption completes. The adapter must retry through
// the 404s and succeed instead of exiting on the first one (ref gc-c69aq).
func TestRegisterAdapterWithRetry404ThenSuccess(t *testing.T) {
	srv := newTestServer(t)
	const failFirst = 3
	var calls atomic.Int32
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		if calls.Add(1) <= failFirst {
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, "city not found or not running: ds-research")
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer gc.Close()
	srv.cfg.gcAPIBase = gc.URL

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.registerAdapterWithRetry(ctx, fastRetry); err != nil {
		t.Fatalf("registerAdapterWithRetry: %v", err)
	}
	if got := calls.Load(); got != failFirst+1 {
		t.Errorf("expected %d attempts (%d×404 then success), got %d", failFirst+1, failFirst, got)
	}
}

// TestRegisterAdapterWithRetryDeadline asserts the loop gives up once the
// ctx deadline passes when the city never comes up, surfacing the last error
// rather than spinning forever.
func TestRegisterAdapterWithRetryDeadline(t *testing.T) {
	srv := newTestServer(t)
	var calls atomic.Int32
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		w.WriteHeader(http.StatusNotFound)
		_, _ = io.WriteString(w, "city not found")
	}))
	defer gc.Close()
	srv.cfg.gcAPIBase = gc.URL

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	err := srv.registerAdapterWithRetry(ctx, fastRetry)
	if err == nil {
		t.Fatal("expected deadline error, got nil")
	}
	if !strings.Contains(err.Error(), "city unreachable") {
		t.Errorf("expected give-up error, got %v", err)
	}
	if calls.Load() == 0 {
		t.Error("expected at least one registration attempt before giving up")
	}
}

// TestRegisterAdapterWithRetryNonRetryable asserts a permanent failure (a
// 4xx that is not 404, e.g. a malformed request) returns immediately without
// burning the backoff loop — backoff cannot fix a misconfiguration.
func TestRegisterAdapterWithRetryNonRetryable(t *testing.T) {
	srv := newTestServer(t)
	var calls atomic.Int32
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		w.WriteHeader(http.StatusBadRequest)
		_, _ = io.WriteString(w, "bad provider")
	}))
	defer gc.Close()
	srv.cfg.gcAPIBase = gc.URL

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	err := srv.registerAdapterWithRetry(ctx, fastRetry)
	if err == nil || !strings.Contains(err.Error(), "bad provider") {
		t.Fatalf("expected immediate non-retryable error surfacing body, got %v", err)
	}
	if got := calls.Load(); got != 1 {
		t.Errorf("expected exactly 1 attempt for a non-retryable error, got %d", got)
	}
}

func TestPostJSONSurfacesErrorStatus(t *testing.T) {
	srv := newTestServer(t)
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = io.WriteString(w, "nope")
	}))
	defer gc.Close()
	if err := srv.postJSON(context.Background(), gc.URL, []byte(`{}`)); err == nil || !strings.Contains(err.Error(), "nope") {
		t.Fatalf("expected error surfacing body, got %v", err)
	}
}

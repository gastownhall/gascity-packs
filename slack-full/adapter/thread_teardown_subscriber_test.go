package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// fakeThreadRegistry records RemoveBySessionID calls and returns
// preconfigured (channelID, threadTS, ok) tuples. Used so the subscriber
// tests don't have to wire a real on-disk thread session registry.
type fakeThreadRegistry struct {
	mu      sync.Mutex
	calls   []string
	results map[string]fakeThreadResult
}

type fakeThreadResult struct {
	channelID string
	threadTS  string
	ok        bool
}

func newFakeThreadRegistry() *fakeThreadRegistry {
	return &fakeThreadRegistry{results: make(map[string]fakeThreadResult)}
}

func (f *fakeThreadRegistry) bind(sessionID, channelID, threadTS string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.results[sessionID] = fakeThreadResult{channelID: channelID, threadTS: threadTS, ok: true}
}

func (f *fakeThreadRegistry) RemoveBySessionID(sessionID string) (string, string, bool) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, sessionID)
	r, ok := f.results[sessionID]
	if !ok {
		return "", "", false
	}
	delete(f.results, sessionID)
	return r.channelID, r.threadTS, r.ok
}

func (f *fakeThreadRegistry) callCount() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.calls)
}

// sseTestServer is a minimal SSE producer that emits queued frames over
// /v0/city/{cityName}/events/stream. Tests push raw frame bytes into the
// queue; the handler writes them and flushes.
type sseTestServer struct {
	mu     sync.Mutex
	frames chan string
	hits   atomic.Int32
}

func newSSETestServer() *sseTestServer {
	return &sseTestServer{frames: make(chan string, 64)}
}

func (s *sseTestServer) push(frame string) {
	s.frames <- frame
}

func (s *sseTestServer) handler(w http.ResponseWriter, r *http.Request) {
	s.hits.Add(1)
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.WriteHeader(http.StatusOK)
	flusher, _ := w.(http.Flusher)
	if flusher != nil {
		flusher.Flush()
	}
	for {
		select {
		case <-r.Context().Done():
			return
		case frame, ok := <-s.frames:
			if !ok {
				return
			}
			if _, err := io.WriteString(w, frame); err != nil {
				return
			}
			if flusher != nil {
				flusher.Flush()
			}
		}
	}
}

// sessionStoppedFrame builds an SSE "event: event\ndata: ...\n\n" frame
// carrying a session.stopped envelope with the typed payload.
func sessionStoppedFrame(seq int, eventType, sessionID, template, reason string) string {
	envelope := map[string]any{
		"seq":   seq,
		"type":  eventType,
		"ts":    time.Now().UTC().Format(time.RFC3339),
		"actor": "gc",
		"payload": map[string]string{
			"session_id": sessionID,
			"template":   template,
			"reason":     reason,
		},
	}
	b, _ := json.Marshal(envelope)
	return fmt.Sprintf("event: event\nid: %d\ndata: %s\n\n", seq, string(b))
}

func TestThreadTeardownSubscriberDropsBindingOnSessionStopped(t *testing.T) {
	srv := newSSETestServer()
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", srv.handler)
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	threadReg := newFakeThreadRegistry()
	threadReg.bind("gc-sess-A", "C1", "1700000000.0001")

	aliasPath := filepath.Join(t.TempDir(), "alias.json")
	aliasReg, err := newHandleAliasRegistry(aliasPath)
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}
	if err := aliasReg.Set("dispatch", "gc-sess-A"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}
	if err := aliasReg.Set("backup", "gc-sess-A"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}
	if err := aliasReg.Set("other", "gc-sess-OTHER"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cfg := teardownSubscriberConfig{
		gcAPIBase:         httpSrv.URL,
		cityName:          "test-city",
		initialBackoff:    10 * time.Millisecond,
		maxBackoff:        100 * time.Millisecond,
		readHeaderTimeout: 2 * time.Second,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, threadReg, aliasReg)
		close(done)
	}()

	srv.push(sessionStoppedFrame(1, "session.stopped", "gc-sess-A", "mayor", "user requested"))

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if threadReg.callCount() >= 1 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if threadReg.callCount() != 1 {
		t.Fatalf("RemoveBySessionID call count = %d; want 1", threadReg.callCount())
	}

	// Aliases pointing at gc-sess-A should be deleted; the unrelated alias remains.
	for time.Now().Before(deadline) {
		if _, ok := aliasReg.Get("dispatch"); !ok {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if _, ok := aliasReg.Get("dispatch"); ok {
		t.Errorf("alias 'dispatch' still present; want deleted")
	}
	if _, ok := aliasReg.Get("backup"); ok {
		t.Errorf("alias 'backup' still present; want deleted")
	}
	if sid, ok := aliasReg.Get("other"); !ok || sid != "gc-sess-OTHER" {
		t.Errorf("alias 'other' = (%q, %v); want (gc-sess-OTHER, true)", sid, ok)
	}

	cancel()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatalf("subscriber did not exit within 2s of cancel")
	}
}

func TestThreadTeardownSubscriberHandlesSessionCrashed(t *testing.T) {
	srv := newSSETestServer()
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", srv.handler)
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	threadReg := newFakeThreadRegistry()
	threadReg.bind("gc-sess-X", "C2", "1700000000.0002")

	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}
	if err := aliasReg.Set("crash-handle", "gc-sess-X"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "test-city",
		initialBackoff: 10 * time.Millisecond,
		maxBackoff:     100 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, threadReg, aliasReg)
		close(done)
	}()

	srv.push(sessionStoppedFrame(1, "session.crashed", "gc-sess-X", "polecat", "process exited"))

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if _, ok := aliasReg.Get("crash-handle"); !ok {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if _, ok := aliasReg.Get("crash-handle"); ok {
		t.Errorf("alias 'crash-handle' should have been deleted")
	}

	cancel()
	<-done
}

func TestThreadTeardownSubscriberIgnoresUnknownSession(t *testing.T) {
	srv := newSSETestServer()
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", srv.handler)
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	threadReg := newFakeThreadRegistry()
	// No bindings.

	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "test-city",
		initialBackoff: 10 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, threadReg, aliasReg)
		close(done)
	}()

	srv.push(sessionStoppedFrame(1, "session.stopped", "gc-sess-UNKNOWN", "", ""))

	// Wait until subscriber has at least observed the event (RemoveBySessionID called).
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if threadReg.callCount() >= 1 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if threadReg.callCount() != 1 {
		t.Fatalf("RemoveBySessionID call count = %d; want 1", threadReg.callCount())
	}

	cancel()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatalf("subscriber did not exit within 2s of cancel")
	}
}

func TestThreadTeardownSubscriberExitsOnContextCancel(t *testing.T) {
	srv := newSSETestServer()
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", srv.handler)
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "test-city",
		initialBackoff: 10 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, newFakeThreadRegistry(), aliasReg)
		close(done)
	}()

	// Wait for first connect to establish.
	deadline := time.Now().Add(1 * time.Second)
	for time.Now().Before(deadline) {
		if srv.hits.Load() >= 1 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	cancel()
	select {
	case <-done:
	case <-time.After(1 * time.Second):
		t.Fatalf("subscriber did not exit within 1s of cancel")
	}
}

func TestThreadTeardownSubscriberReconnectsOnDrop(t *testing.T) {
	// First server: serves one frame and closes the connection. Second
	// server: serves one frame after the subscriber reconnects.
	var connectCount atomic.Int32
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", func(w http.ResponseWriter, r *http.Request) {
		n := connectCount.Add(1)
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, _ := w.(http.Flusher)
		if flusher != nil {
			flusher.Flush()
		}
		if n == 1 {
			// Drop immediately to force reconnect.
			return
		}
		// On second connect: emit a session.stopped frame.
		_, _ = io.WriteString(w, sessionStoppedFrame(int(n), "session.stopped", "gc-sess-RC", "", ""))
		if flusher != nil {
			flusher.Flush()
		}
		<-r.Context().Done()
	})
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	threadReg := newFakeThreadRegistry()
	threadReg.bind("gc-sess-RC", "C-RC", "1700000000.RC")
	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "test-city",
		initialBackoff: 10 * time.Millisecond,
		maxBackoff:     100 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, threadReg, aliasReg)
		close(done)
	}()

	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if threadReg.callCount() >= 1 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if threadReg.callCount() < 1 {
		t.Fatalf("subscriber did not process event after reconnect; calls=%d connects=%d",
			threadReg.callCount(), connectCount.Load())
	}
	if connectCount.Load() < 2 {
		t.Fatalf("subscriber did not reconnect; connects=%d", connectCount.Load())
	}

	cancel()
	<-done
}

func TestThreadTeardownSubscriberSkipsMalformedPayload(t *testing.T) {
	srv := newSSETestServer()
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", srv.handler)
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	threadReg := newFakeThreadRegistry()
	threadReg.bind("gc-sess-OK", "C", "T")
	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "test-city",
		initialBackoff: 10 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, threadReg, aliasReg)
		close(done)
	}()

	// Malformed payload: not JSON-decodable.
	srv.push("event: event\nid: 1\ndata: {not-valid-json\n\n")
	// Empty session_id payload.
	srv.push("event: event\nid: 2\ndata: {\"type\":\"session.stopped\",\"payload\":{\"session_id\":\"\"}}\n\n")
	// Valid event after malformed ones — must still be processed.
	srv.push(sessionStoppedFrame(3, "session.stopped", "gc-sess-OK", "", ""))

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if threadReg.callCount() >= 1 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if threadReg.callCount() != 1 {
		t.Fatalf("RemoveBySessionID call count = %d; want 1 (malformed events should not call into registry)",
			threadReg.callCount())
	}

	cancel()
	<-done
}

func TestThreadTeardownSubscriberIgnoresUnrelatedEvents(t *testing.T) {
	srv := newSSETestServer()
	mux := http.NewServeMux()
	mux.HandleFunc("/v0/city/test-city/events/stream", srv.handler)
	httpSrv := httptest.NewServer(mux)
	defer httpSrv.Close()

	threadReg := newFakeThreadRegistry()
	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "test-city",
		initialBackoff: 10 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, threadReg, aliasReg)
		close(done)
	}()

	// Non-terminal session events should be ignored.
	srv.push(sessionStoppedFrame(1, "session.woke", "gc-sess-Q", "", ""))
	srv.push(sessionStoppedFrame(2, "bead.created", "gc-sess-Q", "", ""))

	// Tiny wait to give subscriber a chance to mishandle.
	time.Sleep(150 * time.Millisecond)
	if threadReg.callCount() != 0 {
		t.Fatalf("RemoveBySessionID called %d times for non-terminal events; want 0",
			threadReg.callCount())
	}

	cancel()
	<-done
}

func TestFindHandlesBySessionID(t *testing.T) {
	reg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}
	// Empty registry → 0 hits.
	if got := reg.findHandlesBySessionID("any"); len(got) != 0 {
		t.Errorf("empty registry: got %v, want []", got)
	}
	// Empty session ID → 0 hits.
	if got := reg.findHandlesBySessionID(""); len(got) != 0 {
		t.Errorf("empty sessionID: got %v, want []", got)
	}
	if err := reg.Set("alpha", "gc-1"); err != nil {
		t.Fatalf("Set: %v", err)
	}
	if err := reg.Set("beta", "gc-1"); err != nil {
		t.Fatalf("Set: %v", err)
	}
	if err := reg.Set("gamma", "gc-2"); err != nil {
		t.Fatalf("Set: %v", err)
	}
	// 1 hit.
	got := reg.findHandlesBySessionID("gc-2")
	if len(got) != 1 || got[0] != "gamma" {
		t.Errorf("gc-2: got %v, want [gamma]", got)
	}
	// Multiple hits.
	got = reg.findHandlesBySessionID("gc-1")
	if len(got) != 2 {
		t.Errorf("gc-1: got %v, want 2 entries", got)
	}
	seen := map[string]bool{}
	for _, h := range got {
		seen[h] = true
	}
	if !seen["alpha"] || !seen["beta"] {
		t.Errorf("gc-1: expected [alpha beta], got %v", got)
	}
	// Non-matching sessionID.
	if got := reg.findHandlesBySessionID("gc-missing"); len(got) != 0 {
		t.Errorf("gc-missing: got %v, want []", got)
	}
}

// TestThreadTeardownSubscriberEscapesCityName verifies that
// runThreadTeardownSubscriber percent-encodes cityName before
// interpolating it into the /v0/city/{city}/events/stream URL
// (gc-cby.48). Mirrors the TestRegisterAdapterEscapesCityName /
// TestPostInboundEscapesCityName pattern: capture both the raw wire form
// (to confirm the escape lands on the wire) and the decoded form (to
// confirm round-trip identity through net/http).
func TestThreadTeardownSubscriberEscapesCityName(t *testing.T) {
	rawPathCh := make(chan string, 1)
	decodedPathCh := make(chan string, 1)
	httpSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case rawPathCh <- r.URL.EscapedPath():
		default:
		}
		select {
		case decodedPathCh <- r.URL.Path:
		default:
		}
		// Hold the connection until the client cancels so the
		// subscriber doesn't reconnect and noisily multiply hits.
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, _ := w.(http.Flusher)
		if flusher != nil {
			flusher.Flush()
		}
		<-r.Context().Done()
	}))
	defer httpSrv.Close()

	aliasReg, err := newHandleAliasRegistry(filepath.Join(t.TempDir(), "alias.json"))
	if err != nil {
		t.Fatalf("alias registry: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cfg := teardownSubscriberConfig{
		gcAPIBase:      httpSrv.URL,
		cityName:       "city/with slash",
		initialBackoff: 10 * time.Millisecond,
		maxBackoff:     50 * time.Millisecond,
	}
	done := make(chan struct{})
	go func() {
		runThreadTeardownSubscriber(ctx, cfg, newFakeThreadRegistry(), aliasReg)
		close(done)
	}()

	var rawPath, decodedPath string
	select {
	case rawPath = <-rawPathCh:
	case <-time.After(2 * time.Second):
		t.Fatal("subscriber did not connect to gc stub within 2s")
	}
	select {
	case decodedPath = <-decodedPathCh:
	default:
	}

	wantRawCity := "city%2Fwith%20slash"
	if !strings.Contains(rawPath, wantRawCity) {
		t.Errorf("raw path %q missing escaped cityName %q", rawPath, wantRawCity)
	}
	if !strings.HasSuffix(rawPath, "/events/stream") {
		t.Errorf("raw path %q missing /events/stream suffix", rawPath)
	}
	wantDecoded := "/v0/city/city/with slash/events/stream"
	if decodedPath != wantDecoded {
		t.Errorf("decoded path = %q, want %q", decodedPath, wantDecoded)
	}

	cancel()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatalf("subscriber did not exit within 2s of cancel")
	}
}

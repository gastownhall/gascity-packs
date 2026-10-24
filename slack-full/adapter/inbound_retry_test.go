package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

// fakeInbound is a stand-in for gc's /extmsg/inbound. Like gc's Append it
// dedups on provider_message_id: a message it has already stored is not
// stored again. failures is the scripted reply per attempt (0 = success);
// once it runs out every attempt succeeds. storeBeforeFail makes a failed
// attempt store the entry first, which is the ambiguous-write case
// (gastownhall/gascity#7977): the 5xx came back after the bd write landed.
type fakeInbound struct {
	mu              sync.Mutex
	failures        []int
	storeBeforeFail bool
	dropConnFirst   bool
	attempts        int
	bodies          []string
	stored          map[string]int
	notified        int
}

func (f *fakeInbound) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(r.Body)
	f.mu.Lock()
	defer f.mu.Unlock()
	f.attempts++
	f.bodies = append(f.bodies, string(raw))
	if f.dropConnFirst && f.attempts == 1 {
		hj, ok := w.(http.Hijacker)
		if !ok {
			panic("fakeInbound: hijack unsupported")
		}
		conn, _, _ := hj.Hijack()
		_ = conn.Close()
		return
	}
	var req struct {
		Message externalInboundMessage `json:"message"`
	}
	if err := json.Unmarshal(raw, &req); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	id := req.Message.ProviderMessageID
	code := 0
	if len(f.failures) > 0 {
		code, f.failures = f.failures[0], f.failures[1:]
	}
	if code != 0 {
		if f.storeBeforeFail && f.stored[id] == 0 {
			f.stored[id]++
		}
		http.Error(w, "scripted failure", code)
		return
	}
	if f.stored[id] == 0 {
		f.stored[id]++
	}
	// Appending or finding the stored entry both notify, once per
	// delivered message.
	f.notified++
	w.WriteHeader(http.StatusAccepted)
}

func newFakeInbound(t *testing.T, f *fakeInbound) config {
	t.Helper()
	f.stored = map[string]int{}
	srv := httptest.NewServer(f)
	t.Cleanup(srv.Close)
	return config{gcAPIBase: srv.URL, cityName: "test-city"}
}

// recordSleeps makes the policy record its delays instead of sleeping.
func recordSleeps(p inboundRetryPolicy) (inboundRetryPolicy, *[]time.Duration) {
	var mu sync.Mutex
	var got []time.Duration
	p.sleep = func(_ context.Context, d time.Duration) error {
		mu.Lock()
		got = append(got, d)
		mu.Unlock()
		return nil
	}
	return p, &got
}

func testInboundMsg() externalInboundMessage {
	return externalInboundMessage{
		ProviderMessageID: "1791999999.000100",
		Conversation:      conversationRef{ConversationID: "C1"},
		Actor:             externalActor{ID: "U1"},
		Text:              "hello",
		DedupKey:          "slack-1791999999.000100",
	}
}

// TestPostInboundRetries5xxThenDeliversOnce: the first attempt stores the
// entry but answers 500; the retry dedups onto it and succeeds. The
// message is stored once and notified once, and both attempts carried
// the same provider_message_id.
func TestPostInboundRetries5xxThenDeliversOnce(t *testing.T) {
	f := &fakeInbound{failures: []int{http.StatusInternalServerError}, storeBeforeFail: true}
	cfg := newFakeInbound(t, f)
	var sleeps *[]time.Duration
	cfg.inboundRetry, sleeps = recordSleeps(inboundRetryPolicy{})

	if err := postInbound(cfg, testInboundMsg()); err != nil {
		t.Fatalf("postInbound: %v", err)
	}
	if f.attempts != 2 {
		t.Fatalf("attempts = %d, want 2", f.attempts)
	}
	if f.bodies[0] != f.bodies[1] {
		t.Errorf("retry changed the body:\n first: %s\nsecond: %s", f.bodies[0], f.bodies[1])
	}
	if got := f.stored["1791999999.000100"]; got != 1 {
		t.Errorf("stored = %d, want 1", got)
	}
	if f.notified != 1 {
		t.Errorf("notified = %d, want 1", f.notified)
	}
	if len(*sleeps) != 1 {
		t.Errorf("sleeps = %v, want one backoff", *sleeps)
	}
}

// TestPostInboundRetriesTransportError: a dropped connection is retried
// like a 5xx.
func TestPostInboundRetriesTransportError(t *testing.T) {
	f := &fakeInbound{dropConnFirst: true}
	cfg := newFakeInbound(t, f)
	cfg.inboundRetry, _ = recordSleeps(inboundRetryPolicy{})

	if err := postInbound(cfg, testInboundMsg()); err != nil {
		t.Fatalf("postInbound: %v", err)
	}
	if f.attempts != 2 || f.notified != 1 {
		t.Errorf("attempts = %d, notified = %d; want 2 and 1", f.attempts, f.notified)
	}
}

// TestPostInboundDoesNotRetry4xx: a 4xx is the request's own fault.
func TestPostInboundDoesNotRetry4xx(t *testing.T) {
	for _, code := range []int{http.StatusBadRequest, http.StatusNotFound, http.StatusTooManyRequests} {
		f := &fakeInbound{failures: []int{code}}
		cfg := newFakeInbound(t, f)
		var sleeps *[]time.Duration
		cfg.inboundRetry, sleeps = recordSleeps(inboundRetryPolicy{})

		err := postInbound(cfg, testInboundMsg())
		if err == nil {
			t.Fatalf("%d: postInbound: want error, got nil", code)
		}
		if f.attempts != 1 || len(*sleeps) != 0 {
			t.Errorf("%d: attempts = %d, sleeps = %v; want 1 attempt, no sleep", code, f.attempts, *sleeps)
		}
		if strings.Contains(err.Error(), "gave up") {
			t.Errorf("%d: a 4xx is not a give-up: %v", code, err)
		}
	}
}

// TestPostInboundGivesUpLoudlyAtCap: a 5xx on every attempt stops at
// maxAttempts and logs a give-up line naming the message. Not parallel:
// captureLog swaps the global logger.
func TestPostInboundGivesUpLoudlyAtCap(t *testing.T) {
	read, cleanup := captureLog(t)
	defer cleanup()

	f := &fakeInbound{failures: []int{503, 503, 503, 503, 503, 503, 503}}
	cfg := newFakeInbound(t, f)
	var sleeps *[]time.Duration
	cfg.inboundRetry, sleeps = recordSleeps(inboundRetryPolicy{})

	err := postInbound(cfg, testInboundMsg())
	if err == nil {
		t.Fatal("postInbound: want error, got nil")
	}
	if f.attempts != defaultInboundRetry.maxAttempts {
		t.Errorf("attempts = %d, want %d", f.attempts, defaultInboundRetry.maxAttempts)
	}
	if len(*sleeps) != defaultInboundRetry.maxAttempts-1 {
		t.Errorf("sleeps = %v, want %d", *sleeps, defaultInboundRetry.maxAttempts-1)
	}
	if !strings.Contains(err.Error(), "gave up after 5 attempts") {
		t.Errorf("err = %v, want a give-up after 5 attempts", err)
	}
	logs := read()
	if !strings.Contains(logs, "inbound POST giving up: msg=C1/1791999999.000100 after 5 attempts") {
		t.Errorf("no give-up line naming the message:\n%s", logs)
	}
	if got := strings.Count(logs, "inbound POST retry: msg=C1/1791999999.000100"); got != 4 {
		t.Errorf("retry lines = %d, want 4:\n%s", got, logs)
	}
}

// TestPostInboundStopsAtBudget: the wall-time budget ends retries before
// maxAttempts when the next backoff would overrun it.
func TestPostInboundStopsAtBudget(t *testing.T) {
	f := &fakeInbound{failures: []int{503, 503, 503, 503, 503, 503, 503, 503, 503, 503}}
	cfg := newFakeInbound(t, f)
	cfg.inboundRetry = inboundRetryPolicy{
		maxAttempts: 10,
		baseDelay:   40 * time.Millisecond,
		maxDelay:    40 * time.Millisecond,
		budget:      100 * time.Millisecond,
	}

	start := time.Now()
	err := postInbound(cfg, testInboundMsg())
	if err == nil || !strings.Contains(err.Error(), "budget") {
		t.Fatalf("err = %v, want a budget give-up", err)
	}
	if f.attempts >= 10 {
		t.Errorf("attempts = %d, want the budget to stop it before 10", f.attempts)
	}
	if el := time.Since(start); el > time.Second {
		t.Errorf("took %s, want about the 100ms budget", el)
	}
}

// TestInboundRetryDelay: delays double from baseDelay, cap at maxDelay,
// and are jittered into [d/2, d].
func TestInboundRetryDelay(t *testing.T) {
	p := defaultInboundRetry
	want := []time.Duration{time.Second, 2 * time.Second, 4 * time.Second, 8 * time.Second, 16 * time.Second, 16 * time.Second}
	for i, d := range want {
		for range 50 {
			got := p.delay(i + 1)
			if got < d/2 || got > d {
				t.Fatalf("delay(%d) = %s, want in [%s, %s]", i+1, got, d/2, d)
			}
		}
	}
	// The default schedule (4 sleeps of at most 1+2+4+8s) fits the budget.
	var worst time.Duration
	for n := 1; n < p.maxAttempts; n++ {
		worst += want[n-1]
	}
	if worst >= p.budget {
		t.Errorf("worst-case backoff %s does not fit the %s budget", worst, p.budget)
	}
}

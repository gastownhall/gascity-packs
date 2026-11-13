package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestInboundEventDedupClaimFinish(t *testing.T) {
	clock := time.Unix(1_700_000_000, 0)
	d := newInboundEventDedup(time.Hour)
	d.now = func() time.Time { return clock }
	const key = "A0SWITCH\x00Ev1"

	if !d.claim(key) {
		t.Fatal("first claim refused")
	}
	// In flight: a concurrent copy (the other transport) is a duplicate.
	if d.claim(key) {
		t.Error("claim granted while the first copy is in flight")
	}
	// A retryable answer releases the claim, so the redelivery Slack makes
	// for it is processed rather than swallowed.
	d.finish(key, false)
	if !d.claim(key) {
		t.Fatal("claim refused after a released (5xx) first copy")
	}
	d.finish(key, true)
	if d.claim(key) {
		t.Error("claim granted for an event already delivered")
	}
	// The memory is bounded by TTL.
	clock = clock.Add(time.Hour + time.Second)
	if !d.claim(key) {
		t.Error("claim refused after the TTL elapsed")
	}
}

func TestInboundEventDedupSweepsExpiredEntries(t *testing.T) {
	clock := time.Unix(1_700_000_000, 0)
	d := newInboundEventDedup(time.Minute)
	d.now = func() time.Time { return clock }
	for _, k := range []string{"a", "b", "c"} {
		d.claim(k)
		d.finish(k, true)
	}
	d.claim("inflight")
	clock = clock.Add(2 * time.Minute)
	d.claim("trigger") // sweep runs on claim once per sweep interval
	d.mu.Lock()
	defer d.mu.Unlock()
	for _, k := range []string{"a", "b", "c"} {
		if _, ok := d.entries[k]; ok {
			t.Errorf("expired entry %q survived the sweep", k)
		}
	}
	// An in-flight claim is never swept from under its handler.
	if _, ok := d.entries["inflight"]; !ok {
		t.Error("sweep evicted an in-flight claim")
	}
}

func TestInboundEventKeyIsPerApp(t *testing.T) {
	// event_id is assigned per delivery to an app. Two apps receiving the
	// same message must not dedup each other; the company gateway owns that
	// cross-app dedup by origin.
	a := inboundEventKey(slackEventEnvelope{APIAppID: "A0SWITCH", EventID: "Ev1"})
	b := inboundEventKey(slackEventEnvelope{APIAppID: "A0AGENT", EventID: "Ev1"})
	if a == b {
		t.Errorf("keys for different apps collide: %q", a)
	}
	if k := inboundEventKey(slackEventEnvelope{APIAppID: "A0SWITCH"}); k != "" {
		t.Errorf("key without event_id = %q, want empty (dedup disabled)", k)
	}
}

func TestInboundEventDedupNilAndEmptyKeyAlwaysClaim(t *testing.T) {
	var nilCache *inboundEventDedup
	if !nilCache.claim("k") || !nilCache.claim("k") {
		t.Error("nil cache refused a claim")
	}
	nilCache.finish("k", true) // must not panic

	d := newInboundEventDedup(time.Hour)
	if !d.claim("") || !d.claim("") {
		t.Error("empty key refused a claim")
	}
}

// dedupTestConfig is a legacy-path config wired with a shared dedup cache, as
// main() wires one for both transports.
func dedupTestConfig(gcURL string) config {
	return config{
		gcAPIBase:       gcURL,
		cityName:        "test-city",
		provider:        "slack",
		accountID:       "T01234567",
		slackSigningKey: "secret",
		dispatchSem:     make(chan struct{}, 8),
		eventDedup:      newInboundEventDedup(inboundEventDedupTTL),
	}
}

// settle waits for asynchronous legacy dispatch to land, then gives a stray
// second dispatch time to show up.
func settle(t *testing.T, gc *fakeGC, want int) {
	t.Helper()
	waitUntil(t, func() bool { return gc.inboundCalls() >= want })
	time.Sleep(150 * time.Millisecond)
	if got := gc.inboundCalls(); got != want {
		t.Errorf("legacy dispatches = %d, want %d", got, want)
	}
}

// TestSlackEventsDedupAcrossTransports: the same event_id arriving over both
// transports is dispatched once, in either order. The duplicate is still
// answered (200 over HTTP, an ack over the socket) so Slack stops retrying.
func TestSlackEventsDedupAcrossTransports(t *testing.T) {
	t.Run("http then socket", func(t *testing.T) {
		gc := newFakeGC(t)
		cfg := dedupTestConfig(gc.server.URL)
		aliasReg := newTestHandleAliasRegistry(t)
		httpHandler := handleSlackEvents(cfg, aliasReg, nil, nil, nil, nil)
		tr := newTestTransport(socketEventDeliverer(serveVerifiedSlackEvents(cfg, aliasReg, nil, nil, nil, nil), cfg.companyGateway.agentAppsSnapshot))

		payload := messagePayload(t, "Ev-both-1", "C_LEGACY", "1700000000.000601", "said once")
		w := httptest.NewRecorder()
		httpHandler(w, signedSlackEventRequest(t, cfg.slackSigningKey, payload))
		if w.Code != http.StatusOK {
			t.Fatalf("HTTP status = %d, want 200", w.Code)
		}
		dupBefore := inboundEventDuplicatesTotal.Load()
		conn := &scriptedConn{frames: [][]byte{eventsAPIFrame(t, "env-1", payload, 0)}}
		if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
			t.Fatalf("pumpSocket err = %v", err)
		}
		if ids := ackedIDs(t, conn); len(ids) != 1 {
			t.Errorf("acks = %v, want the duplicate acked", ids)
		}
		if got := inboundEventDuplicatesTotal.Load(); got != dupBefore+1 {
			t.Errorf("duplicates counter = %d, want %d", got, dupBefore+1)
		}
		settle(t, gc, 1)
	})

	t.Run("socket then http", func(t *testing.T) {
		gc := newFakeGC(t)
		cfg := dedupTestConfig(gc.server.URL)
		aliasReg := newTestHandleAliasRegistry(t)
		httpHandler := handleSlackEvents(cfg, aliasReg, nil, nil, nil, nil)
		tr := newTestTransport(socketEventDeliverer(serveVerifiedSlackEvents(cfg, aliasReg, nil, nil, nil, nil), cfg.companyGateway.agentAppsSnapshot))

		payload := messagePayload(t, "Ev-both-2", "C_LEGACY", "1700000000.000602", "said once")
		conn := &scriptedConn{frames: [][]byte{eventsAPIFrame(t, "env-2", payload, 0)}}
		if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
			t.Fatalf("pumpSocket err = %v", err)
		}
		w := httptest.NewRecorder()
		httpHandler(w, signedSlackEventRequest(t, cfg.slackSigningKey, payload))
		if w.Code != http.StatusOK {
			t.Fatalf("duplicate HTTP status = %d, want 200 (so Slack stops retrying)", w.Code)
		}
		settle(t, gc, 1)
	})
}

// TestSlackEventsDedupSocketRedelivery: Slack redelivers an envelope whose ack
// it never saw, under a new envelope id with retry_attempt set. Both are acked;
// the event is dispatched once.
func TestSlackEventsDedupSocketRedelivery(t *testing.T) {
	gc := newFakeGC(t)
	cfg := dedupTestConfig(gc.server.URL)
	aliasReg := newTestHandleAliasRegistry(t)
	tr := newTestTransport(socketEventDeliverer(serveVerifiedSlackEvents(cfg, aliasReg, nil, nil, nil, nil), cfg.companyGateway.agentAppsSnapshot))

	payload := messagePayload(t, "Ev-redeliver", "C_LEGACY", "1700000000.000700", "once please")
	conn := &scriptedConn{frames: [][]byte{
		eventsAPIFrame(t, "env-first", payload, 0),
		eventsAPIFrame(t, "env-retry", payload, 1),
	}}
	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v", err)
	}
	if ids := ackedIDs(t, conn); len(ids) != 2 || ids[0] != "env-first" || ids[1] != "env-retry" {
		t.Errorf("acks = %v, want both envelopes acked", ids)
	}
	settle(t, gc, 1)
}

// TestSlackEventsDedupDistinctEventsBothDispatch guards against an
// over-eager dedup: two different event_ids are two deliveries.
func TestSlackEventsDedupDistinctEventsBothDispatch(t *testing.T) {
	gc := newFakeGC(t)
	cfg := dedupTestConfig(gc.server.URL)
	aliasReg := newTestHandleAliasRegistry(t)
	tr := newTestTransport(socketEventDeliverer(serveVerifiedSlackEvents(cfg, aliasReg, nil, nil, nil, nil), cfg.companyGateway.agentAppsSnapshot))

	conn := &scriptedConn{frames: [][]byte{
		eventsAPIFrame(t, "env-a", messagePayload(t, "Ev-a", "C_LEGACY", "1700000000.000801", "one"), 0),
		eventsAPIFrame(t, "env-b", messagePayload(t, "Ev-b", "C_LEGACY", "1700000000.000802", "two"), 0),
	}}
	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v", err)
	}
	settle(t, gc, 2)
}

// TestSlackEventsDedupReleasesOnRetryableAnswer drives a company-room event
// over the socket while the gateway's startup barrier is closed. The gateway
// answers 503, so the envelope stays unacked and the dedup claim is released;
// Slack's redelivery (retry_attempt=1) is then admitted once, with its retry
// hint recorded on the receipt; and a late HTTP copy of the same event_id is
// absorbed.
func TestSlackEventsDedupReleasesOnRetryableAnswer(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 8) // barrier closed

	const secret = "test-signing-secret"
	cfg := config{
		gcAPIBase:       gc.server.URL,
		cityName:        "test-city",
		provider:        "slack",
		accountID:       testTeamID,
		slackSigningKey: secret,
		dispatchSem:     make(chan struct{}, 8),
		companyGateway:  h.gw,
		eventDedup:      newInboundEventDedup(inboundEventDedupTTL),
	}
	h.gw.cfg.dispatchSem = cfg.dispatchSem
	aliasReg := newTestHandleAliasRegistry(t)
	serve := serveVerifiedSlackEvents(cfg, aliasReg, nil, nil, nil, nil)
	tr := newTestTransport(socketEventDeliverer(serve, cfg.companyGateway.agentAppsSnapshot))

	ev := humanMessage(baseOrigin().TS, "hello team")
	ev.Type = "message"
	rawEv, _ := json.Marshal(ev)
	payload, _ := json.Marshal(slackEventEnvelope{
		Type: "event_callback", TeamID: testTeamID, APIAppID: "A0SWITCH", EventID: "Ev-company", Event: rawEv,
	})

	first := &scriptedConn{frames: [][]byte{eventsAPIFrame(t, "env-first", payload, 0)}}
	_ = tr.pumpSocket(context.Background(), first, nil)
	if ids := ackedIDs(t, first); len(ids) != 0 {
		t.Fatalf("acks = %v, want the barrier-503 envelope left unacked", ids)
	}
	if r, _ := h.receipts.Get(baseOrigin()); r != nil {
		t.Fatalf("receipt created while barrier closed: %+v", r)
	}

	h.openBarrier()
	retryFrame, _ := json.Marshal(socketEnvelope{
		Type: "events_api", EnvelopeID: "env-retry", Payload: payload, RetryAttempt: 1, RetryReason: "timeout",
	})
	second := &scriptedConn{frames: [][]byte{retryFrame}}
	_ = tr.pumpSocket(context.Background(), second, nil)
	if ids := ackedIDs(t, second); len(ids) != 1 || ids[0] != "env-retry" {
		t.Fatalf("acks = %v, want the redelivery acked", ids)
	}
	h.wait()
	if got := len(gc.sessionCalls()); got != 1 {
		t.Errorf("company deliveries = %d, want 1", got)
	}
	r, _ := h.receipts.Get(baseOrigin())
	if r == nil || r.RetryNum != 1 || r.RetryReason != "timeout" {
		t.Errorf("socket redelivery hints not on the receipt: %+v", r)
	}

	// The same event_id arriving late over HTTP is absorbed before admission.
	w := httptest.NewRecorder()
	handleSlackEvents(cfg, aliasReg, nil, nil, nil, nil)(w, signedSlackEventRequest(t, secret, payload))
	if w.Code != http.StatusOK {
		t.Errorf("late HTTP copy status = %d, want 200", w.Code)
	}
	h.wait()
	if got := len(gc.sessionCalls()); got != 1 {
		t.Errorf("company deliveries after HTTP copy = %d, want still 1", got)
	}
}

func TestHealthzReportsInboundDuplicates(t *testing.T) {
	prev := socketModeEnabled.Load()
	t.Cleanup(func() { socketModeEnabled.Store(prev) })
	socketModeEnabled.Store(true)
	w := httptest.NewRecorder()
	handleHealthz(w, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if !strings.Contains(w.Body.String(), "inbound_event_duplicates_total=") {
		t.Errorf("healthz missing inbound_event_duplicates_total:\n%s", w.Body.String())
	}
}

// TestStatusCaptureAccepted: the dedup claim settles from the answer the
// handler gave. Only a 5xx is retryable; a body with no explicit status, like
// no write at all, is the net/http default 200.
func TestStatusCaptureAccepted(t *testing.T) {
	cases := []struct {
		name string
		do   func(w http.ResponseWriter)
		want bool
	}{
		{"nothing written", func(http.ResponseWriter) {}, true},
		{"body only is 200", func(w http.ResponseWriter) { _, _ = w.Write([]byte("ok")) }, true},
		{"explicit 200", func(w http.ResponseWriter) { w.WriteHeader(http.StatusOK) }, true},
		{"4xx is not retried", func(w http.ResponseWriter) { w.WriteHeader(http.StatusBadRequest) }, true},
		{"503 is retryable", func(w http.ResponseWriter) { w.WriteHeader(http.StatusServiceUnavailable) }, false},
		{"first status wins", func(w http.ResponseWriter) {
			w.WriteHeader(http.StatusServiceUnavailable)
			w.WriteHeader(http.StatusOK)
		}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			sw := &statusCapture{ResponseWriter: rec}
			tc.do(sw)
			if got := sw.accepted(); got != tc.want {
				t.Errorf("accepted() = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestValidSlackChallenge(t *testing.T) {
	cases := []struct {
		in   string
		want bool
	}{
		{"3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P", true},
		{"a", true},
		{"under_score-dash", true},
		{strings.Repeat("a", maxSlackChallengeLen), true},
		{"", false},
		{strings.Repeat("a", maxSlackChallengeLen+1), false},
		{"<script>alert(1)</script>", false},
		{"has space", false},
		{"line\nbreak", false},
		{"semi;colon", false},
		{"quote\"", false},
		{"café", false},
	}
	for _, tc := range cases {
		if got := validSlackChallenge(tc.in); got != tc.want {
			t.Errorf("validSlackChallenge(%q) = %v, want %v", tc.in, got, tc.want)
		}
	}
}

// TestSlackEventsURLVerificationEcho: a signed handshake with a token-shaped
// challenge is echoed as plain text; one carrying markup or an oversized value
// is refused with 400 and never reflected.
func TestSlackEventsURLVerificationEcho(t *testing.T) {
	cfg := dedupTestConfig("http://unused.invalid")
	aliasReg := newTestHandleAliasRegistry(t)
	httpHandler := handleSlackEvents(cfg, aliasReg, nil, nil, nil, nil)

	handshake := func(challenge string) *httptest.ResponseRecorder {
		body, err := json.Marshal(map[string]any{"type": "url_verification", "challenge": challenge})
		if err != nil {
			t.Fatalf("marshal: %v", err)
		}
		w := httptest.NewRecorder()
		httpHandler(w, signedSlackEventRequest(t, cfg.slackSigningKey, body))
		return w
	}

	t.Run("token challenge is echoed", func(t *testing.T) {
		const challenge = "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"
		w := handshake(challenge)
		if w.Code != http.StatusOK {
			t.Fatalf("status = %d, want 200", w.Code)
		}
		if got := w.Body.String(); got != challenge {
			t.Errorf("body = %q, want the challenge echoed", got)
		}
		if ct := w.Header().Get("Content-Type"); ct != "text/plain" {
			t.Errorf("Content-Type = %q, want text/plain", ct)
		}
		if nf := w.Header().Get("X-Content-Type-Options"); nf != "nosniff" {
			t.Errorf("X-Content-Type-Options = %q, want nosniff", nf)
		}
	})

	for name, challenge := range map[string]string{
		"markup":    "<script>alert(1)</script>",
		"oversized": strings.Repeat("a", maxSlackChallengeLen+1),
	} {
		t.Run(name+" challenge is refused", func(t *testing.T) {
			w := handshake(challenge)
			if w.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, want 400", w.Code)
			}
			if strings.Contains(w.Body.String(), challenge) {
				t.Errorf("body reflects the rejected challenge: %q", w.Body.String())
			}
		})
	}
}

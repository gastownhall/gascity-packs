package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// Tests for the Events API redelivery seen-set (hw-94w5k finding #4):
// a Slack retry re-delivers the same envelope with the same event_id,
// and the adapter must forward it into gc exactly once.

// postSignedEvent signs and POSTs one events-API envelope through
// handleSlackEvents, returning the recorder.
func postSignedEvent(t *testing.T, cfg config, envBody []byte) *httptest.ResponseRecorder {
	t.Helper()
	ts := strconv.FormatInt(time.Now().Unix(), 10)
	sig := signFor(cfg.slackSigningKey, ts, envBody)
	req := httptest.NewRequest(http.MethodPost, "/slack/events", bytes.NewReader(envBody))
	req.Header.Set("X-Slack-Request-Timestamp", ts)
	req.Header.Set("X-Slack-Signature", sig)
	w := httptest.NewRecorder()
	handleSlackEvents(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil)(w, req)
	return w
}

// eventEnvelopeBody marshals a plain channel-message event_callback
// with the given event_id (empty means "omit").
func eventEnvelopeBody(t *testing.T, eventID, ts, text string) []byte {
	t.Helper()
	rawMsg, err := json.Marshal(slackMessageEvent{
		Type: "message", Channel: "C1", User: "U1", TS: ts, Text: text,
	})
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}
	envBody, err := json.Marshal(slackEventEnvelope{
		Type: "event_callback", EventID: eventID, Event: rawMsg,
	})
	if err != nil {
		t.Fatalf("marshal envelope: %v", err)
	}
	return envBody
}

// awaitInboundHits polls until the gc stub has seen want inbound POSTs
// or the deadline passes, then asserts the count holds (no extras).
func awaitInboundHits(t *testing.T, hits *int32, want int32) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if atomic.LoadInt32(hits) >= want {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	// Settle window: catch a duplicate forward racing in late.
	time.Sleep(150 * time.Millisecond)
	if got := atomic.LoadInt32(hits); got != want {
		t.Errorf("inbound POSTs = %d, want %d", got, want)
	}
}

func dedupTestConfig(t *testing.T, gcURL string) config {
	t.Helper()
	return config{
		gcAPIBase:       gcURL,
		cityName:        "test-city",
		provider:        "slack",
		accountID:       "T1",
		slackSigningKey: "secret",
		dispatchSem:     make(chan struct{}, 4),
		eventDedup:      newEventDedupCache(eventDedupTTL),
	}
}

func countingGCStub(t *testing.T) (*httptest.Server, *int32) {
	t.Helper()
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		atomic.AddInt32(&hits, 1)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(srv.Close)
	return srv, &hits
}

// A retried delivery — same envelope, same event_id — forwards to gc
// exactly once; the retry is dropped with a dedup log line and still
// sees a 200 ack.
func TestHandleSlackEventsDedupsRetriedEventID(t *testing.T) {
	gcStub, hits := countingGCStub(t)
	cfg := dedupTestConfig(t, gcStub.URL)

	read, cleanup := captureLog(t)
	t.Cleanup(cleanup)

	envBody := eventEnvelopeBody(t, "Ev0001", "1.0", "hi")
	if w := postSignedEvent(t, cfg, envBody); w.Result().StatusCode != http.StatusOK {
		t.Fatalf("first delivery status = %d, want 200", w.Result().StatusCode)
	}
	awaitInboundHits(t, hits, 1)

	if w := postSignedEvent(t, cfg, envBody); w.Result().StatusCode != http.StatusOK {
		t.Fatalf("retry delivery status = %d, want 200 (retries must still be acked)", w.Result().StatusCode)
	}
	awaitInboundHits(t, hits, 1)
	// The drop verdict is logged from the async claim goroutine — poll.
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) && !strings.Contains(read(), "slack event dedup") {
		time.Sleep(10 * time.Millisecond)
	}
	if !strings.Contains(read(), "slack event dedup") {
		t.Errorf("log missing 'slack event dedup' marker:\n%s", read())
	}
}

// Distinct event ids are independent — both forward.
func TestHandleSlackEventsDistinctEventIDsBothForward(t *testing.T) {
	gcStub, hits := countingGCStub(t)
	cfg := dedupTestConfig(t, gcStub.URL)

	postSignedEvent(t, cfg, eventEnvelopeBody(t, "Ev0001", "1.0", "hi"))
	postSignedEvent(t, cfg, eventEnvelopeBody(t, "Ev0002", "2.0", "hello"))
	awaitInboundHits(t, hits, 2)
}

// An envelope with no event_id is never deduped: two deliveries both
// forward. (Only event_callback envelopes carry event_id; nothing
// else must get caught in the seen-set.)
func TestHandleSlackEventsNoEventIDNoDedup(t *testing.T) {
	gcStub, hits := countingGCStub(t)
	cfg := dedupTestConfig(t, gcStub.URL)

	envBody := eventEnvelopeBody(t, "", "1.0", "hi")
	postSignedEvent(t, cfg, envBody)
	postSignedEvent(t, cfg, envBody)
	awaitInboundHits(t, hits, 2)
}

// A delivery dropped at the queue-full boundary must NOT record its
// event_id: Slack's retry is the only recovery for that event, and it
// has to pass the seen-set when capacity is back.
func TestHandleSlackEventsQueueFullDropDoesNotRecordEventID(t *testing.T) {
	gcStub, hits := countingGCStub(t)
	cfg := dedupTestConfig(t, gcStub.URL)
	cfg.dispatchSem = make(chan struct{}, 1)

	holdRelease, _, ok := cfg.acquireDispatchSlot()
	if !ok {
		t.Fatal("acquireDispatchSlot: failed to take initial slot in fresh sem")
	}
	envBody := eventEnvelopeBody(t, "Ev0001", "1.0", "hi")
	postSignedEvent(t, cfg, envBody) // dropped: queue full
	awaitInboundHits(t, hits, 0)

	holdRelease()
	postSignedEvent(t, cfg, envBody) // Slack retry after capacity freed
	awaitInboundHits(t, hits, 1)
}

// A delivery whose forward to gc FAILS must release its event_id: in
// the lost-ack scenario the Slack retry is the only path for the
// message to reach gc, and a committed id would turn the transient
// failure into permanent message loss.
func TestHandleSlackEventsFailedForwardReleasesEventID(t *testing.T) {
	var hits int32
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		// First request fails (gc hiccup); subsequent requests accept.
		if atomic.AddInt32(&hits, 1) == 1 {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)
	cfg := dedupTestConfig(t, gcStub.URL)

	envBody := eventEnvelopeBody(t, "Ev0001", "1.0", "hi")
	postSignedEvent(t, cfg, envBody) // forward fails with 500
	awaitInboundHits(t, &hits, 1)

	postSignedEvent(t, cfg, envBody) // Slack retry: must NOT be deduped
	awaitInboundHits(t, &hits, 2)
}

// A nil cache (mis-wired test config) never dedupes and never panics.
func TestHandleSlackEventsNilDedupCacheForwardsEverything(t *testing.T) {
	gcStub, hits := countingGCStub(t)
	cfg := dedupTestConfig(t, gcStub.URL)
	cfg.eventDedup = nil

	envBody := eventEnvelopeBody(t, "Ev0001", "1.0", "hi")
	postSignedEvent(t, cfg, envBody)
	postSignedEvent(t, cfg, envBody)
	awaitInboundHits(t, hits, 2)
}

// Cache semantics: begin claims an unknown id; a second begin while
// in flight reports a wait channel; after commit it drops; after the
// TTL it proceeds again; empty ids never dedupe.
func TestEventDedupCacheLifecycle(t *testing.T) {
	var mu sync.Mutex
	current := time.Now()
	c := newEventDedupCache(eventDedupTTL)
	c.now = func() time.Time {
		mu.Lock()
		defer mu.Unlock()
		return current
	}

	proceed, wait := c.begin("Ev1")
	if !proceed || wait != nil {
		t.Fatalf("first begin = (%v, %v), want (true, nil)", proceed, wait)
	}
	proceed, wait = c.begin("Ev1")
	if proceed || wait == nil {
		t.Fatalf("in-flight begin = (%v, %v), want (false, wait-chan)", proceed, wait)
	}
	select {
	case <-wait:
		t.Fatal("wait channel closed before the first delivery concluded")
	default:
	}
	c.commit("Ev1")
	select {
	case <-wait:
	default:
		t.Fatal("wait channel not closed by commit")
	}
	proceed, wait = c.begin("Ev1")
	if proceed || wait != nil {
		t.Fatalf("committed begin = (%v, %v), want (false, nil) — duplicate drop", proceed, wait)
	}
	mu.Lock()
	current = current.Add(eventDedupTTL + time.Minute)
	mu.Unlock()
	if proceed, _ = c.begin("Ev1"); !proceed {
		t.Error("begin after TTL = false, want true (entry expired)")
	}
	if proceed, _ = c.begin(""); !proceed {
		t.Error("begin(\"\") = false, want true (empty ids never dedupe)")
	}
}

// Cache semantics: forget erases the claim (closing any waiter) so a
// redelivery proceeds as brand new.
func TestEventDedupCacheForgetReleases(t *testing.T) {
	c := newEventDedupCache(eventDedupTTL)
	if proceed, _ := c.begin("Ev1"); !proceed {
		t.Fatal("first begin = false, want true")
	}
	_, wait := c.begin("Ev1")
	if wait == nil {
		t.Fatal("in-flight begin returned nil wait channel")
	}
	c.forget("Ev1")
	select {
	case <-wait:
	default:
		t.Fatal("wait channel not closed by forget")
	}
	if proceed, _ := c.begin("Ev1"); !proceed {
		t.Error("begin after forget = false, want true (retry takes over)")
	}
	if n := c.size(); n != 1 {
		t.Errorf("size = %d, want 1 (the retry's fresh claim)", n)
	}
}

// Cache semantics: the size cap evicts the oldest committed id,
// keeping the map bounded under an event flood.
func TestEventDedupCacheCapEvictsOldest(t *testing.T) {
	var mu sync.Mutex
	current := time.Now()
	c := newEventDedupCache(eventDedupTTL)
	c.now = func() time.Time {
		mu.Lock()
		defer mu.Unlock()
		return current
	}

	for i := 0; i <= eventDedupMaxEntries; i++ {
		mu.Lock()
		current = current.Add(time.Millisecond)
		mu.Unlock()
		id := fmt.Sprintf("Ev%d", i)
		c.begin(id)
		c.commit(id)
	}
	if n := c.size(); n != eventDedupMaxEntries {
		t.Errorf("size = %d, want cap %d", n, eventDedupMaxEntries)
	}
	if proceed, _ := c.begin("Ev0"); !proceed {
		t.Error("oldest id survived cap eviction; want evicted (begin proceeds)")
	}
	last := fmt.Sprintf("Ev%d", eventDedupMaxEntries)
	if proceed, _ := c.begin(last); proceed {
		t.Error("newest id missing after cap eviction; want kept (begin drops)")
	}
}

// A nil cache is inert on every method.
func TestEventDedupCacheNilSafe(t *testing.T) {
	var c *eventDedupCache
	if proceed, wait := c.begin("Ev1"); !proceed || wait != nil {
		t.Error("begin on nil cache must proceed with no wait")
	}
	c.commit("Ev1")
	c.forget("Ev1")
	if n := c.size(); n != 0 {
		t.Errorf("size on nil cache = %d, want 0", n)
	}
}

// A redelivery racing the FIRST delivery's still-running forward must
// wait for its outcome (codex r2 P1): if the forward fails, the
// waiting retry takes over and the message still reaches gc.
func TestHandleSlackEventsInflightRetryTakesOverAfterFailure(t *testing.T) {
	var hits int32
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		if atomic.AddInt32(&hits, 1) == 1 {
			// First forward: slow AND failing — the retry arrives
			// while this is still in flight.
			time.Sleep(300 * time.Millisecond)
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)
	cfg := dedupTestConfig(t, gcStub.URL)

	envBody := eventEnvelopeBody(t, "Ev0001", "1.0", "hi")
	postSignedEvent(t, cfg, envBody) // async: forward now in flight
	// Redelivery while the first forward is still running. The handler
	// blocks on the in-flight claim, sees the failure verdict, and
	// takes over.
	postSignedEvent(t, cfg, envBody)
	awaitInboundHits(t, &hits, 2)
}

// ...and if the in-flight first delivery SUCCEEDS, the waiting retry
// drops as a duplicate.
func TestHandleSlackEventsInflightRetryDropsAfterSuccess(t *testing.T) {
	var hits int32
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		atomic.AddInt32(&hits, 1)
		time.Sleep(300 * time.Millisecond)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)
	cfg := dedupTestConfig(t, gcStub.URL)

	envBody := eventEnvelopeBody(t, "Ev0001", "1.0", "hi")
	postSignedEvent(t, cfg, envBody)
	postSignedEvent(t, cfg, envBody) // waits on the in-flight claim, then drops
	awaitInboundHits(t, &hits, 1)
}

// codex r12: a completed channel leg survives forget so a retaken
// redelivery skips postInbound and retries only the alias leg;
// commit clears the marker.
func TestEventDedupChannelLegMarker(t *testing.T) {
	c := newEventDedupCache(eventDedupTTL)
	if c.isChannelLegDone("ev1") {
		t.Fatal("marker set before markChannelLegDone")
	}
	proceed, _ := c.begin("ev1")
	if !proceed {
		t.Fatal("begin ev1: want proceed")
	}
	c.markChannelLegDone("ev1")
	c.forget("ev1")
	if !c.isChannelLegDone("ev1") {
		t.Fatal("marker lost across forget; retaken delivery would duplicate the channel leg")
	}
	// The retaken delivery succeeds end-to-end: commit clears the marker.
	proceed, _ = c.begin("ev1")
	if !proceed {
		t.Fatal("re-begin ev1 after forget: want proceed")
	}
	c.commit("ev1")
	if c.isChannelLegDone("ev1") {
		t.Fatal("marker survived commit")
	}
	// nil-safety
	var nilCache *eventDedupCache
	nilCache.markChannelLegDone("x")
	if nilCache.isChannelLegDone("x") {
		t.Fatal("nil cache reported a marker")
	}
}

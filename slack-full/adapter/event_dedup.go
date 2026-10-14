package main

import (
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// inboundEventDedup absorbs a Slack event delivered more than once before it
// reaches dispatch. It is shared by both inbound transports (the
// /slack/events listener and Socket Mode, socketmode.go), so it catches:
//
//   - the same event arriving over both transports while Socket Mode is
//     being switched on or off in the app settings;
//   - a Socket Mode redelivery of an envelope whose ack was lost;
//   - an HTTP retry (X-Slack-Retry-Num) of an event the legacy path already
//     dispatched — that path answers 200 at once, but a slow network can
//     still make Slack retry.
//
// The key is (api_app_id, event_id). Slack assigns event_id per delivery to
// an app, so two apps receiving the same message (a switchboard and a
// registered agent app in one room) carry distinct keys and are both still
// handed to the gateway, which owns that cross-app dedup by origin.
//
// A key moves through two states. claim marks it in flight; finish either
// confirms it (the handler accepted the event: any status below 500) or
// releases it (a retryable 5xx), so the redelivery that 5xx asks for is
// processed rather than swallowed. A duplicate that arrives while the first
// copy is in flight is treated as delivered: the first copy carries the
// retry obligation, and its transport redelivers if it fails.
//
// The memory is in-process and bounded by TTL. It is not a durability
// mechanism: company-room receipts (ingress_receipts.go) remain the durable
// dedup authority for Slack's Delayed Events redelivery, which can run for 24h
// and across adapter restarts. This cache only needs to outlive the minutes a
// duplicate realistically trails its original.
type inboundEventDedup struct {
	mu        sync.Mutex
	ttl       time.Duration
	entries   map[string]dedupEntry
	lastSweep time.Time
	now       func() time.Time
}

type dedupEntry struct {
	expires  time.Time
	inFlight bool
}

// inboundEventDedupTTL is how long a delivered event is remembered. Slack's
// retry ladder for both transports is immediate, +1m, +5m; an hour covers
// it with margin.
const inboundEventDedupTTL = time.Hour

// inboundEventDedupSweepEvery bounds how often claim walks the map to evict
// expired entries.
const inboundEventDedupSweepEvery = time.Minute

// inboundEventDuplicatesTotal counts deliveries the cache absorbed. It
// surfaces on /healthz (in the Socket Mode block) so an operator can see the
// dedup doing work.
var inboundEventDuplicatesTotal atomic.Uint64

func newInboundEventDedup(ttl time.Duration) *inboundEventDedup {
	return &inboundEventDedup{
		ttl:     ttl,
		entries: make(map[string]dedupEntry),
		now:     time.Now,
	}
}

// inboundEventKey is the dedup key for an event envelope, or "" when the
// envelope carries no event_id (url_verification, hand-built test bodies),
// which disables dedup for that delivery.
func inboundEventKey(env slackEventEnvelope) string {
	if env.EventID == "" {
		return ""
	}
	return env.APIAppID + "\x00" + env.EventID
}

// claim reports whether the caller should process the event. false means the
// key is already delivered or in flight. A nil cache and an empty key always
// claim, which keeps every caller that never wired a cache (unit tests,
// handlers built outside main) byte-for-byte unchanged.
func (d *inboundEventDedup) claim(key string) bool {
	if d == nil || key == "" {
		return true
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	now := d.now()
	if now.Sub(d.lastSweep) >= inboundEventDedupSweepEvery {
		for k, e := range d.entries {
			if !e.inFlight && now.After(e.expires) {
				delete(d.entries, k)
			}
		}
		d.lastSweep = now
	}
	if e, ok := d.entries[key]; ok && (e.inFlight || now.Before(e.expires)) {
		inboundEventDuplicatesTotal.Add(1)
		return false
	}
	d.entries[key] = dedupEntry{inFlight: true}
	return true
}

// finish settles a claimed key: accepted confirms it for the TTL, otherwise
// the claim is released so a redelivery is processed. No-op for a nil cache
// or an empty key.
func (d *inboundEventDedup) finish(key string, accepted bool) {
	if d == nil || key == "" {
		return
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	if !accepted {
		delete(d.entries, key)
		return
	}
	d.entries[key] = dedupEntry{expires: d.now().Add(d.ttl)}
}

// statusCapture records the status an http.ResponseWriter was given, so the
// event handler can settle a dedup claim from its own answer.
//
// It deliberately does not override Write: body bytes pass straight through
// the embedded writer. A Write override would only default the status to 200,
// which accepted already reads from an unset code, and a pass-through Write
// method is a body sink CodeQL flags as reflected XSS for every value any
// handler writes to a ResponseWriter (the url_verification echo included).
type statusCapture struct {
	http.ResponseWriter
	code int
}

func (s *statusCapture) WriteHeader(code int) {
	if s.code == 0 {
		s.code = code
	}
	s.ResponseWriter.WriteHeader(code)
}

// accepted reports whether the answer was non-retryable. A handler that wrote
// a body or nothing at all answered 200, as in net/http, and leaves code unset.
func (s *statusCapture) accepted() bool {
	return s.code < http.StatusInternalServerError
}

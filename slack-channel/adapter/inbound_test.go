package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

// inboundCollector stands in for gc's extmsg inbound endpoint, recording
// every delivered message keyed by explicit_target.
type inboundCollector struct {
	srv *httptest.Server
	mu  sync.Mutex
	got map[string]externalInboundMessage
	all []externalInboundMessage
}

func newInboundCollector(t *testing.T, s *server) *inboundCollector {
	t.Helper()
	c := &inboundCollector{got: map[string]externalInboundMessage{}}
	c.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/extmsg/inbound") {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		var wrap struct {
			Message externalInboundMessage `json:"message"`
		}
		if err := json.NewDecoder(r.Body).Decode(&wrap); err != nil {
			t.Errorf("decode inbound: %v", err)
		}
		c.mu.Lock()
		c.got[wrap.Message.ExplicitTarget] = wrap.Message
		c.all = append(c.all, wrap.Message)
		c.mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(c.srv.Close)
	s.cfg.gcAPIBase = c.srv.URL
	return c
}

// count returns how many deliveries have landed so far, safely against the
// goroutine handleSlackEvents routes in.
func (c *inboundCollector) count() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.all)
}

// awaitCount waits up to timeout for the collector to reach want deliveries,
// returning what it actually saw.
func (c *inboundCollector) awaitCount(want int, timeout time.Duration) int {
	deadline := time.Now().Add(timeout)
	for {
		if got := c.count(); got >= want || time.Now().After(deadline) {
			return got
		}
		time.Sleep(2 * time.Millisecond)
	}
}

func routeMessage(s *server, ev slackMessageEvent) {
	raw, _ := json.Marshal(ev)
	s.routeEvent(slackEventEnvelope{Type: "event_callback", Event: raw})
}

func TestRouteEventBoundFanOut(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)
	mustBind(t, srv, "C1", "room", "s1", "s2")

	routeMessage(srv, slackMessageEvent{Type: "message", User: "U9", Text: "deploy please", Channel: "C1", TS: "1700.1"})

	if len(c.all) != 2 {
		t.Fatalf("want 2 deliveries (one per bound session), got %d", len(c.all))
	}
	for _, sid := range []string{"s1", "s2"} {
		msg, ok := c.got[sid]
		if !ok {
			t.Fatalf("no delivery to %s", sid)
		}
		if msg.Text != "deploy please" {
			t.Errorf("%s text = %q, want full body", sid, msg.Text)
		}
		if msg.DedupKey != "slack-1700.1-"+sid {
			t.Errorf("%s dedup_key = %q, want per-target", sid, msg.DedupKey)
		}
		if msg.Conversation.ConversationID != "C1" || msg.Conversation.Kind != "room" {
			t.Errorf("%s conversation = %+v", sid, msg.Conversation)
		}
	}
	// last-inbound recorded for reply-current/react.
	if ref, ok := srv.latestInbound("s1"); !ok || ref.channelID != "C1" || ref.messageTS != "1700.1" {
		t.Errorf("latestInbound(s1) = %+v ok=%v", ref, ok)
	}
}

func TestRouteEventAppMentionStripsInBoundChannel(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)
	mustBind(t, srv, "C1", "room", "s1")

	routeMessage(srv, slackMessageEvent{Type: "app_mention", User: "U9", Text: "<@U0BOT> status?", Channel: "C1", TS: "1700.2"})

	if msg, ok := c.got["s1"]; !ok || msg.Text != "status?" {
		t.Errorf("app_mention to bound session = %q (ok=%v), want stripped 'status?'", msg.Text, ok)
	}
}

func TestRouteEventAliasRouting(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)
	if _, err := srv.upsertHandleAlias("mayor", "sess-m"); err != nil {
		t.Fatal(err)
	}

	// Unbound channel; alias address routes to the aliased session.
	routeMessage(srv, slackMessageEvent{Type: "message", User: "U9", Text: "@mayor: ship it", Channel: "C9", TS: "1700.3"})

	if len(c.all) != 1 {
		t.Fatalf("want 1 delivery, got %d", len(c.all))
	}
	if msg, ok := c.got["sess-m"]; !ok || msg.Text != "ship it" {
		t.Errorf("alias delivery = %q (ok=%v), want stripped 'ship it'", msg.Text, ok)
	}
}

func TestRouteEventAliasOverridesBoundText(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)
	mustBind(t, srv, "C1", "room", "s1")
	if _, err := srv.upsertHandleAlias("mayor", "sess-m"); err != nil {
		t.Fatal(err)
	}

	routeMessage(srv, slackMessageEvent{Type: "message", User: "U9", Text: "@mayor: hi team", Channel: "C1", TS: "1700.4"})

	if len(c.all) != 2 {
		t.Fatalf("want 2 deliveries (bound + alias), got %d", len(c.all))
	}
	if msg := c.got["s1"]; msg.Text != "@mayor: hi team" {
		t.Errorf("bound session text = %q, want full body", msg.Text)
	}
	if msg := c.got["sess-m"]; msg.Text != "hi team" {
		t.Errorf("alias session text = %q, want stripped", msg.Text)
	}
}

func TestRouteEventAppMentionFallback(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)

	// Unbound, unaliased app_mention falls back to the default target.
	routeMessage(srv, slackMessageEvent{Type: "app_mention", User: "U9", Text: "<@U0BOT> hello", Channel: "C9", TS: "1700.5"})

	if msg, ok := c.got["mayor"]; !ok || msg.Text != "hello" {
		t.Errorf("fallback delivery = %q (ok=%v), want 'hello' to mayor", msg.Text, ok)
	}
}

func TestRouteEventDrops(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)
	mustBind(t, srv, "C1", "room", "s1")

	drops := []struct {
		name string
		ev   slackMessageEvent
	}{
		{"plain message unbound channel", slackMessageEvent{Type: "message", User: "U9", Text: "hi", Channel: "C9", TS: "1"}},
		{"bot message", slackMessageEvent{Type: "message", BotID: "B1", Text: "hi", Channel: "C1", TS: "1"}},
		{"subtype edit", slackMessageEvent{Type: "message", Subtype: "message_changed", User: "U9", Text: "hi", Channel: "C1", TS: "1"}},
		{"empty user", slackMessageEvent{Type: "message", Text: "hi", Channel: "C1", TS: "1"}},
		{"unknown type", slackMessageEvent{Type: "reaction_added", User: "U9", Channel: "C1", TS: "1"}},
		{"empty after strip", slackMessageEvent{Type: "app_mention", User: "U9", Text: "<@U0BOT>", Channel: "C1", TS: "1"}},
	}
	for _, tc := range drops {
		t.Run(tc.name, func(t *testing.T) {
			before := len(c.all)
			routeMessage(srv, tc.ev)
			if len(c.all) != before {
				t.Errorf("%s: expected drop, but a delivery was made", tc.name)
			}
		})
	}
}

// TestRouteEventDropsForeignWorkspace pins the foreign-workspace drop at
// routeEvent, the funnel both transports feed. Neither transport establishes
// which workspace an event came from — Socket Mode has no signature, and the
// HTTP path's HMAC proves only that Slack sent it for this app — so a guard on
// one transport leaves the other open. Both arms send the same event payload;
// the local-team arm is the control that proves a drop is the guard firing and
// not the event simply going nowhere.
func TestRouteEventDropsForeignWorkspace(t *testing.T) {
	srv := newTestServer(t)
	c := newInboundCollector(t, srv)

	// The app_mention fallback delivers to the default inbound target from any
	// unbound channel, so an un-dropped event here is always a delivery. Both
	// arms carry the identical payload: the socket frame's payload is
	// byte-for-byte the body Slack would have POSTed.
	frameFor := func(teamID string) socketEnvelope {
		var env socketEnvelope
		if err := json.Unmarshal(appMentionEnvelope(t, "env-fw", teamID, "<@U0BOT> hi"), &env); err != nil {
			t.Fatalf("unmarshal socket frame: %v", err)
		}
		return env
	}

	overSocket := func(t *testing.T, teamID string) {
		t.Helper()
		srv.handleSocketEnvelope(frameFor(teamID))
	}

	overHTTP := func(t *testing.T, teamID string) {
		t.Helper()
		body := []byte(frameFor(teamID).Payload)
		ts := strconv.FormatInt(time.Now().Unix(), 10)
		req := httptest.NewRequest(http.MethodPost, "/slack/events", strings.NewReader(string(body)))
		req.Header.Set("X-Slack-Request-Timestamp", ts)
		req.Header.Set("X-Slack-Signature", signSlack(srv.cfg.signingSecret, ts, body))
		rec := httptest.NewRecorder()
		srv.handleSlackEvents()(rec, req)
		// A valid signature: Slack is satisfied, which is exactly why the
		// signature cannot be what decides the workspace question.
		if rec.Code != http.StatusOK {
			t.Fatalf("status = %d, want 200", rec.Code)
		}
	}

	for _, tc := range []struct {
		name string
		send func(*testing.T, string)
	}{
		{"socket path", overSocket},
		{"http path", overHTTP},
	} {
		t.Run(tc.name, func(t *testing.T) {
			before := c.count()

			tc.send(t, "T_OTHER")
			if got := c.awaitCount(before+1, 250*time.Millisecond); got != before {
				t.Errorf("delivered %d event(s) from a foreign workspace", got-before)
			}

			tc.send(t, srv.cfg.workspaceID)
			if got := c.awaitCount(before+1, 5*time.Second); got != before+1 {
				t.Errorf("local-workspace event delivered %d times, want 1 — the guard is dropping everything", got-before)
			}
		})
	}

	// Slack sends team_id on every event_callback, so an absent one only
	// occurs in hand-built payloads and must not be dropped; the rest of this
	// file's routeEvent tests rely on it.
	before := c.count()
	routeMessage(srv, slackMessageEvent{Type: "app_mention", User: "U9", Text: "<@U0BOT> hi", Channel: "C9", TS: "1700.9"})
	if got := c.count(); got != before+1 {
		t.Errorf("absent team_id delivered %d times, want 1", got-before)
	}
}

func TestHandleSlackEventsURLVerification(t *testing.T) {
	srv := newTestServer(t)
	body := []byte(`{"type":"url_verification","challenge":"c4tt0ken"}`)
	ts := strconv.FormatInt(time.Now().Unix(), 10)

	req := httptest.NewRequest(http.MethodPost, "/slack/events", strings.NewReader(string(body)))
	req.Header.Set("X-Slack-Request-Timestamp", ts)
	req.Header.Set("X-Slack-Signature", signSlack(srv.cfg.signingSecret, ts, body))
	rec := httptest.NewRecorder()

	srv.handleSlackEvents()(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if got := strings.TrimSpace(rec.Body.String()); got != "c4tt0ken" {
		t.Fatalf("challenge echo = %q", got)
	}
}

func TestHandleSlackEventsBadSignature(t *testing.T) {
	srv := newTestServer(t)
	body := []byte(`{"type":"event_callback"}`)
	ts := strconv.FormatInt(time.Now().Unix(), 10)

	req := httptest.NewRequest(http.MethodPost, "/slack/events", strings.NewReader(string(body)))
	req.Header.Set("X-Slack-Request-Timestamp", ts)
	req.Header.Set("X-Slack-Signature", "v0=deadbeef")
	rec := httptest.NewRecorder()

	srv.handleSlackEvents()(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", rec.Code)
	}
}

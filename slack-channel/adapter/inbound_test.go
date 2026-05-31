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

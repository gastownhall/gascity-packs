package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync"
	"testing"
)

// resetAttributionLatch clears the process-lifetime fallback so tests do not
// leak a tripped latch into one another.
func resetAttributionLatch(t *testing.T) {
	t.Helper()
	attributionDisabled.Store(false)
	t.Cleanup(func() { attributionDisabled.Store(false) })
}

// A user message an app posted under the user's id, with the app's
// "Sent using" footer in a context block.
func composedUserMsg() slackMessageEvent {
	return slackMessageEvent{
		Type: "message", Channel: "C1", User: "UPERSON1", TS: "200.000001",
		Text:       "ship it",
		AppID:      "ACURSOR1",
		BotProfile: json.RawMessage(`{"app_id":"ACURSOR1","name":"Cursor"}`),
		Blocks: json.RawMessage(`[
			{"type":"rich_text","elements":[{"type":"rich_text_section"}]},
			{"type":"context","elements":[{"type":"mrkdwn","text":"*Sent using* <@UCURSORBOT|Cursor>"}]}
		]`),
	}
}

func TestSlackAttribution(t *testing.T) {
	cases := []struct {
		name string
		msg  slackMessageEvent
		want map[string]string
	}{
		{
			name: "plain human message carries only the speaker",
			msg:  slackMessageEvent{Type: "message", Channel: "C1", User: "UHUMAN1", TS: "1.0", Text: "hi"},
			want: map[string]string{"attribution_version": "1", "user_id": "UHUMAN1"},
		},
		{
			name: "app composing for a user",
			msg:  composedUserMsg(),
			want: map[string]string{
				"attribution_version": "1", "user_id": "UPERSON1", "app_id": "ACURSOR1",
				"bot_profile_app_id": "ACURSOR1", "composer_user_id": "UCURSORBOT",
			},
		},
		{
			name: "bot in its own voice",
			msg: slackMessageEvent{
				Type: "message", User: "UBOTUSER", TS: "1.0", Text: "built",
				AppID: "ATRUSTED", BotID: "BTRUSTED",
				BotProfile: json.RawMessage(`{"app_id":"ATRUSTED","name":"Trusted"}`),
			},
			want: map[string]string{
				"attribution_version": "1", "user_id": "UBOTUSER", "app_id": "ATRUSTED",
				"bot_id": "BTRUSTED", "bot_profile_app_id": "ATRUSTED",
			},
		},
		{
			name: "footer in the text, subtype kept",
			msg: slackMessageEvent{Type: "message", Subtype: "thread_broadcast", User: "U1", TS: "1.0",
				Text: "done\nSent using <@UAPPBOT>"},
			want: map[string]string{"attribution_version": "1", "user_id": "U1",
				"composer_user_id": "UAPPBOT", "subtype": "thread_broadcast"},
		},
		{
			name: "two different footers are both reported, sorted",
			msg: slackMessageEvent{Type: "message", User: "U1", TS: "1.0",
				Text:   "x Sent using <@UZED>",
				Blocks: json.RawMessage(`[{"type":"context","elements":[{"text":"Sent using <@UALPHA>"}]}]`)},
			want: map[string]string{"attribution_version": "1", "user_id": "U1", "composer_user_id": "UALPHA,UZED"},
		},
		{
			name: "a footer outside a context block is not read",
			msg: slackMessageEvent{Type: "message", User: "U1", TS: "1.0", Text: "x",
				Blocks: json.RawMessage(`[{"type":"section","elements":[{"text":"Sent using <@UALPHA>"}]}]`)},
			want: map[string]string{"attribution_version": "1", "user_id": "U1"},
		},
		{
			name: "malformed blocks do not break attribution",
			msg: slackMessageEvent{Type: "message", User: "U1", TS: "1.0", Text: "x",
				Blocks: json.RawMessage(`{"not":"a list"}`)},
			want: map[string]string{"attribution_version": "1", "user_id": "U1"},
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := slackAttribution(tc.msg); !reflect.DeepEqual(got, tc.want) {
				t.Errorf("slackAttribution = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestAttributionLogTag(t *testing.T) {
	if got := attributionLogTag(map[string]string{"attribution_version": "1", "user_id": "U1"}); got != "" {
		t.Errorf("plain message tag = %q, want empty", got)
	}
	got := attributionLogTag(slackAttribution(composedUserMsg()))
	want := " composer=UCURSORBOT app_id=ACURSOR1 profile_app=ACURSOR1"
	if got != want {
		t.Errorf("tag = %q, want %q", got, want)
	}
}

func attributionInbound(id string, attr map[string]string) externalInboundMessage {
	return externalInboundMessage{
		ProviderMessageID: id,
		Conversation:      conversationRef{ConversationID: "C1"},
		Actor:             externalActor{ID: "U1"},
		Text:              "hello",
		DedupKey:          "slack-" + id,
		Attribution:       attr,
	}
}

// oldGCInbound answers like a gc that predates message.attribution: its
// inbound schema has additionalProperties=false, so a body with the field
// is a 422.
type oldGCInbound struct {
	mu     sync.Mutex
	bodies []string
}

func (o *oldGCInbound) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(r.Body)
	o.mu.Lock()
	o.bodies = append(o.bodies, string(raw))
	o.mu.Unlock()
	if strings.Contains(string(raw), `"attribution"`) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = io.WriteString(w, `{"title":"Unprocessable Entity","status":422,"detail":"validation failed",`+
			`"errors":[{"message":"unexpected property","location":"body.message.attribution"}]}`)
		return
	}
	w.WriteHeader(http.StatusAccepted)
}

func TestPostInboundOldGCDropsAttributionOnce(t *testing.T) {
	resetAttributionLatch(t)
	o := &oldGCInbound{}
	srv := httptest.NewServer(o)
	t.Cleanup(srv.Close)
	cfg := config{gcAPIBase: srv.URL, cityName: "test-city"}

	msg := attributionInbound("1791999999.000100", map[string]string{"attribution_version": "1", "user_id": "U1"})
	read, restore := captureLog(t)
	err := postInbound(cfg, msg)
	logs := read()
	restore()
	if err != nil {
		t.Fatalf("postInbound: %v", err)
	}
	if len(o.bodies) != 2 {
		t.Fatalf("attempts = %d, want 2 (refused, then resent without attribution)", len(o.bodies))
	}
	if strings.Contains(o.bodies[1], "attribution") {
		t.Errorf("resend still carries attribution: %s", o.bodies[1])
	}
	if !strings.Contains(logs, "attribution disabled until restart") {
		t.Errorf("latch not logged:\n%s", logs)
	}
	if !attributionDisabled.Load() {
		t.Error("old-gc refusal did not latch attribution off")
	}
}

// TestPostInboundOldGCLatchesAttribution: N messages against an old gc produce
// exactly one body that carries attribution (the first attempt). That message
// is resent without it, and every later message is plain. The disable log
// fires once.
func TestPostInboundOldGCLatchesAttribution(t *testing.T) {
	resetAttributionLatch(t)
	o := &oldGCInbound{}
	srv := httptest.NewServer(o)
	t.Cleanup(srv.Close)
	cfg := config{gcAPIBase: srv.URL, cityName: "test-city"}

	read, restore := captureLog(t)
	const n = 4
	for i := 0; i < n; i++ {
		msg := attributionInbound(fmt.Sprintf("1791999999.00010%d", i),
			map[string]string{"attribution_version": "1", "user_id": "U1"})
		if err := postInbound(cfg, msg); err != nil {
			restore()
			t.Fatalf("message %d: %v", i, err)
		}
	}
	logs := read()
	restore()

	with := 0
	for _, body := range o.bodies {
		if strings.Contains(body, `"attribution"`) {
			with++
		}
	}
	if with != 1 {
		t.Fatalf("attribution bodies = %d, want 1 across %d messages (%d bodies)", with, n, len(o.bodies))
	}
	if got, want := len(o.bodies), n+1; got != want {
		t.Fatalf("bodies = %d, want %d (one resend plus one post per message)", got, want)
	}
	if got := strings.Count(logs, "attribution disabled until restart"); got != 1 {
		t.Errorf("disable log count = %d, want 1:\n%s", got, logs)
	}
}

// TestPostInboundNewGCKeepsAttribution: a gc that accepts the field keeps it
// on every message, and the latch stays off.
func TestPostInboundNewGCKeepsAttribution(t *testing.T) {
	resetAttributionLatch(t)
	var mu sync.Mutex
	var bodies []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		mu.Lock()
		bodies = append(bodies, string(raw))
		mu.Unlock()
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(srv.Close)
	cfg := config{gcAPIBase: srv.URL, cityName: "test-city"}

	const n = 3
	for i := 0; i < n; i++ {
		msg := attributionInbound(fmt.Sprintf("1791999999.00020%d", i),
			map[string]string{"attribution_version": "1", "user_id": "U1"})
		if err := postInbound(cfg, msg); err != nil {
			t.Fatalf("message %d: %v", i, err)
		}
	}
	mu.Lock()
	defer mu.Unlock()
	if len(bodies) != n {
		t.Fatalf("bodies = %d, want %d", len(bodies), n)
	}
	for i, body := range bodies {
		if !strings.Contains(body, `"attribution"`) {
			t.Errorf("message %d omitted attribution: %s", i, body)
		}
	}
	if attributionDisabled.Load() {
		t.Error("accepting gc latched attribution off")
	}
}

// TestPostInboundOther4xxNotResent: a 4xx that does not name the field is
// the message's own fault, so it is not resent and does not trip the latch.
func TestPostInboundOther4xxNotResent(t *testing.T) {
	resetAttributionLatch(t)
	var mu sync.Mutex
	attempts := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		mu.Lock()
		attempts++
		mu.Unlock()
		http.Error(w, "scripted failure", http.StatusUnprocessableEntity)
	}))
	t.Cleanup(srv.Close)
	cfg := config{gcAPIBase: srv.URL, cityName: "test-city"}
	msg := attributionInbound("1791999999.000100", map[string]string{"attribution_version": "1", "user_id": "U1"})
	if err := postInbound(cfg, msg); err == nil {
		t.Fatal("postInbound: want error, got nil")
	}
	mu.Lock()
	defer mu.Unlock()
	if attempts != 1 {
		t.Errorf("attempts = %d, want 1", attempts)
	}
	if attributionDisabled.Load() {
		t.Error("unrelated 422 latched attribution off")
	}
}

// TestPostInboundNoAttributionKeepsOldBody: absent attribution is not on
// the wire at all, so the body an old gc accepts is unchanged.
func TestPostInboundNoAttributionKeepsOldBody(t *testing.T) {
	resetAttributionLatch(t)
	var body string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		body = string(raw)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(srv.Close)
	cfg := config{gcAPIBase: srv.URL, cityName: "test-city"}
	if err := postInbound(cfg, attributionInbound("1791999999.000100", nil)); err != nil {
		t.Fatalf("postInbound: %v", err)
	}
	if strings.Contains(body, "attribution") {
		t.Errorf("body without attribution mentions it: %s", body)
	}
}

// TestPostInboundAttributionLatchConcurrent: overlapping refusals log the
// disable line once and still deliver every message. The race detector
// covers the atomic latch.
func TestPostInboundAttributionLatchConcurrent(t *testing.T) {
	resetAttributionLatch(t)
	o := &oldGCInbound{}
	srv := httptest.NewServer(o)
	t.Cleanup(srv.Close)
	cfg := config{gcAPIBase: srv.URL, cityName: "test-city"}

	read, restore := captureLog(t)
	const n = 8
	var wg sync.WaitGroup
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func(i int) {
			defer wg.Done()
			msg := attributionInbound(fmt.Sprintf("1791999999.00030%d", i),
				map[string]string{"attribution_version": "1", "user_id": "U1"})
			if err := postInbound(cfg, msg); err != nil {
				t.Errorf("message %d: %v", i, err)
			}
		}(i)
	}
	wg.Wait()
	logs := read()
	restore()

	if got := strings.Count(logs, "attribution disabled until restart"); got != 1 {
		t.Errorf("disable log count = %d, want 1:\n%s", got, logs)
	}
	o.mu.Lock()
	defer o.mu.Unlock()
	delivered := map[string]bool{}
	for _, raw := range o.bodies {
		var req struct {
			Message externalInboundMessage `json:"message"`
		}
		if err := json.Unmarshal([]byte(raw), &req); err != nil {
			t.Errorf("body: %v", err)
			continue
		}
		if !strings.Contains(raw, `"attribution"`) {
			delivered[req.Message.ProviderMessageID] = true
		}
	}
	if len(delivered) != n {
		t.Errorf("plain deliveries = %d, want %d", len(delivered), n)
	}
}

// TestProcessSlackEventCarriesAttribution drives the legacy path end to end:
// the inbound body carries the event's composer evidence and the inbound:
// log line names it.
func TestProcessSlackEventCarriesAttribution(t *testing.T) {
	resetAttributionLatch(t)
	var mu sync.Mutex
	var got []map[string]string
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		if strings.Contains(r.URL.Path, "/extmsg/inbound") {
			var req struct {
				Message externalInboundMessage `json:"message"`
			}
			_ = json.Unmarshal(raw, &req)
			mu.Lock()
			got = append(got, req.Message.Attribution)
			mu.Unlock()
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)
	cfg := config{
		gcAPIBase:   gcStub.URL,
		cityName:    "test-city",
		provider:    "slack",
		accountID:   "T1",
		dispatchSem: defaultTestDispatchSem,
	}
	raw, _ := json.Marshal(composedUserMsg())
	env := slackEventEnvelope{Type: "event_callback", APIAppID: "ASELF", Event: raw}

	read, restore := captureLog(t)
	processSlackEvent(cfg, nil, nil, nil, nil, nil, env, func() {})
	logs := read()
	restore()

	mu.Lock()
	defer mu.Unlock()
	want := []map[string]string{slackAttribution(composedUserMsg())}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("posted attribution = %v, want %v", got, want)
	}
	if !strings.Contains(logs, "inbound: chan=C1 user=UPERSON1 ts=200.000001") ||
		!strings.Contains(logs, "composer=UCURSORBOT app_id=ACURSOR1") {
		t.Errorf("inbound line does not name the composer:\n%s", logs)
	}
}

package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// subteamCapture records both inbound POSTs (extmsg/inbound) and
// alias-dispatched session-message POSTs so a single test can assert
// the full processSlackEvent flow for a Slack User Group mention.
type subteamCapture struct {
	mu             sync.Mutex
	inbounds       []externalInboundMessage
	sessionHits    int32
	sessionPath    string
	sessionPayload []byte
}

func (c *subteamCapture) handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		switch {
		case strings.Contains(r.URL.Path, "/extmsg/inbound"):
			var env struct {
				Message externalInboundMessage `json:"message"`
			}
			if err := json.Unmarshal(body, &env); err == nil {
				c.mu.Lock()
				c.inbounds = append(c.inbounds, env.Message)
				c.mu.Unlock()
			}
			w.WriteHeader(http.StatusAccepted)
		case strings.Contains(r.URL.Path, "/session/") && strings.HasSuffix(r.URL.Path, "/messages"):
			atomic.AddInt32(&c.sessionHits, 1)
			c.mu.Lock()
			c.sessionPath = r.URL.Path
			c.sessionPayload = append([]byte(nil), body...)
			c.mu.Unlock()
			w.WriteHeader(http.StatusAccepted)
		default:
			w.WriteHeader(http.StatusAccepted)
		}
	}
}

func (c *subteamCapture) snapshotInbounds() []externalInboundMessage {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make([]externalInboundMessage, len(c.inbounds))
	copy(out, c.inbounds)
	return out
}

// TestProcessSlackEventSubteamMentionRoutedAsAddressByHandle is the
// happy path for bead gpk-2zi: a Slack User Group mention whose
// `@handle` label matches a registered handle alias must route through
// the existing address-by-handle dispatch path. That means:
//
//  1. The inbound POSTed to gc carries ExplicitTarget="<handle>" and
//     Text stripped of the subteam token (just the trailing remainder).
//  2. The session-message dispatch fires for the aliased session id,
//     exactly as it would have for a human-typed "@<handle>: ..."
//     message.
//
// We exercise the full processSlackEvent path rather than calling the
// parser directly so a regression in either the parse step or the
// aliasReg gate would fail the test.
func TestProcessSlackEventSubteamMentionRoutedAsAddressByHandle(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("mayor", "gc-2568"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000100",
		Text:    "<!subteam^S0123ABCD|@mayor> please check this",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	var releases int32
	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() { atomic.AddInt32(&releases, 1) })

	// The inbound POST must carry the parsed target + remainder.
	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "mayor" {
		t.Errorf("ExplicitTarget = %q, want %q", inbounds[0].ExplicitTarget, "mayor")
	}
	if inbounds[0].Text != "please check this" {
		t.Errorf("Text = %q, want %q", inbounds[0].Text, "please check this")
	}

	// The alias dispatch goroutine fires asynchronously. Wait briefly
	// for the session-message POST so we don't flake on slow CI.
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if atomic.LoadInt32(&capture.sessionHits) > 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if got := atomic.LoadInt32(&capture.sessionHits); got != 1 {
		t.Fatalf("session-message hits = %d, want 1 (alias dispatch should have fired)", got)
	}
	capture.mu.Lock()
	gotPath := capture.sessionPath
	capture.mu.Unlock()
	if !strings.Contains(gotPath, "/session/gc-2568/messages") {
		t.Errorf("session path = %q, want to contain %q", gotPath, "/session/gc-2568/messages")
	}
}

// TestProcessSlackEventSubteamMentionUnregisteredHandleFallsThrough
// asserts the safety gate from bead gpk-2zi: a Slack User Group mention
// whose label does NOT match a registered handle alias must NOT trigger
// address-by-handle dispatch. The inbound still gets posted (so the
// channel's bound session sees the message), but with the full original
// text (token included) and an empty ExplicitTarget. No alias
// session-message POST fires.
//
// This is the safety case for the bead: Slack's @-autocomplete surfaces
// every User Group in the workspace, including ones unrelated to gc.
// Treating those as address-by-handle would silently route messages to
// wrong (or nonexistent) sessions.
func TestProcessSlackEventSubteamMentionUnregisteredHandleFallsThrough(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	// Intentionally do NOT register the handle.

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000200",
		Text:    "<!subteam^S0123ABCD|@notregistered> hello team",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "" {
		t.Errorf("ExplicitTarget = %q, want empty (handle was not in aliasReg)", inbounds[0].ExplicitTarget)
	}
	// Full original text passes through unchanged so the channel-bound
	// session sees the same surface a non-address mention would deliver.
	if inbounds[0].Text != "<!subteam^S0123ABCD|@notregistered> hello team" {
		t.Errorf("Text = %q, want full original token preserved", inbounds[0].Text)
	}

	// Give any (incorrect) alias dispatch goroutine a chance to fire.
	time.Sleep(50 * time.Millisecond)
	if got := atomic.LoadInt32(&capture.sessionHits); got != 0 {
		t.Errorf("session-message hits = %d, want 0 (no alias should have matched)", got)
	}
}

// TestProcessSlackEventSubteamMentionTakesPrecedenceOverSingleAtPrefix
// asserts that when a message starts with a subteam token whose label
// matches the alias registry, the subteam path wins — the existing
// single-`@` parseHandlePrefix path is NOT re-applied to the remainder.
// This protects against a message like
// `<!subteam^S012|@mayor> @ops: status?` being mis-parsed as
// address-by-handle for "ops" (the parser is documented to fire only
// on the trimmed head).
func TestProcessSlackEventSubteamMentionTakesPrecedenceOverSingleAtPrefix(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("mayor", "gc-2568"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000300",
		Text:    "<!subteam^S0123ABCD|@mayor> @ops: status?",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "mayor" {
		t.Errorf("ExplicitTarget = %q, want %q (subteam head must win)", inbounds[0].ExplicitTarget, "mayor")
	}
	// Remainder is delivered verbatim — `@ops: status?` is just text now,
	// not a second address token.
	if inbounds[0].Text != "@ops: status?" {
		t.Errorf("Text = %q, want %q (single-@ parse must NOT run on the remainder)", inbounds[0].Text, "@ops: status?")
	}
}

// TestProcessSlackEventSingleAtHandleStillDispatches is a regression
// guard: the existing `@handle:` text-prefix path must keep working
// unchanged after the subteam parser was added in front of it. This
// duplicates the basic happy path in spirit, but the assertion target
// is "the wiring did not get reordered in a way that breaks the
// single-`@` path", which is exactly the kind of regression a parser
// shuffle can introduce.
func TestProcessSlackEventSingleAtHandleStillDispatches(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("mayor", "gc-2568"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000400",
		Text:    "@mayor: still works",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "mayor" {
		t.Errorf("ExplicitTarget = %q, want %q", inbounds[0].ExplicitTarget, "mayor")
	}
	if inbounds[0].Text != "still works" {
		t.Errorf("Text = %q, want %q", inbounds[0].Text, "still works")
	}

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if atomic.LoadInt32(&capture.sessionHits) > 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if got := atomic.LoadInt32(&capture.sessionHits); got != 1 {
		t.Errorf("session-message hits = %d, want 1 (single-@ alias dispatch must still fire)", got)
	}
}

// TestProcessSlackEventSubteamMentionLabelWithoutAtRoutesToHandle is the
// gpk-ee3 happy path: Slack omits the `@` in a User Group label when a
// human types the mention naturally (e.g. `@zelda-pl` expands to
// `<!subteam^Sxxx|zelda-pl>`). That bare-label form must route through
// the same address-by-handle dispatch path the `@`-labeled form uses —
// before gpk-ee3 it landed with target="" and no dispatch fired.
func TestProcessSlackEventSubteamMentionLabelWithoutAtRoutesToHandle(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("zelda-pl", "gc-9001"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000900",
		Text:    "<!subteam^S0ZELDA|zelda-pl> ship it",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "zelda-pl" {
		t.Errorf("ExplicitTarget = %q, want %q (bare label must route as handle)",
			inbounds[0].ExplicitTarget, "zelda-pl")
	}
	if inbounds[0].Text != "ship it" {
		t.Errorf("Text = %q, want %q (subteam token must be stripped)", inbounds[0].Text, "ship it")
	}

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if atomic.LoadInt32(&capture.sessionHits) > 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if got := atomic.LoadInt32(&capture.sessionHits); got != 1 {
		t.Fatalf("session-message hits = %d, want 1 (bare-label alias dispatch should fire)", got)
	}
	capture.mu.Lock()
	gotPath := capture.sessionPath
	capture.mu.Unlock()
	if !strings.Contains(gotPath, "/session/gc-9001/messages") {
		t.Errorf("session path = %q, want to contain %q", gotPath, "/session/gc-9001/messages")
	}
}

// TestProcessSlackEventSubteamMentionBareLabelInvalidCharFallsThrough is
// the gpk-ee3 safety case: a bare label containing an invalid handle
// character (a space here) must NOT parse as a subteam mention. The
// parser returns ok=false, the inbound posts with the full original
// text and an empty ExplicitTarget, and no alias dispatch fires.
func TestProcessSlackEventSubteamMentionBareLabelInvalidCharFallsThrough(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.001000",
		Text:    "<!subteam^S0XXX|foo bar> hello",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "" {
		t.Errorf("ExplicitTarget = %q, want empty (invalid bare label must not parse)", inbounds[0].ExplicitTarget)
	}
	if inbounds[0].Text != "<!subteam^S0XXX|foo bar> hello" {
		t.Errorf("Text = %q, want full original preserved (parse miss)", inbounds[0].Text)
	}

	time.Sleep(50 * time.Millisecond)
	if got := atomic.LoadInt32(&capture.sessionHits); got != 0 {
		t.Errorf("session-message hits = %d, want 0 (no valid handle, no dispatch)", got)
	}
}

// newTestSubteamAliasMap builds a subteamAliasMap from an in-memory
// {subteam_id: handle} map by staging it through a tmpfile. Tests that
// need a populated map use this rather than touching production
// defaults, so each test owns an isolated state.
func newTestSubteamAliasMap(t *testing.T, entries map[string]string) *subteamAliasMap {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "subteam-aliases.json")
	data, err := json.Marshal(entries)
	if err != nil {
		t.Fatalf("marshal subteam map: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write subteam map: %v", err)
	}
	m, err := newSubteamAliasMap(path)
	if err != nil {
		t.Fatalf("newSubteamAliasMap: %v", err)
	}
	return m
}

// TestProcessSlackEventUnlabeledSubteamMappedRoutesAsAddressByHandle is
// the gpk-hmr.2 happy path: an UNLABELED subteam token
// `<!subteam^Sxxx>` whose ID resolves through subteamAliasMap to a gc
// handle must route through the same address-by-handle dispatch path
// the labeled form uses. The "addressed you" system-reminder is what
// the receiving session expects — anything else (generic channel
// fanout, or just an ExplicitTarget with no alias dispatch) silently
// breaks the gpk-hmr observed-gap fix.
func TestProcessSlackEventUnlabeledSubteamMappedRoutesAsAddressByHandle(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("mayor", "gc-2568"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}
	subteamMap := newTestSubteamAliasMap(t, map[string]string{
		"S0B4MUNDZCH": "mayor",
	})

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000500",
		Text:    "<!subteam^S0B4MUNDZCH> please check the queue",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, subteamMap, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "mayor" {
		t.Errorf("ExplicitTarget = %q, want %q (subteam map should resolve S0B4MUNDZCH→mayor)",
			inbounds[0].ExplicitTarget, "mayor")
	}
	if inbounds[0].Text != "please check the queue" {
		t.Errorf("Text = %q, want %q (subteam token must be stripped)",
			inbounds[0].Text, "please check the queue")
	}

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if atomic.LoadInt32(&capture.sessionHits) > 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if got := atomic.LoadInt32(&capture.sessionHits); got != 1 {
		t.Fatalf("session-message hits = %d, want 1 (alias dispatch should have fired)", got)
	}

	// The dispatched body must carry the "Slack address-by-handle"
	// system-reminder form — that's the gpk-hmr acceptance check. A
	// "New message in shared conversation" generic-fanout body here
	// would indicate the inbound went through the channel-fanout path
	// instead and the bead's observed gap is NOT fixed.
	capture.mu.Lock()
	gotPath := capture.sessionPath
	gotBody := append([]byte(nil), capture.sessionPayload...)
	capture.mu.Unlock()
	if !strings.Contains(gotPath, "/session/gc-2568/messages") {
		t.Errorf("session path = %q, want to contain %q", gotPath, "/session/gc-2568/messages")
	}
	bodyStr := string(gotBody)
	if !strings.Contains(bodyStr, "Slack address-by-handle: @mayor addressed you") {
		t.Errorf("dispatched body missing address-by-handle reminder:\n%s", bodyStr)
	}
	if strings.Contains(bodyStr, "New message in shared conversation") {
		t.Errorf("dispatched body looks like channel-fanout (generic reminder), not address-by-handle:\n%s", bodyStr)
	}
}

// TestProcessSlackEventUnlabeledSubteamUnmappedFallsThroughToChannelFanout
// asserts the gpk-hmr.2 negative case: an unlabeled `<!subteam^Sxxx>`
// whose ID has NO entry in subteamAliasMap must NOT trigger
// address-by-handle dispatch. The inbound still posts (so the
// channel-bound session sees it as a regular shared-conversation
// message), with the full original text preserved and an empty
// ExplicitTarget. No alias session-message POST fires.
func TestProcessSlackEventUnlabeledSubteamUnmappedFallsThroughToChannelFanout(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	// Empty map — no subteam ID is mapped.
	subteamMap := newTestSubteamAliasMap(t, map[string]string{})

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000600",
		Text:    "<!subteam^S_UNKNOWN> hello team",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, subteamMap, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "" {
		t.Errorf("ExplicitTarget = %q, want empty (subteam ID was not in map)", inbounds[0].ExplicitTarget)
	}
	if inbounds[0].Text != "<!subteam^S_UNKNOWN> hello team" {
		t.Errorf("Text = %q, want full original token preserved (fall-through case)", inbounds[0].Text)
	}

	time.Sleep(50 * time.Millisecond)
	if got := atomic.LoadInt32(&capture.sessionHits); got != 0 {
		t.Errorf("session-message hits = %d, want 0 (no map entry, no dispatch)", got)
	}
}

// TestProcessSlackEventUnlabeledSubteamWithNilMapFallsThrough is a
// safety net: even if subteamAliasMap is nil (operator never
// populated it; pre-gpk-hmr.2 callers), an unlabeled subteam token
// must still post the inbound and NOT crash. Nil-safe Get on
// subteamAliasMap is what makes this work; the test pins the
// guarantee.
func TestProcessSlackEventUnlabeledSubteamWithNilMapFallsThrough(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000700",
		Text:    "<!subteam^S0B4MUNDZCH> hi",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	inbounds := capture.snapshotInbounds()
	if len(inbounds) != 1 {
		t.Fatalf("got %d inbound POSTs, want 1", len(inbounds))
	}
	if inbounds[0].ExplicitTarget != "" {
		t.Errorf("ExplicitTarget = %q, want empty (nil subteamMap should fall through)", inbounds[0].ExplicitTarget)
	}
	if inbounds[0].Text != "<!subteam^S0B4MUNDZCH> hi" {
		t.Errorf("Text = %q, want full original (nil map = no rewrite)", inbounds[0].Text)
	}
}

// TestProcessSlackEventLabeledSubteamCarriesAddressByHandleReminder
// upgrades the gpk-2zi happy-path assertion: not only must the
// session-message POST fire, the body must contain the
// "Slack address-by-handle: @<handle> addressed you" reminder. This is
// the strong-form check the gpk-hmr parent acceptance criterion calls
// out for BOTH shapes, and a regression here would silently swap the
// reminder for the generic "New message" form even with the right
// path and target.
func TestProcessSlackEventLabeledSubteamCarriesAddressByHandleReminder(t *testing.T) {
	capture := &subteamCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem:   defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("mayor", "gc-2568"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000800",
		Text:    "<!subteam^S0B4MUNDZCH|@mayor> labeled shape",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, func() {})

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if atomic.LoadInt32(&capture.sessionHits) > 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if got := atomic.LoadInt32(&capture.sessionHits); got != 1 {
		t.Fatalf("session-message hits = %d, want 1 (labeled form alias dispatch must fire)", got)
	}
	capture.mu.Lock()
	bodyStr := string(capture.sessionPayload)
	capture.mu.Unlock()
	if !strings.Contains(bodyStr, "Slack address-by-handle: @mayor addressed you") {
		t.Errorf("labeled-form dispatched body missing address-by-handle reminder:\n%s", bodyStr)
	}
}

package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// newTestThreadSessionRegistry builds an isolated thread-session
// registry in a tmpdir for tests that need one.
func newTestThreadSessionRegistry(t *testing.T) *threadSessionRegistry {
	t.Helper()
	path := filepath.Join(t.TempDir(), "thread_sessions.json")
	reg, err := newThreadSessionRegistry(path)
	if err != nil {
		t.Fatalf("newThreadSessionRegistry: %v", err)
	}
	return reg
}

// captureSlackPostEphemeral installs a fake Slack API base for the
// duration of t and returns a channel that receives every observed
// chat.postEphemeral request body. The fake responds with
// {"ok": true, "message_ts": "..."} for any postEphemeral call.
func captureSlackPostEphemeral(t *testing.T) <-chan map[string]any {
	t.Helper()
	ch := make(chan map[string]any, 4)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.Path, "chat.postEphemeral") {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"ok":true}`))
			return
		}
		body, _ := io.ReadAll(r.Body)
		var parsed map[string]any
		_ = json.Unmarshal(body, &parsed)
		select {
		case ch <- parsed:
		default:
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true,"message_ts":"1.0"}`))
	}))
	t.Cleanup(srv.Close)

	orig := slackAPIBase
	slackAPIBase = srv.URL
	t.Cleanup(func() { slackAPIBase = orig })
	return ch
}

// TestProcessSlackEventDoubleHandleUnclaimedEmitsLauncherEphemeral
// asserts that an inbound `@@new-handle ...` whose handle is NOT
// pre-claimed in the alias registry is routed to the launcher stub:
// the adapter posts an ephemeral telling the user the launcher
// recognized the handle, does NOT post an inbound to gc, does NOT
// touch the single-`@` alias dispatch path.
func TestProcessSlackEventDoubleHandleUnclaimedEmitsLauncherEphemeral(t *testing.T) {
	var inboundHits int32
	var sessionMessageHits int32
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		if strings.Contains(r.URL.Path, "/extmsg/inbound") {
			atomic.AddInt32(&inboundHits, 1)
		}
		if strings.Contains(r.URL.Path, "/session/") && strings.Contains(r.URL.Path, "/messages") {
			atomic.AddInt32(&sessionMessageHits, 1)
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	ephemeralCh := captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U1",
		TS:       "1700000000.000100",
		ThreadTS: "1700000000.000050",
		Text:     "@@launcher-001 spawn me a session",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	var releases int32
	release := func() { atomic.AddInt32(&releases, 1) }
	processSlackEvent(cfg, aliasReg, threadReg, nil, nil, nil, env, release)

	// One ephemeral POST must land within a short deadline.
	select {
	case body := <-ephemeralCh:
		text, _ := body["text"].(string)
		if !strings.Contains(text, "launcher") {
			t.Errorf("ephemeral text missing 'launcher' marker: %q", text)
		}
		if !strings.Contains(text, "@@launcher-001") {
			t.Errorf("ephemeral text should echo @@<handle>: %q", text)
		}
		if got := body["channel"]; got != "C1" {
			t.Errorf("ephemeral channel = %v, want C1", got)
		}
		if got := body["user"]; got != "U1" {
			t.Errorf("ephemeral user = %v, want U1", got)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("expected chat.postEphemeral within 2s for @@<handle> launcher dispatch")
	}

	// No inbound POST and no session-message POST: launcher path is a
	// stub that returns BEFORE postInbound and never enters the alias
	// dispatch branch.
	time.Sleep(50 * time.Millisecond)
	if got := atomic.LoadInt32(&inboundHits); got != 0 {
		t.Errorf("inbound POSTs = %d, want 0 (launcher stub must not post inbound yet)", got)
	}
	if got := atomic.LoadInt32(&sessionMessageHits); got != 0 {
		t.Errorf("session-message POSTs = %d, want 0 (launcher stub must not enter alias dispatch)", got)
	}
	if got := atomic.LoadInt32(&releases); got != 1 {
		t.Errorf("release fired %d times on launcher path; want exactly 1", got)
	}
}

// TestProcessSlackEventDoubleHandlePreClaimedEmitsBoundEphemeral asserts
// that when a `@@<handle>` arrives but the handle is already registered
// in the alias registry, the adapter emits an instructional ephemeral
// ("@@<handle> is bound to an existing session — message that session
// directly with @<handle>") and does NOT enter the launcher path.
func TestProcessSlackEventDoubleHandlePreClaimedEmitsBoundEphemeral(t *testing.T) {
	var inboundHits int32
	var sessionMessageHits int32
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		if strings.Contains(r.URL.Path, "/extmsg/inbound") {
			atomic.AddInt32(&inboundHits, 1)
		}
		if strings.Contains(r.URL.Path, "/session/") && strings.Contains(r.URL.Path, "/messages") {
			atomic.AddInt32(&sessionMessageHits, 1)
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	ephemeralCh := captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:     gcStub.URL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-test",
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("ops", "gc-existing-7"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}
	threadReg := newTestThreadSessionRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000100",
		Text:    "@@ops status?",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	release := func() {}
	processSlackEvent(cfg, aliasReg, threadReg, nil, nil, nil, env, release)

	select {
	case body := <-ephemeralCh:
		text, _ := body["text"].(string)
		if !strings.Contains(text, "@@ops") {
			t.Errorf("ephemeral text should echo @@<handle>: %q", text)
		}
		if !strings.Contains(text, "@ops") {
			t.Errorf("ephemeral text should suggest single-`@` alternative: %q", text)
		}
		if !strings.Contains(strings.ToLower(text), "bound") &&
			!strings.Contains(strings.ToLower(text), "existing") {
			t.Errorf("ephemeral text should signal pre-claimed status: %q", text)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("expected chat.postEphemeral within 2s for pre-claimed @@<handle>")
	}

	// Pre-claimed branch must NOT post inbound (we're refusing the
	// launcher request entirely) and must NOT enter alias dispatch
	// (which would deliver the message — exactly the behavior the
	// ephemeral is telling the user to invoke explicitly).
	time.Sleep(50 * time.Millisecond)
	if got := atomic.LoadInt32(&inboundHits); got != 0 {
		t.Errorf("inbound POSTs = %d, want 0 (pre-claimed branch must short-circuit)", got)
	}
	if got := atomic.LoadInt32(&sessionMessageHits); got != 0 {
		t.Errorf("session-message POSTs = %d, want 0 (pre-claimed branch must not dispatch)", got)
	}
}

// TestProcessSlackEventSingleHandleStillReachesAliasDispatch asserts
// that adding the `@@` parser does NOT regress the existing single-`@`
// alias dispatch path. A `@<handle>` text whose handle is registered
// must still POST a system reminder to the aliased session.
func TestProcessSlackEventSingleHandleStillReachesAliasDispatch(t *testing.T) {
	pathCh := make(chan string, 1)
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		if strings.Contains(r.URL.Path, "/session/") && strings.Contains(r.URL.Path, "/messages") {
			select {
			case pathCh <- r.URL.Path:
			default:
			}
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	cfg := config{
		gcAPIBase:    gcStub.URL,
		cityName:     "test-city",
		provider:     "slack",
		accountID:    "T1",
		handlePrefix: "@",
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("mayor", "gc-2568"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}
	threadReg := newTestThreadSessionRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type: "message", Channel: "C1", User: "U1", TS: "1.0",
		Text: "@mayor please ack",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	release := func() {}
	processSlackEvent(cfg, aliasReg, threadReg, nil, nil, nil, env, release)

	select {
	case path := <-pathCh:
		want := "/v0/city/test-city/session/gc-2568/messages"
		if path != want {
			t.Errorf("alias dispatch path = %q, want %q (single-`@` path must still work)", path, want)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("single-`@` alias dispatch did not POST within 2s — regression")
	}
}

// TestProcessSlackEventPlainTextUnaffected asserts that a message with
// no prefix at all flows through unchanged: inbound posted, no
// ephemeral, no alias dispatch.
func TestProcessSlackEventPlainTextUnaffected(t *testing.T) {
	var inboundHits int32
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		if strings.Contains(r.URL.Path, "/extmsg/inbound") {
			atomic.AddInt32(&inboundHits, 1)
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	ephemeralCh := captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:    gcStub.URL,
		cityName:     "test-city",
		provider:     "slack",
		accountID:    "T1",
		handlePrefix: "@",
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type: "message", Channel: "C1", User: "U1", TS: "1.0",
		Text: "plain text no handle",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	release := func() {}
	processSlackEvent(cfg, aliasReg, threadReg, nil, nil, nil, env, release)

	if got := atomic.LoadInt32(&inboundHits); got != 1 {
		t.Errorf("inbound POSTs = %d, want 1 (plain text must still post inbound)", got)
	}
	select {
	case body := <-ephemeralCh:
		t.Errorf("plain text must not trigger ephemeral; got %v", body)
	case <-time.After(50 * time.Millisecond):
		// expected: no ephemeral
	}
}

// TestProcessSlackEventDoubleHandleNilThreadRegistry guards the runtime
// invariant: when threadReg is nil (e.g. a config that disabled
// launcher mode entirely), the launcher branch must NOT panic. Today's
// stub is happy to fall through, but pinning the contract here keeps
// 5.3's wiring honest.
func TestProcessSlackEventDoubleHandleNilThreadRegistry(t *testing.T) {
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	_ = captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:    gcStub.URL,
		cityName:     "test-city",
		provider:     "slack",
		accountID:    "T1",
		handlePrefix: "@",
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type: "message", Channel: "C1", User: "U1", TS: "1.0",
		Text: "@@launcher-7 hi",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}

	release := func() {}
	// Must not panic.
	processSlackEvent(cfg, aliasReg, nil, nil, nil, nil, env, release)
}

// TestLoadConfigThreadSessionsStorePathDefaultsCity exercises the
// city-rooted default for the thread sessions store. With GC_CITY_PATH
// set, the path is <city>/.gc/slack/thread_sessions.json — same
// convention as siblings (apps.json, channel_mappings.json).
func TestLoadConfigThreadSessionsStorePathDefaultsCity(t *testing.T) {
	env := baseSlackEnv()
	env["GC_CITY_PATH"] = "/tmp/test-city-root"
	cfg, err := loadConfigFromEnv(stubEnv(env))
	if err != nil {
		t.Fatalf("loadConfigFromEnv: %v", err)
	}
	want := "/tmp/test-city-root/.gc/slack/thread_sessions.json"
	if cfg.threadSessionsStorePath != want {
		t.Errorf("threadSessionsStorePath = %q, want %q", cfg.threadSessionsStorePath, want)
	}
}

// TestLoadConfigThreadSessionsStorePathOverride pins the env-var
// override. GC_SLACK_THREAD_SESSIONS_FILE wins regardless of city path
// resolution.
func TestLoadConfigThreadSessionsStorePathOverride(t *testing.T) {
	env := baseSlackEnv()
	env["GC_CITY_PATH"] = "/tmp/test-city-root"
	env["GC_SLACK_THREAD_SESSIONS_FILE"] = "/custom/thread_sessions.json"
	cfg, err := loadConfigFromEnv(stubEnv(env))
	if err != nil {
		t.Fatalf("loadConfigFromEnv: %v", err)
	}
	if cfg.threadSessionsStorePath != "/custom/thread_sessions.json" {
		t.Errorf("threadSessionsStorePath = %q, want /custom/thread_sessions.json", cfg.threadSessionsStorePath)
	}
}

// TestLoadConfigThreadSessionsStorePathFallsBackToTmp pins the
// non-city-rooted default — GC_CITY_PATH unset, env var unset →
// /tmp/gc-slack-adapter/thread_sessions.json. Mirrors the
// /tmp fallback used by every other adapter store path.
func TestLoadConfigThreadSessionsStorePathFallsBackToTmp(t *testing.T) {
	env := baseSlackEnv()
	delete(env, "GC_CITY_PATH")
	cfg, err := loadConfigFromEnv(stubEnv(env))
	if err != nil {
		t.Fatalf("loadConfigFromEnv: %v", err)
	}
	want := "/tmp/gc-slack-adapter/thread_sessions.json"
	if cfg.threadSessionsStorePath != want {
		t.Errorf("threadSessionsStorePath = %q, want %q", cfg.threadSessionsStorePath, want)
	}
}

// signedEventRequest is a thin wrapper that the integration test for
// the inbound handler uses. We need the OUTER handleSlackEvents path
// (signature verify + decode) to wire through the new threadReg
// argument so a future caller doesn't accidentally drop it. This pins
// the signature of handleSlackEvents.
func TestHandleSlackEventsAcceptsThreadRegistry(t *testing.T) {
	cfg := config{
		gcAPIBase:       "http://127.0.0.1:1",
		cityName:        "test-city",
		provider:        "slack",
		accountID:       "T1",
		slackSigningKey: "secret",
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)

	// We are not asserting downstream behavior here — just compile-time
	// + structural acceptance of the (cfg, aliasReg, threadReg) signature.
	rawMsg, _ := json.Marshal(slackMessageEvent{Type: "message", Channel: "C1", User: "U1", TS: "1.0", Text: "x"})
	envBody, _ := json.Marshal(slackEventEnvelope{Type: "event_callback", Event: rawMsg})
	req := signedSlackEventRequest(t, cfg.slackSigningKey, envBody)
	w := httptest.NewRecorder()

	handler := handleSlackEvents(cfg, aliasReg, threadReg, nil, nil, nil)
	handler(w, req)

	// Slack ack happens before downstream work, regardless of gc reachability.
	if w.Result().StatusCode != http.StatusOK {
		t.Errorf("status = %d, want 200", w.Result().StatusCode)
	}
}

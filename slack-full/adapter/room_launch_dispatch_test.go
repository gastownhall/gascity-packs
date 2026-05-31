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

// newTestRoomLaunchRegistry returns an isolated registry with the given
// (workspace, channel) → pool seeded.
func newTestRoomLaunchRegistry(t *testing.T, workspaceID, channelID, pool string) *roomLaunchMappingRegistry {
	t.Helper()
	path := filepath.Join(t.TempDir(), "room_launch_mappings.json")
	reg, err := newRoomLaunchMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRoomLaunchMappingRegistry: %v", err)
	}
	if workspaceID != "" {
		if err := reg.Set(roomLaunchMappingDiskRecord{
			WorkspaceID:  workspaceID,
			ChannelID:    channelID,
			PoolTemplate: pool,
		}); err != nil {
			t.Fatalf("seed Set: %v", err)
		}
	}
	return reg
}

// gcStubHits captures the requests hitting a fake gc API so tests can
// assert exact URL paths and bodies. Using atomic counters avoids
// goroutine races since the spawn flow runs from the foreground.
type gcStubHits struct {
	sessionsCreate   int32
	sessionMessages  int32
	lastCreateBody   atomic.Value // *sessionCreateBodyCapture
	lastMessageBody  atomic.Value // *sessionMessageBodyCapture
	lastMessagePath  atomic.Value // string
	createStatus     atomic.Int32 // override response status if non-zero
	createResponseID atomic.Value // string
	messageStatus    atomic.Int32 // override response status if non-zero
}

type sessionCreateBodyCapture struct {
	Kind    string            `json:"kind"`
	Name    string            `json:"name"`
	Alias   string            `json:"alias"`
	Message string            `json:"message"`
	Title   string            `json:"title"`
	Options map[string]string `json:"options"`
}

type sessionMessageBodyCapture struct {
	Message string `json:"message"`
}

func newGCStub(t *testing.T) (*httptest.Server, *gcStubHits) {
	t.Helper()
	hits := &gcStubHits{}
	hits.createResponseID.Store("sess-test-1")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/v0/sessions":
			atomic.AddInt32(&hits.sessionsCreate, 1)
			body, _ := io.ReadAll(r.Body)
			var cap sessionCreateBodyCapture
			_ = json.Unmarshal(body, &cap)
			hits.lastCreateBody.Store(&cap)
			status := int(hits.createStatus.Load())
			if status == 0 {
				status = http.StatusAccepted
			}
			respID, _ := hits.createResponseID.Load().(string)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(status)
			if status < 400 {
				_, _ = w.Write([]byte(`{"id":"` + respID + `"}`))
			} else {
				_, _ = w.Write([]byte(`{"error":"stub failure"}`))
			}
		case r.Method == http.MethodPost && strings.Contains(r.URL.Path, "/messages"):
			atomic.AddInt32(&hits.sessionMessages, 1)
			body, _ := io.ReadAll(r.Body)
			var cap sessionMessageBodyCapture
			_ = json.Unmarshal(body, &cap)
			hits.lastMessageBody.Store(&cap)
			hits.lastMessagePath.Store(r.URL.Path)
			status := int(hits.messageStatus.Load())
			if status == 0 {
				status = http.StatusAccepted
			}
			w.WriteHeader(status)
		default:
			w.WriteHeader(http.StatusOK)
		}
	}))
	t.Cleanup(srv.Close)
	return srv, hits
}

// TestRoomLaunchDispatchSpawnOnMissCreatesSessionAndPostsFirstMessage
// asserts the canonical happy path: `@@new-handle ...` lands in an
// enabled channel with no existing thread binding. The dispatcher
// must POST /v0/sessions with the configured pool_template, register
// the handle in the alias registry, post the remainder as the first
// message, and emit an ephemeral acknowledging the spawn.
func TestRoomLaunchDispatchSpawnOnMissCreatesSessionAndPostsFirstMessage(t *testing.T) {
	srv, hits := newGCStub(t)
	ephemeralCh := captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:           srv.URL,
		cityName:            "test-city",
		provider:            "slack",
		accountID:           "T1",
		handlePrefix:        "@",
		slackBotToken:       "xoxb-test",
		dispatchConcurrency: 8,
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)
	roomReg := newTestRoomLaunchRegistry(t, "T1", "C1", "mission-control/launcher")

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000100",
		// Top-level post (no thread_ts) — own TS becomes the thread root.
		Text: "@@new-handle please ack",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg, TeamID: "T1"}

	var releases int32
	processSlackEvent(cfg, aliasReg, threadReg, roomReg, nil, nil, env, func() { atomic.AddInt32(&releases, 1) })

	// /v0/sessions POST observed.
	if got := atomic.LoadInt32(&hits.sessionsCreate); got != 1 {
		t.Fatalf("/v0/sessions POSTs = %d, want 1", got)
	}
	createCap, _ := hits.lastCreateBody.Load().(*sessionCreateBodyCapture)
	if createCap == nil {
		t.Fatal("create body capture missing")
	}
	if createCap.Kind != "agent" {
		t.Errorf("kind = %q, want agent", createCap.Kind)
	}
	if createCap.Name != "mission-control/launcher" {
		t.Errorf("name = %q, want mission-control/launcher", createCap.Name)
	}
	// Initial message MUST NOT ride on session-create (per the
	// handler_session_create contract: "message is not supported with
	// async session creation; create the session, then POST
	// /v0/session/{id}/messages").
	if createCap.Message != "" {
		t.Errorf("create body must not include initial message; got %q", createCap.Message)
	}

	// Alias registered for subsequent @<handle> routing.
	if got, ok := aliasReg.Get("new-handle"); !ok || got != "sess-test-1" {
		t.Errorf("alias new-handle = (%q,%v), want (sess-test-1, true)", got, ok)
	}

	// Thread bound for subsequent posts in this thread.
	if got, ok := threadReg.Lookup("C1", "1700000000.000100"); !ok || got != "sess-test-1" {
		t.Errorf("thread Lookup = (%q,%v), want (sess-test-1, true)", got, ok)
	}

	// First-message POST observed at /v0/session/{id}/messages with the
	// remainder verbatim.
	if got := atomic.LoadInt32(&hits.sessionMessages); got != 1 {
		t.Fatalf("/v0/session/{id}/messages POSTs = %d, want 1", got)
	}
	msgPath, _ := hits.lastMessagePath.Load().(string)
	wantPath := "/v0/city/test-city/session/sess-test-1/messages"
	if msgPath != wantPath {
		t.Errorf("first-message path = %q, want %q", msgPath, wantPath)
	}
	msgCap, _ := hits.lastMessageBody.Load().(*sessionMessageBodyCapture)
	if msgCap == nil || !strings.Contains(msgCap.Message, "please ack") {
		t.Errorf("first-message body should carry remainder %q; got %+v", "please ack", msgCap)
	}

	// Ephemeral acknowledges the spawn.
	select {
	case body := <-ephemeralCh:
		text, _ := body["text"].(string)
		if !strings.Contains(text, "@@new-handle") {
			t.Errorf("ephemeral text should echo @@<handle>: %q", text)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("expected chat.postEphemeral within 2s")
	}

	if got := atomic.LoadInt32(&releases); got != 1 {
		t.Errorf("release fired %d times; want 1", got)
	}
}

// TestRoomLaunchDispatchReuseOnHitSkipsCreateAndPostsToExistingSession
// — a second post in the same thread does NOT spawn a new session.
// The thread registry's AcquireOrCreate hit returns the existing
// session id; the dispatcher only posts the new message.
func TestRoomLaunchDispatchReuseOnHitSkipsCreateAndPostsToExistingSession(t *testing.T) {
	srv, hits := newGCStub(t)
	_ = captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:           srv.URL,
		cityName:            "test-city",
		provider:            "slack",
		accountID:           "T1",
		handlePrefix:        "@",
		slackBotToken:       "xoxb-test",
		dispatchConcurrency: 8,
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)
	roomReg := newTestRoomLaunchRegistry(t, "T1", "C1", "mission-control/launcher")

	// Pre-bind the thread → existing session.
	threadTS := "1700000000.000100"
	_, _, err := threadReg.AcquireOrCreate("C1", threadTS, func() (string, error) {
		return "sess-existing-9", nil
	})
	if err != nil {
		t.Fatalf("seed AcquireOrCreate: %v", err)
	}

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  "C1",
		User:     "U1",
		TS:       "1700000000.000200",
		ThreadTS: threadTS, // reply within existing thread root
		Text:     "@@new-handle follow up",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg, TeamID: "T1"}

	processSlackEvent(cfg, aliasReg, threadReg, roomReg, nil, nil, env, func() {})

	// No /v0/sessions POST on a thread hit.
	if got := atomic.LoadInt32(&hits.sessionsCreate); got != 0 {
		t.Errorf("/v0/sessions POSTs = %d, want 0 (reuse path must not spawn)", got)
	}
	// Exactly one /v0/session/{id}/messages POST routed to the existing session.
	if got := atomic.LoadInt32(&hits.sessionMessages); got != 1 {
		t.Errorf("/v0/session/{id}/messages POSTs = %d, want 1", got)
	}
	msgPath, _ := hits.lastMessagePath.Load().(string)
	wantPath := "/v0/city/test-city/session/sess-existing-9/messages"
	if msgPath != wantPath {
		t.Errorf("message path = %q, want %q", msgPath, wantPath)
	}
}

// TestRoomLaunchDispatchChannelNotEnabledEmitsActionableEphemeral —
// `@@<handle>` in a channel without a launcher binding produces a
// fix-it ephemeral and does not POST anything to gc.
func TestRoomLaunchDispatchChannelNotEnabledEmitsActionableEphemeral(t *testing.T) {
	srv, hits := newGCStub(t)
	ephemeralCh := captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:           srv.URL,
		cityName:            "test-city",
		provider:            "slack",
		accountID:           "T1",
		handlePrefix:        "@",
		slackBotToken:       "xoxb-test",
		dispatchConcurrency: 8,
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)
	// Empty registry — no binding for C-other.
	roomReg := newTestRoomLaunchRegistry(t, "", "", "")

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C-other",
		User:    "U1",
		TS:      "1700000000.000100",
		Text:    "@@new-handle hi",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg, TeamID: "T1"}

	processSlackEvent(cfg, aliasReg, threadReg, roomReg, nil, nil, env, func() {})

	if got := atomic.LoadInt32(&hits.sessionsCreate); got != 0 {
		t.Errorf("/v0/sessions POSTs = %d, want 0", got)
	}
	if got := atomic.LoadInt32(&hits.sessionMessages); got != 0 {
		t.Errorf("/v0/session/{id}/messages POSTs = %d, want 0", got)
	}
	select {
	case body := <-ephemeralCh:
		text, _ := body["text"].(string)
		if !strings.Contains(text, "enable-room-launch") {
			t.Errorf("ephemeral should mention enable-room-launch: %q", text)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("expected ephemeral")
	}
}

// TestRoomLaunchDispatchSpawnFailureLeavesRegistryEmpty — when the gc
// /v0/sessions POST returns 500, the threadSessionRegistry.AcquireOrCreate
// contract (cby.5.1) MUST NOT cache the failed sessionID; a retry from
// the same thread should still land in the spawn branch.
func TestRoomLaunchDispatchSpawnFailureLeavesRegistryEmpty(t *testing.T) {
	srv, hits := newGCStub(t)
	hits.createStatus.Store(int32(http.StatusInternalServerError))
	ephemeralCh := captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:           srv.URL,
		cityName:            "test-city",
		provider:            "slack",
		accountID:           "T1",
		handlePrefix:        "@",
		slackBotToken:       "xoxb-test",
		dispatchConcurrency: 8,
		dispatchSem: defaultTestDispatchSem,
	}
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)
	roomReg := newTestRoomLaunchRegistry(t, "T1", "C1", "mission-control/launcher")

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000100",
		Text:    "@@new-handle please ack",
	})
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg, TeamID: "T1"}

	processSlackEvent(cfg, aliasReg, threadReg, roomReg, nil, nil, env, func() {})

	// Registry should NOT cache a failure: AcquireOrCreate's contract
	// (cby.5.1) returns the create-closure error and does not persist.
	if _, ok := threadReg.Lookup("C1", "1700000000.000100"); ok {
		t.Error("threadReg should not cache failed spawns")
	}
	// Alias must also remain unset.
	if _, ok := aliasReg.Get("new-handle"); ok {
		t.Error("aliasReg should not register a handle on spawn failure")
	}

	// Ephemeral surfaces the error so the user knows to retry/diagnose.
	select {
	case body := <-ephemeralCh:
		text, _ := body["text"].(string)
		if !strings.Contains(strings.ToLower(text), "fail") &&
			!strings.Contains(strings.ToLower(text), "error") &&
			!strings.Contains(strings.ToLower(text), "could not") {
			t.Errorf("error ephemeral missing diagnostic marker: %q", text)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("expected error ephemeral")
	}
}

// TestRoomLaunchDispatchSaturationDropsAtOuterSlot — saturation is
// enforced at the outer handleSlackEvents acquireDispatchSlot boundary,
// matching the existing alias-dispatch contract (cby.26 Phase 4):
// the launcher path inherits the same outer slot rather than acquiring
// a second one, so a saturated semaphore drops the event upstream
// before processSlackEvent runs at all. We assert the contract by
// confirming the outer slot is what gates the launcher: with the
// semaphore saturated, calling handleSlackEvents skips processing.
func TestRoomLaunchDispatchSaturationDropsAtOuterSlot(t *testing.T) {
	srv, hits := newGCStub(t)
	_ = captureSlackPostEphemeral(t)

	cfg := config{
		gcAPIBase:           srv.URL,
		cityName:            "test-city",
		provider:            "slack",
		accountID:           "T1",
		handlePrefix:        "@",
		slackBotToken:       "xoxb-test",
		slackSigningKey:     "secret",
		dispatchConcurrency: 1,
		dispatchSem:         make(chan struct{}, 1),
	}
	holdRelease, _, ok := cfg.acquireDispatchSlot()
	if !ok {
		t.Fatal("could not acquire dispatch slot for saturation setup")
	}
	defer holdRelease()
	aliasReg := newTestHandleAliasRegistry(t)
	threadReg := newTestThreadSessionRegistry(t)
	roomReg := newTestRoomLaunchRegistry(t, "T1", "C1", "mission-control/launcher")

	rawMsg, _ := json.Marshal(slackMessageEvent{
		Type:    "message",
		Channel: "C1",
		User:    "U1",
		TS:      "1700000000.000100",
		Text:    "@@new-handle please ack",
	})
	envBody, _ := json.Marshal(slackEventEnvelope{Type: "event_callback", Event: rawMsg, TeamID: "T1"})
	req := signedSlackEventRequest(t, cfg.slackSigningKey, envBody)
	w := httptest.NewRecorder()

	handler := handleSlackEvents(cfg, aliasReg, threadReg, roomReg, nil, nil)
	handler(w, req)

	// Slack always gets 200 (Slack-side retry suppression), but no
	// /v0/sessions POST should occur because the outer slot drop
	// short-circuited dispatch before processSlackEvent ran.
	if w.Result().StatusCode != http.StatusOK {
		t.Errorf("status = %d, want 200", w.Result().StatusCode)
	}
	time.Sleep(50 * time.Millisecond)
	if got := atomic.LoadInt32(&hits.sessionsCreate); got != 0 {
		t.Errorf("/v0/sessions POSTs = %d, want 0 on saturation", got)
	}
}

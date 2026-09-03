package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

// Tests for the busy-reaction lifecycle (hq-xizo): a targeted inbound
// gets the BUSY_REACTION emoji (default "hourglass") added to the
// inbound Slack message and a pending mark recorded; the agent's
// reply publishing back into the same conversation/thread removes the
// reaction and consumes the mark. The lifecycle replaces the previous
// unconditional "eyes" reaction on targeted inbounds and is the
// channel-native stand-in for Slack Assistant-mode setStatus.

// recordedReaction is one captured reactions.add / reactions.remove
// call, decoded from the stub Slack server's request body.
type recordedReaction struct {
	op        string // "add" | "remove"
	channel   string
	name      string
	timestamp string
}

// reactionRecorder collects reaction calls hitting the stub Slack
// server. Each call is also pushed onto ch so tests can await the
// async reaction goroutines without polling.
type reactionRecorder struct {
	mu    sync.Mutex
	calls []recordedReaction
	ch    chan recordedReaction
}

func (r *reactionRecorder) record(rec recordedReaction) {
	r.mu.Lock()
	r.calls = append(r.calls, rec)
	r.mu.Unlock()
	select {
	case r.ch <- rec:
	default:
	}
}

// await blocks until one reaction call arrives or d elapses.
func (r *reactionRecorder) await(t *testing.T, d time.Duration) recordedReaction {
	t.Helper()
	select {
	case rec := <-r.ch:
		return rec
	case <-time.After(d):
		t.Fatalf("no reaction call reached the Slack stub within %v", d)
		return recordedReaction{}
	}
}

// assertNoCall asserts that no (further) reaction call arrives within d.
func (r *reactionRecorder) assertNoCall(t *testing.T, d time.Duration) {
	t.Helper()
	select {
	case rec := <-r.ch:
		t.Fatalf("unexpected reaction call: op=%s chan=%s name=%s ts=%s",
			rec.op, rec.channel, rec.name, rec.timestamp)
	case <-time.After(d):
		// expected: silence
	}
}

// newReactionRecordingSlackStub returns an httptest Slack API stub
// that records reactions.add / reactions.remove calls (answering
// ok:true), answers chat.postMessage with a fixed ts, and answers
// every other method with a bare ok:true. Callers pair it with
// withSlackAPIStub.
func newReactionRecordingSlackStub(t *testing.T) (*httptest.Server, *reactionRecorder) {
	t.Helper()
	rr := &reactionRecorder{ch: make(chan recordedReaction, 16)}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasSuffix(r.URL.Path, "/reactions.add"), strings.HasSuffix(r.URL.Path, "/reactions.remove"):
			var body slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&body)
			op := "add"
			if strings.HasSuffix(r.URL.Path, "/reactions.remove") {
				op = "remove"
			}
			rr.record(recordedReaction{op: op, channel: body.Channel, name: body.Name, timestamp: body.Timestamp})
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		case strings.HasSuffix(r.URL.Path, "/chat.postMessage"):
			_, _ = fmt.Fprint(w, `{"ok":true,"ts":"999.000001"}`)
		default:
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		}
	}))
	t.Cleanup(srv.Close)
	return srv, rr
}

// busyTestConfig builds the minimal cfg for processSlackEvent tests of
// the busy lifecycle, targeting the supplied gc stub.
func busyTestConfig(gcURL string) config {
	return config{
		gcAPIBase:     gcURL,
		cityName:      "test-city",
		provider:      "slack",
		accountID:     "T1",
		handlePrefix:  "@",
		slackBotToken: "xoxb-fake",
		dispatchSem:   defaultTestDispatchSem,
		busyReaction:  busyReactionDefault,
		busyMarks:     newBusyReactionRegistry(),
	}
}

// targetedInboundEnvelope builds an event_callback envelope for a
// channel message explicitly addressing @mayor.
func targetedInboundEnvelope(t *testing.T, channel, ts, threadTS string) slackEventEnvelope {
	t.Helper()
	rawMsg, err := json.Marshal(slackMessageEvent{
		Type:     "message",
		Channel:  channel,
		User:     "U_ALICE",
		TS:       ts,
		ThreadTS: threadTS,
		Text:     "@mayor please deploy the thing",
	})
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}
	return slackEventEnvelope{Type: "event_callback", Event: rawMsg}
}

// publishBody builds a /publish request body targeting conversation
// with an optional thread ts.
func publishBody(conversationID, replyTo string) string {
	b, _ := json.Marshal(publishRequest{
		SessionID:        "gc-1",
		Conversation:     conversationRef{ConversationID: conversationID},
		Text:             "done — deployed",
		ReplyToMessageID: replyTo,
	})
	return string(b)
}

// (a) A targeted inbound adds exactly one busy reaction — the
// configured default "hourglass", NOT the legacy "eyes" — on the
// inbound ts, and records the pending mark under (channel, own-ts)
// for a channel-root message.
func TestBusyReaction_TargetedInboundAddsBusyAndRecordsMark(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	env := targetedInboundEnvelope(t, "C1", "100.000010", "")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	got := reactions.await(t, 2*time.Second)
	if got.op != "add" {
		t.Errorf("reaction op = %q, want %q", got.op, "add")
	}
	if got.name != "hourglass" {
		t.Errorf("reaction name = %q, want %q (busy emoji replaces the legacy eyes)", got.name, "hourglass")
	}
	if got.channel != "C1" || got.timestamp != "100.000010" {
		t.Errorf("reaction target = (%s, %s), want (C1, 100.000010)", got.channel, got.timestamp)
	}
	// Exactly one reaction call: no second add, and in particular no
	// legacy "eyes".
	reactions.assertNoCall(t, 300*time.Millisecond)

	if ts, ok := cfg.busyMarks.pending("C1", "100.000010"); !ok || ts != "100.000010" {
		t.Errorf("busy mark = (%q, %v), want (100.000010, true)", ts, ok)
	}
	if msgs := capture.snapshot(); len(msgs) != 1 {
		t.Fatalf("captured %d inbound messages, want 1", len(msgs))
	}
}

// A targeted inbound that is itself a thread reply records its mark
// under BOTH the thread's root ts (thread_ts) and its own ts — reply
// paths thread under either (codex r2) — still reacting on the
// inbound message's own ts.
func TestBusyReaction_ThreadReplyInboundKeyedByThreadTS(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	env := targetedInboundEnvelope(t, "C1", "100.000020", "100.000001")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	got := reactions.await(t, 2*time.Second)
	if got.op != "add" || got.timestamp != "100.000020" {
		t.Errorf("reaction = (%s on %s), want add on 100.000020", got.op, got.timestamp)
	}
	if ts, ok := cfg.busyMarks.pending("C1", "100.000001"); !ok || ts != "100.000020" {
		t.Errorf("busy mark under thread-root key = (%q, %v), want (100.000020, true)", ts, ok)
	}
	if ts, ok := cfg.busyMarks.pending("C1", "100.000020"); !ok || ts != "100.000020" {
		t.Errorf("busy mark under own-ts key = (%q, %v), want (100.000020, true)", ts, ok)
	}
}

// (b) A subsequent /publish into the same conversation+thread removes
// the busy emoji from the recorded message ts and consumes the
// registry entry. Covers both inbound shapes: a channel-root inbound
// (marked under its own ts) and a thread-reply inbound (marked under
// its thread_ts, reaction on its own ts).
func TestBusyReaction_PublishToSameThreadRemovesBusy(t *testing.T) {
	cases := []struct {
		name         string
		seedThreadTS string // inbound's thread_ts ("" = channel-root inbound)
		seedTS       string // inbound's own ts
		replyTo      string // publish reply_to_message_id
		markedTS     string // ts the reaction sits on
	}{
		{name: "root inbound, reply threads under its ts",
			seedThreadTS: "", seedTS: "100.000010", replyTo: "100.000010", markedTS: "100.000010"},
		{name: "thread-reply inbound, reply threads under the root",
			seedThreadTS: "100.000001", seedTS: "100.000020", replyTo: "100.000001", markedTS: "100.000020"},
		{name: "thread-reply inbound, reply threads under the inbound's own ts (codex r2)",
			seedThreadTS: "100.000001", seedTS: "100.000020", replyTo: "100.000020", markedTS: "100.000020"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			slackStub, reactions := newReactionRecordingSlackStub(t)
			withSlackAPIStub(t, slackStub)

			marks := newBusyReactionRegistry()
			// Close addDone: the add already completed in this scenario.
			done, _ := marks.markBoth("C1", tc.seedThreadTS, tc.seedTS, "")
			close(done)
			cfg := config{slackBotToken: "xoxb-fake", busyReaction: "hourglass", busyMarks: marks}

			req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody("C1", tc.replyTo)))
			rec := httptest.NewRecorder()
			handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
			if rec.Code != http.StatusOK {
				t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
			}
			var receipt publishReceipt
			if err := json.Unmarshal(rec.Body.Bytes(), &receipt); err != nil || !receipt.Delivered {
				t.Fatalf("publish receipt delivered = %v (err=%v, body=%s)", receipt.Delivered, err, rec.Body.String())
			}

			got := reactions.await(t, 2*time.Second)
			if got.op != "remove" {
				t.Errorf("reaction op = %q, want %q", got.op, "remove")
			}
			if got.name != "hourglass" {
				t.Errorf("reaction name = %q, want %q", got.name, "hourglass")
			}
			if got.channel != "C1" || got.timestamp != tc.markedTS {
				t.Errorf("remove target = (%s, %s), want (C1, %s)", got.channel, got.timestamp, tc.markedTS)
			}
			if _, ok := marks.pending("C1", tc.replyTo); ok {
				t.Error("registry entry survived the publish; want consumed")
			}
		})
	}
}

// (c) A /publish that matches no pending mark — unrelated
// conversation (threaded or root), or unrelated thread in the same
// conversation — fires no reactions.remove and leaves existing marks
// untouched.
func TestBusyReaction_UnrelatedPublishDoesNotRemove(t *testing.T) {
	for _, tc := range []struct {
		name         string
		conversation string
		replyTo      string
	}{
		{name: "different conversation, threaded", conversation: "C_OTHER", replyTo: "100.000010"},
		{name: "different conversation, channel root", conversation: "C_OTHER", replyTo: ""},
		{name: "different thread", conversation: "C1", replyTo: "555.000001"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			slackStub, reactions := newReactionRecordingSlackStub(t)
			withSlackAPIStub(t, slackStub)

			marks := newBusyReactionRegistry()
			marks.mark("C1", "100.000010", "100.000010")
			cfg := config{slackBotToken: "xoxb-fake", busyReaction: "hourglass", busyMarks: marks}

			req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody(tc.conversation, tc.replyTo)))
			rec := httptest.NewRecorder()
			handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
			if rec.Code != http.StatusOK {
				t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
			}

			reactions.assertNoCall(t, 300*time.Millisecond)
			if _, ok := marks.pending("C1", "100.000010"); !ok {
				t.Error("unrelated publish consumed the pending mark; want untouched")
			}
		})
	}
}

// A channel-root publish into the SAME conversation — the documented
// default `gc slack reply-current` shape, which carries no
// reply_to_message_id — clears every pending mark in that
// conversation (codex r3): a busy emoji nothing will ever remove is
// worse than clearing a sibling thread's affordance early.
func TestBusyReaction_RootPublishClearsConversationMarks(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)

	marks := newBusyReactionRegistry()
	doneA, _ := marks.markBoth("C1", "", "100.000010", "")
	close(doneA)
	doneB, _ := marks.markBoth("C1", "200.000001", "200.000020", "")
	close(doneB)
	cfg := config{slackBotToken: "xoxb-fake", busyReaction: "hourglass", busyMarks: marks}

	req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody("C1", "")))
	rec := httptest.NewRecorder()
	handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}

	// Two distinct marked messages → two removes (dual-key entries for
	// the thread-reply inbound dedupe to one).
	got := map[string]bool{}
	for i := 0; i < 2; i++ {
		rec := reactions.await(t, 2*time.Second)
		if rec.op != "remove" {
			t.Errorf("reaction op = %q, want remove", rec.op)
		}
		got[rec.timestamp] = true
	}
	if !got["100.000010"] || !got["200.000020"] {
		t.Errorf("removed set = %v, want both 100.000010 and 200.000020", got)
	}
	reactions.assertNoCall(t, 300*time.Millisecond)
	if n := marks.size(); n != 0 {
		t.Errorf("registry has %d entries after root-publish clear, want 0", n)
	}
}

// Re-targeting the same thread before the first reply lands moves the
// busy affordance: the displaced mark's reaction is removed (codex
// r3) — TTL expiry only deletes metadata, never the Slack-side emoji.
func TestBusyReaction_RetargetRemovesSupersededReaction(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	// First targeted inbound: channel-root message M1.
	env1 := targetedInboundEnvelope(t, "C1", "100.000010", "")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env1, func() {})
	first := reactions.await(t, 2*time.Second)
	if first.op != "add" || first.timestamp != "100.000010" {
		t.Fatalf("first reaction = (%s on %s), want add on 100.000010", first.op, first.timestamp)
	}

	// Second targeted inbound M2 replying in M1's thread: displaces
	// M1's mark (root key now points at M2).
	env2 := targetedInboundEnvelope(t, "C1", "100.000020", "100.000010")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env2, func() {})

	// Expect an add on M2 and a remove on the superseded M1, in any
	// order (both async).
	ops := map[string]string{}
	for i := 0; i < 2; i++ {
		rec := reactions.await(t, 2*time.Second)
		ops[rec.op] = rec.timestamp
	}
	if ops["add"] != "100.000020" {
		t.Errorf("add landed on %q, want 100.000020", ops["add"])
	}
	if ops["remove"] != "100.000010" {
		t.Errorf("remove landed on %q, want superseded 100.000010", ops["remove"])
	}
}

// (d) BUSY_REACTION= (set-but-empty) disables the lifecycle: the
// config loads as empty, a targeted inbound adds NO reaction (the
// legacy eyes included — the lifecycle replaced it) and records no
// mark, while the inbound still forwards to gc.
func TestBusyReaction_EmptyEnvDisablesLifecycle(t *testing.T) {
	// Config level: present-but-empty must NOT fall back to the
	// default. Requires the lookup entry point — a plain getenv cannot
	// express "set but empty".
	env := baseSlackEnv()
	env["BUSY_REACTION"] = ""
	cfg0, err := loadConfigFromLookup(func(key string) (string, bool) {
		v, ok := env[key]
		return v, ok
	})
	if err != nil {
		t.Fatalf("loadConfigFromLookup: %v", err)
	}
	if cfg0.busyReaction != "" {
		t.Fatalf("busyReaction = %q with BUSY_REACTION= set-but-empty, want disabled (empty)", cfg0.busyReaction)
	}

	// Behavior level: no reaction of any kind, no mark, inbound still
	// forwarded.
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	cfg.busyReaction = ""
	env2 := targetedInboundEnvelope(t, "C1", "100.000010", "")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env2, func() {})

	reactions.assertNoCall(t, 400*time.Millisecond)
	if n := cfg.busyMarks.size(); n != 0 {
		t.Errorf("registry has %d entries with the lifecycle disabled, want 0", n)
	}
	if msgs := capture.snapshot(); len(msgs) != 1 {
		t.Fatalf("captured %d inbound messages, want 1 (disable must not drop the forward)", len(msgs))
	}
}

// BUSY_REACTION config defaults and overrides through the standard
// env entry points.
func TestBusyReaction_ConfigDefaultsAndOverrides(t *testing.T) {
	cases := []struct {
		name  string
		set   bool
		value string
		want  string
	}{
		{name: "unset defaults to hourglass", set: false, want: "hourglass"},
		{name: "custom emoji honored", set: true, value: "hourglass_flowing_sand", want: "hourglass_flowing_sand"},
		{name: "surrounding colons stripped", set: true, value: ":hourglass_flowing_sand:", want: "hourglass_flowing_sand"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			env := baseSlackEnv()
			if tc.set {
				env["BUSY_REACTION"] = tc.value
			}
			cfg, err := loadConfigFromEnv(stubEnv(env))
			if err != nil {
				t.Fatalf("loadConfigFromEnv: %v", err)
			}
			if cfg.busyReaction != tc.want {
				t.Errorf("busyReaction = %q, want %q", cfg.busyReaction, tc.want)
			}
		})
	}
}

// (e) A custom BUSY_REACTION emoji is used on both sides of the
// lifecycle: the add on dispatch and the remove on reply.
func TestBusyReaction_CustomEmojiHonored(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	cfg.busyReaction = "hourglass_flowing_sand"
	env := targetedInboundEnvelope(t, "C1", "100.000010", "")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	added := reactions.await(t, 2*time.Second)
	if added.op != "add" || added.name != "hourglass_flowing_sand" {
		t.Errorf("add = (%s, %s), want (add, hourglass_flowing_sand)", added.op, added.name)
	}

	req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody("C1", "100.000010")))
	rec := httptest.NewRecorder()
	handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}
	removed := reactions.await(t, 2*time.Second)
	if removed.op != "remove" || removed.name != "hourglass_flowing_sand" || removed.timestamp != "100.000010" {
		t.Errorf("remove = (%s, %s on %s), want (remove, hourglass_flowing_sand on 100.000010)",
			removed.op, removed.name, removed.timestamp)
	}
}

// (f) A reply that lands while the reactions.add is still in flight
// must not have its reactions.remove overtake the add — Slack would
// apply the delayed add last and the busy emoji would stick forever.
// The remove side waits on the mark's addDone channel (hw-94w5k
// codex r1).
func TestBusyReaction_FastReplyWaitsForAddBeforeRemove(t *testing.T) {
	rr := &reactionRecorder{ch: make(chan recordedReaction, 16)}
	slackStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasSuffix(r.URL.Path, "/reactions.add"):
			// Simulate a slow Slack: the add is still in flight when
			// the reply's publish arrives.
			time.Sleep(400 * time.Millisecond)
			var body slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&body)
			rr.record(recordedReaction{op: "add", channel: body.Channel, name: body.Name, timestamp: body.Timestamp})
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		case strings.HasSuffix(r.URL.Path, "/reactions.remove"):
			var body slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&body)
			rr.record(recordedReaction{op: "remove", channel: body.Channel, name: body.Name, timestamp: body.Timestamp})
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		case strings.HasSuffix(r.URL.Path, "/chat.postMessage"):
			_, _ = fmt.Fprint(w, `{"ok":true,"ts":"999.000001"}`)
		default:
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		}
	}))
	t.Cleanup(slackStub.Close)
	withSlackAPIStub(t, slackStub)
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	env := targetedInboundEnvelope(t, "C1", "100.000010", "")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	// Reply immediately — well before the 400ms add completes.
	req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody("C1", "100.000010")))
	rec := httptest.NewRecorder()
	handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}

	first := rr.await(t, 2*time.Second)
	second := rr.await(t, 2*time.Second)
	if first.op != "add" || second.op != "remove" {
		t.Errorf("reaction order = (%s, %s), want (add, remove) — remove must not overtake the in-flight add",
			first.op, second.op)
	}
}

// A threaded /publish-file reply — possibly the agent's entire answer
// — clears the pending busy mark exactly like a text publish
// (hw-94w5k codex r1).
func TestBusyReaction_PublishFileToSameThreadRemovesBusy(t *testing.T) {
	rr := &reactionRecorder{ch: make(chan recordedReaction, 16)}
	uploadStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(uploadStub.Close)
	slackStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasSuffix(r.URL.Path, "/files.getUploadURLExternal"):
			_, _ = fmt.Fprintf(w, `{"ok":true,"upload_url":%q,"file_id":"F1"}`, uploadStub.URL+"/upload")
		case strings.HasSuffix(r.URL.Path, "/files.completeUploadExternal"):
			_, _ = fmt.Fprint(w, `{"ok":true,"files":[{"id":"F1"}]}`)
		case strings.HasSuffix(r.URL.Path, "/reactions.remove"):
			var body slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&body)
			rr.record(recordedReaction{op: "remove", channel: body.Channel, name: body.Name, timestamp: body.Timestamp})
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		default:
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		}
	}))
	t.Cleanup(slackStub.Close)
	withSlackAPIStub(t, slackStub)

	root, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("EvalSymlinks: %v", err)
	}
	filePath := filepath.Join(root, "answer.png")
	if err := os.WriteFile(filePath, []byte("PNGDATA"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	marks := newBusyReactionRegistry()
	close(marks.mark("C1", "100.000010", "100.000010"))
	cfg := config{
		slackBotToken:  "xoxb-fake",
		busyReaction:   "hourglass",
		busyMarks:      marks,
		fileUploadRoot: root,
	}

	body := fmt.Sprintf(`{"conversation":{"conversation_id":"C1"},"file_path":%q,"reply_to_message_id":"100.000010"}`, filePath)
	req := httptest.NewRequest(http.MethodPost, "/publish-file", strings.NewReader(body))
	rec := httptest.NewRecorder()
	handlePublishFile(cfg, nil, nil)(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("publish-file status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}
	var receipt publishFileReceipt
	if err := json.Unmarshal(rec.Body.Bytes(), &receipt); err != nil || !receipt.Delivered {
		t.Fatalf("publish-file receipt delivered = %v (err=%v, body=%s)", receipt.Delivered, err, rec.Body.String())
	}

	got := rr.await(t, 2*time.Second)
	if got.op != "remove" || got.name != "hourglass" || got.channel != "C1" || got.timestamp != "100.000010" {
		t.Errorf("reaction = (%s, %s on %s/%s), want (remove, hourglass on C1/100.000010)",
			got.op, got.name, got.channel, got.timestamp)
	}
	if _, ok := marks.pending("C1", "100.000010"); ok {
		t.Error("registry entry survived the file publish; want consumed")
	}
}

// (h) The mark registers BEFORE the forward to gc (codex r4): a reply
// published while postInbound is still in flight must find the mark,
// and the eventual add must still be removed (ordered after the add).
func TestBusyReaction_ReplyDuringForwardFindsMark(t *testing.T) {
	rr := &reactionRecorder{ch: make(chan recordedReaction, 16)}
	slackStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasSuffix(r.URL.Path, "/reactions.add"):
			var body slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&body)
			rr.record(recordedReaction{op: "add", channel: body.Channel, name: body.Name, timestamp: body.Timestamp})
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		case strings.HasSuffix(r.URL.Path, "/reactions.remove"):
			var body slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&body)
			rr.record(recordedReaction{op: "remove", channel: body.Channel, name: body.Name, timestamp: body.Timestamp})
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		case strings.HasSuffix(r.URL.Path, "/chat.postMessage"):
			_, _ = fmt.Fprint(w, `{"ok":true,"ts":"999.000001"}`)
		default:
			_, _ = fmt.Fprint(w, `{"ok":true}`)
		}
	}))
	t.Cleanup(slackStub.Close)
	withSlackAPIStub(t, slackStub)

	// gc stub: the inbound forward stalls long enough for the agent's
	// reply to arrive first.
	forwardStarted := make(chan struct{}, 1)
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case forwardStarted <- struct{}{}:
		default:
		}
		time.Sleep(300 * time.Millisecond)
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	env := targetedInboundEnvelope(t, "C1", "100.000010", "")
	procDone := make(chan struct{})
	go func() {
		defer close(procDone)
		processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})
	}()
	<-forwardStarted

	// Reply while the forward is still in flight: the mark must exist.
	req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody("C1", "100.000010")))
	rec := httptest.NewRecorder()
	handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}

	first := rr.await(t, 3*time.Second)
	second := rr.await(t, 3*time.Second)
	if first.op != "add" || second.op != "remove" || second.timestamp != "100.000010" {
		t.Errorf("reaction sequence = (%s, %s on %s), want (add, remove on 100.000010)",
			first.op, second.op, second.timestamp)
	}
	<-procDone
}

// A failed forward cancels the pre-registered mark: no reply is
// coming, and the redelivery re-marks on take-over.
func TestBusyReaction_FailedForwardCancelsMark(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	env := targetedInboundEnvelope(t, "C1", "100.000010", "")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	if n := cfg.busyMarks.size(); n != 0 {
		t.Errorf("registry has %d entries after failed forward, want 0 (mark cancelled)", n)
	}
	// No reactions.add either — the forward never succeeded.
	reactions.assertNoCall(t, 300*time.Millisecond)
}

// A re-target whose forward FAILS must not strip the previous
// message's busy affordance: no remove fires, and the displaced mark
// is restored so the earlier agent's eventual reply can still clear
// it (codex r5).
func TestBusyReaction_FailedRetargetRestoresDisplacedMark(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	t.Cleanup(gcStub.Close)

	cfg := busyTestConfig(gcStub.URL)
	// Pre-existing mark: root message M1, its add already completed.
	doneM1, _ := cfg.busyMarks.markBoth("C1", "", "100.000010", "")
	close(doneM1)

	// Targeted thread reply M2 in M1's thread; its forward fails.
	env := targetedInboundEnvelope(t, "C1", "100.000020", "100.000010")
	processSlackEvent(cfg, newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	// No reactions at all: M2's add never fired (forward failed) and
	// M1's emoji must NOT have been removed.
	reactions.assertNoCall(t, 300*time.Millisecond)
	if ts, ok := cfg.busyMarks.pending("C1", "100.000010"); !ok || ts != "100.000010" {
		t.Errorf("displaced mark = (%q, %v), want restored (100.000010, true)", ts, ok)
	}
	if _, ok := cfg.busyMarks.pending("C1", "100.000020"); ok {
		t.Error("failed re-target's own-ts mark survived; want cancelled")
	}
}

// Overlapping re-targets with a failure in the middle must not orphan
// the oldest reaction (codex r6): M2 displaced M1, M3 displaced M2,
// M2's forward fails while M3 owns the key — M1 must merge into M3's
// stale ancestry so the thread's eventual clear removes it.
func TestBusyReactionRegistry_FailedMiddleRetargetPreservesAncestors(t *testing.T) {
	r := newBusyReactionRegistry()
	const m1, m2, m3 = "1.0", "2.0", "3.0"

	d1, disp := r.markBoth("C1", "", m1, "")
	close(d1)
	if len(disp) != 0 {
		t.Fatalf("M1 displaced %v, want none", disp)
	}
	d2, disp2 := r.markBoth("C1", m1, m2, "") // M2 re-targets M1's thread
	d3, disp3 := r.markBoth("C1", m1, m3, "") // M3 re-targets again
	close(d3)
	if len(disp2) == 0 || disp2[0].mark.messageTS != m1 {
		t.Fatalf("M2 displaced %v, want M1", disp2)
	}
	if len(disp3) == 0 || disp3[0].mark.messageTS != m2 {
		t.Fatalf("M3 displaced %v, want M2", disp3)
	}

	// M2's forward fails while M3 owns the key: restore must not
	// clobber M3, and M1 must survive as M3's stale ancestor.
	r.cancelBoth("C1", m1, m2, d2, disp2)
	if ts, ok := r.pending("C1", m1); !ok || ts != m3 {
		t.Fatalf("key owner after failed M2 = (%q, %v), want M3", ts, ok)
	}

	taken := r.take("C1", m1, nil)
	got := map[string]bool{}
	for _, tk := range taken {
		got[tk.messageTS] = true
	}
	if !got[m3] || !got[m1] {
		t.Errorf("take returned %v, want M3's mark plus preserved ancestor M1", got)
	}
	if got[m2] {
		t.Errorf("take returned failed M2 (%v); its reaction never landed and it was displaced into M3's superseded set", got)
	}
}

// takeMessage consumes exactly the named message's reaction and
// re-parks any stale ancestors riding on the entry (codex r6 alias-
// failure cleanup).
func TestBusyReactionRegistry_TakeMessageReparksAncestors(t *testing.T) {
	r := newBusyReactionRegistry()
	const m1, m2, m3 = "1.0", "2.0", "3.0"
	d1, _ := r.markBoth("C1", "", m1, "")
	close(d1)
	d2, disp2 := r.markBoth("C1", m1, m2, "")
	d3, disp3 := r.markBoth("C1", m1, m3, "")
	close(d3)
	r.cancelBoth("C1", m1, m2, d2, disp2) // M1 → M3's stale
	_ = disp3

	taken := r.takeMessage("C1", m1, m3)
	if len(taken) != 1 || taken[0].messageTS != m3 {
		t.Fatalf("takeMessage = %v, want exactly M3", taken)
	}
	// M1 must have been re-parked under the key, still clearable.
	remaining := r.take("C1", m1, nil)
	got := map[string]bool{}
	for _, tk := range remaining {
		got[tk.messageTS] = true
	}
	if !got[m1] {
		t.Errorf("re-parked set = %v, want ancestor M1 preserved", got)
	}
}

// Consuming either alias of a dual-key mark consumes BOTH entries and
// tombstones both keys (codex r10): a reply threading under the
// inbound's own ts is the clearing event for the root-key sibling too.
func TestBusyReactionRegistry_TakeConsumesBothDualKeys(t *testing.T) {
	r := newBusyReactionRegistry()
	d, _ := r.markBoth("C1", "1.0", "2.0", "") // root key 1.0 + own-ts key 2.0
	close(d)

	taken := r.take("C1", "2.0", nil) // reply threads under the inbound's own ts
	if len(taken) != 1 || taken[0].messageTS != "2.0" {
		t.Fatalf("take = %v, want exactly the 2.0 mark once", taken)
	}
	if _, ok := r.pending("C1", "1.0"); ok {
		t.Error("root-key sibling survived the own-ts take; want consumed")
	}
	// Both keys are tombstoned: a restore under the root key blocks.
	dOld := make(chan struct{})
	close(dOld)
	blocked := r.restoreDisplaced("C1", []busyDisplaced{{threadKey: "1.0", mark: busyTaken{messageTS: "0.5", addDone: dOld}}})
	if len(blocked) != 1 || blocked[0].messageTS != "0.5" {
		t.Errorf("restore under consumed root key = blocked %v, want the 0.5 mark handed back", blocked)
	}
}

// A reply that consumed the thread while a displacing dispatch was in
// flight tombstones the key: a failed dispatch must NOT restore the
// displaced mark afterwards — the thread's clearing event already
// happened — and the blocked mark is returned for reaction removal
// (codex r8). A fresh mark on the key re-arms it.
func TestBusyReactionRegistry_TombstoneBlocksRestoreAfterConsume(t *testing.T) {
	r := newBusyReactionRegistry()
	const m1, m2 = "1.0", "2.0"

	d1, _ := r.markBoth("C1", "", m1, "")
	close(d1)
	d2, disp2 := r.markBoth("C1", m1, m2, "") // M2 displaces M1
	if len(disp2) == 0 || disp2[0].mark.messageTS != m1 {
		t.Fatalf("displaced = %v, want M1", disp2)
	}
	// A reply lands while M2's dispatch is in flight and consumes the
	// thread (root key + own-ts key).
	if taken := r.take("C1", m1, nil); len(taken) == 0 {
		t.Fatal("reply take found no mark")
	}
	// M2's dispatch fails: restore must be blocked by the tombstone and
	// M1 handed back for removal.
	blocked := r.cancelBoth("C1", m1, m2, d2, disp2)
	got := map[string]bool{}
	for _, tk := range blocked {
		got[tk.messageTS] = true
	}
	if !got[m1] {
		t.Errorf("blocked = %v, want M1 handed back for removal", got)
	}
	if _, ok := r.pending("C1", m1); ok {
		t.Error("mark restored under a tombstoned key; want blocked")
	}

	// A fresh targeted inbound re-arms the key despite the tombstone.
	d3, _ := r.markBoth("C1", "", m1, "")
	close(d3)
	if _, ok := r.pending("C1", m1); !ok {
		t.Error("fresh mark did not re-arm the tombstoned key")
	}
}

// A re-mark of the SAME message (retaken redelivery) merges add
// completions: the stored done closes only when every add attempt has
// concluded (codex r4).
func TestBusyReactionRegistry_SameMessageRemarkMergesAddDone(t *testing.T) {
	r := newBusyReactionRegistry()
	d1, _ := r.markBoth("C1", "", "1.0", "")
	d2, _ := r.markBoth("C1", "", "1.0", "")

	taken := r.take("C1", "1.0", nil)
	if len(taken) != 1 || taken[0].addDone == nil {
		t.Fatalf("take = %v, want one entry with a merged done channel", taken)
	}
	done := taken[0].addDone
	assertOpen := func(label string) {
		t.Helper()
		select {
		case <-done:
			t.Fatalf("merged done closed %s", label)
		case <-time.After(50 * time.Millisecond):
		}
	}
	assertOpen("before either add concluded")
	close(d1)
	assertOpen("with the second add still in flight")
	close(d2)
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("merged done not closed after both adds concluded")
	}
}

// (g) A mark past busyReactionTTL is dead: the publish consumes the
// stale entry but fires no reactions.remove.
func TestBusyReaction_ExpiredMarkDoesNotRemove(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)

	var mu sync.Mutex
	current := time.Now()
	marks := newBusyReactionRegistry()
	marks.now = func() time.Time {
		mu.Lock()
		defer mu.Unlock()
		return current
	}
	marks.mark("C1", "100.000010", "100.000010")
	mu.Lock()
	current = current.Add(busyReactionTTL + time.Minute)
	mu.Unlock()

	cfg := config{slackBotToken: "xoxb-fake", busyReaction: "hourglass", busyMarks: marks}
	req := httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(publishBody("C1", "100.000010")))
	rec := httptest.NewRecorder()
	handlePublish(cfg, nil, nil, nil, newPublishDedupCache(publishDedupTTL))(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("publish status = %d, want 200 (body=%s)", rec.Code, rec.Body.String())
	}
	var receipt publishReceipt
	if err := json.Unmarshal(rec.Body.Bytes(), &receipt); err != nil || !receipt.Delivered {
		t.Fatalf("publish receipt delivered = %v (err=%v)", receipt.Delivered, err)
	}

	reactions.assertNoCall(t, 300*time.Millisecond)
	if n := marks.size(); n != 0 {
		t.Errorf("registry has %d entries after expired-take, want 0 (stale entry dropped)", n)
	}
}

// Registry semantics: take consumes, re-take misses, expired entries
// are swept opportunistically on mark.
func TestBusyReactionRegistry_TakeAndSweep(t *testing.T) {
	var mu sync.Mutex
	current := time.Now()
	r := newBusyReactionRegistry()
	r.now = func() time.Time {
		mu.Lock()
		defer mu.Unlock()
		return current
	}

	r.mark("C1", "1.0", "1.0")
	if taken := r.take("C1", "1.0", nil); len(taken) != 1 || taken[0].messageTS != "1.0" {
		t.Fatalf("take = %v, want one entry for 1.0", taken)
	}
	if taken := r.take("C1", "1.0", nil); len(taken) != 0 {
		t.Fatal("second take succeeded; want consumed on first take")
	}

	// Opportunistic sweep: an expired entry disappears on the next mark.
	r.mark("C1", "2.0", "2.0")
	mu.Lock()
	current = current.Add(busyReactionTTL + time.Minute)
	mu.Unlock()
	r.mark("C1", "3.0", "3.0")
	if n := r.size(); n != 1 {
		t.Errorf("size after sweep = %d, want 1 (expired 2.0 swept, fresh 3.0 kept)", n)
	}
	if _, ok := r.pending("C1", "2.0"); ok {
		t.Error("expired entry 2.0 survived the sweep")
	}
}

// Registry semantics: the size cap evicts the oldest surviving mark
// (mirroring the dmGateMaxEntries pattern), keeping the map bounded.
func TestBusyReactionRegistry_CapEvictsOldest(t *testing.T) {
	var mu sync.Mutex
	current := time.Now()
	r := newBusyReactionRegistry()
	r.now = func() time.Time {
		mu.Lock()
		defer mu.Unlock()
		return current
	}

	for i := 0; i <= busyReactionMaxEntries; i++ {
		mu.Lock()
		current = current.Add(time.Millisecond)
		mu.Unlock()
		key := fmt.Sprintf("%d.0", i)
		r.mark("C1", key, key)
	}
	if n := r.size(); n != busyReactionMaxEntries {
		t.Errorf("size = %d, want cap %d", n, busyReactionMaxEntries)
	}
	if _, ok := r.pending("C1", "0.0"); ok {
		t.Error("oldest entry survived cap eviction; want evicted")
	}
	last := fmt.Sprintf("%d.0", busyReactionMaxEntries)
	if _, ok := r.pending("C1", last); !ok {
		t.Error("newest entry missing after cap eviction; want kept")
	}
}

// A nil registry is inert on every method — the lifecycle degrades to
// "no busy affordance" instead of panicking (old tests construct cfg
// without busyMarks).
func TestBusyReactionRegistry_NilSafe(t *testing.T) {
	var r *busyReactionRegistry
	if done := r.mark("C1", "1.0", "1.0"); done == nil {
		t.Error("mark on nil registry returned a nil addDone channel; want closable")
	}
	if taken := r.take("C1", "1.0", nil); len(taken) != 0 {
		t.Error("take on nil registry reported a mark")
	}
	if _, ok := r.pending("C1", "1.0"); ok {
		t.Error("pending on nil registry reported a mark")
	}
	if n := r.size(); n != 0 {
		t.Errorf("size on nil registry = %d, want 0", n)
	}
}

// codex r11: a reply may only clear marks recorded for the publishing
// agent. M1 targets alpha, M2 re-targets beta in the same thread —
// alpha's late reply must not consume beta's mark.
func TestBusyReactionRegistry_TakeRespectsHandleMatcher(t *testing.T) {
	r := newBusyReactionRegistry()
	done, _ := r.markBoth("C1", "", "1.0", "beta")
	close(done)

	if taken := r.take("C1", "1.0", func(h string) bool { return h == "alpha" }); len(taken) != 0 {
		t.Fatalf("non-matching publisher consumed %d marks; want 0", len(taken))
	}
	if _, ok := r.pending("C1", "1.0"); !ok {
		t.Fatal("beta's mark gone after non-matching take; want left in place")
	}
	taken := r.take("C1", "1.0", func(h string) bool { return h == "beta" })
	if len(taken) != 1 || taken[0].messageTS != "1.0" {
		t.Fatalf("matching take = %v, want the 1.0 mark", taken)
	}
}

// codex r11: an unthreaded (channel-root) reply clears only the
// publisher's own marks in the conversation, leaving other agents'
// pending affordances alone. Unattributed (empty-handle) marks still
// clear for any publisher.
func TestBusyReactionRegistry_TakeConversationRespectsHandleMatcher(t *testing.T) {
	r := newBusyReactionRegistry()
	dA, _ := r.markBoth("C1", "", "1.0", "alpha")
	close(dA)
	dB, _ := r.markBoth("C1", "", "2.0", "beta")
	close(dB)
	dU, _ := r.markBoth("C1", "", "3.0", "")
	close(dU)

	taken := r.takeConversation("C1", func(h string) bool { return h == "" || h == "alpha" })
	got := map[string]bool{}
	for _, tk := range taken {
		got[tk.messageTS] = true
	}
	if !got["1.0"] || !got["3.0"] || got["2.0"] || len(taken) != 2 {
		t.Fatalf("takeConversation = %v, want exactly [1.0 3.0]", taken)
	}
	if _, ok := r.pending("C1", "2.0"); !ok {
		t.Fatal("beta's mark gone after alpha's root reply; want left in place")
	}
}

// codex r11 wiring: clearBusyReaction resolves the publisher via the
// alias registry — a session that does not own the mark's handle
// cannot clear it; the owning session can.
func TestClearBusyReactionMatchesPublisherSession(t *testing.T) {
	slackStub, reactions := newReactionRecordingSlackStub(t)
	withSlackAPIStub(t, slackStub)

	aliasReg := newTestHandleAliasRegistry(t)
	if err := aliasReg.Set("beta", "gc-beta"); err != nil {
		t.Fatalf("aliasReg.Set: %v", err)
	}
	marks := newBusyReactionRegistry()
	done, _ := marks.markBoth("C1", "", "1.0", "beta")
	close(done)
	cfg := config{slackBotToken: "xoxb-fake", busyReaction: "hourglass", busyMarks: marks}

	clearBusyReaction(cfg, aliasReg, "gc-alpha", "C1", "1.0")
	reactions.assertNoCall(t, 300*time.Millisecond)
	if _, ok := marks.pending("C1", "1.0"); !ok {
		t.Fatal("foreign session's reply consumed beta's mark")
	}

	clearBusyReaction(cfg, aliasReg, "gc-beta", "C1", "1.0")
	got := reactions.await(t, 2*time.Second)
	if got.op != "remove" || got.timestamp != "1.0" {
		t.Fatalf("owning session's reply: got (%s on %s), want remove on 1.0", got.op, got.timestamp)
	}
}

// codex r16: stale ancestors are matched per handle. Alpha's orphaned
// reaction riding in beta's entry must be cleared by ALPHA's reply
// (and only alpha's), while beta's own mark stays for beta.
func TestBusyReactionRegistry_StaleAncestorsMatchedPerHandle(t *testing.T) {
	r := newBusyReactionRegistry()
	// alpha targets the thread; beta re-targets it, displacing alpha's
	// mark under the thread-root key; the failed-re-target path then
	// restores alpha's mark as a stale ancestor on beta's entry.
	dA, _ := r.markBoth("C1", "root.0", "1.0", "alpha")
	close(dA)
	dB, superseded := r.markBoth("C1", "root.0", "2.0", "beta")
	close(dB)
	if len(superseded) != 1 {
		t.Fatalf("superseded = %v, want alpha's displaced mark", superseded)
	}
	r.restoreDisplaced("C1", superseded)

	// Beta's reply clears ONLY beta's mark; alpha's ancestor re-parks.
	taken := r.take("C1", "root.0", func(h string) bool { return h == "beta" })
	got := map[string]bool{}
	for _, tk := range taken {
		got[tk.messageTS] = true
	}
	if !got["2.0"] || got["1.0"] || len(taken) != 1 {
		t.Fatalf("beta's take = %v, want exactly [2.0]", taken)
	}
	// Alpha's reply then clears its re-parked mark.
	taken = r.take("C1", "root.0", func(h string) bool { return h == "alpha" })
	if len(taken) != 1 || taken[0].messageTS != "1.0" {
		t.Fatalf("alpha's take = %v, want [1.0]", taken)
	}
}

// codex r16: takeConversation partitions per mark too — a root reply
// by alpha clears alpha's marks and unattributed ones while beta's
// survive, including when they ride the same entry.
func TestBusyReactionRegistry_TakeConversationPartitionsStale(t *testing.T) {
	r := newBusyReactionRegistry()
	dB, _ := r.markBoth("C1", "", "2.0", "beta")
	close(dB)
	// Alpha's orphan rides beta's entry as a stale ancestor.
	r.restoreDisplaced("C1", []busyDisplaced{{threadKey: "2.0", mark: busyTaken{messageTS: "1.0", handle: "alpha"}}})

	taken := r.takeConversation("C1", func(h string) bool { return h == "alpha" })
	if len(taken) != 1 || taken[0].messageTS != "1.0" {
		t.Fatalf("alpha's root reply took %v, want exactly [1.0]", taken)
	}
	if _, ok := r.pending("C1", "2.0"); !ok {
		t.Fatal("beta's mark gone after alpha's root reply")
	}
}

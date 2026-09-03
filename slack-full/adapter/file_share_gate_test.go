package main

import (
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"
)

// Tests for the inbound message gate's file handling (hw-94w5k
// finding #1): Slack delivers human file posts both as plain message
// events with files[] (modern composer) and as subtype "file_share"
// (older/API surfaces). Both must reach postInbound so the attachment
// pipeline can run; file-only posts (no caption) must not be dropped
// by the empty-text gate; every other subtype stays filtered.

func fileGateConfig(gcURL string) config {
	return config{
		gcAPIBase:   gcURL,
		cityName:    "test-city",
		provider:    "slack",
		accountID:   "T1",
		dispatchSem: defaultTestDispatchSem,
	}
}

// processAndSnapshot runs one event through processSlackEvent and
// returns the inbounds captured by the gc stub after a settle window.
func processAndSnapshot(t *testing.T, msg slackMessageEvent) []externalInboundMessage {
	t.Helper()
	capture := &inboundCapture{}
	gcStub := httptest.NewServer(capture.handler())
	t.Cleanup(gcStub.Close)

	rawMsg, err := json.Marshal(msg)
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}
	env := slackEventEnvelope{Type: "event_callback", Event: rawMsg}
	processSlackEvent(fileGateConfig(gcStub.URL), newTestHandleAliasRegistry(t), nil, nil, nil, nil, env, func() {})

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if len(capture.snapshot()) > 0 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	return capture.snapshot()
}

func testSlackFile() slackFile {
	return slackFile{ID: "F1", Name: "screenshot.png", MIMEType: "image/png"}
}

// A file_share-subtyped human message forwards to gc instead of being
// dropped with the system-noise subtypes.
func TestFileShareSubtypeForwards(t *testing.T) {
	got := processAndSnapshot(t, slackMessageEvent{
		Type: "message", Subtype: "file_share", Channel: "C1", User: "U1",
		TS: "1.0", Text: "look at this", Files: []slackFile{testSlackFile()},
	})
	if len(got) != 1 {
		t.Fatalf("captured %d inbound messages, want 1 (file_share must pass the subtype gate)", len(got))
	}
	if got[0].Text != "look at this" {
		t.Errorf("forwarded text = %q, want %q", got[0].Text, "look at this")
	}
}

// A file-only post — files attached, no caption — forwards despite the
// empty text. (INBOUND_FILE_STORE is unset here so the attachment
// download itself is skipped; the gate decision is what's under test.)
func TestFileOnlyMessageForwards(t *testing.T) {
	got := processAndSnapshot(t, slackMessageEvent{
		Type: "message", Channel: "C1", User: "U1",
		TS: "1.0", Text: "", Files: []slackFile{testSlackFile()},
	})
	if len(got) != 1 {
		t.Fatalf("captured %d inbound messages, want 1 (file-only post must not be dropped)", len(got))
	}
}

// Empty text with no files still drops — nothing to route.
func TestEmptyMessageStillDropped(t *testing.T) {
	got := processAndSnapshot(t, slackMessageEvent{
		Type: "message", Channel: "C1", User: "U1", TS: "1.0", Text: "   ",
	})
	if len(got) != 0 {
		t.Fatalf("captured %d inbound messages, want 0 (no text, no files)", len(got))
	}
}

// Non-file_share subtypes stay filtered as system noise.
func TestOtherSubtypesStillDropped(t *testing.T) {
	for _, subtype := range []string{"message_changed", "message_deleted", "channel_join", "bot_message"} {
		got := processAndSnapshot(t, slackMessageEvent{
			Type: "message", Subtype: subtype, Channel: "C1", User: "U1",
			TS: "1.0", Text: "hi", Files: []slackFile{testSlackFile()},
		})
		if len(got) != 0 {
			t.Errorf("subtype %q: captured %d inbound messages, want 0", subtype, len(got))
		}
	}
}

// A bot-authored file_share stays dropped — the bot gate outranks the
// file_share allowance (echo-loop protection).
func TestBotFileShareStillDropped(t *testing.T) {
	got := processAndSnapshot(t, slackMessageEvent{
		Type: "message", Subtype: "file_share", Channel: "C1", User: "U1",
		BotID: "B1", TS: "1.0", Text: "bot upload", Files: []slackFile{testSlackFile()},
	})
	if len(got) != 0 {
		t.Fatalf("captured %d inbound messages, want 0 (bot file_share must stay dropped)", len(got))
	}
}

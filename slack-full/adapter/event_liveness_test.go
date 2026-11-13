package main

import (
	"encoding/json"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func awaitLivenessFile(t *testing.T, path string) map[string]any {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		data, err := os.ReadFile(path)
		var state map[string]any
		if err == nil && json.Unmarshal(data, &state) == nil {
			return state
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("no liveness state at %s", path)
	return nil
}

func TestVerifiedBotCallbackLiveness(t *testing.T) {
	city := t.TempDir()
	cfg := config{cityPath: city, slackSigningKey: "secret", dispatchSem: defaultTestDispatchSem}
	handler := handleSlackEvents(cfg, nil, nil, nil, nil, nil)
	path := filepath.Join(city, ".gc", "slack", "event-liveness.json")
	for _, requestCase := range []struct{ body, secret string }{
		{`{"type":"event_callback","event":{"type":"message","bot_id":"B1"}}`, "wrong-secret"},
		{`{"type":"url_verification","challenge":"hello"}`, "secret"},
	} {
		request := signedSlackEventRequest(t, requestCase.secret, []byte(requestCase.body))
		handler(httptest.NewRecorder(), request)
	}
	time.Sleep(30 * time.Millisecond)
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("excluded request recorded: %v", err)
	}
	before := time.Now().UTC()
	w := httptest.NewRecorder()
	handler(w, signedSlackEventRequest(t, "secret", []byte(`{"type":"event_callback","event":{"type":"message","bot_id":"B1"}}`)))
	if w.Code != http.StatusOK {
		t.Fatalf("ack = %d", w.Code)
	}
	state := awaitLivenessFile(t, path)
	at, err := time.Parse(time.RFC3339Nano, state["last_event_at"].(string))
	if err != nil || at.Before(before) || state["count"] != float64(1) || state["last_event_type"] != "message" {
		t.Fatalf("state = %v, error = %v", state, err)
	}
}

func TestLivenessWriteFailureAcknowledges(t *testing.T) {
	city := t.TempDir()
	dir := filepath.Join(city, ".gc", "slack")
	if err := os.MkdirAll(dir, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0500); err != nil {
		t.Fatal(err)
	}
	logs := make(livenessLogSink, 20)
	previous := log.Writer()
	log.SetOutput(logs)
	defer log.SetOutput(previous)
	t.Cleanup(func() { os.Chmod(dir, 0700) })
	cfg := config{cityPath: city, slackSigningKey: "secret", dispatchSem: defaultTestDispatchSem}
	handler := handleSlackEvents(cfg, nil, nil, nil, nil, nil)
	w := httptest.NewRecorder()
	handler(w, signedSlackEventRequest(t, "secret", []byte(`{"type":"event_callback","event":{"type":"message","bot_id":"B1"}}`)))
	if w.Code != http.StatusOK {
		t.Fatalf("ack = %d", w.Code)
	}
	timeout := time.After(time.Second)
	for {
		select {
		case line := <-logs:
			if strings.Contains(line, "event liveness write failed") {
				return
			}
		case <-timeout:
			t.Fatal("missing state write failure log")
		}
	}
}

type livenessLogSink chan string

func (sink livenessLogSink) Write(data []byte) (int, error) {
	select {
	case sink <- string(data):
	default:
	}
	return len(data), nil
}

func TestOutboundLivenessPost(t *testing.T) {
	city := t.TempDir()
	t.Setenv("GC_CITY_PATH", city)
	var captured slackPostMessageReq
	fake := newFakeSlackPublishHandler(t, &captured, "1791300000.123456", func() {})
	client := &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
		w := httptest.NewRecorder()
		fake(w, r)
		return w.Result(), nil
	})}
	resp, err := postMessageWithClient(client, "test", slackPostMessageReq{Channel: "C123", Text: "hello"})
	if err != nil || !resp.OK {
		t.Fatalf("post = %v, %v", resp, err)
	}
	state := awaitLivenessFile(t, filepath.Join(city, ".gc", "slack", "outbound-liveness.json"))
	if state["last_outbound_at"] != "2026-10-06T15:20:00.123456Z" {
		t.Fatalf("state = %v", state)
	}
}

func TestLivenessBurstTrailingFlushAndRestart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "event-liveness.json")
	if err := os.WriteFile(path, []byte(`{"count":7,"last_event_at":"2026-01-01T00:00:00Z","last_event_type":"message"}`), 0600); err != nil {
		t.Fatal(err)
	}
	recorder := &eventLivenessRecorder{path: path}
	recorder.record(json.RawMessage(`{"type":"message","bot_id":"B1"}`))
	deadline := time.Now().Add(time.Second)
	for awaitLivenessFile(t, path)["count"] != float64(8) {
		if time.Now().After(deadline) {
			t.Fatal("first callback not persisted")
		}
		time.Sleep(time.Millisecond)
	}
	first, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	last := time.Now().UTC()
	for i := 0; i < 100; i++ {
		recorder.record(json.RawMessage(`{"type":"reaction_added"}`))
	}
	time.Sleep(50 * time.Millisecond)
	data, err := os.ReadFile(path)
	if err != nil || string(first) != string(data) {
		t.Fatalf("burst rewrote state: %s %v", data, err)
	}
	deadline = time.Now().Add(11 * time.Second)
	for {
		state := awaitLivenessFile(t, path)
		if state["count"] == float64(108) {
			at, err := time.Parse(time.RFC3339Nano, state["last_event_at"].(string))
			if err != nil || at.Before(last) || state["last_event_type"] != "reaction_added" {
				t.Fatalf("trailing state = %v", state)
			}
			return
		}
		if time.Now().After(deadline) {
			t.Fatalf("trailing flush missing: %v", state)
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func TestOutboundLivenessKeepsNewestChannelPost(t *testing.T) {
	city := t.TempDir()
	t.Setenv("GC_CITY_PATH", city)
	for _, item := range []struct {
		channel, timestamp string
		ok                 bool
	}{
		{"C123", "1791300000.123456", true},
		{"C123", "1791200000.123456", true},
		{"D123", "1791400000.123456", true},
		{"C123", "1791500000.123456", false},
	} {
		client := &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
			w := httptest.NewRecorder()
			if err := json.NewEncoder(w).Encode(map[string]any{"ok": item.ok, "channel": item.channel, "ts": item.timestamp}); err != nil {
				t.Fatal(err)
			}
			return w.Result(), nil
		})}
		if _, err := postMessageWithClient(client, "test", slackPostMessageReq{Channel: item.channel}); err != nil {
			t.Fatal(err)
		}
	}
	state := awaitLivenessFile(t, filepath.Join(city, ".gc", "slack", "outbound-liveness.json"))
	if state["last_outbound_at"] != "2026-10-06T15:20:00.123456Z" {
		t.Fatalf("state = %v", state)
	}
}

func TestLivenessCorruptStateIsReplaced(t *testing.T) {
	path := filepath.Join(t.TempDir(), "event-liveness.json")
	if err := os.WriteFile(path, []byte("{not json"), 0600); err != nil {
		t.Fatal(err)
	}
	recorder := &eventLivenessRecorder{path: path}
	recorder.record(json.RawMessage(`{"type":"message","bot_id":"B1"}`))
	state := awaitLivenessFile(t, path)
	if state["count"] != float64(1) || state["last_event_type"] != "message" {
		t.Fatalf("corrupt state not replaced: %v", state)
	}
}

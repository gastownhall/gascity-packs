package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"sync"
	"testing"
)

func TestReadbackRedundantAutoLinks(t *testing.T) {
	for _, tc := range []struct {
		posted, stored string
		match          bool
	}{
		{"a@example.test", "<mailto:a@example.test|a@example.test>", true},
		{"+15551234567", "<tel:+15551234567|+15551234567>", true},
		{"https://example.test", "<https://example.test|https://example.test>", true},
		{"<@U123>", "<@U123|name>", true},
		{"<#C123>", "<#C123|channel>", true},
		{"a@example.test", "<mailto:b@example.test|a@example.test>", false},
		{"+15551234567", "<tel:+15557654321|+15551234567>", false},
		{"`a@example.test`", "`<mailto:a@example.test|a@example.test>`", false},
	} {
		t.Run(tc.posted+tc.stored, func(t *testing.T) {
			if got := slackNormalizeText(tc.posted) == slackNormalizeText(tc.stored); got != tc.match {
				t.Fatalf("normalized equality = %v, want %v", got, tc.match)
			}
		})
	}
}

func TestAcceptedReplayMetadataIsIsolated(t *testing.T) {
	fastReadbackTimings(t)
	newSlackReadbackServer(t, "/conversations.history", func(url.Values) {}, `{"ok":true,"messages":[]}`)
	dedup := newPublishDedupCache(publishDedupTTL)
	accepted := publishReceipt{Delivered: true, MessageID: "1700.001",
		Metadata: map[string]string{receiptMetadataKeyReadback: slackReadbackUnavailable}}
	dedup.Put("key", accepted)
	var wg sync.WaitGroup
	for range 8 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r, ok := replayPublishReceipt("xoxb-test", dedup, "key", readbackTarget("expected"))
			if !ok || !r.Delivered || r.FailureKind != "" || r.Metadata[receiptMetadataKeyReadback] != slackReadbackUnconfirmed {
				t.Errorf("replay = %+v, %v", r, ok)
			}
		}()
	}
	wg.Wait()
	if accepted.Metadata[receiptMetadataKeyReadback] != slackReadbackUnavailable {
		t.Fatal("replay mutated the original receipt")
	}
	dedup.Put("key", publishReceipt{Delivered: true, MessageID: accepted.MessageID})
	dedup.Put("key", accepted) // a slower failed read cannot downgrade confirmation
	r, ok := dedup.Get("key")
	if !ok || !publishReadbackConfirmed(r) {
		t.Fatal("stale read downgraded confirmation")
	}
}

func TestPublishWithoutTimestampRemainsFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat.postMessage" {
			t.Errorf("unexpected readback without a timestamp: %s", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	t.Cleanup(server.Close)
	withSlackAPIStub(t, server)
	handler := handlePublish(config{slackBotToken: "xoxb-test"}, nil, nil, newPublishDedupCache(publishDedupTTL))
	w := httptest.NewRecorder()
	handler(w, httptest.NewRequest(http.MethodPost, "/publish", strings.NewReader(
		`{"session_id":"gc-test","conversation":{"conversation_id":"C123"},"text":"hello"}`)))
	if w.Code != http.StatusOK {
		t.Fatalf("publish status = %d: %s", w.Code, w.Body)
	}
	var receipt publishReceipt
	if err := json.Unmarshal(w.Body.Bytes(), &receipt); err != nil {
		t.Fatal(err)
	}
	if receipt.Delivered || receipt.MessageID != "" || receipt.FailureKind != "transient" {
		t.Fatalf("missing timestamp incorrectly accepted: %+v", receipt)
	}
}

// The checked-in shape contains no investor data. Set SLACK_READBACK_INCIDENT
// to the private recorded fixture to run the same comparator on the original
// 3,429-character digest and the exact conversations.replies response.
func TestReadBackInvestorDigest(t *testing.T) {
	posted := "*Investor sweep*\n" + strings.Repeat("• Follow up → waiting…\n", 150) +
		"Email contact@example.test; contact@example.test is >3d overdue & pending."
	stored := strings.NewReplacer("contact@example.test", "<mailto:contact@example.test|contact@example.test>",
		">", "&gt;", "&", "&amp;").Replace(posted)
	fixture := struct {
		Posted    string          `json:"posted"`
		Channel   string          `json:"channel"`
		MessageTS string          `json:"message_ts"`
		ThreadTS  string          `json:"thread_ts"`
		Response  json.RawMessage `json:"response"`
	}{Posted: posted, Channel: "C123", MessageTS: "1791976711.647429", ThreadTS: "1787962615.345489"}
	fixture.Response, _ = json.Marshal(map[string]any{"ok": true, "has_more": false, "messages": []map[string]any{
		{"ts": fixture.ThreadTS, "text": "parent", "reply_count": 113},
		{"ts": fixture.MessageTS, "text": stored},
	}})
	if path := os.Getenv("SLACK_READBACK_INCIDENT"); path != "" {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if err := json.Unmarshal(data, &fixture); err != nil {
			t.Fatal(err)
		}
		t.Log("Using private recorded incident fixture (body omitted)")
	} else {
		t.Log("Using public synthetic incident shape")
	}
	server := newSlackReadbackServer(t, "/conversations.replies", func(query url.Values) {
		assertSlackReadbackQuery(t, query, fixture.Channel, fixture.MessageTS, "2")
		if query.Get("ts") != fixture.ThreadTS {
			t.Errorf("thread timestamp = %q", query.Get("ts"))
		}
	}, string(fixture.Response))
	target := slackReadbackTarget{channel: fixture.Channel, messageTS: fixture.MessageTS,
		threadTS: fixture.ThreadTS, expectedText: fixture.Posted}
	if err := readBackPublishedMessageOnce(server.Client(), "xoxb-test", target); err != nil {
		t.Fatal(err)
	}
	var response slackReadbackResponse
	if err := json.Unmarshal(fixture.Response, &response); err != nil {
		t.Fatal(err)
	}
	for _, message := range response.Messages {
		if message.TS == fixture.MessageTS && slackNormalizeText(fixture.Posted) != slackNormalizeText(message.Text) {
			t.Fatal("incident text differs even after normalization")
		}
	}
	// A different body at that timestamp remains an unconfirmed readback.
	target.expectedText += " changed"
	if err := readBackPublishedMessageOnce(server.Client(), "xoxb-test", target); err == nil {
		t.Fatal("changed text was incorrectly confirmed")
	}
}

func TestAcceptedPublishSurvivesReadbackFailure(t *testing.T) {
	fastReadbackTimings(t)
	for _, tc := range []struct{ name, response, detail string }{
		{"absent", `{"ok":true,"messages":[]}`, slackReadbackUnconfirmed},
		{"mismatch", `{"ok":true,"messages":[{"ts":"1700.001","text":"different"}]}`, slackReadbackUnconfirmed},
		{"auth", `{"ok":false,"error":"missing_scope"}`, slackReadbackAuth},
		{"unavailable", `{"ok":false,"error":"internal_error"}`, slackReadbackUnavailable},
		{"malformed", `not JSON`, slackReadbackUnavailable},
	} {
		t.Run(tc.name, func(t *testing.T) {
			newSlackReadbackServer(t, "/conversations.history", func(query url.Values) {
				assertSlackReadbackQuery(t, query, "C123", "1700.001", "1")
			}, tc.response)
			receipt := publishReceipt{MessageID: "1700.001", Metadata: map[string]string{"truncated": "true"}}
			confirmPublishReceipt("xoxb-test", &receipt, readbackTarget("expected"))
			if !receipt.Delivered || receipt.FailureKind != "" {
				t.Fatalf("accepted post reported as failure: %+v", receipt)
			}
			if receipt.Metadata[receiptMetadataKeyReadback] != tc.detail || receipt.Metadata["truncated"] != "true" {
				t.Fatalf("readback detail or independent metadata lost: %v", receipt.Metadata)
			}
		})
	}
}

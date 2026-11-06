package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// --- G1: GET /channels -----------------------------------------------------

func TestHandleChannelsPaginated(t *testing.T) {
	clearLookupCaches()
	var calls atomic.Int32
	var gotAuth atomic.Value
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		gotAuth.Store(r.Header.Get("Authorization"))
		if !strings.HasSuffix(r.URL.Path, "/conversations.list") {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		cursor := r.URL.Query().Get("cursor")
		switch cursor {
		case "":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"ok":       true,
				"channels": []map[string]string{{"id": "C111", "name": "general"}},
				"response_metadata": map[string]string{
					"next_cursor": "page2",
				},
			})
		case "page2":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"ok":       true,
				"channels": []map[string]string{{"id": "C222", "name": "p-widget"}},
				"response_metadata": map[string]string{
					"next_cursor": "",
				},
			})
		default:
			t.Errorf("unexpected cursor %q", cursor)
		}
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	req := httptest.NewRequest(http.MethodGet, "/channels", nil)
	rec := httptest.NewRecorder()
	handleChannels(cfg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body=%s", rec.Code, rec.Body.String())
	}
	if got := gotAuth.Load().(string); got != "Bearer test-bot-token" {
		t.Errorf("Authorization = %q", got)
	}
	if calls.Load() != 2 {
		t.Fatalf("slack calls = %d, want 2 (pagination)", calls.Load())
	}
	var out struct {
		OK       bool              `json:"ok"`
		Channels map[string]string `json:"channels"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if !out.OK {
		t.Fatalf("ok = false, body=%s", rec.Body.String())
	}
	if out.Channels["general"] != "C111" || out.Channels["p-widget"] != "C222" {
		t.Errorf("channels = %v, want general→C111 and p-widget→C222", out.Channels)
	}
}

func TestHandleChannelsCachedWithTTL(t *testing.T) {
	clearLookupCaches()
	var calls atomic.Int32
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":                true,
			"channels":          []map[string]string{{"id": "C111", "name": "general"}},
			"response_metadata": map[string]string{"next_cursor": ""},
		})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	get := func() *httptest.ResponseRecorder {
		rec := httptest.NewRecorder()
		handleChannels(cfg)(rec, httptest.NewRequest(http.MethodGet, "/channels", nil))
		return rec
	}

	if rec := get(); rec.Code != http.StatusOK {
		t.Fatalf("first status = %d", rec.Code)
	}
	if rec := get(); rec.Code != http.StatusOK {
		t.Fatalf("second status = %d", rec.Code)
	}
	if calls.Load() != 1 {
		t.Fatalf("slack calls after 2 requests = %d, want 1 (cached)", calls.Load())
	}

	// Expire the cache: the next request must refetch.
	channelsCache.mu.Lock()
	channelsCache.expires = time.Now().Add(-time.Second)
	channelsCache.mu.Unlock()
	if rec := get(); rec.Code != http.StatusOK {
		t.Fatalf("post-expiry status = %d", rec.Code)
	}
	if calls.Load() != 2 {
		t.Errorf("slack calls after expiry = %d, want 2 (refetch)", calls.Load())
	}
}

func TestHandleChannelsSlackError(t *testing.T) {
	clearLookupCaches()
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "missing_scope"})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	rec := httptest.NewRecorder()
	handleChannels(cfg)(rec, httptest.NewRequest(http.MethodGet, "/channels", nil))

	if rec.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "missing_scope") {
		t.Errorf("error not surfaced: %s", rec.Body.String())
	}
}

func TestHandleChannelsMethodNotAllowed(t *testing.T) {
	cfg := config{botToken: "test-bot-token"}
	rec := httptest.NewRecorder()
	handleChannels(cfg)(rec, httptest.NewRequest(http.MethodPost, "/channels", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status = %d, want 405", rec.Code)
	}
}

// --- G2: GET /user-id ------------------------------------------------------

func TestHandleUserID(t *testing.T) {
	clearLookupCaches()
	var gotEmail atomic.Value
	var gotAuth atomic.Value
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotEmail.Store(r.URL.Query().Get("email"))
		gotAuth.Store(r.Header.Get("Authorization"))
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":   true,
			"user": map[string]string{"id": "U99"},
		})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	rec := httptest.NewRecorder()
	handleUserID(cfg)(rec, httptest.NewRequest(http.MethodGet, "/user-id?email=ada@example.com", nil))

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body=%s", rec.Code, rec.Body.String())
	}
	if got := gotEmail.Load().(string); got != "ada@example.com" {
		t.Errorf("email query = %q", got)
	}
	if got := gotAuth.Load().(string); got != "Bearer test-bot-token" {
		t.Errorf("Authorization = %q", got)
	}
	var out map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if out["ok"] != true || out["id"] != "U99" {
		t.Errorf("response = %v, want ok + id U99", out)
	}
}

func TestHandleUserIDCached(t *testing.T) {
	clearLookupCaches()
	var calls atomic.Int32
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":   true,
			"user": map[string]string{"id": "U99"},
		})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	for i := 0; i < 2; i++ {
		rec := httptest.NewRecorder()
		handleUserID(cfg)(rec, httptest.NewRequest(http.MethodGet, "/user-id?email=ada@example.com", nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("request %d status = %d", i, rec.Code)
		}
	}
	if calls.Load() != 1 {
		t.Fatalf("slack calls = %d, want 1 (cached)", calls.Load())
	}
}

func TestHandleUserIDNotFoundIs404(t *testing.T) {
	clearLookupCaches()
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "users_not_found"})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	rec := httptest.NewRecorder()
	handleUserID(cfg)(rec, httptest.NewRequest(http.MethodGet, "/user-id?email=ghost@example.com", nil))

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "users_not_found") {
		t.Errorf("body = %s, want users_not_found", rec.Body.String())
	}
}

func TestHandleUserIDMissingEmail(t *testing.T) {
	cfg := config{botToken: "test-bot-token"}
	rec := httptest.NewRecorder()
	handleUserID(cfg)(rec, httptest.NewRequest(http.MethodGet, "/user-id", nil))
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", rec.Code)
	}
}

func TestHandleUserIDSlackError(t *testing.T) {
	clearLookupCaches()
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "invalid_auth"})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	rec := httptest.NewRecorder()
	handleUserID(cfg)(rec, httptest.NewRequest(http.MethodGet, "/user-id?email=a@b.c", nil))
	if rec.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502", rec.Code)
	}
}

// --- G5: SLACK_MINI_INBOUND=off --------------------------------------------

func TestLoadConfigInboundOff(t *testing.T) {
	getenv := func(k string) string {
		switch k {
		case "SLACK_BOT_TOKEN":
			return "test-bot-token"
		case "SLACK_WORKSPACE_ID":
			return "T123"
		case "GC_CITY_NAME":
			return "mycity"
		case "SLACK_MINI_INBOUND":
			return "off"
		default:
			return ""
		}
	}
	cfg, err := loadConfigFromEnv(getenv)
	if err != nil {
		t.Fatalf("inbound=off without signing secret should pass, got %v", err)
	}
	if cfg.inboundEnabled {
		t.Error("inboundEnabled = true, want false")
	}
	if cfg.socketMode() {
		t.Error("socketMode = true with inbound off, want false")
	}
}

func TestLoadConfigInboundOffIgnoresAppToken(t *testing.T) {
	getenv := func(k string) string {
		switch k {
		case "SLACK_BOT_TOKEN":
			return "test-bot-token"
		case "SLACK_WORKSPACE_ID":
			return "T123"
		case "GC_CITY_NAME":
			return "mycity"
		case "SLACK_MINI_INBOUND":
			return "off"
		case "SLACK_APP_TOKEN":
			return "test-bot-token-pasted-by-mistake"
		default:
			return ""
		}
	}
	cfg, err := loadConfigFromEnv(getenv)
	if err != nil {
		t.Fatalf("inbound=off should skip app-token checks, got %v", err)
	}
	if cfg.socketMode() {
		t.Error("socketMode = true with inbound off, want false (token ignored)")
	}
}

func TestLoadConfigInboundDefaultUnchanged(t *testing.T) {
	base := map[string]string{
		"SLACK_BOT_TOKEN":    "test-bot-token",
		"SLACK_WORKSPACE_ID": "T123",
		"GC_CITY_NAME":       "mycity",
	}
	for _, tc := range []struct {
		name  string
		extra map[string]string
	}{
		{"unset", nil},
		{"explicit on", map[string]string{"SLACK_MINI_INBOUND": "on"}},
		{"empty", map[string]string{"SLACK_MINI_INBOUND": ""}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			m := map[string]string{}
			for k, v := range base {
				m[k] = v
			}
			for k, v := range tc.extra {
				m[k] = v
			}
			cfg, err := loadConfigFromEnv(func(k string) string { return m[k] })
			if err == nil || !strings.Contains(err.Error(), "SLACK_SIGNING_SECRET") {
				t.Fatalf("expected missing SLACK_SIGNING_SECRET error, got cfg=%+v err=%v", cfg, err)
			}
			if !cfg.inboundEnabled {
				t.Error("inboundEnabled = false, want true (default)")
			}
		})
	}
}

// --- G6: unfurl passthrough -------------------------------------------------

func TestHandlePostMessageUnfurlPassthrough(t *testing.T) {
	var gotBody map[string]any
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewDecoder(r.Body).Decode(&gotBody)
		_ = json.NewEncoder(w).Encode(slackPostMessageResp{OK: true, TS: "1", Channel: "C42"})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	reqBody := `{"channel":"C42","text":"see https://example.com/x","unfurl_links":false,"unfurl_media":true}`
	req := httptest.NewRequest(http.MethodPost, "/post-message", strings.NewReader(reqBody))
	rec := httptest.NewRecorder()
	handlePostMessage(cfg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body=%s", rec.Code, rec.Body.String())
	}
	if gotBody["unfurl_links"] != false {
		t.Errorf("unfurl_links forwarded = %v, want false", gotBody["unfurl_links"])
	}
	if gotBody["unfurl_media"] != true {
		t.Errorf("unfurl_media forwarded = %v, want true", gotBody["unfurl_media"])
	}
}

func TestHandlePostMessageUnfurlAbsentMeansDefault(t *testing.T) {
	var gotBody map[string]any
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewDecoder(r.Body).Decode(&gotBody)
		_ = json.NewEncoder(w).Encode(slackPostMessageResp{OK: true, TS: "1", Channel: "C42"})
	}))
	defer slack.Close()

	cfg := config{botToken: "test-bot-token", slackAPIBase: slack.URL}
	req := httptest.NewRequest(http.MethodPost, "/post-message", strings.NewReader(`{"channel":"C42","text":"hi"}`))
	rec := httptest.NewRecorder()
	handlePostMessage(cfg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body=%s", rec.Code, rec.Body.String())
	}
	if _, ok := gotBody["unfurl_links"]; ok {
		t.Errorf("unfurl_links present = %v, want absent (Slack default)", gotBody["unfurl_links"])
	}
	if _, ok := gotBody["unfurl_media"]; ok {
		t.Errorf("unfurl_media present = %v, want absent (Slack default)", gotBody["unfurl_media"])
	}
}

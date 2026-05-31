package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"testing"
	"time"
)

// signSlack produces a valid X-Slack-Signature header for the given body,
// timestamp, and secret — the inverse of verifySlackSignature.
func signSlack(secret, ts string, body []byte) string {
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte("v0:" + ts + ":"))
	_, _ = mac.Write(body)
	return "v0=" + hex.EncodeToString(mac.Sum(nil))
}

// fixedClock returns a deterministic time so on-disk created_at/updated_at
// stamps are stable across a test run.
func fixedClock() func() time.Time {
	t := time.Date(2026, 5, 30, 12, 0, 0, 0, time.UTC)
	return func() time.Time { return t }
}

// newTestServer builds a server backed by a fresh temp registry directory
// and a fixed clock. Slack/gc API bases are left empty; tests that exercise
// the network paths set them to httptest servers.
func newTestServer(t *testing.T) *server {
	t.Helper()
	cfg := config{
		cityName:      "mycity",
		provider:      "slack",
		workspaceID:   "T123",
		botToken:      "xoxb-test",
		signingSecret: "secret",
		inboundTarget: "mayor",
		slackAPIBase:  "https://slack.test/api",
		gcAPIBase:     "http://gc.test",
		registryDir:   t.TempDir(),
	}
	srv, err := newServer(cfg)
	if err != nil {
		t.Fatalf("newServer: %v", err)
	}
	srv.now = fixedClock()
	return srv
}

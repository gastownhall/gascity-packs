package main

import (
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
)

func TestHandleInteractionsAck(t *testing.T) {
	srv := newTestServer(t)
	body := []byte("payload=%7B%22type%22%3A%22block_actions%22%7D")
	ts := strconv.FormatInt(time.Now().Unix(), 10)

	req := httptest.NewRequest(http.MethodPost, "/slack/interactions", strings.NewReader(string(body)))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("X-Slack-Request-Timestamp", ts)
	req.Header.Set("X-Slack-Signature", signSlack(srv.cfg.signingSecret, ts, body))
	rec := httptest.NewRecorder()

	srv.handleInteractions()(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
}

func TestHandleInteractionsBadSignature(t *testing.T) {
	srv := newTestServer(t)
	req := httptest.NewRequest(http.MethodPost, "/slack/interactions", strings.NewReader("payload=%7B%7D"))
	req.Header.Set("X-Slack-Request-Timestamp", strconv.FormatInt(time.Now().Unix(), 10))
	req.Header.Set("X-Slack-Signature", "v0=deadbeef")
	rec := httptest.NewRecorder()

	srv.handleInteractions()(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", rec.Code)
	}
}

func TestHandleHealthz(t *testing.T) {
	rec := httptest.NewRecorder()
	handleHealthz(rec, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if rec.Code != http.StatusOK || strings.TrimSpace(rec.Body.String()) != "ok" {
		t.Fatalf("healthz = %d %q", rec.Code, rec.Body.String())
	}
}

func TestListenUDS(t *testing.T) {
	path := t.TempDir() + "/adapter.sock"
	lis, err := listenUDS(path)
	if err != nil {
		t.Fatalf("listenUDS: %v", err)
	}
	_ = lis.Close()
	// A stale socket file must not block a restart.
	lis2, err := listenUDS(path)
	if err != nil {
		t.Fatalf("listenUDS over stale: %v", err)
	}
	_ = lis2.Close()
}

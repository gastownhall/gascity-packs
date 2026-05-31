package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestRegisterAdapter(t *testing.T) {
	srv := newTestServer(t)
	var got adapterRegisterRequest
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/extmsg/adapters") {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		_ = json.NewDecoder(r.Body).Decode(&got)
		w.WriteHeader(http.StatusOK)
	}))
	defer gc.Close()
	srv.cfg.gcAPIBase = gc.URL

	if err := srv.registerAdapter(context.Background()); err != nil {
		t.Fatalf("registerAdapter: %v", err)
	}
	if got.Provider != "slack" || got.AccountID != "T123" {
		t.Errorf("register payload = %+v", got)
	}
	if got.Capabilities.SupportsChildConversations {
		t.Error("Tier 2 must not advertise child conversations")
	}
}

func TestPostJSONSurfacesErrorStatus(t *testing.T) {
	srv := newTestServer(t)
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = io.WriteString(w, "nope")
	}))
	defer gc.Close()
	if err := srv.postJSON(context.Background(), gc.URL, []byte(`{}`)); err == nil || !strings.Contains(err.Error(), "nope") {
		t.Fatalf("expected error surfacing body, got %v", err)
	}
}

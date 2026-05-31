package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func doMethod(method string, h http.HandlerFunc, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, "/x", strings.NewReader(body))
	rec := httptest.NewRecorder()
	h(rec, req)
	return rec
}

func TestHandleBind(t *testing.T) {
	srv := newTestServer(t)
	rec := doMethod(http.MethodPost, srv.handleBind(), `{"channel_id":"C1","kind":"room","session_ids":["s2","s1"]}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	got, ok := srv.bindingForChannel("C1")
	if !ok || got.Kind != "room" {
		t.Fatalf("binding not stored: %+v ok=%v", got, ok)
	}
	var resp struct {
		OK      bool           `json:"ok"`
		Binding channelBinding `json:"binding"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if !resp.OK || len(resp.Binding.SessionIDs) != 2 {
		t.Errorf("response = %+v", resp)
	}
}

func TestHandleBindValidation(t *testing.T) {
	srv := newTestServer(t)
	rec := doMethod(http.MethodPost, srv.handleBind(), `{"channel_id":"C1","kind":"thread","session_ids":["s1"]}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("bad kind should 400, got %d", rec.Code)
	}
}

func TestHandleIdentitySetAndRemove(t *testing.T) {
	srv := newTestServer(t)
	rec := doMethod(http.MethodPost, srv.handleIdentitySet(), `{"session_id":"s1","username":"PL","icon_emoji":"robot_face"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("set status=%d body=%s", rec.Code, rec.Body.String())
	}
	if id, ok := srv.identityFor("s1"); !ok || id.Username != "PL" {
		t.Fatalf("identity not set: %+v", id)
	}

	rec = doMethod(http.MethodDelete, srv.handleIdentityRemove(), `{"session_id":"s1"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("remove status=%d", rec.Code)
	}
	if _, ok := srv.identityFor("s1"); ok {
		t.Error("identity should be removed")
	}
}

func TestHandleIdentitySetValidation(t *testing.T) {
	srv := newTestServer(t)
	// both icon fields set is invalid
	rec := doMethod(http.MethodPost, srv.handleIdentitySet(), `{"session_id":"s1","icon_url":"u","icon_emoji":"e"}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status=%d", rec.Code)
	}
}

func TestHandleAliasSetAndRemove(t *testing.T) {
	srv := newTestServer(t)
	rec := doMethod(http.MethodPost, srv.handleAliasSet(), `{"handle":"@Mayor","session_id":"sess-1"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("set status=%d body=%s", rec.Code, rec.Body.String())
	}
	if a, ok := srv.aliasFor("mayor"); !ok || a.SessionID != "sess-1" {
		t.Fatalf("alias not set: %+v", a)
	}

	rec = doMethod(http.MethodDelete, srv.handleAliasRemove(), `{"handle":"mayor"}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("remove status=%d", rec.Code)
	}
	if _, ok := srv.aliasFor("mayor"); ok {
		t.Error("alias should be removed")
	}
}

func TestHandleAliasSetValidation(t *testing.T) {
	srv := newTestServer(t)
	rec := doMethod(http.MethodPost, srv.handleAliasSet(), `{"handle":"bad handle","session_id":"s1"}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status=%d", rec.Code)
	}
}

func TestRegistryHandlersRejectBadJSON(t *testing.T) {
	srv := newTestServer(t)
	handlers := map[string]http.HandlerFunc{
		"bind":         srv.handleBind(),
		"identity-set": srv.handleIdentitySet(),
		"identity-rm":  srv.handleIdentityRemove(),
		"alias-set":    srv.handleAliasSet(),
		"alias-rm":     srv.handleAliasRemove(),
	}
	for name, h := range handlers {
		t.Run(name, func(t *testing.T) {
			if rec := doMethod(http.MethodPost, h, `{bad`); rec.Code != http.StatusBadRequest {
				t.Fatalf("%s: status=%d, want 400", name, rec.Code)
			}
		})
	}
}

func TestHandleIdentityRemoveRequiresSession(t *testing.T) {
	srv := newTestServer(t)
	if rec := doMethod(http.MethodDelete, srv.handleIdentityRemove(), `{}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("status=%d, want 400", rec.Code)
	}
}

func TestHandleAliasRemoveRejectsEmptyHandle(t *testing.T) {
	srv := newTestServer(t)
	if rec := doMethod(http.MethodDelete, srv.handleAliasRemove(), `{"handle":"@"}`); rec.Code != http.StatusBadRequest {
		t.Fatalf("status=%d, want 400", rec.Code)
	}
}

func TestRemoveSaveErrors(t *testing.T) {
	srv := newTestServer(t)
	if _, err := srv.upsertIdentity("s1", "PL", "", ""); err != nil {
		t.Fatal(err)
	}
	if _, err := srv.upsertHandleAlias("mayor", "s1"); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(srv.cfg.registryDir, 0o500); err != nil {
		t.Skip("chmod unsupported on this platform")
	}
	t.Cleanup(func() { _ = os.Chmod(srv.cfg.registryDir, 0o700) })

	if rec := doMethod(http.MethodDelete, srv.handleIdentityRemove(), `{"session_id":"s1"}`); rec.Code != http.StatusInternalServerError {
		t.Errorf("identity remove save error status=%d, want 500", rec.Code)
	}
	if rec := doMethod(http.MethodDelete, srv.handleAliasRemove(), `{"handle":"mayor"}`); rec.Code != http.StatusBadRequest {
		t.Errorf("alias remove save error status=%d, want 400", rec.Code)
	}
}

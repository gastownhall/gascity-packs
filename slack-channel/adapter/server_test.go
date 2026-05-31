package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestUpsertBindingPersistsAndReloads(t *testing.T) {
	srv := newTestServer(t)
	rec, err := srv.upsertBinding("C1", "room", []string{"s2", "s1"})
	if err != nil {
		t.Fatalf("upsertBinding: %v", err)
	}
	if !reflect.DeepEqual(rec.SessionIDs, []string{"s1", "s2"}) {
		t.Errorf("session_ids = %v, want sorted", rec.SessionIDs)
	}

	// A fresh server over the same registry dir sees the persisted binding.
	reloaded, err := newServer(srv.cfg)
	if err != nil {
		t.Fatalf("reload server: %v", err)
	}
	got, ok := reloaded.bindingForChannel("C1")
	if !ok {
		t.Fatal("binding not reloaded from disk")
	}
	if got.Kind != "room" || got.WorkspaceID != "T123" {
		t.Errorf("reloaded binding = %+v", got)
	}
}

func TestUpsertBindingIdempotentCreatedAt(t *testing.T) {
	srv := newTestServer(t)
	first, _ := srv.upsertBinding("C1", "dm", []string{"s1"})
	second, _ := srv.upsertBinding("C1", "dm", []string{"s1", "s3"})
	if second.CreatedAt != first.CreatedAt {
		t.Errorf("created_at changed on rebind: %q -> %q", first.CreatedAt, second.CreatedAt)
	}
}

func TestChannelsForSession(t *testing.T) {
	srv := newTestServer(t)
	mustBind(t, srv, "C1", "room", "s1", "s2")
	mustBind(t, srv, "C2", "room", "s1")
	mustBind(t, srv, "C3", "dm", "s9")

	if got := srv.channelsForSession("s1"); !reflect.DeepEqual(got, []string{"C1", "C2"}) {
		t.Errorf("channelsForSession(s1) = %v, want [C1 C2]", got)
	}
	if got := srv.channelsForSession("s2"); !reflect.DeepEqual(got, []string{"C1"}) {
		t.Errorf("channelsForSession(s2) = %v", got)
	}
	if got := srv.channelsForSession("nobody"); got != nil {
		t.Errorf("channelsForSession(nobody) = %v, want nil", got)
	}
}

func TestIdentityLifecycle(t *testing.T) {
	srv := newTestServer(t)
	if _, ok := srv.identityFor("s1"); ok {
		t.Fatal("identity should be absent initially")
	}
	if _, err := srv.upsertIdentity("s1", "PL", "https://x/a.png", ""); err != nil {
		t.Fatalf("upsert: %v", err)
	}
	id, ok := srv.identityFor("s1")
	if !ok || id.Username != "PL" || id.IconURL != "https://x/a.png" {
		t.Errorf("identity = %+v ok=%v", id, ok)
	}
	removed, err := srv.removeIdentity("s1")
	if err != nil || !removed {
		t.Errorf("remove = %v, err=%v", removed, err)
	}
	// Idempotent: removing again reports false, no error.
	removed, err = srv.removeIdentity("s1")
	if err != nil || removed {
		t.Errorf("second remove = %v, err=%v", removed, err)
	}
}

func TestHandleAliasLifecycle(t *testing.T) {
	srv := newTestServer(t)
	if _, err := srv.upsertHandleAlias("@Mayor", "sess-1"); err != nil {
		t.Fatalf("upsert: %v", err)
	}
	rec, ok := srv.aliasFor("mayor")
	if !ok || rec.SessionID != "sess-1" {
		t.Errorf("alias = %+v ok=%v", rec, ok)
	}
	// Lookup normalizes the queried handle too.
	if _, ok := srv.aliasFor("@MAYOR"); !ok {
		t.Error("alias lookup should normalize the query")
	}
	removed, err := srv.removeHandleAlias("MAYOR")
	if err != nil || !removed {
		t.Errorf("remove = %v err=%v", removed, err)
	}
	if _, ok := srv.aliasFor("mayor"); ok {
		t.Error("alias should be gone after remove")
	}
}

func TestLastInboundTracking(t *testing.T) {
	srv := newTestServer(t)
	if _, ok := srv.latestInbound("s1"); ok {
		t.Fatal("no inbound expected initially")
	}
	srv.recordInbound("s1", inboundRef{channelID: "C1", messageTS: "1.1", threadTS: "1.0"})
	ref, ok := srv.latestInbound("s1")
	if !ok || ref.channelID != "C1" || ref.messageTS != "1.1" || ref.threadTS != "1.0" {
		t.Errorf("latestInbound = %+v ok=%v", ref, ok)
	}
}

func TestNewServerRejectsCorruptRegistry(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "channel_mappings.json"), []byte("{bad json"), 0o600); err != nil {
		t.Fatal(err)
	}
	cfg := config{
		cityName: "c", provider: "slack", workspaceID: "T1",
		slackAPIBase: "x", gcAPIBase: "y", registryDir: dir,
	}
	if _, err := newServer(cfg); err == nil {
		t.Fatal("expected newServer to fail loading a corrupt registry")
	}
}

func TestUpsertBindingSaveError(t *testing.T) {
	srv := newTestServer(t)
	if err := os.Chmod(srv.cfg.registryDir, 0o500); err != nil {
		t.Skip("chmod unsupported on this platform")
	}
	t.Cleanup(func() { _ = os.Chmod(srv.cfg.registryDir, 0o700) })
	if _, err := srv.upsertBinding("C1", "room", []string{"s1"}); err == nil {
		t.Fatal("expected a save error on a read-only registry directory")
	}
}

func mustBind(t *testing.T, srv *server, channel, kind string, sessions ...string) {
	t.Helper()
	if _, err := srv.upsertBinding(channel, kind, sessions); err != nil {
		t.Fatalf("bind %s: %v", channel, err)
	}
}

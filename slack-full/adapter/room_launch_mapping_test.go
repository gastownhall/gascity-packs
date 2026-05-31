package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestRoomLaunchRegistryReadsCmdGcWrittenFormat — the adapter MUST be
// able to load a file produced by `gc slack enable-room-launch`. We
// emulate the cmd/gc-side write by emitting the same JSON shape and
// asserting LookupPoolTemplate returns the expected pool.
func TestRoomLaunchRegistryReadsCmdGcWrittenFormat(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "room_launch_mappings.json")
	stored := map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {
			WorkspaceID:  "T1",
			ChannelID:    "C1",
			PoolTemplate: "mission-control/launcher",
		},
	}
	data, _ := json.MarshalIndent(stored, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}

	reg, err := newRoomLaunchMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRoomLaunchMappingRegistry: %v", err)
	}
	pool, ok := reg.LookupPoolTemplate("T1", "C1")
	if !ok {
		t.Fatal("LookupPoolTemplate miss after load")
	}
	if pool != "mission-control/launcher" {
		t.Errorf("pool = %q, want %q", pool, "mission-control/launcher")
	}
}

// TestRoomLaunchRegistryLookupMissReturnsFalse — a channel without a
// binding returns ok=false; the dispatcher must then emit the
// "channel-not-enabled" ephemeral.
func TestRoomLaunchRegistryLookupMissReturnsFalse(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "room_launch_mappings.json")
	reg, err := newRoomLaunchMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := reg.LookupPoolTemplate("T1", "C-not-enabled"); ok {
		t.Error("LookupPoolTemplate should miss on a channel without a binding")
	}
}

// TestRoomLaunchRegistryRejectsCorruptStore guards against silently
// serving malformed bindings.
func TestRoomLaunchRegistryRejectsCorruptStore(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "room_launch_mappings.json")
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := newRoomLaunchMappingRegistry(path); err == nil {
		t.Fatal("expected error on corrupt store")
	}
}

// TestRoomLaunchRegistryRejectsMissingFields — a hand-edited file with
// an empty pool_template is surfaced rather than served as policy.
func TestRoomLaunchRegistryRejectsMissingFields(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "room_launch_mappings.json")
	stored := map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: ""},
	}
	data, _ := json.MarshalIndent(stored, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := newRoomLaunchMappingRegistry(path); err == nil {
		t.Fatal("expected error for record missing pool_template")
	}
}

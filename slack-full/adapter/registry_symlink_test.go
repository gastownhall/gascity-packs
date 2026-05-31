package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// gc-cby.38: defense-in-depth against an attacker with same-UID write
// access to .gc/slack/ replacing a registry file with a symlink that
// redirects SIGHUP reads to an arbitrary file readable by the adapter
// UID. The four parseX functions all funnel through openRegistryFile,
// which Lstat-checks the path and rejects symlinks. The TOCTOU window
// between Lstat and Open is acknowledged in the helper comment — same
// trust-boundary trade-off documented on the bead.
//
// Each subtest writes a real registry file, points a symlink at it, and
// asserts that parseX(symlinkPath) returns an error mentioning "symlink".
// The real-file-still-works path is already covered by other tests in
// this package; we only pin the new rejection contract here.

func TestParseAppsRegistryRejectsSymlink(t *testing.T) {
	dir := t.TempDir()
	realPath := filepath.Join(dir, "apps-real.json")
	data, err := json.Marshal(map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "v1"},
	})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(realPath, data, 0o600); err != nil {
		t.Fatalf("write real: %v", err)
	}
	linkPath := filepath.Join(dir, "apps.json")
	if err := os.Symlink(realPath, linkPath); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	snap, err := parseAppsRegistry(linkPath)
	if err == nil {
		t.Fatalf("parseAppsRegistry on symlink: want error, got snap=%v", snap)
	}
	if !strings.Contains(err.Error(), "symlink") {
		t.Errorf("parseAppsRegistry error = %v, want mention of 'symlink'", err)
	}
}

func TestParseChannelMappingRegistryRejectsSymlink(t *testing.T) {
	dir := t.TempDir()
	realPath := filepath.Join(dir, "chans-real.json")
	now := time.Now().UTC()
	data, err := json.Marshal(map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "s1", CreatedAt: now, UpdatedAt: now},
	})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(realPath, data, 0o600); err != nil {
		t.Fatalf("write real: %v", err)
	}
	linkPath := filepath.Join(dir, "channel_mappings.json")
	if err := os.Symlink(realPath, linkPath); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	snap, err := parseChannelMappingRegistry(linkPath)
	if err == nil {
		t.Fatalf("parseChannelMappingRegistry on symlink: want error, got snap=%v", snap)
	}
	if !strings.Contains(err.Error(), "symlink") {
		t.Errorf("parseChannelMappingRegistry error = %v, want mention of 'symlink'", err)
	}
}

func TestParseRigMappingRegistryRejectsSymlink(t *testing.T) {
	dir := t.TempDir()
	realPath := filepath.Join(dir, "rigs-real.json")
	now := time.Now().UTC()
	data, err := json.Marshal(map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C1"}, SlingTarget: "rig-a/role", CreatedAt: now, UpdatedAt: now},
	})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(realPath, data, 0o600); err != nil {
		t.Fatalf("write real: %v", err)
	}
	linkPath := filepath.Join(dir, "rig_mappings.json")
	if err := os.Symlink(realPath, linkPath); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	snap, err := parseRigMappingRegistry(linkPath)
	if err == nil {
		t.Fatalf("parseRigMappingRegistry on symlink: want error, got snap=%v", snap)
	}
	if !strings.Contains(err.Error(), "symlink") {
		t.Errorf("parseRigMappingRegistry error = %v, want mention of 'symlink'", err)
	}
}

func TestParseRoomLaunchMappingRegistryRejectsSymlink(t *testing.T) {
	dir := t.TempDir()
	realPath := filepath.Join(dir, "rooms-real.json")
	now := time.Now().UTC()
	data, err := json.Marshal(map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: "v0", CreatedAt: now, UpdatedAt: now},
	})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(realPath, data, 0o600); err != nil {
		t.Fatalf("write real: %v", err)
	}
	linkPath := filepath.Join(dir, "room_launch_mappings.json")
	if err := os.Symlink(realPath, linkPath); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	snap, err := parseRoomLaunchMappingRegistry(linkPath)
	if err == nil {
		t.Fatalf("parseRoomLaunchMappingRegistry on symlink: want error, got snap=%v", snap)
	}
	if !strings.Contains(err.Error(), "symlink") {
		t.Errorf("parseRoomLaunchMappingRegistry error = %v, want mention of 'symlink'", err)
	}
}

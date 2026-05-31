package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

// gc-cby.23: the four read-only adapter registries — channelMappingRegistry,
// rigMappingRegistry, roomLaunchMappingRegistry, and appsRegistry — all gain
// Stage / Commit / Reload so SIGHUP can pick up CLI-driven file rewrites
// without restarting the adapter binary. Tests in this file pin the SIGHUP
// reload contract (the apps registry has its own reload tests inline in
// apps_registry_test.go alongside the rest of its suite).

// --- channelMappingRegistry --------------------------------------------------

func writeChannelMappingFile(t *testing.T, path string, recs map[string]channelMappingDiskRecord) {
	t.Helper()
	data, err := json.MarshalIndent(recs, "", "  ")
	if err != nil {
		t.Fatalf("marshal channel mapping seed: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write channel mapping seed: %v", err)
	}
}

func TestChannelMappingReloadPicksUpNewRecords(t *testing.T) {
	path := filepath.Join(t.TempDir(), "channel_mappings.json")
	writeChannelMappingFile(t, path, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "old-session"},
	})
	reg, err := newChannelMappingRegistry(path)
	if err != nil {
		t.Fatalf("newChannelMappingRegistry: %v", err)
	}

	writeChannelMappingFile(t, path, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "rotated-session"},
		"T1:C2": {WorkspaceID: "T1", ChannelID: "C2", TargetKind: channelMappingTargetKindRig, TargetID: "rig-x"},
	})
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}
	if got := reg.Len(); got != 2 {
		t.Errorf("post-Reload Len = %d, want 2", got)
	}
	rec, ok := reg.Get("T1", "C1")
	if !ok || rec.TargetID != "rotated-session" {
		t.Errorf("C1 after Reload = %+v ok=%v, want TargetID=rotated-session", rec, ok)
	}
	rec, ok = reg.Get("T1", "C2")
	if !ok || rec.TargetID != "rig-x" {
		t.Errorf("C2 after Reload = %+v ok=%v, want new rig-x record", rec, ok)
	}
}

func TestChannelMappingReloadOnMissingFileIsNoop(t *testing.T) {
	path := filepath.Join(t.TempDir(), "channel_mappings.json")
	writeChannelMappingFile(t, path, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "preserved"},
	})
	reg, err := newChannelMappingRegistry(path)
	if err != nil {
		t.Fatalf("newChannelMappingRegistry: %v", err)
	}
	if err := os.Remove(path); err != nil {
		t.Fatalf("rm: %v", err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload on missing file should be a no-op, got: %v", err)
	}
	rec, ok := reg.Get("T1", "C1")
	if !ok || rec.TargetID != "preserved" {
		t.Errorf("post-Reload state = %+v ok=%v, want preserved record", rec, ok)
	}
}

func TestChannelMappingReloadOnCorruptFilePreservesState(t *testing.T) {
	path := filepath.Join(t.TempDir(), "channel_mappings.json")
	writeChannelMappingFile(t, path, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "preserved"},
	})
	reg, err := newChannelMappingRegistry(path)
	if err != nil {
		t.Fatalf("newChannelMappingRegistry: %v", err)
	}
	// Bogus target_kind → parse rejects.
	writeChannelMappingFile(t, path, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: "bogus", TargetID: "x"},
	})
	if err := reg.Reload(); err == nil {
		t.Fatal("Reload on corrupt target_kind: want error")
	}
	rec, ok := reg.Get("T1", "C1")
	if !ok || rec.TargetID != "preserved" {
		t.Errorf("post-failed-Reload state = %+v ok=%v, want preserved record (failed Reload must not mutate)", rec, ok)
	}
}

// --- rigMappingRegistry ------------------------------------------------------

func writeRigMappingFile(t *testing.T, path string, recs map[string]rigMappingDiskRecord) {
	t.Helper()
	data, err := json.MarshalIndent(recs, "", "  ")
	if err != nil {
		t.Fatalf("marshal rig mapping seed: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write rig mapping seed: %v", err)
	}
}

func TestRigMappingReloadRebuildsByChannelIndex(t *testing.T) {
	// Pinning C1 of gc-cby.23 architect review (C1): byKey and byChannel
	// must never desync. Reload that re-binds a channel from rig-a to
	// rig-b must update both indexes atomically.
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	writeRigMappingFile(t, path, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C1"}, SlingTarget: "rig-a/role", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRigMappingRegistry: %v", err)
	}
	rec, _, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok || rec.RigName != "rig-a" {
		t.Fatalf("initial channel lookup = %+v ok=%v, want rig-a", rec, ok)
	}

	// Re-bind C1 to rig-b (and rig-a now owns C2 instead).
	writeRigMappingFile(t, path, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C2"}, SlingTarget: "rig-a/role", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
		"T1:rig-b": {WorkspaceID: "T1", RigName: "rig-b", ChannelIDs: []string{"C1"}, SlingTarget: "rig-b/role", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}

	rec, _, ok = reg.LookupRigForChannel("T1", "C1")
	if !ok || rec.RigName != "rig-b" {
		t.Errorf("post-Reload C1 = %+v ok=%v, want rig-b (byChannel must reflect re-binding)", rec, ok)
	}
	rec, _, ok = reg.LookupRigForChannel("T1", "C2")
	if !ok || rec.RigName != "rig-a" {
		t.Errorf("post-Reload C2 = %+v ok=%v, want rig-a", rec, ok)
	}
}

func TestRigMappingReloadOnCorruptFilePreservesBothIndexes(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	writeRigMappingFile(t, path, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C1"}, SlingTarget: "rig-a/role", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRigMappingRegistry: %v", err)
	}
	// Empty channel_ids → parse rejects.
	writeRigMappingFile(t, path, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: nil, SlingTarget: "rig-a/role", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	if err := reg.Reload(); err == nil {
		t.Fatal("Reload on empty channel_ids: want error")
	}
	if got := reg.Len(); got != 1 {
		t.Errorf("post-failed-Reload byKey Len = %d, want 1 (preserved)", got)
	}
	if _, _, ok := reg.LookupRigForChannel("T1", "C1"); !ok {
		t.Error("post-failed-Reload byChannel lost C1 → both indexes desynced")
	}
}

func TestRigMappingReloadOnMissingFileIsNoop(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	writeRigMappingFile(t, path, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C1"}, SlingTarget: "rig-a/role", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRigMappingRegistry: %v", err)
	}
	if err := os.Remove(path); err != nil {
		t.Fatalf("rm: %v", err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload on missing file should be a no-op: %v", err)
	}
	if got := reg.Len(); got != 1 {
		t.Errorf("post-Reload Len = %d, want 1", got)
	}
}

// --- roomLaunchMappingRegistry ----------------------------------------------

func writeRoomLaunchMappingFile(t *testing.T, path string, recs map[string]roomLaunchMappingDiskRecord) {
	t.Helper()
	data, err := json.MarshalIndent(recs, "", "  ")
	if err != nil {
		t.Fatalf("marshal room launch mapping seed: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write room launch mapping seed: %v", err)
	}
}

func TestRoomLaunchMappingReloadPicksUpNewBindings(t *testing.T) {
	path := filepath.Join(t.TempDir(), "room_launch_mappings.json")
	writeRoomLaunchMappingFile(t, path, map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: "old-pool", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	reg, err := newRoomLaunchMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRoomLaunchMappingRegistry: %v", err)
	}

	writeRoomLaunchMappingFile(t, path, map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: "rotated-pool", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
		"T1:C2": {WorkspaceID: "T1", ChannelID: "C2", PoolTemplate: "new-pool", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}
	pool, ok := reg.LookupPoolTemplate("T1", "C1")
	if !ok || pool != "rotated-pool" {
		t.Errorf("C1 after Reload = %q ok=%v, want rotated-pool", pool, ok)
	}
	pool, ok = reg.LookupPoolTemplate("T1", "C2")
	if !ok || pool != "new-pool" {
		t.Errorf("C2 after Reload = %q ok=%v, want new-pool", pool, ok)
	}
}

func TestRoomLaunchMappingReloadOnCorruptFilePreservesState(t *testing.T) {
	path := filepath.Join(t.TempDir(), "room_launch_mappings.json")
	writeRoomLaunchMappingFile(t, path, map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: "preserved", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	reg, err := newRoomLaunchMappingRegistry(path)
	if err != nil {
		t.Fatalf("newRoomLaunchMappingRegistry: %v", err)
	}
	// Missing pool_template → parse rejects.
	writeRoomLaunchMappingFile(t, path, map[string]roomLaunchMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: "", CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC()},
	})
	if err := reg.Reload(); err == nil {
		t.Fatal("Reload on missing pool_template: want error")
	}
	pool, ok := reg.LookupPoolTemplate("T1", "C1")
	if !ok || pool != "preserved" {
		t.Errorf("post-failed-Reload state = %q ok=%v, want preserved", pool, ok)
	}
}

// --- reloadAllRegistries (orchestrator) -------------------------------------

// fourRegistries is the test fixture for reloadAllRegistries. All four
// registries share a tempdir so a single seedAll call lays down a
// consistent baseline.
type fourRegistries struct {
	dir       string
	apps      *appsRegistry
	chans     *channelMappingRegistry
	rigs      *rigMappingRegistry
	rooms     *roomLaunchMappingRegistry
	appsPath  string
	chansPath string
	rigsPath  string
	roomsPath string
	now       time.Time
}

func newFourRegistries(t *testing.T) *fourRegistries {
	t.Helper()
	dir := t.TempDir()
	now := time.Now().UTC()
	f := &fourRegistries{
		dir:       dir,
		appsPath:  filepath.Join(dir, "apps.json"),
		chansPath: filepath.Join(dir, "channel_mappings.json"),
		rigsPath:  filepath.Join(dir, "rig_mappings.json"),
		roomsPath: filepath.Join(dir, "room_launch_mappings.json"),
		now:       now,
	}
	writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "v0"},
	})
	writeChannelMappingFile(t, f.chansPath, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "v0", CreatedAt: now, UpdatedAt: now},
	})
	writeRigMappingFile(t, f.rigsPath, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C2"}, SlingTarget: "rig-a/role", CreatedAt: now, UpdatedAt: now},
	})
	writeRoomLaunchMappingFile(t, f.roomsPath, map[string]roomLaunchMappingDiskRecord{
		"T1:C3": {WorkspaceID: "T1", ChannelID: "C3", PoolTemplate: "v0", CreatedAt: now, UpdatedAt: now},
	})

	var err error
	if f.apps, err = newAppsRegistry(f.appsPath); err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	if f.chans, err = newChannelMappingRegistry(f.chansPath); err != nil {
		t.Fatalf("newChannelMappingRegistry: %v", err)
	}
	if f.rigs, err = newRigMappingRegistry(f.rigsPath); err != nil {
		t.Fatalf("newRigMappingRegistry: %v", err)
	}
	if f.rooms, err = newRoomLaunchMappingRegistry(f.roomsPath); err != nil {
		t.Fatalf("newRoomLaunchMappingRegistry: %v", err)
	}
	return f
}

func TestReloadAllRegistriesCommitsAllOnSuccess(t *testing.T) {
	f := newFourRegistries(t)

	// Rewrite each file with new content.
	writeAppsRegistryFile(t, f.dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "v1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "v1"},
	})
	writeChannelMappingFile(t, f.chansPath, map[string]channelMappingDiskRecord{
		"T1:C1": {WorkspaceID: "T1", ChannelID: "C1", TargetKind: channelMappingTargetKindSession, TargetID: "v1", CreatedAt: f.now, UpdatedAt: f.now},
	})
	writeRigMappingFile(t, f.rigsPath, map[string]rigMappingDiskRecord{
		"T1:rig-a": {WorkspaceID: "T1", RigName: "rig-a", ChannelIDs: []string{"C2", "C9"}, SlingTarget: "rig-a/role", CreatedAt: f.now, UpdatedAt: f.now},
	})
	writeRoomLaunchMappingFile(t, f.roomsPath, map[string]roomLaunchMappingDiskRecord{
		"T1:C3": {WorkspaceID: "T1", ChannelID: "C3", PoolTemplate: "v1", CreatedAt: f.now, UpdatedAt: f.now},
	})

	if err := reloadAllRegistries(f.apps, f.chans, f.rigs, f.rooms, nil); err != nil {
		t.Fatalf("reloadAllRegistries: %v", err)
	}

	if got := f.apps.Len(); got != 2 {
		t.Errorf("apps Len = %d, want 2", got)
	}
	rec, ok := f.chans.Get("T1", "C1")
	if !ok || rec.TargetID != "v1" {
		t.Errorf("channel C1 = %+v, want v1 TargetID", rec)
	}
	if _, _, ok := f.rigs.LookupRigForChannel("T1", "C9"); !ok {
		t.Error("rig byChannel did not pick up new C9 binding")
	}
	pool, ok := f.rooms.LookupPoolTemplate("T1", "C3")
	if !ok || pool != "v1" {
		t.Errorf("room C3 pool = %q, want v1", pool)
	}
}

func TestReloadAllRegistriesAbortsOnAnyParseFailure(t *testing.T) {
	// Pinning H2 of gc-cby.23 architect review: all-or-nothing reload.
	// If any single registry fails to parse, NO registry is committed —
	// otherwise the adapter serves inconsistent policy (e.g. new app
	// secrets routing through stale channel mappings).
	f := newFourRegistries(t)

	// Rewrite apps.json (good) AND channel_mappings.json (corrupt).
	writeAppsRegistryFile(t, f.dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "v1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "v1"},
	})
	// Write corrupt channel mappings file directly (bypass writer
	// validation): bogus target_kind.
	if err := os.WriteFile(f.chansPath,
		[]byte(`{"T1:C1":{"workspace_id":"T1","channel_id":"C1","target_kind":"bogus","target_id":"x","created_at":"2025-01-01T00:00:00Z","updated_at":"2025-01-01T00:00:00Z"}}`),
		0o600); err != nil {
		t.Fatalf("write corrupt: %v", err)
	}

	err := reloadAllRegistries(f.apps, f.chans, f.rigs, f.rooms, nil)
	if err == nil {
		t.Fatal("reloadAllRegistries with one corrupt file: want error")
	}
	// Apps must NOT have been committed despite parsing successfully.
	if got := f.apps.Len(); got != 1 {
		t.Errorf("apps Len = %d after aborted reload, want 1 (no commit on partial failure)", got)
	}
	// Channel mapping must remain at the original record.
	rec, ok := f.chans.Get("T1", "C1")
	if !ok || rec.TargetID != "v0" {
		t.Errorf("channel C1 after aborted reload = %+v, want preserved v0", rec)
	}
}

func TestReloadAllRegistriesAggregatesAllErrors(t *testing.T) {
	// Multiple parse failures must all be reported, not just the first
	// one — operators need the full picture in a single SIGHUP cycle.
	f := newFourRegistries(t)

	if err := os.WriteFile(f.chansPath, []byte("not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(f.rigsPath, []byte("not json either"), 0o600); err != nil {
		t.Fatal(err)
	}

	err := reloadAllRegistries(f.apps, f.chans, f.rigs, f.rooms, nil)
	if err == nil {
		t.Fatal("want error")
	}
	msg := err.Error()
	if !strings.Contains(msg, "channel mapping") || !strings.Contains(msg, "rig mapping") {
		t.Errorf("aggregated error %q should mention both channel mapping and rig mapping failures", msg)
	}
}

func TestReloadAllRegistriesAllMissingFilesIsNoop(t *testing.T) {
	f := newFourRegistries(t)
	// Remove every file; SIGHUP semantics say "preserve live state".
	for _, p := range []string{f.appsPath, f.chansPath, f.rigsPath, f.roomsPath} {
		if err := os.Remove(p); err != nil {
			t.Fatalf("rm %s: %v", p, err)
		}
	}
	if err := reloadAllRegistries(f.apps, f.chans, f.rigs, f.rooms, nil); err != nil {
		t.Fatalf("reloadAllRegistries should be a no-op when all files missing: %v", err)
	}
	// All four must keep their seeded state.
	if got := f.apps.Len(); got != 1 {
		t.Errorf("apps Len = %d, want 1 (preserved)", got)
	}
	if got := f.chans.Len(); got != 1 {
		t.Errorf("chans Len = %d, want 1 (preserved)", got)
	}
	if got := f.rigs.Len(); got != 1 {
		t.Errorf("rigs Len = %d, want 1 (preserved)", got)
	}
	if got := f.rooms.Len(); got != 1 {
		t.Errorf("rooms Len = %d, want 1 (preserved)", got)
	}
}

// --- runReloadLoop (signal goroutine wiring) ---------------------------------

func TestRunReloadLoopFiresReloadOnEachSignal(t *testing.T) {
	sigCh := make(chan os.Signal, 1)
	stop := make(chan struct{})
	done := make(chan struct{})

	// Each reload call decrements the WaitGroup; wg.Wait below blocks
	// until exactly N calls fire, so the test is timing-independent.
	var wg sync.WaitGroup
	const want = 3
	wg.Add(want)
	go func() {
		runReloadLoop(stop, sigCh, func() { wg.Done() })
		close(done)
	}()

	for i := 0; i < want; i++ {
		sigCh <- testSignal{}
	}
	waitOrFail(t, wg.Wait, 2*time.Second, "reload loop did not invoke reload N times")

	close(stop)
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("runReloadLoop did not return after stop closed")
	}
}

// waitOrFail invokes wait in a goroutine and fails the test if it does
// not return within deadline. Lets sync.WaitGroup-based tests stay
// deterministic without the test itself blocking forever on regression.
func waitOrFail(t *testing.T, wait func(), deadline time.Duration, msg string) {
	t.Helper()
	doneCh := make(chan struct{})
	go func() {
		wait()
		close(doneCh)
	}()
	select {
	case <-doneCh:
	case <-time.After(deadline):
		t.Fatal(msg)
	}
}

func TestRunReloadLoopExitsWhenStopClosed(t *testing.T) {
	sigCh := make(chan os.Signal)
	stop := make(chan struct{})
	done := make(chan struct{})
	go func() {
		runReloadLoop(stop, sigCh, func() { t.Error("reload should not fire when no signal") })
		close(done)
	}()
	close(stop)
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("runReloadLoop did not return after stop closed")
	}
}

// testSignal is a minimal os.Signal so the loop test doesn't need to
// pull in real syscall.SIGHUP delivery (which is global and racy under
// `go test -race`).
type testSignal struct{}

func (testSignal) String() string { return "test-signal" }
func (testSignal) Signal()        {}

// Sanity: parseAppsRegistry on a missing file returns the SIGHUP "no
// change" sentinel pair (nil, nil). Same contract for the other three.
func TestParseFunctionsReturnNilSentinelOnMissingFile(t *testing.T) {
	dir := t.TempDir()
	missing := filepath.Join(dir, "does-not-exist.json")
	if snap, err := parseAppsRegistry(missing); snap != nil || err != nil {
		t.Errorf("parseAppsRegistry missing = (%v, %v), want (nil, nil)", snap, err)
	}
	if snap, err := parseChannelMappingRegistry(missing); snap != nil || err != nil {
		t.Errorf("parseChannelMappingRegistry missing = (%v, %v), want (nil, nil)", snap, err)
	}
	if snap, err := parseRigMappingRegistry(missing); snap != nil || err != nil {
		t.Errorf("parseRigMappingRegistry missing = (%v, %v), want (nil, nil)", snap, err)
	}
	if snap, err := parseRoomLaunchMappingRegistry(missing); snap != nil || err != nil {
		t.Errorf("parseRoomLaunchMappingRegistry missing = (%v, %v), want (nil, nil)", snap, err)
	}
}

// --- scrubAppsRegistryError --------------------------------------------------
//
// gc-cby.37: defensive scrub before logReloadOutcome writes to journald. The
// apps registry error wraps json.Decoder offsets and file paths today — Go's
// stdlib does not embed payload values in type-mismatch messages, but a
// future stdlib change or a json-decoder swap could change that. Replace any
// apps-registry-prefixed error component with a fixed sentinel; keep other
// registries' errors verbatim so operators retain actionable context.

func TestScrubAppsRegistryErrorReplacesAppsOnlyError(t *testing.T) {
	err := fmt.Errorf("apps registry: decode apps registry: invalid character 'x' looking for value")
	got := scrubAppsRegistryError(err)
	if strings.Contains(got, "invalid character") || strings.Contains(got, "decode apps registry") {
		t.Errorf("scrubbed output %q must not contain raw apps-registry parse detail", got)
	}
	if !strings.Contains(got, "apps registry: reload failed") {
		t.Errorf("scrubbed output %q must contain sentinel", got)
	}
}

func TestScrubAppsRegistryErrorPreservesNonAppsErrorVerbatim(t *testing.T) {
	err := fmt.Errorf("rig mapping: parse rig_mappings.json: unexpected EOF")
	got := scrubAppsRegistryError(err)
	if got != err.Error() {
		t.Errorf("non-apps error must be verbatim: got %q, want %q", got, err.Error())
	}
}

func TestScrubAppsRegistryErrorScrubsOnlyAppsPortionOfJoinedChain(t *testing.T) {
	apps := fmt.Errorf("apps registry: decode apps registry: secret-bearing detail %s", "v=hunter2")
	chans := fmt.Errorf("channel mapping: parse channel_mappings.json: unexpected EOF")
	rigs := fmt.Errorf("rig mapping: empty channel_ids for rig-a")
	joined := errors.Join(apps, chans, rigs)

	got := scrubAppsRegistryError(joined)

	if strings.Contains(got, "hunter2") || strings.Contains(got, "secret-bearing") {
		t.Errorf("scrubbed joined output %q must not leak apps-registry detail", got)
	}
	if !strings.Contains(got, "apps registry: reload failed") {
		t.Errorf("scrubbed joined output %q must contain sentinel", got)
	}
	if !strings.Contains(got, "channel mapping: parse channel_mappings.json: unexpected EOF") {
		t.Errorf("scrubbed joined output %q must preserve channel mapping error verbatim", got)
	}
	if !strings.Contains(got, "rig mapping: empty channel_ids for rig-a") {
		t.Errorf("scrubbed joined output %q must preserve rig mapping error verbatim", got)
	}
}

func TestScrubAppsRegistryErrorHandlesAppsErrorWithEmbeddedNewlines(t *testing.T) {
	// Defensive: even if a future apps-registry error contains a newline
	// (e.g. a multi-line JSON decode message), the structural unwrap of
	// errors.Join components must still scrub the entire apps component.
	apps := fmt.Errorf("apps registry: decode failed at offset 42:\nleaked-line: hunter2")
	chans := fmt.Errorf("channel mapping: parse channel_mappings.json: unexpected EOF")
	joined := errors.Join(apps, chans)

	got := scrubAppsRegistryError(joined)
	if strings.Contains(got, "hunter2") || strings.Contains(got, "leaked-line") {
		t.Errorf("scrubbed output %q must not leak content from multi-line apps error", got)
	}
	if !strings.Contains(got, "channel mapping: parse channel_mappings.json: unexpected EOF") {
		t.Errorf("scrubbed output %q must preserve channel mapping error verbatim", got)
	}
}

func TestScrubAppsRegistryErrorOnNilReturnsEmpty(t *testing.T) {
	if got := scrubAppsRegistryError(nil); got != "" {
		t.Errorf("scrubAppsRegistryError(nil) = %q, want empty string", got)
	}
}

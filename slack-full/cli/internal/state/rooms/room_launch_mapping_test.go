package rooms

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// newTestCity creates a minimal city directory (with city.toml marker)
// rooted at t.TempDir() and returns its absolute path. Mirrors the
// minimum shape the rest of cmd/gc city tests rely on.
func newTestCity(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	cityRoot := filepath.Join(dir, "testcity")
	if err := os.MkdirAll(cityRoot, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(cityRoot, "city.toml"),
		[]byte("[workspace]\nname = \"test\"\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	return cityRoot
}

// TestPathIsCityRooted pins the on-disk path convention. The
// slack-pack adapter resolves the same path from GC_CITY_PATH at
// startup; both sides MUST agree.
func TestPathIsCityRooted(t *testing.T) {
	cityRoot := newTestCity(t)
	got := Path(cityRoot)
	want := filepath.Join(cityRoot, ".gc", "slack", "room_launch_mappings.json")
	if got != want {
		t.Errorf("Path(%q) = %q, want %q", cityRoot, got, want)
	}
}

// TestRegistryEmptyOnMissing — tolerant load on a missing
// file yields an empty registry, matching every other slack-side
// registry (apps, channel, rig).
func TestRegistryEmptyOnMissing(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatalf("NewRegistry: %v", err)
	}
	if got := len(reg.AllSorted()); got != 0 {
		t.Errorf("empty registry has %d records, want 0", got)
	}
}

// TestRegistrySetGetRoundtrip pins set/get via composite key.
func TestRegistrySetGetRoundtrip(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatalf("NewRegistry: %v", err)
	}
	rec := Record{
		WorkspaceID:  "T1",
		ChannelID:    "C1",
		PoolTemplate: "mission-control/launcher",
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}
	got, ok := reg.Get("T1", "C1")
	if !ok {
		t.Fatal("Get after Set returned ok=false")
	}
	if got.PoolTemplate != "mission-control/launcher" {
		t.Errorf("PoolTemplate = %q, want %q", got.PoolTemplate, "mission-control/launcher")
	}
	if got.CreatedAt.IsZero() || got.UpdatedAt.IsZero() {
		t.Error("CreatedAt/UpdatedAt must be populated by Set")
	}
}

// TestRegistrySetPersistsCreatedAtAcrossReBind asserts the
// idempotent re-bind contract: re-binding the same channel preserves
// CreatedAt and advances UpdatedAt.
func TestRegistrySetPersistsCreatedAtAcrossReBind(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	first := Record{
		WorkspaceID:  "T1",
		ChannelID:    "C1",
		PoolTemplate: "rigA/launcher",
	}
	if err := reg.Set(first); err != nil {
		t.Fatalf("first Set: %v", err)
	}
	got1, _ := reg.Get("T1", "C1")
	createdAt := got1.CreatedAt

	// Reload from disk to mirror the CLI's per-invocation lifecycle:
	// each `gc slack enable-room-launch` opens a fresh registry from
	// disk, so the in-memory CreatedAt is irrelevant — only the on-disk
	// value matters.
	reg2, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	second := Record{
		WorkspaceID:  "T1",
		ChannelID:    "C1",
		PoolTemplate: "rigB/launcher",
	}
	if err := reg2.Set(second); err != nil {
		t.Fatalf("second Set: %v", err)
	}
	got2, ok := reg2.Get("T1", "C1")
	if !ok {
		t.Fatal("missing after re-Set")
	}
	if !got2.CreatedAt.Equal(createdAt) {
		t.Errorf("CreatedAt drifted on re-bind: was %v, now %v", createdAt, got2.CreatedAt)
	}
	if !got2.UpdatedAt.After(got2.CreatedAt) && !got2.UpdatedAt.Equal(got2.CreatedAt) {
		t.Errorf("UpdatedAt should be >= CreatedAt: created=%v updated=%v", got2.CreatedAt, got2.UpdatedAt)
	}
	if got2.PoolTemplate != "rigB/launcher" {
		t.Errorf("PoolTemplate not replaced: got %q", got2.PoolTemplate)
	}
}

// TestRegistrySetRejectsEmpty pins validation: every required
// field must be non-empty so the registry never holds a useless record.
func TestRegistrySetRejectsEmpty(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	cases := []Record{
		{WorkspaceID: "", ChannelID: "C1", PoolTemplate: "p/q"},
		{WorkspaceID: "T1", ChannelID: "", PoolTemplate: "p/q"},
		{WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: ""},
	}
	for i, rec := range cases {
		if err := reg.Set(rec); err == nil {
			t.Errorf("case %d: Set with empty field should fail; got nil", i)
		}
	}
}

// TestRegistryRemove pins idempotent removal.
func TestRegistryRemove(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, _ := NewRegistry(Path(cityRoot))
	_ = reg.Set(Record{WorkspaceID: "T1", ChannelID: "C1", PoolTemplate: "p/q"})

	existed, err := reg.Remove("T1", "C1")
	if err != nil {
		t.Fatalf("Remove: %v", err)
	}
	if !existed {
		t.Error("Remove of present record should report existed=true")
	}
	// Idempotent.
	existed2, err := reg.Remove("T1", "C1")
	if err != nil {
		t.Fatalf("Remove (second): %v", err)
	}
	if existed2 {
		t.Error("Remove of absent record should report existed=false")
	}
}

// TestRegistryTolerantLoadMissing — opening at a path that
// does not exist yields an empty registry, not an error. Matches every
// other slack registry's tolerant-load contract.
func TestRegistryTolerantLoadMissing(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "nope", "missing.json")
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("tolerant load on missing: %v", err)
	}
	if reg == nil {
		t.Fatal("nil registry")
	}
}

// TestRegistryRejectsCorruptStore — a malformed JSON file is
// surfaced rather than silently overwritten. Callers can choose to
// rename/repair; we don't drop bad data on the floor.
func TestRegistryRejectsCorruptStore(t *testing.T) {
	tmp := t.TempDir()
	path := filepath.Join(tmp, "room_launch.json")
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := NewRegistry(path)
	if err == nil {
		t.Fatal("expected error on corrupt store")
	}
	if !strings.Contains(err.Error(), "decode") && !strings.Contains(err.Error(), "JSON") &&
		!strings.Contains(err.Error(), "json") {
		t.Errorf("error message should reference decode/json: %v", err)
	}
}

package channels

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"
)

// newTestCity creates a minimal city directory (with city.toml marker)
// rooted at t.TempDir() and returns its absolute path.
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

func TestPathIsCityRooted(t *testing.T) {
	cityRoot := newTestCity(t)
	got := Path(cityRoot)
	want := filepath.Join(cityRoot, ".gc", "slack", "channel_mappings.json")
	if got != want {
		t.Errorf("Path(%q) = %q, want %q", cityRoot, got, want)
	}
}

func TestRegistryTolerantLoadOnMissingFile(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatalf("NewRegistry on missing file: %v", err)
	}
	if got := len(reg.All()); got != 0 {
		t.Errorf("fresh registry: All() len = %d, want 0", got)
	}
	if _, ok := reg.Get("T1", "C1"); ok {
		t.Errorf("fresh registry Get returned ok=true, want false")
	}
}

func TestRegistrySetAndGet(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	rec := Record{
		WorkspaceID: "T123", ChannelID: "C456",
		TargetKind: "session", TargetID: "gc-2568",
		CreatedAt: now, UpdatedAt: now,
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}
	got, ok := reg.Get("T123", "C456")
	if !ok {
		t.Fatalf("Get not ok after Set")
	}
	if got.TargetKind != "session" || got.TargetID != "gc-2568" {
		t.Errorf("got = %+v, want target_kind=session target_id=gc-2568", got)
	}
}

func TestRegistryRequiredFields(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	cases := []Record{
		{WorkspaceID: "", ChannelID: "C1", TargetKind: "rig", TargetID: "x", CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", ChannelID: "", TargetKind: "rig", TargetID: "x", CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", ChannelID: "C1", TargetKind: "", TargetID: "x", CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", ChannelID: "C1", TargetKind: "rig", TargetID: "", CreatedAt: now, UpdatedAt: now},
	}
	for _, rec := range cases {
		if err := reg.Set(rec); err == nil {
			t.Errorf("Set(%+v): expected error, got nil", rec)
		}
	}
}

func TestRegistryRejectsUnknownTargetKind(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	err = reg.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1", TargetKind: "bogus", TargetID: "x",
		CreatedAt: now, UpdatedAt: now,
	})
	if err == nil {
		t.Fatal("expected error for unknown target_kind, got nil")
	}
	if !strings.Contains(err.Error(), "target_kind") {
		t.Errorf("error should mention target_kind: %v", err)
	}
}

func TestRegistryRejectsCorruptFile(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	corrupt := map[string]Record{
		"T1:C1": {
			WorkspaceID: "T1", ChannelID: "C1",
			TargetKind: "bogus", TargetID: "x",
			CreatedAt: time.Now().UTC(), UpdatedAt: time.Now().UTC(),
		},
	}
	data, _ := json.MarshalIndent(corrupt, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := NewRegistry(path)
	if err == nil {
		t.Fatal("expected error loading corrupt file, got nil")
	}
	if !strings.Contains(err.Error(), "bogus") {
		t.Errorf("error should mention the bad target_kind value: %v", err)
	}
}

// TestRegistryRejectsUnknownField pins the
// DisallowUnknownFields decoder behavior: a hand-edited file that
// adds an unknown JSON field must be rejected at load time, mirroring
// the rig-mapping store's policy. Symmetric strictness across both
// stores is what closes sec-S-02.
func TestRegistryRejectsUnknownField(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(`{"T1:C1":{"workspace_id":"T1","channel_id":"C1","target_kind":"session","target_id":"gc-1","created_at":"2025-01-01T00:00:00Z","updated_at":"2025-01-01T00:00:00Z","bogus":42}}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewRegistry(path); err == nil {
		t.Fatal("expected error for unknown field, got nil")
	}
}

func TestRegistryIdempotentOverwrite(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	t0 := time.Now().UTC().Add(-time.Hour)
	t1 := time.Now().UTC()

	if err := reg.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "rig", TargetID: "alpha",
		CreatedAt: t0, UpdatedAt: t0,
	}); err != nil {
		t.Fatal(err)
	}
	// Re-set with different target + advanced UpdatedAt; CreatedAt should NOT advance.
	if err := reg.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "rig", TargetID: "beta",
		CreatedAt: t1, // caller passes t1 but registry must preserve t0
		UpdatedAt: t1,
	}); err != nil {
		t.Fatal(err)
	}
	if got := len(reg.All()); got != 1 {
		t.Errorf("idempotent re-set: All() len = %d, want 1", got)
	}
	got, _ := reg.Get("T1", "C1")
	if got.TargetID != "beta" {
		t.Errorf("re-set TargetID = %q, want beta", got.TargetID)
	}
	if !got.CreatedAt.Equal(t0) {
		t.Errorf("re-set CreatedAt = %v, want preserved t0=%v", got.CreatedAt, t0)
	}
	if !got.UpdatedAt.Equal(t1) {
		t.Errorf("re-set UpdatedAt = %v, want t1=%v", got.UpdatedAt, t1)
	}
}

func TestRegistryRemove(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "session", TargetID: "gc-1",
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}

	existed, err := reg.Remove("T1", "C1")
	if err != nil {
		t.Fatalf("Remove: %v", err)
	}
	if !existed {
		t.Errorf("first Remove existed=false, want true")
	}
	// Idempotent: second remove succeeds with existed=false.
	existed, err = reg.Remove("T1", "C1")
	if err != nil {
		t.Fatalf("second Remove: %v", err)
	}
	if existed {
		t.Errorf("second Remove existed=true, want false")
	}

	// Reload from disk to confirm removal persisted.
	reg2, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := reg2.Get("T1", "C1"); ok {
		t.Errorf("after reload Get ok=true, want false (deletion not persisted)")
	}
}

func TestRegistryAllIsSortedByKey(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	keys := []struct {
		ws, ch string
	}{
		{"T2", "C9"}, {"T1", "C1"}, {"T1", "C2"}, {"T2", "C0"},
	}
	for _, k := range keys {
		if err := reg.Set(Record{
			WorkspaceID: k.ws, ChannelID: k.ch,
			TargetKind: "rig", TargetID: "r",
			CreatedAt: now, UpdatedAt: now,
		}); err != nil {
			t.Fatal(err)
		}
	}
	got := reg.All()
	gotKeys := make([]string, len(got))
	for i, r := range got {
		gotKeys[i] = r.WorkspaceID + ":" + r.ChannelID
	}
	want := append([]string(nil), gotKeys...)
	sort.Strings(want)
	for i := range want {
		if gotKeys[i] != want[i] {
			t.Errorf("All() not sorted: got=%v want=%v", gotKeys, want)
			break
		}
	}
}

func TestRegistryFilePermissions(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "rig", TargetID: "r",
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if mode := fi.Mode().Perm(); mode != 0o600 {
		t.Errorf("channel_mappings.json mode = %o, want 0600", mode)
	}
	dirfi, err := os.Stat(filepath.Dir(path))
	if err != nil {
		t.Fatal(err)
	}
	if mode := dirfi.Mode().Perm(); mode != 0o700 {
		t.Errorf("dir mode = %o, want 0700", mode)
	}
}

func TestRegistryAtomicWriteCleansTmp(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "session", TargetID: "gc-1",
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(filepath.Dir(path))
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		if strings.Contains(e.Name(), ".tmp") {
			t.Errorf("stray tmp file lingered: %s", e.Name())
		}
	}
}

func TestRegistryConcurrentSets(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			ch := "C" + string(rune('0'+i))
			if err := reg.Set(Record{
				WorkspaceID: "T1", ChannelID: ch,
				TargetKind: "rig", TargetID: "r",
				CreatedAt: now, UpdatedAt: now,
			}); err != nil {
				t.Errorf("concurrent Set: %v", err)
			}
		}(i)
	}
	wg.Wait()

	// All 10 must persist; the on-disk file must be valid JSON.
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var roundtrip map[string]Record
	if err := json.Unmarshal(data, &roundtrip); err != nil {
		t.Fatalf("disk JSON invalid after concurrent writes: %v", err)
	}
	if len(roundtrip) != 10 {
		t.Errorf("after 10 concurrent Sets, on-disk count = %d, want 10", len(roundtrip))
	}
}

func TestRegistryPersistsAndReloads(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg1, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg1.Set(Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "session", TargetID: "gc-7",
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	reg2, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	got, ok := reg2.Get("T1", "C1")
	if !ok {
		t.Fatal("reload Get not ok")
	}
	if got.TargetID != "gc-7" || got.TargetKind != "session" {
		t.Errorf("reloaded record mismatch: %+v", got)
	}
}

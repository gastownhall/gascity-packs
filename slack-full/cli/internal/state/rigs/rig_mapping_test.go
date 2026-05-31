package rigs

import (
	"encoding/json"
	"os"
	"path/filepath"
	"slices"
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

// TestPathIsCityRooted pins the on-disk location to
// <cityPath>/.gc/slack/rig_mappings.json so the adapter and CLI agree.
func TestPathIsCityRooted(t *testing.T) {
	cityRoot := newTestCity(t)
	got := Path(cityRoot)
	want := filepath.Join(cityRoot, ".gc", "slack", "rig_mappings.json")
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
	if got := len(reg.AllSorted()); got != 0 {
		t.Errorf("fresh registry: AllSorted() len = %d, want 0", got)
	}
	if _, _, ok := reg.LookupRigForChannel("T1", "C1"); ok {
		t.Errorf("fresh registry LookupRigForChannel returned ok=true, want false")
	}
}

func TestRegistrySetAndLookup(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	rec := Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C2", "C1"},
		CreatedAt:  now, UpdatedAt: now,
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}
	got, src, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatalf("LookupRigForChannel(T1,C1) ok=false, want true")
	}
	if src != "rig" {
		t.Errorf("source = %q, want %q", src, "rig")
	}
	if got.RigName != "alpha" {
		t.Errorf("RigName = %q, want alpha", got.RigName)
	}
	// Channels should be sorted+deduped after Set.
	if len(got.ChannelIDs) != 2 || got.ChannelIDs[0] != "C1" || got.ChannelIDs[1] != "C2" {
		t.Errorf("ChannelIDs = %v, want [C1 C2] (sorted)", got.ChannelIDs)
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
		{WorkspaceID: "", RigName: "alpha", ChannelIDs: []string{"C1"}, CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", RigName: "", ChannelIDs: []string{"C1"}, CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", RigName: "alpha", ChannelIDs: []string{}, CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", RigName: "alpha", ChannelIDs: nil, CreatedAt: now, UpdatedAt: now},
		// All-empty channel after dedup → reject.
		{WorkspaceID: "T1", RigName: "alpha", ChannelIDs: []string{""}, CreatedAt: now, UpdatedAt: now},
	}
	for _, rec := range cases {
		if err := reg.Set(rec); err == nil {
			t.Errorf("Set(%+v): expected error, got nil", rec)
		}
	}
}

func TestRegistryRejectsInvalidRigName(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	bad := []string{
		"alpha beta",  // whitespace
		"alpha\tbeta", // tab
		"alpha/beta",  // slash
		"alpha\\beta", // backslash
		"alpha\nbeta", // newline (control char)
		"alpha\x00",   // null
	}
	for _, name := range bad {
		err := reg.Set(Record{
			WorkspaceID: "T1", RigName: name,
			ChannelIDs: []string{"C1"},
			CreatedAt:  now, UpdatedAt: now,
		})
		if err == nil {
			t.Errorf("Set rig_name=%q: expected error, got nil", name)
		}
	}
}

func TestRegistryDedupesAndSortsChannels(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C2", "C1", "C2", "C3"},
		CreatedAt:  now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	rec, _, _ := reg.LookupRigForChannel("T1", "C1")
	if len(rec.ChannelIDs) != 3 {
		t.Fatalf("dedup failed: %v", rec.ChannelIDs)
	}
	for i, want := range []string{"C1", "C2", "C3"} {
		if rec.ChannelIDs[i] != want {
			t.Errorf("ChannelIDs[%d] = %q, want %q", i, rec.ChannelIDs[i], want)
		}
	}
}

func TestRegistryIdempotentReSet(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	t0 := time.Now().UTC().Add(-time.Hour)
	t1 := time.Now().UTC()
	if err := reg.Set(Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1", "C2"},
		CreatedAt:  t0, UpdatedAt: t0,
	}); err != nil {
		t.Fatal(err)
	}
	if err := reg.Set(Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C3", "C4"},
		CreatedAt:  t1, // caller passes t1 but registry must preserve t0
		UpdatedAt:  t1,
	}); err != nil {
		t.Fatal(err)
	}
	all := reg.AllSorted()
	if len(all) != 1 {
		t.Fatalf("re-set grew registry: %d records", len(all))
	}
	rec := all[0]
	if !rec.CreatedAt.Equal(t0) {
		t.Errorf("CreatedAt = %v, want preserved t0=%v", rec.CreatedAt, t0)
	}
	if !rec.UpdatedAt.Equal(t1) {
		t.Errorf("UpdatedAt = %v, want t1=%v", rec.UpdatedAt, t1)
	}
	if rec.ChannelIDs[0] != "C3" || rec.ChannelIDs[1] != "C4" {
		t.Errorf("ChannelIDs = %v, want [C3 C4]", rec.ChannelIDs)
	}
	// byChannel must reflect the replacement: C1/C2 dropped, C3/C4 added.
	if _, _, ok := reg.LookupRigForChannel("T1", "C1"); ok {
		t.Errorf("byChannel still has C1 after replacement")
	}
	if _, _, ok := reg.LookupRigForChannel("T1", "C3"); !ok {
		t.Errorf("byChannel missing C3 after replacement")
	}
}

func TestRegistryRejectsCrossRigOverlap(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
		CreatedAt:  now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	err = reg.Set(Record{
		WorkspaceID: "T1", RigName: "beta",
		ChannelIDs: []string{"C1"},
		CreatedAt:  now, UpdatedAt: now,
	})
	if err == nil {
		t.Fatal("expected error for cross-rig overlap, got nil")
	}
	if !strings.Contains(err.Error(), "alpha") {
		t.Errorf("error should mention conflicting rig %q: %v", "alpha", err)
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
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1", "C2"},
		CreatedAt:  now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	existed, err := reg.Remove("T1", "alpha")
	if err != nil {
		t.Fatalf("Remove: %v", err)
	}
	if !existed {
		t.Errorf("first Remove existed=false, want true")
	}
	if _, _, ok := reg.LookupRigForChannel("T1", "C1"); ok {
		t.Errorf("byChannel still has C1 after Remove")
	}
	// Idempotent.
	existed, err = reg.Remove("T1", "alpha")
	if err != nil {
		t.Fatalf("second Remove: %v", err)
	}
	if existed {
		t.Errorf("second Remove existed=true, want false")
	}

	// Reload to confirm persistence.
	reg2, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	if _, _, ok := reg2.LookupRigForChannel("T1", "C1"); ok {
		t.Errorf("after reload Get ok=true, want false (deletion not persisted)")
	}
}

func TestRegistryAllSorted(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	for _, k := range []struct{ ws, rig string }{
		{"T2", "z"}, {"T1", "b"}, {"T1", "a"}, {"T2", "a"},
	} {
		if err := reg.Set(Record{
			WorkspaceID: k.ws, RigName: k.rig,
			ChannelIDs: []string{"C-" + k.ws + "-" + k.rig},
			CreatedAt:  now, UpdatedAt: now,
		}); err != nil {
			t.Fatal(err)
		}
	}
	got := reg.AllSorted()
	want := []string{"T1:a", "T1:b", "T2:a", "T2:z"}
	if len(got) != len(want) {
		t.Fatalf("len = %d, want %d", len(got), len(want))
	}
	for i, w := range want {
		k := got[i].WorkspaceID + ":" + got[i].RigName
		if k != w {
			t.Errorf("AllSorted()[%d] = %q, want %q", i, k, w)
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
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
		CreatedAt:  now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if mode := fi.Mode().Perm(); mode != 0o600 {
		t.Errorf("rig_mappings.json mode = %o, want 0600", mode)
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
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
		CreatedAt:  now, UpdatedAt: now,
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
			rig := "rig-" + string(rune('a'+i))
			if err := reg.Set(Record{
				WorkspaceID: "T1", RigName: rig,
				ChannelIDs: []string{"C-" + rig},
				CreatedAt:  now, UpdatedAt: now,
			}); err != nil {
				t.Errorf("concurrent Set: %v", err)
			}
		}(i)
	}
	wg.Wait()
	if got := len(reg.AllSorted()); got != 10 {
		t.Errorf("concurrent Sets: All() len = %d, want 10", got)
	}
}

func TestRegistryRejectsCorruptFile(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	// Unknown field should be rejected via DisallowUnknownFields.
	if err := os.WriteFile(path, []byte(`{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":["C1"],"created_at":"2025-01-01T00:00:00Z","updated_at":"2025-01-01T00:00:00Z","bogus":42}}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewRegistry(path); err == nil {
		t.Fatal("expected error for unknown field, got nil")
	}
}

func TestRegistryRejectsEmptyChannelIDsOnLoad(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	corrupt := map[string]Record{
		"T1:alpha": {
			WorkspaceID: "T1", RigName: "alpha",
			ChannelIDs: []string{},
			CreatedAt:  time.Now().UTC(), UpdatedAt: time.Now().UTC(),
		},
	}
	data, _ := json.MarshalIndent(corrupt, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewRegistry(path); err == nil {
		t.Fatal("expected error for empty channel_ids on load")
	}
}

func TestRegistryLoadWarnsOnHandEditedOverlap(t *testing.T) {
	// A hand-edited file with overlapping channels across two records:
	// load succeeds (we can't refuse to start the CLI on an operator
	// edit), but the byChannel index keeps the first-by-sorted-key as
	// winner so subsequent lookups are deterministic.
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	corrupt := map[string]Record{
		"T1:alpha": {
			WorkspaceID: "T1", RigName: "alpha",
			ChannelIDs: []string{"C1"},
			CreatedAt:  now, UpdatedAt: now,
		},
		"T1:beta": {
			WorkspaceID: "T1", RigName: "beta",
			ChannelIDs: []string{"C1"},
			CreatedAt:  now, UpdatedAt: now,
		},
	}
	data, _ := json.MarshalIndent(corrupt, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("load with overlap should succeed (with WARN): %v", err)
	}
	rec, _, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatal("byChannel did not survive overlap WARN")
	}
	// First-by-sorted-key wins. T1:alpha < T1:beta lexicographically.
	if rec.RigName != "alpha" {
		t.Errorf("overlap winner = %q, want alpha (first-by-sorted-key)", rec.RigName)
	}
}

// TestRegistryRoundTripWithSlingTargetAndFixFormula
// pins the new fields (cby.18.a) — round-trip on disk preserves the
// values the operator supplied via `gc slack map-rig --sling-target
// ... --fix-formula ...`.
func TestRegistryRoundTripWithSlingTargetAndFixFormula(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	want := Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "alpha/polecat",
		FixFormula:  "mol-slack-fix-issue",
		CreatedAt:   now, UpdatedAt: now,
	}
	if err := reg.Set(want); err != nil {
		t.Fatalf("Set: %v", err)
	}
	reg2, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	got, ok := reg2.Get("T1", "alpha")
	if !ok {
		t.Fatal("Get after reload ok=false")
	}
	if got.SlingTarget != want.SlingTarget {
		t.Errorf("SlingTarget = %q, want %q", got.SlingTarget, want.SlingTarget)
	}
	if got.FixFormula != want.FixFormula {
		t.Errorf("FixFormula = %q, want %q", got.FixFormula, want.FixFormula)
	}
}

// TestRegistryLoadsLegacyRecordWithoutNewFields covers
// the tolerance contract: a rig_mappings.json written before cby.18.a
// (no sling_target / fix_formula keys) must still load cleanly. The
// resolution-time check (not load-time) surfaces the missing field.
func TestRegistryLoadsLegacyRecordWithoutNewFields(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	// Hand-write a legacy record with NO sling_target / fix_formula keys.
	legacy := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":["C1"],"created_at":"2025-01-01T00:00:00Z","updated_at":"2025-01-01T00:00:00Z"}}`
	if err := os.WriteFile(path, []byte(legacy), 0o600); err != nil {
		t.Fatal(err)
	}
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("legacy record load: %v", err)
	}
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("legacy record missing after load")
	}
	if rec.SlingTarget != "" {
		t.Errorf("SlingTarget = %q, want empty (legacy)", rec.SlingTarget)
	}
	if rec.FixFormula != "" {
		t.Errorf("FixFormula = %q, want empty (legacy)", rec.FixFormula)
	}
}

// TestValidateSlingTargetShape pins the shape rule: sling targets must
// match `<rig>/<role>` (a single forward slash, non-empty segments,
// printable identifiers).
func TestValidateSlingTargetShape(t *testing.T) {
	good := []string{
		"alpha/polecat",
		"mission-control/polecat",
		"rig_1/role_2",
		"rig.alpha/polecat-1",
	}
	for _, s := range good {
		if err := validateSlingTarget(s); err != nil {
			t.Errorf("validateSlingTarget(%q) = %v, want nil", s, err)
		}
	}
	bad := []string{
		"",
		"alpha",               // no slash
		"/polecat",            // empty rig segment
		"alpha/",              // empty role segment
		"alpha/polecat/extra", // too many segments
		"alpha polecat",       // whitespace
		"alpha\\polecat",
		"alpha\npolecat",
	}
	for _, s := range bad {
		if err := validateSlingTarget(s); err == nil {
			t.Errorf("validateSlingTarget(%q) = nil, want error", s)
		}
	}
}

// TestRegistryRejectsInvalidSlingTargetOnSet ensures we
// fail fast on invalid sling_target shape at write time, mirroring
// validateRigName behavior.
func TestRegistryRejectsInvalidSlingTargetOnSet(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	err = reg.Set(Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "no-slash",
		CreatedAt:   now, UpdatedAt: now,
	})
	if err == nil {
		t.Fatal("expected error for malformed sling_target, got nil")
	}
}

// TestPatternsRoundTrip verifies channel_patterns are
// persisted and loaded byte-for-byte, and that a record may carry
// patterns alone (no literal channel_ids).
func TestPatternsRoundTrip(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	rec := Record{
		WorkspaceID:     "T1",
		RigName:         "alpha",
		ChannelPatterns: []string{"oversight-*", "team-?", "alpha-prod"},
		CreatedAt:       now, UpdatedAt: now,
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set with patterns only: %v", err)
	}

	// Reload from disk and confirm the patterns came back sorted+deduped.
	reg2, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	got, ok := reg2.Get("T1", "alpha")
	if !ok {
		t.Fatal("record missing after reload")
	}
	wantPatterns := []string{"alpha-prod", "oversight-*", "team-?"}
	if !slices.Equal(got.ChannelPatterns, wantPatterns) {
		t.Errorf("ChannelPatterns = %v, want %v", got.ChannelPatterns, wantPatterns)
	}
	if len(got.ChannelIDs) != 0 {
		t.Errorf("ChannelIDs should be empty, got %v", got.ChannelIDs)
	}
}

// TestPatternsAndChannelsCoexist confirms a record may
// carry both literal channel_ids and channel_patterns; both round-trip.
func TestPatternsAndChannelsCoexist(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	rec := Record{
		WorkspaceID:     "T1",
		RigName:         "alpha",
		ChannelIDs:      []string{"C1", "C2"},
		ChannelPatterns: []string{"oversight-*"},
		CreatedAt:       now, UpdatedAt: now,
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}
	// Literal-channel index still works.
	got, src, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok || src != "rig" || got.RigName != "alpha" {
		t.Errorf("LookupRigForChannel(T1,C1) = (%+v,%q,%v); want alpha,rig,true", got, src, ok)
	}
	if !slices.Equal(got.ChannelPatterns, []string{"oversight-*"}) {
		t.Errorf("ChannelPatterns = %v, want [oversight-*]", got.ChannelPatterns)
	}
}

// TestRegistryRequiresChannelOrPattern confirms zero-of-both is
// rejected at Set time.
func TestRegistryRequiresChannelOrPattern(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	cases := []Record{
		// nil/empty both
		{WorkspaceID: "T1", RigName: "alpha", CreatedAt: now, UpdatedAt: now},
		{WorkspaceID: "T1", RigName: "alpha", ChannelIDs: []string{}, ChannelPatterns: []string{}, CreatedAt: now, UpdatedAt: now},
		// All entries empty after dedup
		{WorkspaceID: "T1", RigName: "alpha", ChannelIDs: []string{""}, ChannelPatterns: []string{""}, CreatedAt: now, UpdatedAt: now},
	}
	for i, rec := range cases {
		if err := reg.Set(rec); err == nil {
			t.Errorf("case %d: Set with no channels or patterns: expected error, got nil", i)
		}
	}
}

// TestRegistryRejectsMalformedPattern confirms each class of
// invalid pattern (charset, malformed glob, empty) is rejected at Set.
func TestRegistryRejectsMalformedPattern(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	bad := []string{
		"Oversight-*", // uppercase
		"team prod",   // whitespace
		"team\tprod",  // tab
		"team/prod",   // slash separator
		"team\\prod",  // backslash
		"team\nprod",  // control char
		"team[",       // unclosed bracket — path.Match ErrBadPattern
		"team[a-",     // unclosed range
		"team.prod",   // dot not in slack channel charset
		"team-[!xyz]", // '!' is path.Match literal, not negation; rejected to avoid operator footgun
		"",            // empty
	}
	for _, p := range bad {
		err := reg.Set(Record{
			WorkspaceID: "T1", RigName: "alpha",
			ChannelPatterns: []string{p},
			CreatedAt:       now, UpdatedAt: now,
		})
		if err == nil {
			t.Errorf("Set channel_pattern=%q: expected error, got nil", p)
		}
	}
}

// TestRegistryRejectsOversizePattern caps a single pattern's
// length at maxChannelPatternLen so an operator (or hand-edit) can't
// stuff a multi-kilobyte pattern into a record that the resolver tier
// (cby.b) would later replay against every inbound channel name.
func TestRegistryRejectsOversizePattern(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	huge := strings.Repeat("a", maxChannelPatternLen+1)
	err = reg.Set(Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelPatterns: []string{huge},
		CreatedAt:       now, UpdatedAt: now,
	})
	if err == nil {
		t.Fatal("expected error for oversize pattern, got nil")
	}
	// At-cap is acceptable.
	atCap := strings.Repeat("a", maxChannelPatternLen)
	if err := reg.Set(Record{
		WorkspaceID: "T1", RigName: "beta",
		ChannelPatterns: []string{atCap},
		CreatedAt:       now, UpdatedAt: now,
	}); err != nil {
		t.Errorf("at-cap pattern should be accepted: %v", err)
	}
}

// TestPatternsAcceptsValid confirms each class of valid
// glob pattern survives validation.
func TestPatternsAcceptsValid(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	good := []string{
		"oversight-*",
		"*-prod",
		"team-?",
		"alpha-[abc]",
		"alpha-[a-z]",
		"alpha-[^xyz]", // path.Match negated class — leading '^' inside [...]
		"plain-channel",
		"a",
		"_underscore-leading",
	}
	for _, p := range good {
		err := reg.Set(Record{
			WorkspaceID: "T1", RigName: "rig-" + p,
			ChannelPatterns: []string{p},
			CreatedAt:       now, UpdatedAt: now,
		})
		if err != nil {
			t.Errorf("Set channel_pattern=%q: unexpected error: %v", p, err)
		}
	}
}

// TestPatternsSortedDeduped confirms patterns are sorted
// and deduped on Set, identical to ChannelIDs ergonomics.
func TestPatternsSortedDeduped(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	rec := Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelPatterns: []string{"zeta-*", "alpha-*", "alpha-*", "", "beta-?"},
		CreatedAt:       now, UpdatedAt: now,
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}
	got, _ := reg.Get("T1", "alpha")
	want := []string{"alpha-*", "beta-?", "zeta-*"}
	if !slices.Equal(got.ChannelPatterns, want) {
		t.Errorf("ChannelPatterns = %v, want %v", got.ChannelPatterns, want)
	}
}

// TestLoadRejectsMalformedPattern confirms hand-edited
// files with malformed patterns are rejected at load — symmetric with
// the existing rig_name validation.
func TestLoadRejectsMalformedPattern(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	// Hand-rolled to skirt Set's validation.
	corrupt := `{
  "T1:alpha": {
    "workspace_id": "T1",
    "rig_name": "alpha",
    "channel_ids": [],
    "channel_patterns": ["Oversight-BAD"],
    "created_at": "` + now + `",
    "updated_at": "` + now + `"
  }
}`
	if err := os.WriteFile(path, []byte(corrupt), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewRegistry(path); err == nil {
		t.Error("expected load error for malformed pattern, got nil")
	}
}

// TestLoadRejectsZeroOfBoth confirms hand-edited records
// missing both channel_ids and channel_patterns are rejected at load.
func TestLoadRejectsZeroOfBoth(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	corrupt := `{
  "T1:alpha": {
    "workspace_id": "T1",
    "rig_name": "alpha",
    "channel_ids": [],
    "channel_patterns": [],
    "created_at": "` + now + `",
    "updated_at": "` + now + `"
  }
}`
	if err := os.WriteFile(path, []byte(corrupt), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := NewRegistry(path); err == nil {
		t.Error("expected load error for zero-of-both, got nil")
	}
}

// TestLegacyRecordWithoutPatternsLoads confirms a record
// written before this bead (no channel_patterns field) still loads
// — DisallowUnknownFields would reject the new field; we need
// backwards-compat in the OTHER direction (missing field is fine).
func TestLegacyRecordWithoutPatternsLoads(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	legacy := `{
  "T1:alpha": {
    "workspace_id": "T1",
    "rig_name": "alpha",
    "channel_ids": ["C1"],
    "created_at": "` + now + `",
    "updated_at": "` + now + `"
  }
}`
	if err := os.WriteFile(path, []byte(legacy), 0o600); err != nil {
		t.Fatal(err)
	}
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("legacy load failed: %v", err)
	}
	got, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("record missing")
	}
	if len(got.ChannelPatterns) != 0 {
		t.Errorf("legacy record ChannelPatterns = %v, want empty", got.ChannelPatterns)
	}
}

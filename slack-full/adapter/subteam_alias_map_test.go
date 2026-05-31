package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"testing"
)

// writeSubteamAliasFile writes a JSON map to a tmpfile and returns its
// path. Tests use this to stage operator-edited subteam-aliases.json
// states without exercising the (non-existent in v1) write API.
func writeSubteamAliasFile(t *testing.T, dir string, entries map[string]string) string {
	t.Helper()
	path := filepath.Join(dir, "subteam-aliases.json")
	data, err := json.Marshal(entries)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
	return path
}

// TestSubteamAliasMapEmptyAndAbsent confirms the constructor accepts
// both "file does not exist" (locked-down workspace, never wrote the
// map) and "file is `{}`" (operator cleared all bindings) as valid
// empty states. The map should NOT crash startup in either case —
// crashing would block adapter launch on workspaces that haven't yet
// adopted subteam routing.
func TestSubteamAliasMapEmptyAndAbsent(t *testing.T) {
	dir := t.TempDir()
	missing := filepath.Join(dir, "subteam-aliases.json")
	m, err := newSubteamAliasMap(missing)
	if err != nil {
		t.Fatalf("missing-file: %v", err)
	}
	if m.Len() != 0 {
		t.Errorf("missing-file Len = %d, want 0", m.Len())
	}
	if _, ok := m.Get("S0123ABCD"); ok {
		t.Errorf("missing-file Get returned ok=true for unknown id")
	}

	empty := writeSubteamAliasFile(t, dir, map[string]string{})
	m2, err := newSubteamAliasMap(empty)
	if err != nil {
		t.Fatalf("empty-file: %v", err)
	}
	if m2.Len() != 0 {
		t.Errorf("empty-file Len = %d, want 0", m2.Len())
	}
}

// TestSubteamAliasMapLoadAndGet exercises the happy path: operator
// writes a valid JSON map, constructor reads it, Get returns the
// expected handle for each registered subteam ID and ok=false for any
// unregistered ID.
func TestSubteamAliasMapLoadAndGet(t *testing.T) {
	dir := t.TempDir()
	path := writeSubteamAliasFile(t, dir, map[string]string{
		"S0B4MUNDZCH": "mayor",
		"S0123ABCD":   "cos",
		"S0456EFGH":   "gc-pl",
	})
	m, err := newSubteamAliasMap(path)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if m.Len() != 3 {
		t.Errorf("Len = %d, want 3", m.Len())
	}
	cases := []struct {
		id, want string
		wantOK   bool
	}{
		{"S0B4MUNDZCH", "mayor", true},
		{"S0123ABCD", "cos", true},
		{"S0456EFGH", "gc-pl", true},
		{"S_NOPE", "", false},
		{"", "", false},
	}
	for _, tc := range cases {
		got, ok := m.Get(tc.id)
		if got != tc.want || ok != tc.wantOK {
			t.Errorf("Get(%q) = (%q, %v), want (%q, %v)", tc.id, got, ok, tc.want, tc.wantOK)
		}
	}
}

// TestSubteamAliasMapRejectsCorruptEntries asserts that parse failures
// preserve the existing live state (the map is constructed but the
// load error surfaces). A subteam_id with empty handle would silently
// dispatch to "" — refuse to load it rather than serve a corrupt
// allowlist.
func TestSubteamAliasMapRejectsCorruptEntries(t *testing.T) {
	dir := t.TempDir()
	cases := []struct {
		name    string
		payload string
	}{
		{"empty handle", `{"S0123":""}`},
		{"empty key", `{"":"mayor"}`},
		{"unknown nested field", `{"S0123":{"handle":"mayor"}}`}, // wrong shape — value must be string
		{"not an object", `["S0123","mayor"]`},
		{"malformed JSON", `{`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			path := filepath.Join(dir, "bad-"+tc.name+".json")
			if err := os.WriteFile(path, []byte(tc.payload), 0o600); err != nil {
				t.Fatalf("write: %v", err)
			}
			if _, err := newSubteamAliasMap(path); err == nil {
				t.Errorf("payload %q parsed cleanly; want error", tc.payload)
			}
		})
	}
}

// TestSubteamAliasMapReloadOnUpdate confirms the SIGHUP reload path
// picks up operator edits without an adapter restart. This is the
// promise the startup log line makes ("read-only; SIGHUP or restart to
// reload") — break it and operators silently serve stale policy.
func TestSubteamAliasMapReloadOnUpdate(t *testing.T) {
	dir := t.TempDir()
	path := writeSubteamAliasFile(t, dir, map[string]string{
		"S0123": "mayor",
	})
	m, err := newSubteamAliasMap(path)
	if err != nil {
		t.Fatalf("initial load: %v", err)
	}
	if h, ok := m.Get("S0123"); !ok || h != "mayor" {
		t.Fatalf("initial Get(S0123) = (%q, %v), want (mayor, true)", h, ok)
	}

	// Operator edits the file: rename mayor → cos, add a new binding.
	writeSubteamAliasFile(t, dir, map[string]string{
		"S0123":  "cos",
		"S_NEW":  "probe-pl",
	})
	if err := m.Reload(); err != nil {
		t.Fatalf("reload: %v", err)
	}
	if h, ok := m.Get("S0123"); !ok || h != "cos" {
		t.Errorf("after reload, Get(S0123) = (%q, %v), want (cos, true)", h, ok)
	}
	if h, ok := m.Get("S_NEW"); !ok || h != "probe-pl" {
		t.Errorf("after reload, Get(S_NEW) = (%q, %v), want (probe-pl, true)", h, ok)
	}
	if m.Len() != 2 {
		t.Errorf("after reload, Len = %d, want 2", m.Len())
	}
}

// TestSubteamAliasMapAllSortedForDiffStability asserts that All()
// returns entries in deterministic order so test fixtures and
// operator-facing list output don't flap between adapter restarts.
func TestSubteamAliasMapAllSortedForDiffStability(t *testing.T) {
	dir := t.TempDir()
	path := writeSubteamAliasFile(t, dir, map[string]string{
		"S_B": "cos",
		"S_A": "mayor",
		"S_C": "gc-pl",
	})
	m, err := newSubteamAliasMap(path)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	got := m.All()
	want := []string{"S_A=mayor", "S_B=cos", "S_C=gc-pl"}
	if !sort.StringsAreSorted(got) {
		t.Errorf("All() not sorted: %v", got)
	}
	if len(got) != len(want) {
		t.Fatalf("All() len = %d, want %d (got=%v)", len(got), len(want), got)
	}
	for i := range got {
		if got[i] != want[i] {
			t.Errorf("All()[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

// TestSubteamAliasMapNilSafe documents the nil-safety contract the
// processSlackEvent wiring relies on: a nil *subteamAliasMap MUST
// behave like an empty map (Get returns ok=false, Len returns 0).
// Without this, callers would need to nil-check every call site, and
// the dispatch code path becomes harder to follow.
func TestSubteamAliasMapNilSafe(t *testing.T) {
	var m *subteamAliasMap
	if got, ok := m.Get("S0123"); ok || got != "" {
		t.Errorf("nil Get = (%q, %v), want (\"\", false)", got, ok)
	}
	if n := m.Len(); n != 0 {
		t.Errorf("nil Len = %d, want 0", n)
	}
	if got := m.All(); got != nil {
		t.Errorf("nil All = %v, want nil", got)
	}
}

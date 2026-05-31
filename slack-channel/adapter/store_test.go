package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadJSONMapMissingFile(t *testing.T) {
	m := map[string]string{}
	if err := loadJSONMap(filepath.Join(t.TempDir(), "nope.json"), &m); err != nil {
		t.Fatalf("missing file should not error: %v", err)
	}
	if len(m) != 0 {
		t.Errorf("map should stay empty, got %v", m)
	}
}

func TestLoadJSONMapEmptyFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "empty.json")
	if err := os.WriteFile(path, nil, 0o600); err != nil {
		t.Fatal(err)
	}
	m := map[string]string{}
	if err := loadJSONMap(path, &m); err != nil {
		t.Fatalf("empty file should not error: %v", err)
	}
}

func TestLoadJSONMapParseError(t *testing.T) {
	path := filepath.Join(t.TempDir(), "bad.json")
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	m := map[string]string{}
	if err := loadJSONMap(path, &m); err == nil {
		t.Fatal("expected parse error")
	}
}

func TestSaveJSONAtomicMkdirError(t *testing.T) {
	// A regular file where a directory component is expected makes MkdirAll
	// fail, surfacing as an error rather than a silent miss.
	f := filepath.Join(t.TempDir(), "afile")
	if err := os.WriteFile(f, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(f, "sub", "out.json") // f is a file, not a dir
	if err := saveJSONAtomic(path, map[string]string{"a": "1"}); err == nil {
		t.Fatal("expected error when a parent path component is a file")
	}
}

func TestSaveJSONAtomicRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nested", "out.json")
	in := map[string]string{"a": "1", "b": "2"}
	if err := saveJSONAtomic(path, in); err != nil {
		t.Fatalf("save: %v", err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("file perm = %o, want 600", perm)
	}
	out := map[string]string{}
	if err := loadJSONMap(path, &out); err != nil {
		t.Fatalf("reload: %v", err)
	}
	if out["a"] != "1" || out["b"] != "2" {
		t.Errorf("round-trip = %v", out)
	}
	// No leftover temp files in the directory.
	entries, _ := os.ReadDir(filepath.Dir(path))
	if len(entries) != 1 {
		t.Errorf("expected only the final file, got %d entries", len(entries))
	}
}

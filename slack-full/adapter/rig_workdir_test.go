package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeRoutesJSONL is a test helper that creates <cityPath>/.beads/routes.jsonl
// with the given JSONL body. Mirrors the on-disk shape produced by
// cmd/gc/rig_beads.go:writeRoutesFile.
func writeRoutesJSONL(t *testing.T, cityPath, body string) {
	t.Helper()
	beadsDir := filepath.Join(cityPath, ".beads")
	if err := os.MkdirAll(beadsDir, 0o755); err != nil {
		t.Fatalf("mkdir .beads: %v", err)
	}
	if err := os.WriteFile(filepath.Join(beadsDir, "routes.jsonl"), []byte(body), 0o644); err != nil {
		t.Fatalf("write routes.jsonl: %v", err)
	}
}

func TestRigWorkdir_HitRelativePath(t *testing.T) {
	cityPath := t.TempDir()
	feDir := filepath.Join(cityPath, "rigs", "frontend")
	if err := os.MkdirAll(feDir, 0o755); err != nil {
		t.Fatalf("mkdir feDir: %v", err)
	}
	// Routes are emitted by cmd/gc as relative paths from the rig hosting
	// the routes file. For the city's own routes.jsonl, paths are relative
	// to cityPath.
	body := `{"prefix":"mc","path":"."}
{"prefix":"fe","path":"rigs/frontend"}
`
	writeRoutesJSONL(t, cityPath, body)

	got, err := rigWorkdir(cityPath, "fe")
	if err != nil {
		t.Fatalf("rigWorkdir() error = %v", err)
	}
	if !filepath.IsAbs(got) {
		t.Errorf("rigWorkdir() = %q, want absolute path", got)
	}
	// Compare cleanly to the expected absolute path.
	want, err := filepath.Abs(feDir)
	if err != nil {
		t.Fatalf("filepath.Abs(feDir): %v", err)
	}
	if got != want {
		t.Errorf("rigWorkdir() = %q, want %q", got, want)
	}
}

func TestRigWorkdir_HitDotIsCityRoot(t *testing.T) {
	cityPath := t.TempDir()
	body := `{"prefix":"mc","path":"."}
`
	writeRoutesJSONL(t, cityPath, body)

	got, err := rigWorkdir(cityPath, "mc")
	if err != nil {
		t.Fatalf("rigWorkdir() error = %v", err)
	}
	want, err := filepath.Abs(cityPath)
	if err != nil {
		t.Fatalf("filepath.Abs(cityPath): %v", err)
	}
	if got != want {
		t.Errorf("rigWorkdir() = %q, want %q", got, want)
	}
}

func TestRigWorkdir_HitAbsolutePathPassesThrough(t *testing.T) {
	cityPath := t.TempDir()
	// External rig case — cmd/gc emits the absolute path computed via
	// filepath.Rel, but if the path is already absolute it must be
	// returned unchanged.
	external := filepath.Join(t.TempDir(), "external")
	if err := os.MkdirAll(external, 0o755); err != nil {
		t.Fatalf("mkdir external: %v", err)
	}
	body := `{"prefix":"ext","path":"` + external + `"}
`
	writeRoutesJSONL(t, cityPath, body)

	got, err := rigWorkdir(cityPath, "ext")
	if err != nil {
		t.Fatalf("rigWorkdir() error = %v", err)
	}
	if got != external {
		t.Errorf("rigWorkdir() = %q, want %q", got, external)
	}
}

func TestRigWorkdir_Miss(t *testing.T) {
	cityPath := t.TempDir()
	body := `{"prefix":"mc","path":"."}
`
	writeRoutesJSONL(t, cityPath, body)

	_, err := rigWorkdir(cityPath, "nope")
	if err == nil {
		t.Fatal("rigWorkdir() expected error for missing rig, got nil")
	}
	if !strings.Contains(err.Error(), "nope") {
		t.Errorf("error %q should mention the missing rig name", err)
	}
}

func TestRigWorkdir_MissingFile(t *testing.T) {
	cityPath := t.TempDir()
	// No routes.jsonl on disk at all.
	_, err := rigWorkdir(cityPath, "mc")
	if err == nil {
		t.Fatal("rigWorkdir() expected error when routes.jsonl missing, got nil")
	}
	if !strings.Contains(err.Error(), "routes.jsonl") {
		t.Errorf("error %q should reference routes.jsonl", err)
	}
}

func TestRigWorkdir_MalformedLineSkipped(t *testing.T) {
	cityPath := t.TempDir()
	feDir := filepath.Join(cityPath, "rigs", "frontend")
	if err := os.MkdirAll(feDir, 0o755); err != nil {
		t.Fatalf("mkdir feDir: %v", err)
	}
	// First line is not valid JSON; resolver should skip it and still
	// find the matching entry on the second line. Mirrors the tolerance
	// in internal/api/handler_beads.go:resolveRoutePrefix.
	body := `not json at all
{"prefix":"fe","path":"rigs/frontend"}
`
	writeRoutesJSONL(t, cityPath, body)

	got, err := rigWorkdir(cityPath, "fe")
	if err != nil {
		t.Fatalf("rigWorkdir() error = %v", err)
	}
	want, err := filepath.Abs(feDir)
	if err != nil {
		t.Fatalf("filepath.Abs(feDir): %v", err)
	}
	if got != want {
		t.Errorf("rigWorkdir() = %q, want %q", got, want)
	}
}

func TestRigWorkdir_BlankLinesIgnored(t *testing.T) {
	cityPath := t.TempDir()
	body := "\n{\"prefix\":\"mc\",\"path\":\".\"}\n\n"
	writeRoutesJSONL(t, cityPath, body)

	if _, err := rigWorkdir(cityPath, "mc"); err != nil {
		t.Fatalf("rigWorkdir() error = %v", err)
	}
}

func TestRigWorkdir_EmptyRigName(t *testing.T) {
	cityPath := t.TempDir()
	body := `{"prefix":"mc","path":"."}
`
	writeRoutesJSONL(t, cityPath, body)

	_, err := rigWorkdir(cityPath, "")
	if err == nil {
		t.Fatal("rigWorkdir() expected error for empty rig name, got nil")
	}
}

func TestRigWorkdir_EmptyCityPath(t *testing.T) {
	_, err := rigWorkdir("", "mc")
	if err == nil {
		t.Fatal("rigWorkdir() expected error for empty cityPath, got nil")
	}
}

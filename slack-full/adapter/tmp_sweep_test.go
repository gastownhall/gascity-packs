package main

import (
	"errors"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// TestSweepOrphanTmpFilesLegacyFixedName — the identityRegistry and
// handleAliasRegistry write atomically via "<diskPath>.tmp" (a fixed
// name, not randomized). A crash between OpenFile and Rename leaves
// exactly that file behind. The sweep must remove it.
func TestSweepOrphanTmpFilesLegacyFixedName(t *testing.T) {
	dir := t.TempDir()
	diskPath := filepath.Join(dir, "identities.json")
	orphan := diskPath + ".tmp"
	if err := os.WriteFile(orphan, []byte(`{"corrupted":""}`), 0o600); err != nil {
		t.Fatalf("seed orphan: %v", err)
	}
	if err := sweepOrphanTmpFiles(diskPath); err != nil {
		t.Fatalf("sweep: %v", err)
	}
	if _, err := os.Stat(orphan); !errors.Is(err, os.ErrNotExist) {
		t.Errorf("orphan %q still exists (err=%v); want removed", orphan, err)
	}
}

// TestSweepOrphanTmpFilesRandomizedName — channel/rig/apps registries
// write via writeFile0600 which uses os.CreateTemp pattern
// "<basename>-*.tmp". Crash between create and rename leaves
// "<basename>-<random>.tmp". The sweep must remove all such files.
func TestSweepOrphanTmpFilesRandomizedName(t *testing.T) {
	dir := t.TempDir()
	diskPath := filepath.Join(dir, "channel_mappings.json")
	orphans := []string{
		filepath.Join(dir, "channel_mappings.json-1234567890.tmp"),
		filepath.Join(dir, "channel_mappings.json-abcdef.tmp"),
	}
	for _, p := range orphans {
		if err := os.WriteFile(p, []byte("{}"), 0o600); err != nil {
			t.Fatalf("seed %q: %v", p, err)
		}
	}
	if err := sweepOrphanTmpFiles(diskPath); err != nil {
		t.Fatalf("sweep: %v", err)
	}
	for _, p := range orphans {
		if _, err := os.Stat(p); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("orphan %q still exists; want removed", p)
		}
	}
}

// TestSweepOrphanTmpFilesPreservesUnrelatedFiles — sweep must NOT
// remove files that don't match the two known atomic-write patterns.
// Operator-placed backups, swap files, log rotations, and the actual
// store file itself must all be preserved.
func TestSweepOrphanTmpFilesPreservesUnrelatedFiles(t *testing.T) {
	dir := t.TempDir()
	diskPath := filepath.Join(dir, "channel_mappings.json")
	keepers := []string{
		diskPath, // the real store
		filepath.Join(dir, "channel_mappings.json.bak"),       // backup
		filepath.Join(dir, "unrelated.tmp"),                   // different prefix
		filepath.Join(dir, "channel_mappings.json.swp"),       // editor swap
		filepath.Join(dir, "other_store.json-12345.tmp"),      // different basename
		filepath.Join(dir, "channel_mappings.json-no-suffix"), // missing .tmp
	}
	for _, p := range keepers {
		if err := os.WriteFile(p, []byte("keep"), 0o600); err != nil {
			t.Fatalf("seed %q: %v", p, err)
		}
	}
	if err := sweepOrphanTmpFiles(diskPath); err != nil {
		t.Fatalf("sweep: %v", err)
	}
	for _, p := range keepers {
		if _, err := os.Stat(p); err != nil {
			t.Errorf("unrelated file %q was removed: %v", p, err)
		}
	}
}

// TestSweepOrphanTmpFilesMissingDirIsNoop — first-time startup before
// any store has been created leaves the parent dir absent. The sweep
// must treat that as a no-op, not a fatal error.
func TestSweepOrphanTmpFilesMissingDirIsNoop(t *testing.T) {
	root := t.TempDir()
	diskPath := filepath.Join(root, "does", "not", "exist", "store.json")
	if err := sweepOrphanTmpFiles(diskPath); err != nil {
		t.Errorf("sweep on missing dir: err=%v, want nil", err)
	}
}

// TestSweepOrphanTmpFilesEmptyDiskPathIsNoop — registry construction
// passes empty diskPath in some test paths to disable persistence.
// Sweep must not panic or stat ".".
func TestSweepOrphanTmpFilesEmptyDiskPathIsNoop(t *testing.T) {
	if err := sweepOrphanTmpFiles(""); err != nil {
		t.Errorf("sweep on empty diskPath: err=%v, want nil", err)
	}
}

// TestSweepOrphanTmpFilesRemoveErrorLoggedAndContinues — when an
// individual os.Remove fails (e.g. parent directory lacks write
// permission), the sweep must log the failure and keep going through
// the remaining matching entries rather than aborting. The function
// signature still returns nil for per-file failures; only a directory
// listing failure surfaces as a returned error.
//
// Implementation: chmod 0o500 (r-x) on the parent dir AFTER seeding
// the orphans blocks unlink without blocking ReadDir. We restore
// 0o700 in a t.Cleanup registered BEFORE t.TempDir's own cleanup runs
// (Cleanup is LIFO, so registering after t.TempDir guarantees the
// restore runs first and TempDir auto-cleanup can then proceed).
//
// Skipped on Windows (no POSIX directory-write semantics) and when
// running as root (uid 0 bypasses directory permission checks on
// most kernels — see DAC_OVERRIDE).
//
// Do NOT add t.Parallel() to this test. It mutates the package-global
// log.Default() writer via log.SetOutput, which races any concurrent
// test that also calls log.Printf. This package has no t.Parallel
// today; the broader logger-race story is tracked by gc-cby.36.
func TestSweepOrphanTmpFilesRemoveErrorLoggedAndContinues(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("POSIX directory write-permission semantics required")
	}
	if os.Geteuid() == 0 {
		t.Skip("root bypasses directory permission checks; cannot induce os.Remove failure")
	}

	dir := t.TempDir()
	diskPath := filepath.Join(dir, "identities.json")
	orphans := []string{
		diskPath + ".tmp", // legacy fixed-name
		filepath.Join(dir, "identities.json-1234567890.tmp"), // randomized
	}
	for _, p := range orphans {
		if err := os.WriteFile(p, []byte("x"), 0o600); err != nil {
			t.Fatalf("seed %q: %v", p, err)
		}
	}

	// Restore parent dir perms BEFORE t.TempDir's auto-cleanup runs.
	// Cleanup is LIFO — registering this after t.TempDir guarantees
	// it fires first.
	t.Cleanup(func() {
		if err := os.Chmod(dir, 0o700); err != nil {
			t.Logf("restore dir perms: %v", err)
		}
	})
	if err := os.Chmod(dir, 0o500); err != nil {
		t.Fatalf("chmod parent dir read-only: %v", err)
	}

	var logs strings.Builder
	prevOut := log.Writer()
	log.SetOutput(&logs)
	t.Cleanup(func() { log.SetOutput(prevOut) })

	if err := sweepOrphanTmpFiles(diskPath); err != nil {
		t.Fatalf("sweep returned error on per-file unlink failure: %v", err)
	}

	logged := logs.String()
	for _, p := range orphans {
		if !strings.Contains(logged, p) {
			t.Errorf("expected log to mention failed-remove path %q; got: %s", p, logged)
		}
	}
	if !strings.Contains(logged, "failed") {
		t.Errorf("expected log to contain failure marker; got: %s", logged)
	}

	// Loop continued past the first failure: both orphans must still
	// be on disk (every Remove failed under 0o500), proving the
	// function did not abort after the first error.
	for _, p := range orphans {
		if _, err := os.Stat(p); err != nil {
			t.Errorf("orphan %q unexpectedly missing after blocked sweep: %v", p, err)
		}
	}
}

// TestSweepOrphanTmpFilesBothPatternsTogether — production case: a
// registry that has switched patterns over its lifetime (cby.14 will
// migrate identity/alias to randomized) may leave both orphan shapes
// in the same dir. The sweep must clean both in one pass.
func TestSweepOrphanTmpFilesBothPatternsTogether(t *testing.T) {
	dir := t.TempDir()
	diskPath := filepath.Join(dir, "identities.json")
	legacy := diskPath + ".tmp"
	rand := filepath.Join(dir, "identities.json-99999.tmp")
	for _, p := range []string{legacy, rand} {
		if err := os.WriteFile(p, []byte("x"), 0o600); err != nil {
			t.Fatalf("seed %q: %v", p, err)
		}
	}
	if err := sweepOrphanTmpFiles(diskPath); err != nil {
		t.Fatalf("sweep: %v", err)
	}
	for _, p := range []string{legacy, rand} {
		if _, err := os.Stat(p); !errors.Is(err, os.ErrNotExist) {
			t.Errorf("%q still exists after combined sweep", p)
		}
	}
}

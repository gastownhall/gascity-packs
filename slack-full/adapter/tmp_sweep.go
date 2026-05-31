package main

import (
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
)

// sweepOrphanTmpFiles removes atomic-write-pattern .tmp files in
// filepath.Dir(diskPath) that were left behind by a crash between the
// CreateTemp/OpenFile and the Rename. Two shapes are recognized
// (matching the two atomic-write helpers used in this adapter):
//
//   - "<basename>.tmp" — the legacy fixed-name pattern used by
//     identityRegistry.saveLocked and handleAliasRegistry.saveLocked.
//   - "<basename>-*.tmp" — the os.CreateTemp-randomized pattern used
//     by writeFile0600 (interactions.go) on behalf of the channel,
//     rig, and apps registries.
//
// Files that do not match either shape are left untouched. The actual
// store file ("<diskPath>") is never a match (it has no ".tmp"
// suffix). A missing parent directory is treated as a no-op so the
// caller can sweep before first-startup directory creation. Per-file
// removal errors are logged and the sweep continues — this is
// best-effort hygiene, not a correctness primitive.
//
// Returns a non-nil error only on a directory-listing failure that
// indicates the filesystem itself is in a state worth surfacing
// (permission denied on the dir, etc.).
func sweepOrphanTmpFiles(diskPath string) error {
	if diskPath == "" {
		return nil
	}
	dir := filepath.Dir(diskPath)
	base := filepath.Base(diskPath)
	entries, err := os.ReadDir(dir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return fmt.Errorf("scan %q for orphan tmp files: %w", dir, err)
	}
	legacy := base + ".tmp"
	prefix := base + "-"
	const suffix = ".tmp"
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !isOrphanTmpName(name, legacy, prefix, suffix) {
			continue
		}
		full := filepath.Join(dir, name)
		if err := os.Remove(full); err != nil {
			log.Printf("orphan-tmp sweep: remove %q failed: %v", full, err)
			continue
		}
		log.Printf("orphan-tmp sweep: removed %q", full)
	}
	return nil
}

// isOrphanTmpName returns true iff name matches one of the two
// recognized atomic-write tmp shapes for the given store basename.
// Split out for readability and direct unit-testability.
func isOrphanTmpName(name, legacy, prefix, suffix string) bool {
	if name == legacy {
		return true
	}
	if len(name) <= len(prefix)+len(suffix) {
		return false
	}
	if name[:len(prefix)] != prefix {
		return false
	}
	if name[len(name)-len(suffix):] != suffix {
		return false
	}
	return true
}

package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// openBeneath is the userspace RESOLVE_BENEATH walk backing
// readConfinedFile. These tests pin the mechanism: legitimate nested
// paths open, and a symlink at ANY component — the stand-in for a
// parent directory swapped mid-flight — is a hard failure.

func TestOpenBeneathReadsNestedFile(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "a", "b"), 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(root, "a", "b", "f.txt"), []byte("payload"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	f, err := openBeneath(root, filepath.Join("a", "b", "f.txt"))
	if err != nil {
		t.Fatalf("openBeneath: %v", err)
	}
	defer f.Close()
	buf := make([]byte, 16)
	n, _ := f.Read(buf)
	if got := string(buf[:n]); got != "payload" {
		t.Errorf("read %q, want %q", got, "payload")
	}
}

func TestOpenBeneathRefusesSymlinkComponents(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "secret"), []byte("loot"), 0o600); err != nil {
		t.Fatalf("write outside: %v", err)
	}

	// Intermediate component is a symlink to a directory outside root —
	// the post-swap shape of the parent-directory race.
	if err := os.Symlink(outside, filepath.Join(root, "swapped")); err != nil {
		t.Fatalf("symlink dir: %v", err)
	}
	if _, err := openBeneath(root, filepath.Join("swapped", "secret")); err == nil {
		t.Fatal("openBeneath followed a symlinked intermediate directory, want failure")
	}

	// Leaf component is a symlink — O_NOFOLLOW parity with the old code.
	if err := os.Symlink(filepath.Join(outside, "secret"), filepath.Join(root, "leaf")); err != nil {
		t.Fatalf("symlink leaf: %v", err)
	}
	if _, err := openBeneath(root, "leaf"); err == nil {
		t.Fatal("openBeneath followed a leaf symlink, want failure")
	}
}

func TestOpenBeneathRefusesInRootLeafSymlink(t *testing.T) {
	// A RELATIVE leaf symlink to another file INSIDE the root: os.Root
	// happily resolves it (O_NOFOLLOW is not honored for in-root
	// links), which would upload a different in-root file than the one
	// the caller validated. The Lstat + inode-pin gate must reject it.
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "target.txt"), []byte("other"), 0o600); err != nil {
		t.Fatalf("write target: %v", err)
	}
	if err := os.Symlink("target.txt", filepath.Join(root, "link")); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	if _, err := openBeneath(root, "link"); err == nil {
		t.Fatal("openBeneath followed an in-root leaf symlink, want failure")
	}
}

func TestOpenBeneathRefusesInRootIntermediateSymlink(t *testing.T) {
	// An intermediate directory swapped for a RELATIVE symlink to
	// another directory INSIDE the root: os.Root follows it (it never
	// escapes), so both the leaf Lstat and the open would resolve
	// through the link to a different in-root file than validated.
	// The per-component Lstat + identity pin must reject it.
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "real"), 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(root, "real", "f.txt"), []byte("x"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}
	if err := os.Symlink("real", filepath.Join(root, "alias")); err != nil {
		t.Fatalf("symlink: %v", err)
	}
	if _, err := openBeneath(root, filepath.Join("alias", "f.txt")); err == nil {
		t.Fatal("openBeneath followed an in-root intermediate symlink, want failure")
	}
}

func TestOpenBeneathRefusesSymlinkedRoot(t *testing.T) {
	// The ROOT itself swapped for a symlink — the post-swap shape of
	// the terminal-root race. os.OpenRoot follows it by contract, so
	// the O_NOFOLLOW pre-open must reject it.
	base := t.TempDir()
	realRoot := filepath.Join(base, "real")
	if err := os.MkdirAll(realRoot, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(realRoot, "f.txt"), []byte("x"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}
	rootLink := filepath.Join(base, "rootlink")
	if err := os.Symlink(realRoot, rootLink); err != nil {
		t.Fatalf("symlink root: %v", err)
	}
	if _, err := openBeneath(rootLink, "f.txt"); err == nil {
		t.Fatal("openBeneath accepted a symlinked root, want failure")
	}
}

func TestOpenBeneathRejectsInvalidRel(t *testing.T) {
	root := t.TempDir()
	// "a/../b" is absent: filepath.Clean collapses it to "b" before the
	// component check, which is correct — the cleaned form is beneath root.
	for _, rel := range []string{"", ".", "/etc/passwd", "..", filepath.Join("..", "x")} {
		if _, err := openBeneath(root, rel); err == nil {
			t.Errorf("openBeneath(%q) succeeded, want rejection", rel)
		}
	}
}

func TestReadConfinedFileStillReadsAndStillConfines(t *testing.T) {
	// Canonicalize: readConfinedFile's contract is an EvalSymlinks-resolved
	// path, and on darwin t.TempDir() sits under the /var -> /private/var
	// symlink.
	root, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatalf("EvalSymlinks: %v", err)
	}
	sub := filepath.Join(root, "files")
	if err := os.MkdirAll(sub, 0o700); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	path := filepath.Join(sub, "report.txt")
	if err := os.WriteFile(path, []byte("contents"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	got, err := readConfinedFile(root, path)
	if err != nil {
		t.Fatalf("readConfinedFile: %v", err)
	}
	if string(got) != "contents" {
		t.Errorf("read %q, want %q", got, "contents")
	}

	if _, err := readConfinedFile(root, "/etc/passwd"); err == nil ||
		!strings.Contains(err.Error(), "outside root") {
		t.Errorf("escape attempt error = %v, want outside-root rejection", err)
	}
}

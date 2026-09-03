package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)

// openBeneath opens rel (a Clean, root-relative path containing no
// "..") beneath rootAbs with a per-component pinned walk built on
// os.Root — the portable replacement for the raw syscall.Openat walk
// (which does not exist on darwin and made the adapter linux-only).
//
// os.Root alone follows symlinks it considers safe: a symlink at the
// ROOT argument itself, and in-root symlinks at ANY component
// (O_NOFOLLOW passed to Root.OpenFile does not opt out — verified
// empirically on go1.26). The caller's contract is stronger than
// confinement: realPath was EvalSymlinks-resolved before this call,
// so every component of a legitimate path is a real directory or
// file, and ANY symlink anywhere on the path means an inode was
// swapped in the race window — the open must fail rather than return
// a different (even in-root) file than the one validated.
//
// The walk restores the old per-component guarantee portably:
//
//   - The root is first opened with plain open(2) +
//     O_NOFOLLOW|O_DIRECTORY (rejecting a root swapped for a symlink)
//     and the os.Root handle must match that fd's (dev, ino).
//   - Each intermediate component is Lstat'd through the current
//     pinned sub-root (symlink → hard failure), descended into with
//     Root.OpenRoot, and the opened sub-root must match the Lstat'd
//     (dev, ino) — so a component swapped between the two calls fails
//     the identity check instead of being silently followed.
//   - The leaf is Lstat'd (symlink → hard failure), opened with
//     O_NOFOLLOW, and the opened file must match the Lstat'd
//     (dev, ino).
func openBeneath(rootAbs, rel string) (*os.File, error) {
	if rel == "" || rel == "." || filepath.IsAbs(rel) {
		return nil, fmt.Errorf("openBeneath: invalid relative path %q", rel)
	}
	comps := strings.Split(filepath.Clean(rel), string(filepath.Separator))
	for _, c := range comps {
		if c == "" || c == "." || c == ".." {
			return nil, fmt.Errorf("openBeneath: invalid path component %q in %q", c, rel)
		}
	}

	// Pin the verified root directory. O_NOFOLLOW applies to the final
	// component of rootAbs, so a root swapped for a symlink fails here
	// (ELOOP on linux, ENOTDIR via O_DIRECTORY on darwin).
	rootFD, err := syscall.Open(rootAbs, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, fmt.Errorf("openBeneath: open root %q: %w", rootAbs, err)
	}
	defer syscall.Close(rootFD)
	var rootSt syscall.Stat_t
	if err := syscall.Fstat(rootFD, &rootSt); err != nil {
		return nil, fmt.Errorf("openBeneath: fstat root %q: %w", rootAbs, err)
	}

	cur, err := os.OpenRoot(rootAbs)
	if err != nil {
		return nil, fmt.Errorf("openBeneath: open root %q: %w", rootAbs, err)
	}
	defer func() { _ = cur.Close() }()
	// os.OpenRoot re-resolved rootAbs independently of the pinned fd
	// above; require both opens to have landed on the same directory
	// inode so a swap between the two calls cannot substitute a
	// different root.
	rootFI, err := cur.Stat(".")
	if err != nil {
		return nil, fmt.Errorf("openBeneath: stat root %q: %w", rootAbs, err)
	}
	if !sameInode(rootFI, &rootSt) {
		return nil, fmt.Errorf("openBeneath: root %q changed identity between opens", rootAbs)
	}

	// Descend one pinned sub-root at a time (see doc comment).
	for _, c := range comps[:len(comps)-1] {
		li, err := cur.Lstat(c)
		if err != nil {
			return nil, fmt.Errorf("openBeneath: lstat component %q of %q: %w", c, rel, err)
		}
		if li.Mode()&os.ModeSymlink != 0 {
			return nil, fmt.Errorf("openBeneath: component %q of %q is a symlink", c, rel)
		}
		compSt, ok := li.Sys().(*syscall.Stat_t)
		if !ok {
			return nil, fmt.Errorf("openBeneath: lstat component %q of %q: no unix stat", c, rel)
		}
		next, err := cur.OpenRoot(c)
		if err != nil {
			return nil, fmt.Errorf("openBeneath: open component %q of %q: %w", c, rel, err)
		}
		nextFI, err := next.Stat(".")
		if err != nil {
			_ = next.Close()
			return nil, fmt.Errorf("openBeneath: stat component %q of %q: %w", c, rel, err)
		}
		if !sameInode(nextFI, compSt) {
			_ = next.Close()
			return nil, fmt.Errorf("openBeneath: component %q of %q changed identity during open", c, rel)
		}
		_ = cur.Close()
		cur = next
	}

	// Leaf swap detection: a symlink at the leaf is a hard failure,
	// and the opened file must be the exact inode the Lstat verified —
	// covering both swap orders around the two calls.
	leaf := comps[len(comps)-1]
	li, err := cur.Lstat(leaf)
	if err != nil {
		return nil, fmt.Errorf("openBeneath: lstat %q beneath %q: %w", rel, rootAbs, err)
	}
	if li.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("openBeneath: %q beneath %q is a symlink", rel, rootAbs)
	}
	leafSt, ok := li.Sys().(*syscall.Stat_t)
	if !ok {
		return nil, fmt.Errorf("openBeneath: lstat %q beneath %q: no unix stat", rel, rootAbs)
	}
	f, err := cur.OpenFile(leaf, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, fmt.Errorf("openBeneath: open %q beneath %q: %w", rel, rootAbs, err)
	}
	openedFI, err := f.Stat()
	if err != nil {
		_ = f.Close()
		return nil, fmt.Errorf("openBeneath: stat opened %q beneath %q: %w", rel, rootAbs, err)
	}
	if !sameInode(openedFI, leafSt) {
		_ = f.Close()
		return nil, fmt.Errorf("openBeneath: %q beneath %q changed identity during open", rel, rootAbs)
	}
	return f, nil
}

// sameInode reports whether fi refers to the same (dev, ino) identity
// as want. A FileInfo without a unix *syscall.Stat_t fails closed.
func sameInode(fi os.FileInfo, want *syscall.Stat_t) bool {
	st, ok := fi.Sys().(*syscall.Stat_t)
	if !ok {
		return false
	}
	return st.Dev == want.Dev && st.Ino == want.Ino
}

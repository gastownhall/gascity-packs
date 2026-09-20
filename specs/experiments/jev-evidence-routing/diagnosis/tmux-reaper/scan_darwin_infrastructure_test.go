//go:build darwin

package proctable

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDarwinScannerExcludesSharedTmuxServer(t *testing.T) {
	dir := t.TempDir()
	// Replace ps with fixture output before disabling the live-scan guard.
	// No host process enumeration or signaling occurs in this test.
	data := "#!/bin/sh\ncat <<'ROWS'\n19620 1 tmux -u -L experiment new-session -e GC_SESSION_ID=retired -e GC_CITY=/tmp/city\n19630 19620 claude GC_SESSION_ID=active GC_CITY=/tmp/city\n19631 19630 child GC_SESSION_ID=active GC_CITY=/tmp/city\nROWS\n"
	if err := os.WriteFile(filepath.Join(dir, "ps"), []byte(data), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", dir+string(os.PathListSeparator)+os.Getenv("PATH"))
	t.Cleanup(SetScanRootForTesting(dir))
	got, err := ScanBySessionID("")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].PID != 19630 {
		t.Errorf("want only live Claude worker PID19630; got %+v", got)
	}
	if IsScanRoot(19620) {
		t.Error("shared tmux server must never be an agent root")
	}
	if !IsScanRoot(19630) {
		t.Error("Claude child of tmux must remain an agent root")
	}
	if IsScanRoot(19631) {
		t.Error("worker descendant must not be a separate root")
	}
}

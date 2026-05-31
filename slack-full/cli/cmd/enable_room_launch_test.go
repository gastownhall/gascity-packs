package cmd

import (
	"bytes"
	"strings"
	"testing"
	"time"

	"github.com/sjarmak/gc-slack-cli/internal/state/rooms"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// execEnableRoomLaunchCmd executes `gc-slack-cli enable-room-launch`
// directly against a temp city, mirroring the test pattern used for
// the sibling map-channel/map-rig verbs.
func execEnableRoomLaunchCmd(t *testing.T, cityRoot string, args ...string) (string, string, error) {
	t.Helper()
	t.Setenv(cityPathEnv, cityRoot)
	var stdout, stderr bytes.Buffer
	cmd := NewEnableRoomLaunchCmd(&stdout, &stderr)
	cmd.SetOut(&stdout)
	cmd.SetErr(&stderr)
	cmd.SetArgs(args)
	err := cmd.Execute()
	return stdout.String(), stderr.String(), err
}

// TestEnableRoomLaunchHappyPath — the common case writes a
// (workspace, channel) → pool_template record, prints a confirmation,
// and reminds the operator to restart the slack-pack adapter.
func TestEnableRoomLaunchHappyPath(t *testing.T) {
	cityRoot := newTestCity(t)

	stdout, stderr, err := execEnableRoomLaunchCmd(t, cityRoot,
		"C0123", "--workspace-id", "T123", "--launcher", "mission-control/launcher",
	)
	if err != nil {
		t.Fatalf("enable-room-launch: %v\nstderr=%s", err, stderr)
	}
	if !strings.Contains(stdout, "C0123") || !strings.Contains(stdout, "mission-control/launcher") {
		t.Errorf("stdout should mention channel and launcher pool: %q", stdout)
	}
	if !strings.Contains(stdout, "Send SIGHUP to slack-pack adapter") {
		t.Errorf("stdout should remind operator how to reload adapter: %q", stdout)
	}

	reg, err := rooms.NewRegistry(rooms.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	rec, ok := reg.Get("T123", "C0123")
	if !ok {
		t.Fatal("registry missing record after enable-room-launch")
	}
	if rec.PoolTemplate != "mission-control/launcher" {
		t.Errorf("PoolTemplate = %q, want %q", rec.PoolTemplate, "mission-control/launcher")
	}
}

// TestEnableRoomLaunchPreservesCreatedAtOnReBind — re-binding the
// same channel keeps the original CreatedAt and refreshes UpdatedAt.
// Mirrors the cby.3/cby.4 idempotent-re-bind contract.
func TestEnableRoomLaunchPreservesCreatedAtOnReBind(t *testing.T) {
	cityRoot := newTestCity(t)

	if _, _, err := execEnableRoomLaunchCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--launcher", "rigA/pool",
	); err != nil {
		t.Fatalf("first bind: %v", err)
	}
	reg1, _ := rooms.NewRegistry(rooms.Path(cityRoot))
	rec1, _ := reg1.Get("T1", "C1")
	createdAt := rec1.CreatedAt

	// Sleep a hair so UpdatedAt can advance on second write.
	time.Sleep(2 * time.Millisecond)

	if _, _, err := execEnableRoomLaunchCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--launcher", "rigB/pool",
	); err != nil {
		t.Fatalf("re-bind: %v", err)
	}
	reg2, _ := rooms.NewRegistry(rooms.Path(cityRoot))
	rec2, ok := reg2.Get("T1", "C1")
	if !ok {
		t.Fatal("missing record after re-bind")
	}
	if !rec2.CreatedAt.Equal(createdAt) {
		t.Errorf("CreatedAt drifted on re-bind: was %v, now %v", createdAt, rec2.CreatedAt)
	}
	if rec2.PoolTemplate != "rigB/pool" {
		t.Errorf("PoolTemplate not replaced on re-bind: got %q", rec2.PoolTemplate)
	}
}

// TestEnableRoomLaunchMissingLauncher — the verb refuses an empty
// --launcher because the slack-pack adapter has nothing to spawn.
func TestEnableRoomLaunchMissingLauncher(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execEnableRoomLaunchCmd(t, cityRoot,
		"C1", "--workspace-id", "T1",
	)
	if err == nil {
		t.Fatal("expected error when --launcher is missing")
	}
}

// TestEnableRoomLaunchMissingWorkspaceID — the verb refuses an
// empty workspace id when SLACK_WORKSPACE_ID is not set.
func TestEnableRoomLaunchMissingWorkspaceID(t *testing.T) {
	t.Setenv(workspace.IDEnv, "")
	cityRoot := newTestCity(t)
	_, _, err := execEnableRoomLaunchCmd(t, cityRoot,
		"C1", "--launcher", "rigA/pool",
	)
	if err == nil {
		t.Fatal("expected error when --workspace-id is unset and SLACK_WORKSPACE_ID is empty")
	}
}

// TestEnableRoomLaunchEmptyChannel — the channel argument cannot
// be empty (cobra's ExactArgs takes care of presence; this guards
// whitespace-only input).
func TestEnableRoomLaunchEmptyChannel(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execEnableRoomLaunchCmd(t, cityRoot,
		"   ", "--workspace-id", "T1", "--launcher", "rigA/pool",
	)
	if err == nil {
		t.Fatal("expected error for blank/whitespace channel")
	}
}

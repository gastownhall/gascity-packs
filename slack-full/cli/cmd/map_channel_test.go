package cmd

import (
	"bytes"
	"strings"
	"testing"

	"github.com/sjarmak/gc-slack-cli/internal/state/channels"
	"github.com/sjarmak/gc-slack-cli/internal/state/rigs"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// execMapChannelCmd executes the verb directly against a temp city.
//
// Honors GC_CITY_PATH=cityRoot (set via t.Setenv) so tests are not
// at the mercy of the polecat session's inherited GC_CITY_PATH.
func execMapChannelCmd(t *testing.T, cityRoot string, args ...string) (string, string, error) {
	t.Helper()
	t.Setenv(cityPathEnv, cityRoot)
	var stdout, stderr bytes.Buffer
	cmd := NewMapChannelCmd(&stdout, &stderr)
	cmd.SetOut(&stdout)
	cmd.SetErr(&stderr)
	cmd.SetArgs(args)
	err := cmd.Execute()
	return stdout.String(), stderr.String(), err
}

func TestMapChannelHappyPathRig(t *testing.T) {
	cityRoot := newTestCity(t)

	stdout, stderr, err := execMapChannelCmd(t, cityRoot,
		"C0123", "--workspace-id", "T123", "--rig", "alpha",
	)
	if err != nil {
		t.Fatalf("map-channel: %v\nstderr=%s", err, stderr)
	}
	if !strings.Contains(stdout, "C0123") || !strings.Contains(stdout, "alpha") {
		t.Errorf("stdout should mention channel and rig: %q", stdout)
	}

	reg, err := channels.NewRegistry(channels.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	rec, ok := reg.Get("T123", "C0123")
	if !ok {
		t.Fatal("registry missing record after map-channel")
	}
	if rec.TargetKind != "rig" || rec.TargetID != "alpha" {
		t.Errorf("record mismatch: %+v", rec)
	}
}

func TestMapChannelHappyPathSession(t *testing.T) {
	cityRoot := newTestCity(t)
	_, stderr, err := execMapChannelCmd(t, cityRoot,
		"C9", "--workspace-id", "T1", "--session", "gc-2568",
	)
	if err != nil {
		t.Fatalf("map-channel --session: %v\nstderr=%s", err, stderr)
	}
	reg, _ := channels.NewRegistry(channels.Path(cityRoot))
	rec, ok := reg.Get("T1", "C9")
	if !ok {
		t.Fatal("missing record")
	}
	if rec.TargetKind != "session" || rec.TargetID != "gc-2568" {
		t.Errorf("record mismatch: %+v", rec)
	}
}

func TestMapChannelMissingWorkspaceID(t *testing.T) {
	t.Setenv(workspace.IDEnv, "")
	cityRoot := newTestCity(t)
	_, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--rig", "alpha",
	)
	if err == nil {
		t.Fatal("expected error for missing --workspace-id")
	}
}

func TestMapChannelMutuallyExclusiveTargets(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "alpha", "--session", "gc-1",
	)
	if err == nil {
		t.Fatal("expected error for both --rig and --session")
	}
}

func TestMapChannelMissingTarget(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1",
	)
	if err == nil {
		t.Fatal("expected error when neither --rig nor --session nor --remove given")
	}
}

func TestMapChannelRemoveExisting(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "alpha",
	); err != nil {
		t.Fatal(err)
	}
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove existing: %v", err)
	}
	if !strings.Contains(stdout, "Removed channel mapping C1") {
		t.Errorf("stdout = %q, want substring 'Removed channel mapping C1'", stdout)
	}
	reg, _ := channels.NewRegistry(channels.Path(cityRoot))
	if _, ok := reg.Get("T1", "C1"); ok {
		t.Errorf("record still present after --remove")
	}
}

func TestMapChannelRemoveMissing(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove missing should succeed (idempotent): %v", err)
	}
	if !strings.Contains(stdout, "No binding for channel C1") {
		t.Errorf("stdout = %q, want substring 'No binding for channel C1'", stdout)
	}
}

func TestMapChannelRemoveWithTargetIsError(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--remove", "--rig", "alpha",
	)
	if err == nil {
		t.Fatal("expected error for --remove with --rig")
	}
	_, _, err = execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--remove", "--session", "gc-1",
	)
	if err == nil {
		t.Fatal("expected error for --remove with --session")
	}
}

// mapChannelRestartHint is the trailing reminder appended by
// every success-path output of `gc-slack-cli map-channel`, parallel to
// the cby.4 rig-mapping CLI.
const mapChannelRestartHint = "Send SIGHUP to slack-pack adapter"

func TestMapChannelHappyPathIncludesRestartReminder(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C0123", "--workspace-id", "T123", "--rig", "alpha",
	)
	if err != nil {
		t.Fatalf("map-channel: %v", err)
	}
	if !strings.Contains(stdout, mapChannelRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
}

func TestMapChannelRemoveExistingIncludesRestartReminder(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "alpha",
	); err != nil {
		t.Fatal(err)
	}
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove: %v", err)
	}
	if !strings.Contains(stdout, mapChannelRestartHint) {
		t.Errorf("--remove existing missing restart hint: %q", stdout)
	}
}

func TestMapChannelRemoveMissingIncludesRestartReminder(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove missing: %v", err)
	}
	if !strings.Contains(stdout, mapChannelRestartHint) {
		t.Errorf("--remove missing missing restart hint: %q", stdout)
	}
}

func TestMapChannelSessionIncludesRestartReminder(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--session", "gc-1",
	)
	if err != nil {
		t.Fatalf("map-channel --session: %v", err)
	}
	if !strings.Contains(stdout, mapChannelRestartHint) {
		t.Errorf("session map missing restart hint: %q", stdout)
	}
}

func TestMapChannelCrossStoreConflictDifferentRig(t *testing.T) {
	cityRoot := newTestCity(t)
	// Pre-write rig alpha owning C1 in cby.4.
	rigReg, err := rigs.NewRegistry(rigs.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	if err := rigReg.Set(rigs.Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
	}); err != nil {
		t.Fatal(err)
	}
	// Trying to map-channel C1 → rig beta should be rejected.
	_, _, err = execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "beta",
	)
	if err == nil {
		t.Fatal("expected cross-store conflict error, got nil")
	}
	if !strings.Contains(err.Error(), "alpha") {
		t.Errorf("error should mention conflicting rig %q: %v", "alpha", err)
	}
}

func TestMapChannelCrossStoreSameRigOK(t *testing.T) {
	cityRoot := newTestCity(t)
	rigReg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	_ = rigReg.Set(rigs.Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
	})
	if _, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "alpha",
	); err != nil {
		t.Fatalf("same-rig override should be OK: %v", err)
	}
}

func TestMapChannelCrossStoreSessionIgnoresRigStore(t *testing.T) {
	cityRoot := newTestCity(t)
	rigReg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	_ = rigReg.Set(rigs.Record{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
	})
	// --session is an explicit override, even on top of an existing
	// rig binding, so it must succeed without touching the rig
	// store.
	if _, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--session", "gc-1",
	); err != nil {
		t.Fatalf("session override should not be blocked by rig binding: %v", err)
	}
}

// mapChannelRigDeprecationHint is the substring cobra's
// MarkDeprecated emits whenever an operator invokes `gc-slack-cli
// map-channel --rig`. Option-1 unification (gc-cby.25): per-channel
// rig bindings are deprecated in favor of `gc-slack-cli map-rig`. The
// flag remains functional (back-compat) and cobra steers operators
// to the canonical verb. Match a minimal, stable substring so the
// flag-deprecation message wording can evolve without breaking the
// assertion. Cobra writes the warning to OutOrStderr → cmd.outWriter
// (i.e., stdout in this codebase, where root.SetOut(stdout) is set);
// see cmd_events.go --json deprecation for the same pattern.
const mapChannelRigDeprecationHint = "deprecated"

func TestMapChannelRigFlagEmitsDeprecationWarning(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C0123", "--workspace-id", "T123", "--rig", "alpha",
	)
	if err != nil {
		t.Fatalf("map-channel --rig should still succeed (soft deprecation): %v", err)
	}
	if !strings.Contains(stdout, mapChannelRigDeprecationHint) {
		t.Errorf("stdout missing cobra deprecation warning: %q", stdout)
	}
	if !strings.Contains(stdout, "map-rig") {
		t.Errorf("stdout deprecation should redirect to 'map-rig': %q", stdout)
	}
	// Operation must still complete: registry record persisted.
	reg, _ := channels.NewRegistry(channels.Path(cityRoot))
	if rec, ok := reg.Get("T123", "C0123"); !ok || rec.TargetID != "alpha" {
		t.Errorf("record missing/wrong after deprecated --rig: %+v ok=%v", rec, ok)
	}
	if !strings.Contains(stdout, "alpha") {
		t.Errorf("stdout missing rig name: %q", stdout)
	}
}

func TestMapChannelSessionDoesNotEmitDeprecationWarning(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--session", "gc-1",
	)
	if err != nil {
		t.Fatalf("map-channel --session: %v", err)
	}
	if strings.Contains(stdout, mapChannelRigDeprecationHint) {
		t.Errorf("--session must NOT emit --rig deprecation warning: %q", stdout)
	}
}

func TestMapChannelRigFlagHiddenFromHelp(t *testing.T) {
	cmd := NewMapChannelCmd(nil, nil)
	flag := cmd.Flags().Lookup("rig")
	if flag == nil {
		t.Fatal("--rig flag missing entirely; soft deprecation must keep the flag")
	}
	if !flag.Hidden {
		t.Errorf("--rig flag must be Hidden:true after deprecation, got Hidden=%v", flag.Hidden)
	}
}

func TestMapChannelIdempotentReSetPreservesCreatedAt(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "alpha",
	); err != nil {
		t.Fatal(err)
	}
	reg, _ := channels.NewRegistry(channels.Path(cityRoot))
	rec1, _ := reg.Get("T1", "C1")
	createdAt := rec1.CreatedAt

	if _, _, err := execMapChannelCmd(t, cityRoot,
		"C1", "--workspace-id", "T1", "--rig", "beta",
	); err != nil {
		t.Fatal(err)
	}
	reg2, _ := channels.NewRegistry(channels.Path(cityRoot))
	rec2, _ := reg2.Get("T1", "C1")
	if !rec2.CreatedAt.Equal(createdAt) {
		t.Errorf("CreatedAt advanced on re-set: was %v, now %v", createdAt, rec2.CreatedAt)
	}
	if rec2.TargetID != "beta" {
		t.Errorf("re-set TargetID = %q, want beta", rec2.TargetID)
	}
}

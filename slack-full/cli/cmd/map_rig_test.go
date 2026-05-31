package cmd

import (
	"bytes"
	"strings"
	"testing"
	"time"

	"github.com/sjarmak/gc-slack-cli/internal/state/channels"
	"github.com/sjarmak/gc-slack-cli/internal/state/rigs"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// execMapRigCmd executes the verb directly against a temp city.
//
// Honors GC_CITY_PATH=cityRoot (set via t.Setenv) so tests aren't at
// the mercy of the polecat session's inherited GC_CITY_PATH.
func execMapRigCmd(t *testing.T, cityRoot string, args ...string) (string, string, error) {
	t.Helper()
	t.Setenv(cityPathEnv, cityRoot)
	var stdout, stderr bytes.Buffer
	cmd := NewMapRigCmd(&stdout, &stderr)
	cmd.SetOut(&stdout)
	cmd.SetErr(&stderr)
	cmd.SetArgs(args)
	err := cmd.Execute()
	return stdout.String(), stderr.String(), err
}

const mapRigRestartHint = "Send SIGHUP to slack-pack adapter"

func TestMapRigHappyPath(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, stderr, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1", "--channel", "C2",
	)
	if err != nil {
		t.Fatalf("map-rig: %v\nstderr=%s", err, stderr)
	}
	if !strings.Contains(stdout, "alpha") {
		t.Errorf("stdout should mention rig alpha: %q", stdout)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
	reg, err := rigs.NewRegistry(rigs.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	rec, _, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatal("rig mapping missing after map-rig")
	}
	if rec.RigName != "alpha" {
		t.Errorf("RigName = %q, want alpha", rec.RigName)
	}
	if len(rec.ChannelIDs) != 2 || rec.ChannelIDs[0] != "C1" || rec.ChannelIDs[1] != "C2" {
		t.Errorf("ChannelIDs = %v, want [C1 C2] (sorted)", rec.ChannelIDs)
	}
}

func TestMapRigCommaSeparatedChannels(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2",
	); err != nil {
		t.Fatalf("map-rig comma-separated: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, _, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatal("missing record")
	}
	if len(rec.ChannelIDs) != 2 {
		t.Errorf("ChannelIDs = %v, want 2", rec.ChannelIDs)
	}
}

func TestMapRigMixedFlagAndCommas(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1", "--channel", "C2,C3",
	); err != nil {
		t.Fatalf("map-rig mixed: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, _, _ := reg.LookupRigForChannel("T1", "C1")
	if len(rec.ChannelIDs) != 3 {
		t.Errorf("ChannelIDs = %v, want 3", rec.ChannelIDs)
	}
}

func TestMapRigDedupesChannels(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1", "--channel", "C1",
	); err != nil {
		t.Fatalf("map-rig: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, _, _ := reg.LookupRigForChannel("T1", "C1")
	if len(rec.ChannelIDs) != 1 {
		t.Errorf("ChannelIDs = %v, want 1 (deduped)", rec.ChannelIDs)
	}
}

func TestMapRigMissingWorkspaceID(t *testing.T) {
	t.Setenv(workspace.IDEnv, "")
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--channel", "C1",
	)
	if err == nil {
		t.Fatal("expected error for missing --workspace-id")
	}
}

func TestMapRigMissingChannel(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
	)
	if err == nil {
		t.Fatal("expected error when --channel missing without --remove")
	}
}

func TestMapRigRemoveExisting(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove existing: %v", err)
	}
	if !strings.Contains(stdout, "Removed rig mapping alpha") {
		t.Errorf("stdout = %q, want substring 'Removed rig mapping alpha'", stdout)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	if _, _, ok := reg.LookupRigForChannel("T1", "C1"); ok {
		t.Errorf("byChannel still has C1 after --remove")
	}
}

func TestMapRigRemoveMissing(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove missing should succeed (idempotent): %v", err)
	}
	if !strings.Contains(stdout, "No rig mapping alpha") {
		t.Errorf("stdout = %q, want substring 'No rig mapping alpha'", stdout)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
}

func TestMapRigRemoveWithChannelIsError(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove", "--channel", "C1",
	)
	if err == nil {
		t.Fatal("expected error for --remove with --channel")
	}
}

func TestMapRigReplaceWithDropsWarning(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2,C3",
	); err != nil {
		t.Fatal(err)
	}
	_, stderr, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C2,C3",
	)
	if err != nil {
		t.Fatalf("re-set: %v", err)
	}
	if !strings.Contains(stderr, "dropped: C1") {
		t.Errorf("stderr should warn about dropped channels: %q", stderr)
	}
}

func TestMapRigCrossStoreConflictDifferentRig(t *testing.T) {
	cityRoot := newTestCity(t)
	// Pre-write cby.3 channel mapping C1 → rig beta.
	chanReg, err := channels.NewRegistry(channels.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := chanReg.Set(channels.Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "rig", TargetID: "beta",
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	// Now try to map-rig alpha to include C1 → should fail.
	_, _, err = execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	)
	if err == nil {
		t.Fatal("expected cross-store conflict error, got nil")
	}
	if !strings.Contains(err.Error(), "beta") {
		t.Errorf("error should mention conflicting rig %q: %v", "beta", err)
	}
}

func TestMapRigCrossStoreSameRigOK(t *testing.T) {
	cityRoot := newTestCity(t)
	// Pre-write cby.3 channel mapping C1 → rig alpha.
	chanReg, _ := channels.NewRegistry(channels.Path(cityRoot))
	now := time.Now().UTC()
	_ = chanReg.Set(channels.Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "rig", TargetID: "alpha",
		CreatedAt: now, UpdatedAt: now,
	})
	// Now map-rig alpha including C1 — same rig, should succeed.
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatalf("same-rig should be OK: %v", err)
	}
}

func TestMapRigCrossStoreSessionMappingOK(t *testing.T) {
	cityRoot := newTestCity(t)
	// Pre-write cby.3 channel mapping C1 → session gc-1 (an explicit override).
	chanReg, _ := channels.NewRegistry(channels.Path(cityRoot))
	now := time.Now().UTC()
	_ = chanReg.Set(channels.Record{
		WorkspaceID: "T1", ChannelID: "C1",
		TargetKind: "session", TargetID: "gc-1",
		CreatedAt: now, UpdatedAt: now,
	})
	// map-rig alpha including C1 should succeed; the per-channel
	// session mapping is the explicit override (the intended
	// composition pattern).
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatalf("session override should not block map-rig: %v", err)
	}
}

func TestMapRigCrossRigConflictWithinCBy4(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	_, _, err := execMapRigCmd(t, cityRoot,
		"beta", "--workspace-id", "T1", "--channel", "C1",
	)
	if err == nil {
		t.Fatal("expected cross-rig conflict, got nil")
	}
}

func TestMapRigRemoveChannelsPartial(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2,C3",
	); err != nil {
		t.Fatal(err)
	}
	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C2",
	)
	if err != nil {
		t.Fatalf("--remove-channels partial: %v", err)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("record vanished after partial removal")
	}
	if len(rec.ChannelIDs) != 2 || rec.ChannelIDs[0] != "C1" || rec.ChannelIDs[1] != "C3" {
		t.Errorf("ChannelIDs = %v, want [C1 C3]", rec.ChannelIDs)
	}
}

func TestMapRigRemoveChannelsMultiple(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2,C3",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C2,C3",
	); err != nil {
		t.Fatalf("--remove-channels multi: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("record missing after multi removal")
	}
	if len(rec.ChannelIDs) != 1 || rec.ChannelIDs[0] != "C1" {
		t.Errorf("ChannelIDs = %v, want [C1]", rec.ChannelIDs)
	}
}

func TestMapRigRemoveChannelsRepeatedFlag(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2,C3",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C2", "--remove-channels", "C3",
	); err != nil {
		t.Fatalf("--remove-channels repeat: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("record missing")
	}
	if len(rec.ChannelIDs) != 1 || rec.ChannelIDs[0] != "C1" {
		t.Errorf("ChannelIDs = %v, want [C1]", rec.ChannelIDs)
	}
}

func TestMapRigRemoveChannelsEmptyAfterDeletesRecord(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2",
	); err != nil {
		t.Fatal(err)
	}
	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C1,C2",
	)
	if err != nil {
		t.Fatalf("--remove-channels empty-after: %v", err)
	}
	if !strings.Contains(stdout, "Removed rig mapping alpha") {
		t.Errorf("stdout = %q, want substring 'Removed rig mapping alpha' (record deleted because channel set became empty)", stdout)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint after empty-after deletion: %q", stdout)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	if _, ok := reg.Get("T1", "alpha"); ok {
		t.Errorf("record should be deleted after channel set became empty")
	}
}

func TestMapRigRemoveChannelsIdempotentForUnknownChannels(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C99,C100",
	); err != nil {
		t.Fatalf("--remove-channels for unknown channels should be a silent no-op: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("record vanished")
	}
	if len(rec.ChannelIDs) != 1 || rec.ChannelIDs[0] != "C1" {
		t.Errorf("ChannelIDs = %v, want [C1] (unchanged)", rec.ChannelIDs)
	}
}

func TestMapRigRemoveChannelsMissingRigIsNoOp(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C1",
	)
	if err != nil {
		t.Fatalf("--remove-channels for missing rig should succeed (idempotent): %v", err)
	}
	if !strings.Contains(stdout, "alpha") {
		t.Errorf("stdout = %q, want substring 'alpha'", stdout)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
}

func TestMapRigRemoveChannelsWithRemoveIsError(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove", "--remove-channels", "C1",
	)
	if err == nil {
		t.Fatal("expected error for --remove with --remove-channels")
	}
}

func TestMapRigRemoveChannelsWithChannelIsError(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1", "--remove-channels", "C2",
	)
	if err == nil {
		t.Fatal("expected error for --channel with --remove-channels")
	}
}

func TestMapRigRemoveChannelsEmptyValueIsError(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "",
	)
	if err == nil {
		t.Fatal("expected error for --remove-channels with no non-empty values")
	}
}

func TestMapRigIdempotentReSetPreservesCreatedAt(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	reg1, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec1, _, _ := reg1.LookupRigForChannel("T1", "C1")
	createdAt := rec1.CreatedAt

	time.Sleep(2 * time.Millisecond)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2",
	); err != nil {
		t.Fatal(err)
	}
	reg2, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec2, _, _ := reg2.LookupRigForChannel("T1", "C1")
	if !rec2.CreatedAt.Equal(createdAt) {
		t.Errorf("CreatedAt advanced on re-set: was %v, now %v", createdAt, rec2.CreatedAt)
	}
	if !rec2.UpdatedAt.After(createdAt) {
		t.Errorf("UpdatedAt did not advance: %v vs %v", rec2.UpdatedAt, createdAt)
	}
}

// TestMapRigSlingTargetAndFixFormulaPersisted exercises the
// cby.18.a flags: --sling-target and --fix-formula are persisted on
// the rig record so the adapter's /slack/interactions handler can
// route without hardcoded role names.
func TestMapRigSlingTargetAndFixFormulaPersisted(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
		"--sling-target", "alpha/polecat",
		"--fix-formula", "mol-slack-fix-issue",
	); err != nil {
		t.Fatalf("map-rig with --sling-target/--fix-formula: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("missing record")
	}
	if rec.SlingTarget != "alpha/polecat" {
		t.Errorf("SlingTarget = %q, want alpha/polecat", rec.SlingTarget)
	}
	if rec.FixFormula != "mol-slack-fix-issue" {
		t.Errorf("FixFormula = %q, want mol-slack-fix-issue", rec.FixFormula)
	}
}

// TestMapRigInvalidSlingTargetIsRejected ensures the CLI refuses a
// malformed --sling-target before touching disk.
func TestMapRigInvalidSlingTargetIsRejected(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
		"--sling-target", "no-slash",
	)
	if err == nil {
		t.Fatal("expected error for malformed --sling-target, got nil")
	}
}

// TestMapRigPreservesSlingTargetOnReSet ensures an idempotent
// re-bind that omits --sling-target/--fix-formula keeps the previously
// stored values rather than clearing them.
func TestMapRigPreservesSlingTargetOnReSet(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
		"--sling-target", "alpha/polecat",
		"--fix-formula", "mol-slack-fix-issue",
	); err != nil {
		t.Fatal(err)
	}
	// Re-bind with new channel set, no --sling-target/--fix-formula.
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2",
	); err != nil {
		t.Fatalf("re-bind without flags: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, _ := reg.Get("T1", "alpha")
	if rec.SlingTarget != "alpha/polecat" {
		t.Errorf("SlingTarget cleared on re-bind: got %q", rec.SlingTarget)
	}
	if rec.FixFormula != "mol-slack-fix-issue" {
		t.Errorf("FixFormula cleared on re-bind: got %q", rec.FixFormula)
	}
}

// TestMapRigChannelPatternFlag covers the cby.22 surface: a rig
// can be bound by glob pattern alone (no literal --channel) and the
// result round-trips through the registry.
func TestMapRigChannelPatternFlag(t *testing.T) {
	cityRoot := newTestCity(t)
	stdout, stderr, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel-pattern", "oversight-*",
		"--channel-pattern", "team-?",
	)
	if err != nil {
		t.Fatalf("map-rig --channel-pattern: %v\nstderr=%s", err, stderr)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("stdout missing restart hint: %q", stdout)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("rig record missing")
	}
	if len(rec.ChannelIDs) != 0 {
		t.Errorf("ChannelIDs should be empty, got %v", rec.ChannelIDs)
	}
	want := []string{"oversight-*", "team-?"}
	if len(rec.ChannelPatterns) != len(want) ||
		rec.ChannelPatterns[0] != want[0] || rec.ChannelPatterns[1] != want[1] {
		t.Errorf("ChannelPatterns = %v, want %v", rec.ChannelPatterns, want)
	}
}

// TestMapRigChannelPatternCommaSeparated confirms the
// --channel-pattern flag accepts comma-separated values.
func TestMapRigChannelPatternCommaSeparated(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel-pattern", "oversight-*,team-?",
	); err != nil {
		t.Fatalf("map-rig comma-pattern: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, _ := reg.Get("T1", "alpha")
	if len(rec.ChannelPatterns) != 2 {
		t.Errorf("expected 2 patterns, got %v", rec.ChannelPatterns)
	}
}

// TestMapRigMixesChannelsAndPatterns confirms a rig can carry
// both literal --channel ids and --channel-pattern globs in a single
// invocation.
func TestMapRigMixesChannelsAndPatterns(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel", "C1",
		"--channel-pattern", "oversight-*",
	); err != nil {
		t.Fatalf("mix channels+patterns: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, _ := reg.Get("T1", "alpha")
	if len(rec.ChannelIDs) != 1 || rec.ChannelIDs[0] != "C1" {
		t.Errorf("ChannelIDs = %v, want [C1]", rec.ChannelIDs)
	}
	if len(rec.ChannelPatterns) != 1 || rec.ChannelPatterns[0] != "oversight-*" {
		t.Errorf("ChannelPatterns = %v, want [oversight-*]", rec.ChannelPatterns)
	}
	// Literal channel still resolves through inverted index.
	if _, _, ok := reg.LookupRigForChannel("T1", "C1"); !ok {
		t.Error("literal channel C1 should still resolve via byChannel")
	}
}

// TestMapRigRejectsMalformedPattern confirms invalid patterns are
// surfaced as CLI errors before disk write.
func TestMapRigRejectsMalformedPattern(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel-pattern", "Bad-Caps-*",
	)
	if err == nil {
		t.Fatal("expected error for uppercase pattern, got nil")
	}
}

// TestMapRigRequiresChannelOrPattern confirms invoking map-rig
// with neither --channel nor --channel-pattern (and not --remove) is
// rejected by the CLI rather than silently writing an empty record.
func TestMapRigRequiresChannelOrPattern(t *testing.T) {
	cityRoot := newTestCity(t)
	_, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
	)
	if err == nil {
		t.Fatal("expected error when neither --channel nor --channel-pattern supplied")
	}
}

// TestMapRigAddPatternsToExistingChannelsRig covers the
// incremental-migration path: a rig already exists with literal
// channels; operator re-binds with --channel-pattern only. Existing
// channels MUST be preserved (mirrors --sling-target preservation).
func TestMapRigAddPatternsToExistingChannelsRig(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel-pattern", "oversight-*",
	); err != nil {
		t.Fatalf("re-bind with patterns only: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("rig missing after re-bind")
	}
	if len(rec.ChannelIDs) != 2 || rec.ChannelIDs[0] != "C1" || rec.ChannelIDs[1] != "C2" {
		t.Errorf("ChannelIDs not preserved: %v", rec.ChannelIDs)
	}
	if len(rec.ChannelPatterns) != 1 || rec.ChannelPatterns[0] != "oversight-*" {
		t.Errorf("ChannelPatterns missing: %v", rec.ChannelPatterns)
	}
}

// TestMapRigAddChannelsToExistingPatternsRig covers the
// symmetric incremental path: a rig exists with patterns only;
// operator re-binds with --channel only. Existing patterns MUST be
// preserved.
func TestMapRigAddChannelsToExistingPatternsRig(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel-pattern", "oversight-*",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatalf("re-bind with channels only: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("rig missing after re-bind")
	}
	if len(rec.ChannelPatterns) != 1 || rec.ChannelPatterns[0] != "oversight-*" {
		t.Errorf("ChannelPatterns not preserved: %v", rec.ChannelPatterns)
	}
	if len(rec.ChannelIDs) != 1 || rec.ChannelIDs[0] != "C1" {
		t.Errorf("ChannelIDs missing: %v", rec.ChannelIDs)
	}
}

// TestMapRigRemoveChannelsKeepsPatterns confirms --remove-channels
// (literal-id removal) does not touch ChannelPatterns. Operators
// removing a literal id from a hybrid record should keep their globs.
func TestMapRigRemoveChannelsKeepsPatterns(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel", "C1,C2",
		"--channel-pattern", "oversight-*",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--remove-channels", "C1",
	); err != nil {
		t.Fatalf("remove-channels: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("rig should still exist after removing one literal")
	}
	if len(rec.ChannelIDs) != 1 || rec.ChannelIDs[0] != "C2" {
		t.Errorf("ChannelIDs = %v, want [C2]", rec.ChannelIDs)
	}
	if len(rec.ChannelPatterns) != 1 || rec.ChannelPatterns[0] != "oversight-*" {
		t.Errorf("ChannelPatterns = %v, want [oversight-*]", rec.ChannelPatterns)
	}
}

// TestMapRigRemoveAllLiteralsKeepsRecordWhenPatternsRemain
// confirms removing the last literal channel from a record that ALSO
// has patterns leaves the record intact (pattern-only is valid).
func TestMapRigRemoveAllLiteralsKeepsRecordWhenPatternsRemain(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel", "C1",
		"--channel-pattern", "oversight-*",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--remove-channels", "C1",
	); err != nil {
		t.Fatalf("remove last literal: %v", err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	rec, ok := reg.Get("T1", "alpha")
	if !ok {
		t.Fatal("rig should remain because patterns are still present")
	}
	if len(rec.ChannelIDs) != 0 {
		t.Errorf("ChannelIDs should be empty, got %v", rec.ChannelIDs)
	}
	if len(rec.ChannelPatterns) != 1 {
		t.Errorf("ChannelPatterns lost: %v", rec.ChannelPatterns)
	}
}

// TestMapRigRemoveChannelsDeletesRecordWhenAllEmpty confirms the
// existing "empty after removal → delete" behavior still triggers
// when there are no patterns to keep the record alive.
func TestMapRigRemoveChannelsDeletesRecordWhenAllEmpty(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1",
		"--remove-channels", "C1",
	); err != nil {
		t.Fatal(err)
	}
	reg, _ := rigs.NewRegistry(rigs.Path(cityRoot))
	if _, ok := reg.Get("T1", "alpha"); ok {
		t.Error("rig should be deleted when last literal removed and no patterns")
	}
}

// seedChannelMapping is a test helper that writes a channels.Record
// directly into the registry — used to seed the orphan-WARN tests
// without going through `gc slack map-channel`.
func seedChannelMapping(t *testing.T, cityRoot, workspaceID, channelID, targetKind, targetID string) {
	t.Helper()
	reg, err := channels.NewRegistry(channels.Path(cityRoot))
	if err != nil {
		t.Fatalf("open channel mapping registry: %v", err)
	}
	now := time.Now().UTC()
	if err := reg.Set(channels.Record{
		WorkspaceID: workspaceID, ChannelID: channelID,
		TargetKind: targetKind, TargetID: targetID,
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatalf("seed channel mapping: %v", err)
	}
}

// TestMapRigRemoveWarnsOnOrphanChannelMappings exercises the
// --remove path's symmetric notice for the channel-mapping registry:
// when a rig is removed but channel-level overrides still target it,
// stdout must surface the dangling bindings (gc-px8.8). The verify
// step is multi-orphan + sorted-list to lock in determinism.
func TestMapRigRemoveWarnsOnOrphanChannelMappings(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	// Two channel-level overrides explicitly target rig alpha,
	// inserted in non-sorted order so the WARN's stable ordering is
	// observable.
	seedChannelMapping(t, cityRoot, "T1", "C9", channels.TargetKindRig, "alpha")
	seedChannelMapping(t, cityRoot, "T1", "C2", channels.TargetKindRig, "alpha")

	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove with orphans should succeed (warn-only): %v", err)
	}
	if !strings.Contains(stdout, "Removed rig mapping alpha") {
		t.Errorf("missing remove-success line: %q", stdout)
	}
	if !strings.Contains(stdout, `WARN: 2 channel-mappings still target rig "alpha": C2, C9`) {
		t.Errorf("missing/malformed orphan WARN; stdout=%q", stdout)
	}
	if !strings.Contains(stdout, mapRigRestartHint) {
		t.Errorf("missing restart hint: %q", stdout)
	}
}

// TestMapRigRemoveSilentWhenNoOrphans confirms the WARN path is gated
// on actual orphans: a clean removal stays quiet on the
// channel-mapping registry side.
func TestMapRigRemoveSilentWhenNoOrphans(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove no orphans: %v", err)
	}
	if strings.Contains(stdout, "WARN") {
		t.Errorf("unexpected WARN on clean --remove: %q", stdout)
	}
}

// TestMapRigRemoveOrphanIsolatedByWorkspace checks that the WARN
// scans only orphans in the same workspace as the removed rig — a
// rig of the same name in workspace T2 must NOT pull T1 channels
// into the WARN list.
func TestMapRigRemoveOrphanIsolatedByWorkspace(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	// Orphan-shaped record exists, but in workspace T2 — must be
	// invisible to the T1 removal.
	seedChannelMapping(t, cityRoot, "T2", "C9", channels.TargetKindRig, "alpha")

	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove: %v", err)
	}
	if strings.Contains(stdout, "WARN") {
		t.Errorf("workspace-isolated WARN leaked: %q", stdout)
	}
}

// TestMapRigRemoveOrphanIgnoresSessionTarget confirms the WARN scans
// only TargetKind=="rig" entries; a session-tier override pointing at
// the rig's name is a different binding and must not be flagged.
func TestMapRigRemoveOrphanIgnoresSessionTarget(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1",
	); err != nil {
		t.Fatal(err)
	}
	// A session override uses target_kind="session"; even if its
	// target_id collides with the rig name, it's a different tier.
	seedChannelMapping(t, cityRoot, "T1", "C9", channels.TargetKindSession, "alpha")

	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove",
	)
	if err != nil {
		t.Fatalf("--remove: %v", err)
	}
	if strings.Contains(stdout, "WARN") {
		t.Errorf("session-target should not trigger rig orphan WARN: %q", stdout)
	}
}

// TestMapRigRemoveChannelsEmptyAfterWarnsOnOrphans exercises the
// --remove-channels path that empties the rig's channel set and
// deletes the record. The orphan WARN must fire on this path too.
func TestMapRigRemoveChannelsEmptyAfterWarnsOnOrphans(t *testing.T) {
	cityRoot := newTestCity(t)
	if _, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--channel", "C1,C2",
	); err != nil {
		t.Fatal(err)
	}
	seedChannelMapping(t, cityRoot, "T1", "C7", channels.TargetKindRig, "alpha")

	stdout, _, err := execMapRigCmd(t, cityRoot,
		"alpha", "--workspace-id", "T1", "--remove-channels", "C1,C2",
	)
	if err != nil {
		t.Fatalf("--remove-channels empty-after: %v", err)
	}
	if !strings.Contains(stdout, "Removed rig mapping alpha") {
		t.Errorf("missing remove-success line: %q", stdout)
	}
	if !strings.Contains(stdout, `WARN: 1 channel-mappings still target rig "alpha": C7`) {
		t.Errorf("missing/malformed orphan WARN on empty-after path; stdout=%q", stdout)
	}
}

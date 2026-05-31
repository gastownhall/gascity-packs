package main

import (
	"log"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestRigMappingRegistryRoundTripWithSlingTargetAndFixFormula pins the
// new fields (cby.18.a) — round-trip on disk preserves the values
// written by `gc slack map-rig --sling-target ... --fix-formula ...`.
func TestRigMappingRegistryRoundTripWithSlingTargetAndFixFormula(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	rec := rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "alpha/polecat",
		FixFormula:  "mol-slack-fix-issue",
		CreatedAt:   now, UpdatedAt: now,
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}
	reg2, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	got, _, ok := reg2.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatal("LookupRigForChannel ok=false after reload")
	}
	if got.SlingTarget != "alpha/polecat" {
		t.Errorf("SlingTarget = %q, want alpha/polecat", got.SlingTarget)
	}
	if got.FixFormula != "mol-slack-fix-issue" {
		t.Errorf("FixFormula = %q, want mol-slack-fix-issue", got.FixFormula)
	}
}

// TestRigMappingRegistryLoadsLegacyRecord covers the tolerance
// contract: a legacy rig_mappings.json with no sling_target /
// fix_formula keys must still load.
func TestRigMappingRegistryLoadsLegacyRecord(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	legacy := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":["C1"],"created_at":"2025-01-01T00:00:00Z","updated_at":"2025-01-01T00:00:00Z"}}`
	if err := os.WriteFile(path, []byte(legacy), 0o600); err != nil {
		t.Fatal(err)
	}
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatalf("legacy record load: %v", err)
	}
	rec, _, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatal("legacy record missing")
	}
	if rec.SlingTarget != "" || rec.FixFormula != "" {
		t.Errorf("expected empty sling_target/fix_formula on legacy record, got %q / %q",
			rec.SlingTarget, rec.FixFormula)
	}
}

// TestResolveSlingTargetReturnsErrorWhenSlingTargetEmpty exercises the
// resolution-time error contract: legacy records (or partially-
// configured rigs) MUST surface a fix-it message rather than route to
// an empty target.
func TestResolveSlingTargetReturnsErrorWhenSlingTargetEmpty(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
		// no SlingTarget — simulate legacy record
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	_, _, err = reg.ResolveSlingTarget("T1", "alpha")
	if err == nil {
		t.Fatal("expected error when sling_target is empty, got nil")
	}
	msg := err.Error()
	for _, want := range []string{"sling target", "gc slack map-rig", "--sling-target"} {
		if !strings.Contains(msg, want) {
			t.Errorf("error %q missing substring %q", msg, want)
		}
	}
}

// TestResolveSlingTargetSucceedsForConfiguredRig pins the success path:
// when sling_target is present, ResolveSlingTarget returns it (and the
// optional fix_formula default).
func TestResolveSlingTargetSucceedsForConfiguredRig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "alpha/polecat",
		FixFormula:  "mol-slack-fix-issue",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	target, fixFormula, err := reg.ResolveSlingTarget("T1", "alpha")
	if err != nil {
		t.Fatalf("ResolveSlingTarget: %v", err)
	}
	if target != "alpha/polecat" {
		t.Errorf("target = %q, want alpha/polecat", target)
	}
	if fixFormula != "mol-slack-fix-issue" {
		t.Errorf("fixFormula = %q, want mol-slack-fix-issue", fixFormula)
	}
}

// TestResolveSlingTargetReturnsErrorForUnknownRig pins the
// not-found path so the dispatch handler can surface a clear "no rig
// mapping" error rather than a zero-value silent success.
func TestResolveSlingTargetReturnsErrorForUnknownRig(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := reg.ResolveSlingTarget("T1", "ghost"); err == nil {
		t.Fatal("expected error for unknown rig, got nil")
	}
}

// TestRigMappingRegistryParsesChannelPatterns confirms the adapter
// tolerates the new channel_patterns field — without explicit parsing,
// DisallowUnknownFields would reject every file written by the new CLI.
func TestRigMappingRegistryParsesChannelPatterns(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	now := time.Now().UTC().Format(time.RFC3339Nano)
	contents := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":["C1"],"channel_patterns":["oversight-*","team-?"],"created_at":"` + now + `","updated_at":"` + now + `"}}`
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	rec, _, ok := reg.LookupRigForChannel("T1", "C1")
	if !ok {
		t.Fatal("literal channel resolution lost")
	}
	if len(rec.ChannelPatterns) != 2 {
		t.Errorf("ChannelPatterns = %v, want 2 entries", rec.ChannelPatterns)
	}
}

// TestRigMappingRegistryLoadsPatternOnlyRecord confirms a record with
// channel_patterns and EMPTY channel_ids still loads — the relaxed
// "either-or" invariant introduced by gc-cby.22.
func TestRigMappingRegistryLoadsPatternOnlyRecord(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	now := time.Now().UTC().Format(time.RFC3339Nano)
	contents := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":[],"channel_patterns":["oversight-*"],"created_at":"` + now + `","updated_at":"` + now + `"}}`
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := newRigMappingRegistry(path); err != nil {
		t.Fatalf("pattern-only load: %v", err)
	}
}

// TestRigMappingRegistryRejectsZeroOfBothOnLoad confirms the relaxed
// invariant still rejects records with no channels AND no patterns —
// loosening "channel_ids ≥ 1" all the way to "anything goes" would
// allow corrupt or partially-deleted files to load silently.
func TestRigMappingRegistryRejectsZeroOfBothOnLoad(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	now := time.Now().UTC().Format(time.RFC3339Nano)
	contents := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":[],"channel_patterns":[],"created_at":"` + now + `","updated_at":"` + now + `"}}`
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := newRigMappingRegistry(path); err == nil {
		t.Fatal("expected load error for zero-of-both, got nil")
	}
}

// TestRigMappingRegistryRejectsMalformedPatternOnLoad confirms a
// hand-edited pattern that escapes the Slack channel-name charset
// (uppercase, slash, etc.) is rejected at load — symmetric with the
// CLI write-time validation.
func TestRigMappingRegistryRejectsMalformedPatternOnLoad(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	now := time.Now().UTC().Format(time.RFC3339Nano)
	contents := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":[],"channel_patterns":["Oversight-BAD"],"created_at":"` + now + `","updated_at":"` + now + `"}}`
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := newRigMappingRegistry(path); err == nil {
		t.Fatal("expected load error for malformed pattern, got nil")
	}
}

// TestRigMappingRegistrySetNormalisesPatterns confirms Set sorts and
// deduplicates ChannelPatterns before storing — byKey[k].ChannelPatterns
// must agree with PatternsForRig so callers reading either path see the
// same ordering. (Adapter Set is test-only, but operator-written files
// flow through parseRigMappingRegistry which already normalises; this
// pins the in-process write path symmetrically.)
func TestRigMappingRegistrySetNormalisesPatterns(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	if err := reg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelPatterns: []string{"zeta-*", "alpha-*", "alpha-*", "", "beta-?"},
		CreatedAt:       now, UpdatedAt: now,
	}); err != nil {
		t.Fatalf("Set: %v", err)
	}
	indexed := reg.PatternsForRig("T1", "alpha")
	want := []string{"alpha-*", "beta-?", "zeta-*"}
	if len(indexed) != len(want) {
		t.Fatalf("indexed = %v, want %v", indexed, want)
	}
	// PatternsForRig and the record must agree.
	rec, _, _ := reg.LookupRigForChannel("T1", "C-not-bound")
	_ = rec // record-by-channel lookup misses; pull from byKey via Reload.
	// Reload from disk to verify the persisted record is also normalised.
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}
	indexed2 := reg.PatternsForRig("T1", "alpha")
	for i, w := range want {
		if indexed[i] != w || indexed2[i] != w {
			t.Errorf("pattern[%d]: in-memory=%q reloaded=%q want=%q", i, indexed[i], indexed2[i], w)
		}
	}
}

// TestRigMappingSnapshotAtomicallySwapsPatternIndex pins the SIGHUP-
// reload contract: when a Stage/Commit cycle introduces a new pattern
// set, the in-memory pattern index swaps atomically alongside byKey
// and byChannel — readers never observe a mismatched state.
func TestRigMappingSnapshotAtomicallySwapsPatternIndex(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	// Initial state: literal-only.
	v1 := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":["C1"],"created_at":"` + now + `","updated_at":"` + now + `"}}`
	if err := os.WriteFile(path, []byte(v1), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload v1: %v", err)
	}
	if got := reg.PatternsForRig("T1", "alpha"); len(got) != 0 {
		t.Errorf("v1 patterns = %v, want empty", got)
	}

	// Updated state: add patterns.
	v2 := `{"T1:alpha":{"workspace_id":"T1","rig_name":"alpha","channel_ids":["C1"],"channel_patterns":["oversight-*"],"created_at":"` + now + `","updated_at":"` + now + `"}}`
	if err := os.WriteFile(path, []byte(v2), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload v2: %v", err)
	}
	got := reg.PatternsForRig("T1", "alpha")
	if len(got) != 1 || got[0] != "oversight-*" {
		t.Errorf("v2 patterns = %v, want [oversight-*]", got)
	}

	// Reverting drops patterns again.
	if err := os.WriteFile(path, []byte(v1), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload v1 again: %v", err)
	}
	if got := reg.PatternsForRig("T1", "alpha"); len(got) != 0 {
		t.Errorf("v1-revert patterns = %v, want empty", got)
	}
}

// helper used by the LookupRigForChannelName tests below to populate a
// fresh registry with a record. Keeps the table-style tests terse.
func setRig(t *testing.T, reg *rigMappingRegistry, workspace, rig string, channelIDs, patterns []string) {
	t.Helper()
	now := time.Now().UTC()
	if err := reg.Set(rigMappingDiskRecord{
		WorkspaceID:     workspace,
		RigName:         rig,
		ChannelIDs:      channelIDs,
		ChannelPatterns: patterns,
		CreatedAt:       now, UpdatedAt: now,
	}); err != nil {
		t.Fatalf("Set %s/%s: %v", workspace, rig, err)
	}
}

// TestLookupRigForChannelNameLiteralWinsOverPattern pins the precedence
// contract: when a literal channel-ID hit and a pattern hit both exist
// for the same channel, the literal hit wins (cby.22 design — existing
// behaviour is unchanged).
func TestLookupRigForChannelNameLiteralWinsOverPattern(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "literalrig", []string{"C1"}, nil)
	setRig(t, reg, "T1", "patternrig", nil, []string{"oversight-*"})

	rec, src, ok := reg.LookupRigForChannelName("T1", "C1", "oversight-platform")
	if !ok {
		t.Fatal("ok=false; literal should have hit")
	}
	if src != "rig" {
		t.Errorf("source = %q, want rig", src)
	}
	if rec.RigName != "literalrig" {
		t.Errorf("RigName = %q, want literalrig (literal beats pattern)", rec.RigName)
	}
}

// TestLookupRigForChannelNamePatternHitWhenLiteralMisses pins tier 3:
// no literal channel-ID hit, but the channel name matches a registered
// pattern → returned with source="rig-pattern".
func TestLookupRigForChannelNamePatternHitWhenLiteralMisses(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "oversight", nil, []string{"oversight-*"})

	rec, src, ok := reg.LookupRigForChannelName("T1", "C-UNBOUND", "oversight-platform")
	if !ok {
		t.Fatal("ok=false; pattern should have hit")
	}
	if src != "rig-pattern" {
		t.Errorf("source = %q, want rig-pattern", src)
	}
	if rec.RigName != "oversight" {
		t.Errorf("RigName = %q, want oversight", rec.RigName)
	}
}

// TestLookupRigForChannelNameEmptyNameSkipsPatterns confirms the
// resolver does NOT consult patterns when the caller has no channel
// name in hand. Mirrors the legacy LookupRigForChannel behaviour.
func TestLookupRigForChannelNameEmptyNameSkipsPatterns(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "oversight", nil, []string{"*"})

	if _, src, ok := reg.LookupRigForChannelName("T1", "C-UNBOUND", ""); ok {
		t.Errorf("ok=true with empty channelName; pattern matching must be gated on a non-empty name. src=%q", src)
	}
}

// TestLookupRigForChannelNameLongestMatchWins pins the conflict policy:
// when multiple patterns match, the longer pattern beats the shorter.
// Rationale: longer patterns are more specific and must take precedence
// so an operator can carve a sub-namespace out of a coarser claim.
func TestLookupRigForChannelNameLongestMatchWins(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "broad", nil, []string{"oversight-*"})
	setRig(t, reg, "T1", "narrow", nil, []string{"oversight-platform-*"})

	rec, src, ok := reg.LookupRigForChannelName("T1", "C-X", "oversight-platform-deploys")
	if !ok {
		t.Fatal("ok=false")
	}
	if src != "rig-pattern" {
		t.Errorf("source = %q, want rig-pattern", src)
	}
	if rec.RigName != "narrow" {
		t.Errorf("RigName = %q, want narrow (longest pattern wins)", rec.RigName)
	}
}

// TestLookupRigForChannelNameLexicalTiebreak pins the secondary rule:
// equal-length matches break by lexical pattern order ascending. Without
// this rule, multi-match resolution would be non-deterministic across
// map iteration order.
func TestLookupRigForChannelNameLexicalTiebreak(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "zeta", nil, []string{"team-z-*"})
	setRig(t, reg, "T1", "alpha", nil, []string{"team-a-*"})
	// Both patterns are length 8 and both match "team-?-anything". Use a
	// channel name that lex-sorts under both.
	setRig(t, reg, "T1", "beta", nil, []string{"team-?-x"})

	// With channel-name "team-a-x" patterns "team-a-*" (len 8) and
	// "team-?-x" (len 8) both match. Lex order ascending: "team-?-x"
	// (? < a) wins.
	rec, _, ok := reg.LookupRigForChannelName("T1", "C-X", "team-a-x")
	if !ok {
		t.Fatal("ok=false")
	}
	if rec.RigName != "beta" {
		t.Errorf("RigName = %q, want beta (lex tiebreak: ? < a)", rec.RigName)
	}
}

// TestLookupRigForChannelNameLogsMultiMatchConflict pins the operator
// observability requirement: when 2+ patterns match, the resolver MUST
// log a WARN that names every match so the conflict is visible in
// adapter logs even though the runtime result is deterministic.
func TestLookupRigForChannelNameLogsMultiMatchConflict(t *testing.T) {
	var logs strings.Builder
	prevOut := log.Writer()
	log.SetOutput(&logs)
	t.Cleanup(func() { log.SetOutput(prevOut) })

	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "broad", nil, []string{"oversight-*"})
	setRig(t, reg, "T1", "narrow", nil, []string{"oversight-platform-*"})

	if _, _, ok := reg.LookupRigForChannelName("T1", "C-X", "oversight-platform-deploys"); !ok {
		t.Fatal("ok=false")
	}
	out := logs.String()
	if !strings.Contains(out, "WARN") || !strings.Contains(out, "channel_patterns") {
		t.Errorf("expected multi-match WARN in logs, got: %s", out)
	}
	if !strings.Contains(out, "oversight-*") || !strings.Contains(out, "oversight-platform-*") {
		t.Errorf("expected both patterns named in WARN, got: %s", out)
	}
}

// TestLookupRigForChannelNameSingleMatchDoesNotWarn keeps the WARN
// signal high-information. A single match is the happy path; logging it
// at WARN would drown out the actual conflict warnings.
func TestLookupRigForChannelNameSingleMatchDoesNotWarn(t *testing.T) {
	var logs strings.Builder
	prevOut := log.Writer()
	log.SetOutput(&logs)
	t.Cleanup(func() { log.SetOutput(prevOut) })

	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "oversight", nil, []string{"oversight-*"})

	if _, _, ok := reg.LookupRigForChannelName("T1", "C-X", "oversight-platform"); !ok {
		t.Fatal("ok=false")
	}
	if strings.Contains(logs.String(), "WARN") {
		t.Errorf("single match should not emit WARN; got: %s", logs.String())
	}
}

// TestLookupRigForChannelNameWorkspaceScoped pins multi-tenant
// isolation: a pattern registered under workspace T1 must NOT match a
// channel name under workspace T2 even when names are identical.
func TestLookupRigForChannelNameWorkspaceScoped(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "oversight", nil, []string{"oversight-*"})

	if _, _, ok := reg.LookupRigForChannelName("T2", "C-X", "oversight-platform"); ok {
		t.Errorf("pattern leaked across workspace boundary")
	}
}

// TestLookupRigForChannelNameNoMatch covers the unbound case — neither
// literal nor pattern hits — and confirms the (zero, "", false) shape.
func TestLookupRigForChannelNameNoMatch(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rig_mappings.json")
	reg, err := newRigMappingRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	setRig(t, reg, "T1", "oversight", nil, []string{"oversight-*"})

	rec, src, ok := reg.LookupRigForChannelName("T1", "C-X", "ops-platform")
	if ok {
		t.Errorf("ok=true on unrelated channel; got rec=%+v src=%q", rec, src)
	}
	if src != "" {
		t.Errorf("source on miss = %q, want empty", src)
	}
}

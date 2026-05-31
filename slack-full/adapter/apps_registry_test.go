package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// TestAppsRegistryLoadMissingFile — tolerant load when apps.json doesn't exist.
// Mirrors identityRegistry semantics so adapter restarts on a fresh city
// (no apps imported yet) succeed instead of fatal.
func TestAppsRegistryLoadMissingFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "apps.json")
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry on missing file: %v", err)
	}
	if reg == nil {
		t.Fatal("newAppsRegistry returned nil")
	}
	if got := reg.GetByTeamID("T1"); len(got) != 0 {
		t.Errorf("GetByTeamID on empty registry = %v, want empty", got)
	}
}

func writeAppsRegistryFile(t *testing.T, dir string, recs map[string]appRecord) string {
	t.Helper()
	path := filepath.Join(dir, "apps.json")
	data, err := json.MarshalIndent(recs, "", "  ")
	if err != nil {
		t.Fatalf("marshal apps registry seed: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write apps registry seed: %v", err)
	}
	return path
}

func TestAppsRegistryLoadAndGetByTeamID(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "secret-a1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "secret-a2"},
		"T2:A3": {WorkspaceID: "T2", AppID: "A3", SigningSecret: "secret-a3"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	got := reg.GetByTeamID("T1")
	if len(got) != 2 {
		t.Fatalf("GetByTeamID(T1) returned %d records, want 2", len(got))
	}
	seen := map[string]bool{}
	for _, rec := range got {
		seen[rec.AppID] = true
	}
	if !seen["A1"] || !seen["A2"] {
		t.Errorf("GetByTeamID(T1) missing A1/A2: %v", got)
	}

	t2 := reg.GetByTeamID("T2")
	if len(t2) != 1 || t2[0].AppID != "A3" {
		t.Errorf("GetByTeamID(T2) = %v, want single A3", t2)
	}

	if got := reg.GetByTeamID("T_UNKNOWN"); len(got) != 0 {
		t.Errorf("GetByTeamID(unknown) = %v, want empty", got)
	}
}

// TestLookupSigningSecretsByTeam — registry has 3 apps for T1, one with empty
// signing_secret (post-import but pre-OAuth). Lookup must return the 2 with
// non-empty secrets and skip the empty one — empty signing_secret is "OAuth
// hasn't run yet", not an error.
func TestLookupSigningSecretsByTeam(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "secret-a1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: ""},
		"T1:A3": {WorkspaceID: "T1", AppID: "A3", SigningSecret: "secret-a3"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	got := lookupSigningSecrets(reg, "env-fallback", "T1")
	// Registry has matches with non-empty secrets — env fallback NOT used.
	if len(got) != 2 {
		t.Fatalf("lookupSigningSecrets returned %d, want 2: %v", len(got), got)
	}
	seen := map[string]bool{}
	for _, s := range got {
		seen[s] = true
	}
	if !seen["secret-a1"] || !seen["secret-a3"] {
		t.Errorf("lookupSigningSecrets missing secret-a1/secret-a3: %v", got)
	}
	if seen["env-fallback"] {
		t.Errorf("lookupSigningSecrets included env fallback when registry had matches: %v", got)
	}
}

func TestLookupSigningSecretsFallsBackToEnvWhenRegistryNil(t *testing.T) {
	got := lookupSigningSecrets(nil, "env-secret", "T1")
	if len(got) != 1 || got[0] != "env-secret" {
		t.Errorf("lookupSigningSecrets(nil) = %v, want [env-secret]", got)
	}
}

func TestLookupSigningSecretsFallsBackToEnvOnTeamMiss(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T2:A3": {WorkspaceID: "T2", AppID: "A3", SigningSecret: "secret-a3"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	got := lookupSigningSecrets(reg, "env-secret", "T1")
	if len(got) != 1 || got[0] != "env-secret" {
		t.Errorf("lookupSigningSecrets(team-miss) = %v, want [env-secret]", got)
	}
}

// TestLookupSigningSecretsFallsBackToEnvWhenAllRegistryRecordsEmpty — a
// matching team has only post-import-pre-OAuth records (empty
// signing_secret). Treat as "no usable registry secret for this team" and
// fall through to env, instead of yielding an empty candidate list.
func TestLookupSigningSecretsFallsBackToEnvWhenAllRegistryRecordsEmpty(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: ""},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	got := lookupSigningSecrets(reg, "env-secret", "T1")
	if len(got) != 1 || got[0] != "env-secret" {
		t.Errorf("lookupSigningSecrets(all-empty) = %v, want [env-secret]", got)
	}
}

func TestLookupSigningSecretsNoneAvailable(t *testing.T) {
	got := lookupSigningSecrets(nil, "", "T1")
	if len(got) != 0 {
		t.Errorf("lookupSigningSecrets(no env, no reg) = %v, want empty", got)
	}
}

// TestLookupSigningSecretsEmptyTeamIDFallsBackToEnv — no team_id parsed
// from body (e.g. legitimately-truncated event). Skip registry lookup
// (key would be empty) and use env. Single-app dev installs still work;
// multi-app installs reject with 401 if env is also empty.
func TestLookupSigningSecretsEmptyTeamIDFallsBackToEnv(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "secret-a1"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	got := lookupSigningSecrets(reg, "env-secret", "")
	if len(got) != 1 || got[0] != "env-secret" {
		t.Errorf("lookupSigningSecrets(empty team) = %v, want [env-secret]", got)
	}
}

// TestAppsRegistryConcurrentReads exercises RLock semantics. A pile of
// concurrent GetByTeamID calls must neither deadlock nor return torn
// state. Run with -race for full value.
func TestAppsRegistryConcurrentReads(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "secret-a1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "secret-a2"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	const readers = 32
	var wg sync.WaitGroup
	wg.Add(readers)
	for i := 0; i < readers; i++ {
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				got := reg.GetByTeamID("T1")
				if len(got) != 2 {
					t.Errorf("concurrent GetByTeamID got %d records, want 2", len(got))
					return
				}
			}
		}()
	}
	wg.Wait()
}

// TestAppsRegistryLoadRejectsOversizedFile pins the 10 MiB cap. Without
// the LimitReader the read would allocate the full hostile payload before
// failing; the test guarantees the cap is enforced and the error mentions
// the size violation.
func TestAppsRegistryLoadRejectsOversizedFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "apps.json")
	payload := strings.Repeat("x", maxRegistryBytes+1)
	if err := os.WriteFile(path, []byte(payload), 0o600); err != nil {
		t.Fatalf("seed oversized file: %v", err)
	}
	_, err := newAppsRegistry(path)
	if err == nil {
		t.Fatal("newAppsRegistry on oversized file: want error, got nil")
	}
	if !strings.Contains(err.Error(), "exceeds") {
		t.Errorf("error %q does not mention size cap", err)
	}
}

// TestAppsRegistryReloadPicksUpNewRecords — gc-cby.23: after the CLI
// (`gc slack import-app` or post-OAuth callback) rewrites apps.json, a
// SIGHUP-driven Reload must surface the new records without restarting
// the adapter binary.
func TestAppsRegistryReloadPicksUpNewRecords(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "old-secret"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	if got := reg.Len(); got != 1 {
		t.Fatalf("initial Len = %d, want 1", got)
	}

	// CLI rewrites apps.json with a new record + secret rotation on the
	// existing one.
	data, err := json.MarshalIndent(map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "rotated-secret"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "new-secret"},
	}, "", "  ")
	if err != nil {
		t.Fatalf("marshal new file: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("rewrite apps.json: %v", err)
	}

	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}
	if got := reg.Len(); got != 2 {
		t.Errorf("post-Reload Len = %d, want 2", got)
	}
	got := reg.GetByTeamID("T1")
	if len(got) != 2 {
		t.Fatalf("post-Reload GetByTeamID(T1) returned %d, want 2", len(got))
	}
	for _, rec := range got {
		if rec.AppID == "A1" && rec.SigningSecret != "rotated-secret" {
			t.Errorf("A1 secret = %q after Reload, want rotated-secret", rec.SigningSecret)
		}
	}
}

// TestAppsRegistryReloadHandlesDeletedRecords — when apps.json is
// rewritten with a record removed, Reload drops it from in-memory state.
func TestAppsRegistryReloadHandlesDeletedRecords(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "s1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "s2"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	// Rewrite with A2 removed.
	data, _ := json.MarshalIndent(map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "s1"},
	}, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("rewrite: %v", err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}
	if got := reg.Len(); got != 1 {
		t.Errorf("post-Reload Len = %d, want 1", got)
	}
}

// TestAppsRegistryReloadEmptyJSONClearsState — operators clear the
// registry by writing `{}`, NOT by removing the file. This documents the
// missing-file vs empty-object distinction in Reload semantics.
func TestAppsRegistryReloadEmptyJSONClearsState(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "s1"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	if err := os.WriteFile(path, []byte("{}"), 0o600); err != nil {
		t.Fatalf("write empty: %v", err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload: %v", err)
	}
	if got := reg.Len(); got != 0 {
		t.Errorf("post-Reload Len after `{}` = %d, want 0 (empty JSON clears)", got)
	}
}

// TestAppsRegistryReloadOnMissingFileIsNoop — missing file means "no
// change," NOT "clear state." Operators who `rm apps.json` then SIGHUP
// keep their old in-memory bindings (paranoid default — rm is more
// likely a mistake than a deliberate clear).
func TestAppsRegistryReloadOnMissingFileIsNoop(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "preserved"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	if err := os.Remove(path); err != nil {
		t.Fatalf("rm: %v", err)
	}
	if err := reg.Reload(); err != nil {
		t.Fatalf("Reload on missing file should be a no-op, got err: %v", err)
	}
	got := reg.GetByTeamID("T1")
	if len(got) != 1 || got[0].SigningSecret != "preserved" {
		t.Errorf("post-Reload state = %v, want preserved single A1 record", got)
	}
}

// TestAppsRegistryReloadOnCorruptFilePreservesState — Reload on a
// corrupt/oversized file must return an error AND leave the live state
// intact. This is the all-or-nothing guarantee that reloadAllRegistries
// builds on for cross-registry atomicity.
func TestAppsRegistryReloadOnCorruptFilePreservesState(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "preserved"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	if err := os.WriteFile(path, []byte("not valid json {"), 0o600); err != nil {
		t.Fatalf("write corrupt: %v", err)
	}
	if err := reg.Reload(); err == nil {
		t.Fatal("Reload on corrupt file: want error, got nil")
	}
	// State must be unchanged.
	got := reg.GetByTeamID("T1")
	if len(got) != 1 || got[0].SigningSecret != "preserved" {
		t.Errorf("post-failed-Reload state = %v, want preserved single A1 record (Reload error must NOT corrupt live state)", got)
	}
}

// TestAppsRegistryStageDoesNotMutate — Stage parses without committing.
// Repeated calls must not affect live state.
func TestAppsRegistryStageDoesNotMutate(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "live"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	// Rewrite the file with different content.
	data, _ := json.MarshalIndent(map[string]appRecord{
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "staged"},
	}, "", "  ")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("rewrite: %v", err)
	}
	snap, err := reg.Stage()
	if err != nil {
		t.Fatalf("Stage: %v", err)
	}
	if snap == nil {
		t.Fatal("Stage on present file returned nil snapshot")
	}
	// Live state must still be the original A1.
	got := reg.GetByTeamID("T1")
	if len(got) != 1 || got[0].AppID != "A1" {
		t.Errorf("post-Stage live state = %v, want unchanged A1 (Stage must not mutate)", got)
	}
	// After Commit, state reflects the staged file.
	reg.Commit(snap)
	got = reg.GetByTeamID("T1")
	if len(got) != 1 || got[0].AppID != "A2" {
		t.Errorf("post-Commit state = %v, want A2 from staged file", got)
	}
}

// TestAppsRegistryReloadConcurrentReadsSafe — Reload swap under the
// write lock must not race with concurrent GetByTeamID readers. Run
// with -race to catch lock-omission bugs.
func TestAppsRegistryReloadConcurrentReadsSafe(t *testing.T) {
	dir := t.TempDir()
	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "v1"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}

	stop := make(chan struct{})
	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-stop:
					return
				default:
					_ = reg.GetByTeamID("T1")
				}
			}
		}()
	}

	for i := 0; i < 50; i++ {
		secret := "v" + strings.Repeat("x", i%4+1)
		data, _ := json.MarshalIndent(map[string]appRecord{
			"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: secret},
		}, "", "  ")
		if err := os.WriteFile(path, data, 0o600); err != nil {
			t.Fatalf("rewrite: %v", err)
		}
		if err := reg.Reload(); err != nil {
			t.Fatalf("Reload iteration %d: %v", i, err)
		}
	}
	close(stop)
	wg.Wait()
}

// TestAppsRegistryLen exposes the entry count to the startup log so
// operators see "registry loaded empty" cases immediately. The startup
// log uses Len() to print entries=N alongside the store path.
func TestAppsRegistryLen(t *testing.T) {
	dir := t.TempDir()
	emptyReg, err := newAppsRegistry(filepath.Join(dir, "missing.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry empty: %v", err)
	}
	if got := emptyReg.Len(); got != 0 {
		t.Errorf("empty registry Len = %d, want 0", got)
	}

	path := writeAppsRegistryFile(t, dir, map[string]appRecord{
		"T1:A1": {WorkspaceID: "T1", AppID: "A1", SigningSecret: "s1"},
		"T1:A2": {WorkspaceID: "T1", AppID: "A2", SigningSecret: "s2"},
		"T2:A3": {WorkspaceID: "T2", AppID: "A3", SigningSecret: "s3"},
	})
	reg, err := newAppsRegistry(path)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	if got := reg.Len(); got != 3 {
		t.Errorf("Len = %d, want 3", got)
	}
}

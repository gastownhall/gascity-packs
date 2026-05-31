package cmd

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// usergroupsListStub returns an httptest server that answers
// usergroups.list with the supplied response body and records how many
// times it was hit. Non-usergroups.list paths 404 so a wrong endpoint
// fails loudly.
func usergroupsListStub(t *testing.T, respBody string) (*httptest.Server, *int) {
	t.Helper()
	hits := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/"+slackUsergroupsListMethod) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		hits++
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(respBody))
	}))
	t.Cleanup(srv.Close)
	return srv, &hits
}

// stageCity points GC_CITY_PATH at a fresh temp city (with a .gc marker
// so ResolveCityPath accepts it) and returns the city path plus the
// subteam-aliases.json path beneath it. When seed is non-nil it is
// written as the pre-existing file.
func stageCity(t *testing.T, seed map[string]string) (cityPath, aliasPath string) {
	t.Helper()
	cityPath = t.TempDir()
	if err := os.MkdirAll(filepath.Join(cityPath, ".gc", "slack"), 0o700); err != nil {
		t.Fatalf("mkdir city: %v", err)
	}
	t.Setenv(cityPathEnv, cityPath)
	aliasPath = filepath.Join(cityPath, ".gc", "slack", subteamAliasesFilename)
	if seed != nil {
		data, err := json.MarshalIndent(seed, "", "  ")
		if err != nil {
			t.Fatalf("marshal seed: %v", err)
		}
		if err := os.WriteFile(aliasPath, data, 0o600); err != nil {
			t.Fatalf("write seed: %v", err)
		}
	}
	return cityPath, aliasPath
}

func readAliasFile(t *testing.T, path string) map[string]string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read alias file: %v", err)
	}
	var m map[string]string
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("decode alias file %q: %v", string(data), err)
	}
	return m
}

// TestSyncSubteamAliasesHappyPath: three live User Groups, no existing
// file → three entries written.
func TestSyncSubteamAliasesHappyPath(t *testing.T) {
	srv, hits := usergroupsListStub(t, `{
		"ok": true,
		"usergroups": [
			{"id": "S001", "team_id": "T1", "handle": "mayor", "name": "Mayor"},
			{"id": "S002", "team_id": "T1", "handle": "cos", "name": "Chief of Staff"},
			{"id": "S003", "team_id": "T1", "handle": "zelda-pl", "name": "Zelda Polecats"}
		]
	}`)
	_, aliasPath := stageCity(t, nil)

	var out bytes.Buffer
	opts := subteamSyncOpts{
		workspaceID: "T1",
		token:       "xoxb-test",
		apiBase:     srv.URL,
		output:      "json",
		timeout:     defaultTestTimeout(),
	}
	if err := runSlackSyncSubteamAliases(context.Background(), &out, opts); err != nil {
		t.Fatalf("run: %v", err)
	}
	if *hits != 1 {
		t.Errorf("usergroups.list hits = %d, want 1", *hits)
	}

	got := readAliasFile(t, aliasPath)
	want := map[string]string{"S001": "mayor", "S002": "cos", "S003": "zelda-pl"}
	if len(got) != len(want) {
		t.Fatalf("wrote %d entries, want %d (%v)", len(got), len(want), got)
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("entry %s = %q, want %q", k, got[k], v)
		}
	}

	var env subteamSyncEnvelope
	if err := json.Unmarshal(out.Bytes(), &env); err != nil {
		t.Fatalf("decode json envelope: %v", err)
	}
	if !env.WriteIssued {
		t.Errorf("WriteIssued = false, want true")
	}
	if len(env.Diff.Added) != 3 {
		t.Errorf("Added = %d, want 3", len(env.Diff.Added))
	}
	if env.Total != 3 {
		t.Errorf("Total = %d, want 3", env.Total)
	}
}

// TestSyncSubteamAliasesMissingScope: an ok:false missing_scope response
// becomes a readable error that names the needed scope and writes
// nothing.
func TestSyncSubteamAliasesMissingScope(t *testing.T) {
	srv, _ := usergroupsListStub(t, `{
		"ok": false,
		"error": "missing_scope",
		"needed": "usergroups:read",
		"provided": "chat:write,commands"
	}`)
	_, aliasPath := stageCity(t, nil)

	var out bytes.Buffer
	opts := subteamSyncOpts{
		workspaceID: "T1",
		token:       "xoxb-test",
		apiBase:     srv.URL,
		output:      "text",
		timeout:     defaultTestTimeout(),
	}
	err := runSlackSyncSubteamAliases(context.Background(), &out, opts)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	msg := err.Error()
	if !strings.Contains(msg, "missing_scope") {
		t.Errorf("error %q does not mention missing_scope", msg)
	}
	if !strings.Contains(msg, "usergroups:read") {
		t.Errorf("error %q does not name the needed scope", msg)
	}
	if _, statErr := os.Stat(aliasPath); !os.IsNotExist(statErr) {
		t.Errorf("alias file was written on missing_scope failure (stat err = %v)", statErr)
	}
}

// TestSyncSubteamAliasesMergePreservesUnrelatedKeys: a pre-existing file
// has a hand-added entry whose id is NOT in the live list, plus one that
// IS (with a stale handle). The merge must update the live one, add the
// new one, and keep the unrelated hand-added key untouched.
func TestSyncSubteamAliasesMergePreservesUnrelatedKeys(t *testing.T) {
	srv, _ := usergroupsListStub(t, `{
		"ok": true,
		"usergroups": [
			{"id": "S001", "team_id": "T1", "handle": "mayor", "name": "Mayor"},
			{"id": "S009", "team_id": "T1", "handle": "newgroup", "name": "New Group"}
		]
	}`)
	_, aliasPath := stageCity(t, map[string]string{
		"S001":     "old-mayor-handle", // live id, stale handle -> changed
		"S0MANUAL": "hand-added",       // not in live -> preserved
	})

	var out bytes.Buffer
	opts := subteamSyncOpts{
		workspaceID: "T1",
		token:       "xoxb-test",
		apiBase:     srv.URL,
		output:      "json",
		timeout:     defaultTestTimeout(),
	}
	if err := runSlackSyncSubteamAliases(context.Background(), &out, opts); err != nil {
		t.Fatalf("run: %v", err)
	}

	got := readAliasFile(t, aliasPath)
	want := map[string]string{
		"S001":     "mayor",      // refreshed from live
		"S009":     "newgroup",   // added from live
		"S0MANUAL": "hand-added", // preserved untouched
	}
	if len(got) != len(want) {
		t.Fatalf("merged map = %v, want %v", got, want)
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("entry %s = %q, want %q", k, got[k], v)
		}
	}

	var env subteamSyncEnvelope
	if err := json.Unmarshal(out.Bytes(), &env); err != nil {
		t.Fatalf("decode json envelope: %v", err)
	}
	if len(env.Diff.Added) != 1 || env.Diff.Added[0].SubteamID != "S009" {
		t.Errorf("Added = %+v, want one S009", env.Diff.Added)
	}
	if len(env.Diff.Changed) != 1 || env.Diff.Changed[0].SubteamID != "S001" {
		t.Errorf("Changed = %+v, want one S001", env.Diff.Changed)
	}
	if len(env.Diff.LocalOnly) != 1 || env.Diff.LocalOnly[0].SubteamID != "S0MANUAL" {
		t.Errorf("LocalOnly = %+v, want one S0MANUAL", env.Diff.LocalOnly)
	}
}

// TestSyncSubteamAliasesDryRun: --dry-run reports the diff but leaves the
// file exactly as it was.
func TestSyncSubteamAliasesDryRun(t *testing.T) {
	srv, _ := usergroupsListStub(t, `{
		"ok": true,
		"usergroups": [
			{"id": "S001", "team_id": "T1", "handle": "mayor", "name": "Mayor"},
			{"id": "S002", "team_id": "T1", "handle": "cos", "name": "Chief of Staff"}
		]
	}`)
	seed := map[string]string{"S001": "mayor"} // S002 would be added
	_, aliasPath := stageCity(t, seed)
	before := readAliasFile(t, aliasPath)

	var out bytes.Buffer
	opts := subteamSyncOpts{
		workspaceID: "T1",
		token:       "xoxb-test",
		apiBase:     srv.URL,
		dryRun:      true,
		output:      "json",
		timeout:     defaultTestTimeout(),
	}
	if err := runSlackSyncSubteamAliases(context.Background(), &out, opts); err != nil {
		t.Fatalf("run: %v", err)
	}

	after := readAliasFile(t, aliasPath)
	if len(after) != len(before) || after["S001"] != before["S001"] {
		t.Errorf("dry-run mutated file: before=%v after=%v", before, after)
	}
	if _, ok := after["S002"]; ok {
		t.Errorf("dry-run added S002 to file: %v", after)
	}

	var env subteamSyncEnvelope
	if err := json.Unmarshal(out.Bytes(), &env); err != nil {
		t.Fatalf("decode json envelope: %v", err)
	}
	if env.WriteIssued {
		t.Errorf("WriteIssued = true on dry-run, want false")
	}
	if !env.DryRun {
		t.Errorf("DryRun = false, want true")
	}
	if len(env.Diff.Added) != 1 || env.Diff.Added[0].SubteamID != "S002" {
		t.Errorf("Added = %+v, want one S002 in the diff", env.Diff.Added)
	}
}

// TestSyncSubteamAliasesFiltersOtherWorkspaces: an org-level token may
// return User Groups from other teams; with --workspace-id set, those
// must be filtered out of the written file.
func TestSyncSubteamAliasesFiltersOtherWorkspaces(t *testing.T) {
	srv, _ := usergroupsListStub(t, `{
		"ok": true,
		"usergroups": [
			{"id": "S001", "team_id": "T1", "handle": "mayor", "name": "Mayor"},
			{"id": "S002", "team_id": "T2", "handle": "other-team", "name": "Other"}
		]
	}`)
	_, aliasPath := stageCity(t, nil)

	var out bytes.Buffer
	opts := subteamSyncOpts{
		workspaceID: "T1",
		token:       "xoxb-test",
		apiBase:     srv.URL,
		output:      "text",
		timeout:     defaultTestTimeout(),
	}
	if err := runSlackSyncSubteamAliases(context.Background(), &out, opts); err != nil {
		t.Fatalf("run: %v", err)
	}
	got := readAliasFile(t, aliasPath)
	if _, ok := got["S002"]; ok {
		t.Errorf("entry from other workspace T2 leaked into file: %v", got)
	}
	if got["S001"] != "mayor" {
		t.Errorf("own-workspace entry missing/wrong: %v", got)
	}
}

func defaultTestTimeout() time.Duration { return 30 * time.Second }

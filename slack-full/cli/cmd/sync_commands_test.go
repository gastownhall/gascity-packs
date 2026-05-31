package cmd

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"reflect"
	"regexp"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/sjarmak/gc-slack-cli/internal/state/apps"
)

// fakeSlackAPI is a minimal stub of api.slack.com/api covering the two
// endpoints sync-commands calls: apps.manifest.export and
// apps.manifest.update. It records call counts so tests can assert
// idempotent no-op behavior (zero updates when local == live).
//
// Concurrency: HTTP handlers run on net/http's goroutine pool while the
// test goroutine sets up response queues. A mutex guards the response
// slices so popping from a handler does not race the setup writes.
type fakeSlackAPI struct {
	server      *httptest.Server
	exportCalls atomic.Int64
	updateCalls atomic.Int64

	mu              sync.Mutex
	exportResponses []slackAPIResponse // popped front-to-back; last response sticks
	updateResponses []slackAPIResponse // same semantics
	expectedToken   string             // if set, handler asserts on Authorization
	wantUpdateForm  func(*testing.T, url.Values)
}

// slackAPIResponse models a canned Slack envelope. Either Body is set
// verbatim (raw JSON) OR Status + ManifestObj are used to build a
// well-formed response. Body wins when both are set.
type slackAPIResponse struct {
	Status      int             // default 200
	Body        string          // verbatim wire body
	ManifestObj json.RawMessage // wraps as {"ok":true,"manifest": ...}
	Error       string          // top-level Slack error code
	Errors      []slackErrEntry // structured error list
	AppID       string          // for update responses
}

type slackErrEntry struct {
	Code    string `json:"code"`
	Message string `json:"message,omitempty"`
	Pointer string `json:"pointer,omitempty"`
}

func (r slackAPIResponse) writeTo(t *testing.T, w http.ResponseWriter) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	status := r.Status
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	if r.Body != "" {
		_, _ = io.WriteString(w, r.Body)
		return
	}
	envelope := map[string]any{"ok": r.Error == ""}
	if r.Error != "" {
		envelope["error"] = r.Error
	}
	if len(r.Errors) > 0 {
		envelope["errors"] = r.Errors
	}
	if len(r.ManifestObj) > 0 {
		envelope["manifest"] = r.ManifestObj
	}
	if r.AppID != "" {
		envelope["app_id"] = r.AppID
	}
	body, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("encode fake slack response: %v", err)
	}
	_, _ = w.Write(body)
}

func newFakeSlackAPI(t *testing.T) *fakeSlackAPI {
	t.Helper()
	api := &fakeSlackAPI{}
	checkAuth := func(method, header string) {
		api.mu.Lock()
		want := api.expectedToken
		api.mu.Unlock()
		if want == "" {
			return
		}
		if header != "Bearer "+want {
			t.Errorf("%s Authorization = %q, want Bearer %s", method, header, want)
		}
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/api/apps.manifest.export", func(w http.ResponseWriter, r *http.Request) {
		api.exportCalls.Add(1)
		checkAuth("export", r.Header.Get("Authorization"))
		api.popResponse(&api.exportResponses).writeTo(t, w)
	})
	mux.HandleFunc("/api/apps.manifest.update", func(w http.ResponseWriter, r *http.Request) {
		api.updateCalls.Add(1)
		checkAuth("update", r.Header.Get("Authorization"))
		if err := r.ParseForm(); err != nil {
			t.Errorf("update parse form: %v", err)
		}
		// Snapshot the callback under the mutex so a test setup that
		// mutates wantUpdateForm doesn't race the handler.
		api.mu.Lock()
		cb := api.wantUpdateForm
		api.mu.Unlock()
		if cb != nil {
			// IMPORTANT: cb must NOT call t.Fatal/t.FailNow — we run
			// inside the http handler goroutine. Use t.Errorf only.
			cb(t, r.PostForm)
		}
		api.popResponse(&api.updateResponses).writeTo(t, w)
	})
	api.server = httptest.NewServer(mux)
	t.Cleanup(api.server.Close)
	return api
}

// testAllowAnySlackAPIBaseURL relaxes the slack.com host allowlist
// for the duration of the test so httptest.NewServer URLs (which
// resolve to 127.0.0.1) are accepted. Production callers always see
// isSlackAPIBaseURL. Mirrors the testAllowAnyURL pattern in the
// slack-pack adapter.
func testAllowAnySlackAPIBaseURL(t *testing.T) {
	t.Helper()
	prev := slackAPIBaseURLAllowed
	slackAPIBaseURLAllowed = func(string) error { return nil }
	t.Cleanup(func() { slackAPIBaseURLAllowed = prev })
}

// popResponse pops the front of slot under the mutex. The last queued
// response is "sticky" — repeated calls past the queue length keep
// returning it — so tests don't have to enumerate trailing identical
// responses.
func (api *fakeSlackAPI) popResponse(slot *[]slackAPIResponse) slackAPIResponse {
	api.mu.Lock()
	defer api.mu.Unlock()
	if len(*slot) == 0 {
		return slackAPIResponse{Body: `{"ok":false,"error":"test_no_response_queued"}`, Status: 500}
	}
	r := (*slot)[0]
	if len(*slot) > 1 {
		*slot = (*slot)[1:]
	}
	return r
}

// assertNoTokenLeak verifies the configuration access token does not
// appear in either output stream. Called from every test that sets a
// token to catch accidental log/error echoes on success paths too.
func assertNoTokenLeak(t *testing.T, token, stdout, stderr string) {
	t.Helper()
	if token == "" {
		return
	}
	if strings.Contains(stdout, token) {
		t.Errorf("token leaked into stdout: %s", stdout)
	}
	if strings.Contains(stderr, token) {
		t.Errorf("token leaked into stderr: %s", stderr)
	}
}

// readRegistryRecord re-opens the on-disk registry and returns the
// record import-app wrote. Used by tests that need to assert the
// update body re-uses the stored manifest_raw verbatim.
func readRegistryRecord(t *testing.T, cityRoot, workspaceID, appID string) apps.Record {
	t.Helper()
	reg, err := apps.NewRegistry(apps.Path(cityRoot))
	if err != nil {
		t.Fatalf("readRegistryRecord: %v", err)
	}
	rec, ok := reg.Get(workspaceID, appID)
	if !ok {
		t.Fatalf("readRegistryRecord: missing record %s/%s", workspaceID, appID)
	}
	return rec
}

// regexFindOnLine scans s line-by-line and returns true if any line
// matches pat. Used to assert "/gc" appears as a distinct token rather
// than just as a prefix of "/gc-status".
func regexFindOnLine(s, pat string) bool {
	re := regexp.MustCompile(pat)
	for _, line := range strings.Split(s, "\n") {
		if re.MatchString(line) {
			return true
		}
	}
	return false
}

// jsonEquivalent compares two raw JSON byte slices for semantic
// equality (whitespace-insensitive, key-order-insensitive).
func jsonEquivalent(t *testing.T, a, b []byte) bool {
	t.Helper()
	var av, bv any
	if err := json.Unmarshal(a, &av); err != nil {
		t.Fatalf("jsonEquivalent: a is not valid JSON: %v", err)
	}
	if err := json.Unmarshal(b, &bv); err != nil {
		t.Fatalf("jsonEquivalent: b is not valid JSON: %v", err)
	}
	return reflect.DeepEqual(av, bv)
}

// importAppViaCmd runs the existing import-app verb so that the
// sync-commands tests start from the same registry shape that real
// operators see, rather than backdooring records into the registry
// directly.
func importAppViaCmd(t *testing.T, cityRoot string, manifest []byte, workspaceID, appID string) { //nolint:unparam // workspaceID is the registry key callers may vary in future fixtures
	t.Helper()
	manifestPath := writeManifest(t, t.TempDir(), manifest)
	if _, stderr, err := execImportAppCmd(t, cityRoot,
		manifestPath, "--workspace-id", workspaceID, "--app-id", appID); err != nil {
		t.Fatalf("seed import-app: %v\nstderr=%s", err, stderr)
	}
}

// execSyncCommandsCmd executes the verb in-process against a temp
// city, with the fake Slack base URL injected via env.
//
// CONTRACT: the implementation MUST honor the GC_SLACK_API_URL env var
// as the Slack API base URL when set (with no trailing slash). This is
// the ONLY injection mechanism the tests use to point the verb at a
// httptest server; production runs leave it unset and default to
// https://slack.com/api. Changing the variable name is a breaking
// change to the test contract.
//
// In production GC_SLACK_API_URL is restricted to *.slack.com over
// https; tests must call testAllowAnySlackAPIBaseURL to relax that
// guard before calling this helper.
func execSyncCommandsCmd(t *testing.T, cityRoot, baseURL, token string, args ...string) (string, string, error) {
	t.Helper()
	testAllowAnySlackAPIBaseURL(t)
	t.Setenv(cityPathEnv, cityRoot)
	t.Setenv("GC_SLACK_API_URL", baseURL+"/api")
	t.Setenv("SLACK_CONFIG_ACCESS_TOKEN", token)

	var stdout, stderr bytes.Buffer
	cmd := NewSyncCommandsCmd(&stdout, &stderr)
	cmd.SetOut(&stdout)
	cmd.SetErr(&stderr)
	cmd.SetArgs(args)
	err := cmd.Execute()
	return stdout.String(), stderr.String(), err
}

// twoCommandsManifest is a manifest with two slash commands installed.
// The validator requires the full bot-scope set, so all required scopes
// are present.
func twoCommandsManifest() []byte {
	return []byte(`{
  "display_information": { "name": "gc-oversight", "description": "test" },
  "features": {
    "bot_user": { "display_name": "gc-oversight" },
    "slash_commands": [
      { "command": "/gc",        "description": "Run gc",      "url": "https://example/slack/interactions" },
      { "command": "/gc-status", "description": "Show status", "url": "https://example/slack/interactions" }
    ]
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "commands","chat:write","chat:write.customize",
        "channels:history","groups:history","im:history","mpim:history",
        "files:read","files:write","reactions:write"
      ]
    }
  }
}`)
}

// liveManifestSubset returns just the parsed manifest JSON the fake
// apps.manifest.export endpoint would return — i.e. the same bytes as
// the canonical local manifest, optionally with a different
// slash_commands array.
func liveManifest(t *testing.T, slashCmds string) json.RawMessage {
	t.Helper()
	tmpl := `{
  "display_information": { "name": "gc-oversight", "description": "test" },
  "features": {
    "bot_user": { "display_name": "gc-oversight" },
    "slash_commands": ` + slashCmds + `
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "commands","chat:write","chat:write.customize",
        "channels:history","groups:history","im:history","mpim:history",
        "files:read","files:write","reactions:write"
      ]
    }
  }
}`
	// Validate it parses.
	var probe map[string]any
	if err := json.Unmarshal([]byte(tmpl), &probe); err != nil {
		t.Fatalf("liveManifest produced invalid JSON: %v", err)
	}
	return json.RawMessage(tmpl)
}

// --- TESTS ---------------------------------------------------------------

func TestSyncCommandsHappyPath_PushesUpdateAndVerifies(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	// Local has 2 commands; live starts with only 1. After update, live
	// matches local.
	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	api.exportResponses = []slackAPIResponse{
		// Pre-update export: live missing /gc-status.
		{ManifestObj: liveManifest(t, `[{"command":"/gc","description":"Run gc","url":"https://example/slack/interactions"}]`)},
		// Post-update verify: live now matches local.
		{ManifestObj: liveManifest(t, `[
			{"command":"/gc","description":"Run gc","url":"https://example/slack/interactions"},
			{"command":"/gc-status","description":"Show status","url":"https://example/slack/interactions"}
		]`)},
	}
	api.updateResponses = []slackAPIResponse{{AppID: "A1"}}
	// Read the registry record so we can verify the update body re-uses
	// manifest_raw byte-for-byte (semantic equality).
	stored := readRegistryRecord(t, cityRoot, "T1", "A1")
	api.wantUpdateForm = func(t *testing.T, form url.Values) {
		if form.Get("app_id") != "A1" {
			t.Errorf("update form app_id = %q, want A1", form.Get("app_id"))
		}
		raw := form.Get("manifest")
		if raw == "" {
			t.Errorf("update form missing manifest")
			return
		}
		// Must be a JSON-encoded STRING in the form body (Slack's
		// apps.manifest.update wire format), and must round-trip to
		// exactly the bytes import-app captured on the registry.
		if !jsonEquivalent(t, []byte(raw), stored.ManifestRaw) {
			t.Errorf("update manifest does not match registry manifest_raw\n got: %s\nwant: %s",
				raw, stored.ManifestRaw)
		}
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err != nil {
		t.Fatalf("sync-commands: %v\nstdout=%s\nstderr=%s", err, stdout, stderr)
	}
	if got := api.updateCalls.Load(); got != 1 {
		t.Errorf("update calls = %d, want 1", got)
	}
	if got := api.exportCalls.Load(); got != 2 {
		t.Errorf("export calls = %d, want 2 (pre-diff + post-verify)", got)
	}
	if !strings.Contains(stdout, "/gc-status") {
		t.Errorf("stdout missing added command /gc-status; stdout=%s", stdout)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, stderr)
}

func TestSyncCommandsDryRun_IssuesNoUpdate(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: liveManifest(t, `[]`)}, // live has zero commands; both local cmds are added.
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1", "--dry-run")
	if err != nil {
		t.Fatalf("sync-commands --dry-run: %v\nstderr=%s", err, stderr)
	}
	if got := api.updateCalls.Load(); got != 0 {
		t.Errorf("--dry-run made %d update calls, want 0", got)
	}
	if got := api.exportCalls.Load(); got != 1 {
		t.Errorf("--dry-run export calls = %d, want 1", got)
	}
	// /gc is a strict prefix of /gc-status, so a substring search would
	// false-positive on /gc when only /gc-status is present. Match the
	// command names with surrounding non-name chars.
	if !regexFindOnLine(stdout, `(^|[\s"\(\[])/gc($|[\s"\)\],])`) {
		t.Errorf("dry-run output missing /gc as a distinct entry; stdout=%s", stdout)
	}
	if !strings.Contains(stdout, "/gc-status") {
		t.Errorf("dry-run output missing /gc-status; stdout=%s", stdout)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, stderr)
}

func TestSyncCommandsIdempotentNoOp_WhenLiveMatchesLocal(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Live already matches local.
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: liveManifest(t, `[
			{"command":"/gc","description":"Run gc","url":"https://example/slack/interactions"},
			{"command":"/gc-status","description":"Show status","url":"https://example/slack/interactions"}
		]`)},
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err != nil {
		t.Fatalf("sync-commands no-op: %v\nstderr=%s", err, stderr)
	}
	if got := api.updateCalls.Load(); got != 0 {
		t.Errorf("idempotent no-op should make zero update calls; got %d", got)
	}
	// Canonical no-op message — implementation must emit this exact
	// phrase for predictable scripting against the verb.
	if !strings.Contains(stdout, "in sync") {
		t.Errorf(`expected stdout to contain "in sync"; got %q`, stdout)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, stderr)
}

func TestSyncCommandsRegistryMiss_FailsBeforeAnyHTTPCall(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)

	// No import-app run — registry is empty.
	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, "xoxe.xoxp-token",
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected error on registry miss; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "T1") || !strings.Contains(combined, "A1") {
		t.Errorf("error should name the missing (workspace, app) key: %s", combined)
	}
	if got := api.exportCalls.Load() + api.updateCalls.Load(); got != 0 {
		t.Errorf("registry miss made %d HTTP calls, want 0", got)
	}
	assertNoTokenLeak(t, "xoxe.xoxp-token", stdout, combined)
}

func TestSyncCommandsMissingToken_FailsBeforeAnyHTTPCall(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, "",
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected error for missing token; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "SLACK_CONFIG_ACCESS_TOKEN") && !strings.Contains(combined, "--token") {
		t.Errorf("error should hint where to set the token: %s", combined)
	}
	if got := api.exportCalls.Load() + api.updateCalls.Load(); got != 0 {
		t.Errorf("missing-token made %d HTTP calls, want 0", got)
	}
}

func TestSyncCommandsSlackErrorSurface_PointersIncluded(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Pre-update export succeeds with mismatch so we proceed to update.
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: liveManifest(t, `[]`)},
	}
	// Update fails with structured errors.
	api.updateResponses = []slackAPIResponse{
		{Error: "invalid_manifest", Errors: []slackErrEntry{
			{Code: "invalid_scopes", Pointer: "/oauth_config/scopes/bot/3", Message: "scope not allowed"},
		}},
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected error on Slack ok:false; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "invalid_manifest") {
		t.Errorf("error should include slack 'error' code: %s", combined)
	}
	if !strings.Contains(combined, "/oauth_config/scopes/bot/3") {
		t.Errorf("error should include errors[].pointer: %s", combined)
	}
	// Token must NEVER appear in any output.
	if strings.Contains(combined, api.expectedToken) || strings.Contains(stdout, api.expectedToken) {
		t.Errorf("token leaked into output: stdout=%s combined=%s", stdout, combined)
	}
}

func TestSyncCommandsTokenExpired_HasMintHint(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Slack returns token_expired on the first export.
	api.exportResponses = []slackAPIResponse{
		{Error: "token_expired"},
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected error on token_expired; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "token_expired") {
		t.Errorf("error should name token_expired: %s", combined)
	}
	// Mint hint — match the form import-app uses for documentation.
	if !strings.Contains(combined, "api.slack.com/apps") {
		t.Errorf("expired-token error should hint at the slack app config URL: %s", combined)
	}
	if got := api.updateCalls.Load(); got != 0 {
		t.Errorf("token_expired path called update %d times, want 0", got)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, combined)
}

func TestSyncCommandsNonCommandDrift_RefusedByDefault(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Live has different display_information.name AND a different slash
	// command set, so the diff includes both kinds of drift.
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: json.RawMessage(`{
			"display_information": { "name": "renamed-bot", "description": "test" },
			"features": {
				"bot_user": { "display_name": "gc-oversight" },
				"slash_commands": []
			},
			"oauth_config": {
				"scopes": {
					"bot": [
						"commands","chat:write","chat:write.customize",
						"channels:history","groups:history","im:history","mpim:history",
						"files:read","files:write","reactions:write"
					]
				}
			}
		}`)},
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected error on non-command drift without --allow-non-command-drift; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "non-command") && !strings.Contains(combined, "display_information") {
		t.Errorf("error should explain non-command-fields drift: %s", combined)
	}
	if got := api.updateCalls.Load(); got != 0 {
		t.Errorf("drift refusal called update %d times, want 0", got)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, combined)
}

func TestSyncCommandsNonCommandDrift_AllowedWithFlag(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: json.RawMessage(`{
			"display_information": { "name": "renamed-bot", "description": "test" },
			"features": {
				"bot_user": { "display_name": "gc-oversight" },
				"slash_commands": []
			},
			"oauth_config": {
				"scopes": {
					"bot": [
						"commands","chat:write","chat:write.customize",
						"channels:history","groups:history","im:history","mpim:history",
						"files:read","files:write","reactions:write"
					]
				}
			}
		}`)},
		// Post-update verification — return local-shaped manifest so verify passes.
		{ManifestObj: liveManifest(t, `[
			{"command":"/gc","description":"Run gc","url":"https://example/slack/interactions"},
			{"command":"/gc-status","description":"Show status","url":"https://example/slack/interactions"}
		]`)},
	}
	api.updateResponses = []slackAPIResponse{{AppID: "A1"}}
	stored := readRegistryRecord(t, cityRoot, "T1", "A1")
	api.wantUpdateForm = func(t *testing.T, form url.Values) {
		// Verify the impl pushes the LOCAL manifest, not the live one
		// (which has different display_information.name and zero
		// slash_commands). A bug that round-tripped the live manifest
		// back would fail this check.
		raw := form.Get("manifest")
		if !jsonEquivalent(t, []byte(raw), stored.ManifestRaw) {
			t.Errorf("update body must match stored manifest_raw, not live manifest\n got: %s", raw)
		}
		if !strings.Contains(raw, "/gc-status") {
			t.Errorf("update body should include local slash command /gc-status; got: %s", raw)
		}
		if strings.Contains(raw, "renamed-bot") {
			t.Errorf("update body should NOT include the live display name 'renamed-bot' (would mean we pushed live, not local); got: %s", raw)
		}
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1", "--allow-non-command-drift")
	if err != nil {
		t.Fatalf("sync-commands --allow-non-command-drift: %v\nstderr=%s", err, stderr)
	}
	if got := api.updateCalls.Load(); got != 1 {
		t.Errorf("allow-non-command-drift made %d update calls, want 1", got)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, stderr)
}

func TestSyncCommandsDiffClassification_AddedRemovedChanged(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Local = /gc + /gc-status. Live has:
	//   /gc (changed: different description)
	//   /gc-old (removed: not in local)
	// Local /gc-status will be reported as added.
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: liveManifest(t, `[
			{"command":"/gc","description":"OLD description","url":"https://example/slack/interactions"},
			{"command":"/gc-old","description":"deprecated","url":"https://example/slack/interactions"}
		]`)},
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1", "--dry-run")
	if err != nil {
		t.Fatalf("sync-commands --dry-run: %v\nstderr=%s", err, stderr)
	}
	classifications := parseDryRunSections(stdout)
	if !slices.Contains(classifications["added"], "/gc-status") {
		t.Errorf("classification 'added' missing /gc-status; sections=%v", classifications)
	}
	if !slices.Contains(classifications["removed"], "/gc-old") {
		t.Errorf("classification 'removed' missing /gc-old; sections=%v", classifications)
	}
	if !slices.Contains(classifications["changed"], "/gc") {
		t.Errorf("classification 'changed' missing /gc; sections=%v", classifications)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, stderr)
}

var (
	dryRunLabelRE = regexp.MustCompile(`(?i)^\s*(added|removed|changed)\b`)
	dryRunCmdRE   = regexp.MustCompile(`(/[A-Za-z0-9_-]+)`)
)

// parseDryRunSections splits dry-run text output into label->commands
// blocks. The implementation is contractually required to print
// classification labels (case-insensitive) on their own line followed
// by command-name entries until the next label or blank line.
func parseDryRunSections(s string) map[string][]string {
	out := map[string][]string{}
	var current string
	labelRE := dryRunLabelRE
	cmdRE := dryRunCmdRE
	for _, line := range strings.Split(s, "\n") {
		if m := labelRE.FindStringSubmatch(line); m != nil {
			current = strings.ToLower(m[1])
			if cm := cmdRE.FindString(line); cm != "" {
				out[current] = append(out[current], cm)
			}
			continue
		}
		if current == "" {
			continue
		}
		if strings.TrimSpace(line) == "" {
			current = ""
			continue
		}
		if cm := cmdRE.FindString(line); cm != "" {
			out[current] = append(out[current], cm)
		}
	}
	return out
}

func TestSyncCommandsVerifyFailure_AfterUpdate(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Pre-update mismatch.
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: liveManifest(t, `[]`)},
		// Post-update STILL shows zero commands — verify must fail.
		{ManifestObj: liveManifest(t, `[]`)},
	}
	api.updateResponses = []slackAPIResponse{{AppID: "A1"}}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected verification failure; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(strings.ToLower(combined), "diverged") {
		t.Errorf(`verify-failure error must contain "diverged"; got: %s`, combined)
	}
	assertNoTokenLeak(t, api.expectedToken, "", combined)
}

func TestSyncCommandsJSONOutput_HasStructuredEnvelope(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	api.exportResponses = []slackAPIResponse{
		{ManifestObj: liveManifest(t, `[]`)},
		{ManifestObj: liveManifest(t, `[
			{"command":"/gc","description":"Run gc","url":"https://example/slack/interactions"},
			{"command":"/gc-status","description":"Show status","url":"https://example/slack/interactions"}
		]`)},
	}
	api.updateResponses = []slackAPIResponse{{AppID: "A1"}}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1", "--output", "json")
	if err != nil {
		t.Fatalf("sync-commands --output json: %v\nstderr=%s", err, stderr)
	}
	var got struct {
		WorkspaceID string `json:"workspace_id"`
		AppID       string `json:"app_id"`
		Diff        struct {
			Added                   []map[string]any `json:"added"`
			Removed                 []map[string]any `json:"removed"`
			Changed                 []map[string]any `json:"changed"`
			NonCommandFieldsChanged bool             `json:"non_command_fields_changed"`
		} `json:"diff"`
		UpdateIssued bool `json:"update_issued"`
		Verified     bool `json:"verified"`
	}
	if err := json.Unmarshal([]byte(stdout), &got); err != nil {
		t.Fatalf("--output json produced non-JSON stdout: %v\nstdout=%s", err, stdout)
	}
	if got.WorkspaceID != "T1" || got.AppID != "A1" {
		t.Errorf("json envelope key fields wrong: %+v", got)
	}
	if !got.UpdateIssued {
		t.Errorf("json envelope: update_issued = false, want true")
	}
	if !got.Verified {
		t.Errorf("json envelope: verified = false, want true")
	}
	if len(got.Diff.Added) == 0 {
		t.Errorf("json envelope: diff.added empty, want at least one entry")
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, stderr)
}

func TestSyncCommandsTimeoutBudget_AppliesToHTTPCalls(t *testing.T) {
	cityRoot := newTestCity(t)
	api := &fakeSlackAPI{}
	release := make(chan struct{})
	mux := http.NewServeMux()
	mux.HandleFunc("/api/apps.manifest.export", func(_ http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
			return
		case <-release:
			return
		}
	})
	api.server = httptest.NewServer(mux)
	t.Cleanup(api.server.Close)
	t.Cleanup(func() { close(release) })

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, "xoxe.xoxp-token",
		"--workspace-id", "T1", "--app-id", "A1", "--timeout", "200ms")
	if err == nil {
		t.Fatalf("expected timeout error; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(strings.ToLower(combined), "context") &&
		!strings.Contains(strings.ToLower(combined), "deadline") &&
		!strings.Contains(strings.ToLower(combined), "timeout") {
		t.Errorf("expected context/deadline/timeout in error: %s", combined)
	}
	assertNoTokenLeak(t, "xoxe.xoxp-token", stdout, combined)
}

func TestSyncCommandsRefusesNonSlackBaseURL(t *testing.T) {
	// Production guard: a hostile env var that points GC_SLACK_API_URL
	// at a non-slack.com host MUST fail before any HTTP call.
	cityRoot := newTestCity(t)
	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")

	// NOTE: do NOT call testAllowAnySlackAPIBaseURL — that's the whole
	// point. We invoke the cobra command directly to bypass
	// execSyncCommandsCmd's helper relax.
	t.Setenv(cityPathEnv, cityRoot)
	// Use https so we exercise the host-allowlist branch specifically.
	t.Setenv("GC_SLACK_API_URL", "https://evil.example.com/api")
	t.Setenv("SLACK_CONFIG_ACCESS_TOKEN", "xoxe.xoxp-token")

	var stdout, stderr bytes.Buffer
	cmd := NewSyncCommandsCmd(&stdout, &stderr)
	cmd.SetOut(&stdout)
	cmd.SetErr(&stderr)
	cmd.SetArgs([]string{"--workspace-id", "T1", "--app-id", "A1"})
	err := cmd.Execute()
	if err == nil {
		t.Fatalf("expected refusal of non-slack.com base URL; stdout=%s", stdout.String())
	}
	combined := err.Error() + stderr.String()
	if !strings.Contains(combined, "GC_SLACK_API_URL") {
		t.Errorf("error should name the env var: %s", combined)
	}
	if !strings.Contains(combined, "slack.com") {
		t.Errorf("error should explain the slack.com allowlist: %s", combined)
	}
	assertNoTokenLeak(t, "xoxe.xoxp-token", stdout.String(), combined)
}

func TestSyncCommandsRejectsNonPositiveTimeout(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, "xoxe.xoxp-token",
		"--workspace-id", "T1", "--app-id", "A1", "--timeout", "0s")
	if err == nil {
		t.Fatalf("expected --timeout 0 to be rejected; stdout=%s", stdout)
	}
	if !strings.Contains(err.Error(), "--timeout") {
		t.Errorf("error should name --timeout flag: %v", err)
	}
	if got := api.exportCalls.Load() + api.updateCalls.Load(); got != 0 {
		t.Errorf("--timeout 0 made %d HTTP calls, want 0", got)
	}
	_ = stderr
}

func TestSyncCommandsRejectsUnknownOutputFormat(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")

	stdout, _, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, "xoxe.xoxp-token",
		"--workspace-id", "T1", "--app-id", "A1", "--output", "garbage")
	if err == nil {
		t.Fatalf("expected --output garbage to be rejected; stdout=%s", stdout)
	}
	if !strings.Contains(err.Error(), "--output") {
		t.Errorf("error should name --output flag: %v", err)
	}
	if got := api.exportCalls.Load() + api.updateCalls.Load(); got != 0 {
		t.Errorf("invalid --output made %d HTTP calls, want 0", got)
	}
}

func TestSyncCommandsRejectsEmptyManifestField(t *testing.T) {
	cityRoot := newTestCity(t)
	api := newFakeSlackAPI(t)
	api.expectedToken = "xoxe.xoxp-test-token"

	importAppViaCmd(t, cityRoot, twoCommandsManifest(), "T1", "A1")
	// Slack returns ok:true but no manifest field. The verb must
	// refuse rather than treat the absence as an empty manifest
	// (which would mass-classify every local command as "added").
	api.exportResponses = []slackAPIResponse{
		{Body: `{"ok":true}`},
	}

	stdout, stderr, err := execSyncCommandsCmd(t, cityRoot, api.server.URL, api.expectedToken,
		"--workspace-id", "T1", "--app-id", "A1")
	if err == nil {
		t.Fatalf("expected error for missing manifest field; stdout=%s", stdout)
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "manifest field") &&
		!strings.Contains(combined, "manifest is absent") {
		t.Errorf("error should explain missing manifest field: %s", combined)
	}
	if got := api.updateCalls.Load(); got != 0 {
		t.Errorf("missing-manifest path called update %d times, want 0", got)
	}
	assertNoTokenLeak(t, api.expectedToken, stdout, combined)
}

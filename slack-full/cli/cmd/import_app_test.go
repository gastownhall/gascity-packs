package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/sjarmak/gc-slack-cli/internal/state/apps"
)

// canonicalManifest returns a copy of the in-tree manifest scaffold so
// tests don't depend on read paths into examples/.
func canonicalManifest() []byte {
	return []byte(`{
  "display_information": {
    "name": "gc-oversight",
    "description": "Test app",
    "background_color": "#1f2933"
  },
  "features": {
    "bot_user": { "display_name": "gc-oversight", "always_online": true },
    "slash_commands": []
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "commands",
        "chat:write",
        "chat:write.customize",
        "channels:history",
        "groups:history",
        "im:history",
        "mpim:history",
        "files:read",
        "files:write",
        "reactions:write"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": ["app_mention","message.im"]
    },
    "interactivity": { "is_enabled": false }
  }
}`)
}

func writeManifest(t *testing.T, dir string, body []byte) string {
	t.Helper()
	p := filepath.Join(dir, "app.json")
	if err := os.WriteFile(p, body, 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

// execImportAppCmd executes the verb directly against a temp city. It
// invokes the cobra command in-process so flag parsing is exercised.
//
// Honors GC_CITY_PATH=cityRoot (set via t.Setenv) so tests are not at
// the mercy of the polecat session's inherited GC_CITY_PATH.
func execImportAppCmd(t *testing.T, cityRoot string, args ...string) (string, string, error) { //nolint:unparam // helper returns stdout for callers that may grow to inspect it
	t.Helper()
	t.Setenv(cityPathEnv, cityRoot)

	var stdout, stderr bytes.Buffer
	cmd := NewImportAppCmd(&stdout, &stderr)
	cmd.SetOut(&stdout)
	cmd.SetErr(&stderr)
	cmd.SetArgs(args)
	err := cmd.Execute()
	return stdout.String(), stderr.String(), err
}

func TestImportAppHappyPath(t *testing.T) {
	cityRoot := newTestCity(t)
	manifestPath := writeManifest(t, t.TempDir(), canonicalManifest())

	_, stderr, err := execImportAppCmd(t, cityRoot,
		manifestPath,
		"--workspace-id", "T123",
		"--app-id", "A456",
	)
	if err != nil {
		t.Fatalf("import-app: %v\nstderr=%s", err, stderr)
	}

	reg, err := apps.NewRegistry(apps.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	rec, ok := reg.Get("T123", "A456")
	if !ok {
		t.Fatalf("registry has no record after import")
	}
	if rec.DisplayName != "gc-oversight" {
		t.Errorf("DisplayName = %q, want gc-oversight", rec.DisplayName)
	}
	if !sliceHasAll(rec.Scopes, []string{"commands", "chat:write", "chat:write.customize"}) {
		t.Errorf("Scopes missing required entries: %v", rec.Scopes)
	}
	if rec.ManifestPath == "" {
		t.Errorf("ManifestPath empty")
	}
	if len(rec.ManifestRaw) == 0 {
		t.Errorf("ManifestRaw empty")
	}
	// BotUserID and SigningSecret are populated post-OAuth (gc-cby.9),
	// not at import time. Document this contract in tests so a future
	// change that pulls them from the manifest is intentional.
	if rec.BotUserID != "" {
		t.Errorf("BotUserID should be empty at import (populated post-OAuth); got %q", rec.BotUserID)
	}
	if rec.SigningSecret != "" {
		t.Errorf("SigningSecret should be empty at import (populated post-OAuth); got %q", rec.SigningSecret)
	}
}

func TestImportAppExtractsSlashCommands(t *testing.T) {
	cityRoot := newTestCity(t)
	body := []byte(`{
  "display_information": { "name": "gc-oversight" },
  "features": {
    "slash_commands": [
      { "command": "/gc",       "description": "Run gc",      "url": "https://example/slack/interactions" },
      { "command": "/gc-status","description": "Show status", "url": "https://example/slack/interactions" }
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
	p := writeManifest(t, t.TempDir(), body)

	_, stderr, err := execImportAppCmd(t, cityRoot,
		p, "--workspace-id", "T1", "--app-id", "A1",
	)
	if err != nil {
		t.Fatalf("import-app: %v\nstderr=%s", err, stderr)
	}

	reg, _ := apps.NewRegistry(apps.Path(cityRoot))
	rec, ok := reg.Get("T1", "A1")
	if !ok {
		t.Fatal("record missing")
	}
	if !sliceHasAll(rec.SlashCommands, []string{"/gc", "/gc-status"}) {
		t.Errorf("SlashCommands missing expected entries: %v", rec.SlashCommands)
	}
}

func TestImportAppMalformedJSON(t *testing.T) {
	cityRoot := newTestCity(t)
	p := writeManifest(t, t.TempDir(), []byte(`{"display_information": "not-an-object"`))

	_, stderr, err := execImportAppCmd(t, cityRoot,
		p, "--workspace-id", "T1", "--app-id", "A1",
	)
	if err == nil {
		t.Fatalf("expected error for malformed JSON, got nil\nstderr=%s", stderr)
	}
	if !strings.Contains(err.Error(), "manifest") && !strings.Contains(stderr, "manifest") {
		t.Errorf("error should mention manifest: err=%v stderr=%s", err, stderr)
	}
}

func TestImportAppMissingRequiredScope(t *testing.T) {
	cityRoot := newTestCity(t)
	// Manifest with `commands` scope removed.
	body := []byte(`{
  "display_information": { "name": "gc-oversight" },
  "oauth_config": { "scopes": { "bot": ["chat:write", "chat:write.customize"] } }
}`)
	p := writeManifest(t, t.TempDir(), body)

	_, stderr, err := execImportAppCmd(t, cityRoot,
		p, "--workspace-id", "T1", "--app-id", "A1",
	)
	if err == nil {
		t.Fatalf("expected error for missing required scope, got nil")
	}
	combined := err.Error() + stderr
	if !strings.Contains(combined, "commands") {
		t.Errorf("error should name missing scope 'commands': %s", combined)
	}
}

func TestImportAppMissingRequiredFlag(t *testing.T) {
	cityRoot := newTestCity(t)
	p := writeManifest(t, t.TempDir(), canonicalManifest())

	// Missing --app-id
	_, stderr, err := execImportAppCmd(t, cityRoot,
		p, "--workspace-id", "T1",
	)
	if err == nil {
		t.Fatalf("expected error for missing --app-id, got nil\nstderr=%s", stderr)
	}
}

func TestImportAppIdempotentReimport(t *testing.T) {
	cityRoot := newTestCity(t)
	p := writeManifest(t, t.TempDir(), canonicalManifest())

	for i := 0; i < 2; i++ {
		_, stderr, err := execImportAppCmd(t, cityRoot,
			p, "--workspace-id", "T1", "--app-id", "A1",
		)
		if err != nil {
			t.Fatalf("import-app pass %d: %v\nstderr=%s", i, err, stderr)
		}
	}

	reg, err := apps.NewRegistry(apps.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	if got := len(reg.All()); got != 1 {
		t.Errorf("after 2 re-imports: All() len = %d, want 1", got)
	}
}

func TestImportAppRegistryPathIsCityRootedFromNestedCwd(t *testing.T) {
	cityRoot := newTestCity(t)
	nested := filepath.Join(cityRoot, "deep", "nested", "subdir")
	if err := os.MkdirAll(nested, 0o755); err != nil {
		t.Fatal(err)
	}
	p := writeManifest(t, t.TempDir(), canonicalManifest())

	// Use cwd-walk (no env override) to exercise the nested-resolution
	// path the cmd/gc original tests cover. t.Setenv("") clears the
	// inherited polecat-session GC_CITY_PATH.
	t.Setenv(cityPathEnv, "")
	t.Chdir(nested)

	var stdout, stderr bytes.Buffer
	c := NewImportAppCmd(&stdout, &stderr)
	c.SetOut(&stdout)
	c.SetErr(&stderr)
	c.SetArgs([]string{p, "--workspace-id", "T1", "--app-id", "A1"})
	if err := c.Execute(); err != nil {
		t.Fatalf("import-app from nested cwd: %v\nstderr=%s", err, stderr.String())
	}

	// Registry must land at <cityRoot>/.gc/slack/apps.json — NOT at nested cwd.
	want := filepath.Join(cityRoot, ".gc", "slack", "apps.json")
	if _, err := os.Stat(want); err != nil {
		t.Fatalf("apps.json missing at city-rooted path %q: %v", want, err)
	}
	stray := filepath.Join(nested, ".gc", "slack", "apps.json")
	if _, err := os.Stat(stray); err == nil {
		t.Errorf("apps.json wrongly created at cwd-rooted path %q", stray)
	}

	// Stat is not enough — guard against an implementation that creates
	// the file at the right path but writes the record somewhere else
	// (or writes an empty stub).
	reg, err := apps.NewRegistry(want)
	if err != nil {
		t.Fatal(err)
	}
	if rec, ok := reg.Get("T1", "A1"); !ok {
		t.Errorf("city-rooted apps.json missing the expected record")
	} else if rec.WorkspaceID != "T1" || rec.AppID != "A1" {
		t.Errorf("city-rooted apps.json has wrong record: %+v", rec)
	}
}

func TestImportAppRejectsOversizeManifest(t *testing.T) {
	cityRoot := newTestCity(t)
	// Build a manifest that's structurally valid but bigger than the cap.
	body := canonicalManifest()
	pad := make([]byte, maxManifestBytes)
	for i := range pad {
		pad[i] = 'A'
	}
	body = append(body[:len(body)-1], []byte(`,"_pad":"`)...)
	body = append(body, pad...)
	body = append(body, []byte(`"}`)...)
	p := writeManifest(t, t.TempDir(), body)

	_, _, err := execImportAppCmd(t, cityRoot,
		p, "--workspace-id", "T1", "--app-id", "A1",
	)
	if err == nil {
		t.Fatal("expected error for oversize manifest, got nil")
	}
	if !strings.Contains(err.Error(), "too large") {
		t.Errorf("error should name size limit; got: %v", err)
	}
}

func TestImportAppManifestNotFound(t *testing.T) {
	cityRoot := newTestCity(t)
	bogus := filepath.Join(t.TempDir(), "does-not-exist.json")

	_, _, err := execImportAppCmd(t, cityRoot,
		bogus, "--workspace-id", "T1", "--app-id", "A1",
	)
	if err == nil {
		t.Fatal("expected error for missing manifest, got nil")
	}
}

func TestImportAppForwardCompatUnknownFields(t *testing.T) {
	cityRoot := newTestCity(t)
	body := canonicalManifest()
	// Splice in an unknown top-level field.
	var raw map[string]any
	if err := json.Unmarshal(body, &raw); err != nil {
		t.Fatal(err)
	}
	raw["future_slack_field"] = map[string]any{"shape": "unknown"}
	merged, err := json.Marshal(raw)
	if err != nil {
		t.Fatal(err)
	}
	p := writeManifest(t, t.TempDir(), merged)

	_, stderr, err := execImportAppCmd(t, cityRoot,
		p, "--workspace-id", "T1", "--app-id", "A1",
	)
	if err != nil {
		t.Fatalf("import-app should ignore unknown fields: %v\nstderr=%s", err, stderr)
	}

	reg, err := apps.NewRegistry(apps.Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	rec, ok := reg.Get("T1", "A1")
	if !ok {
		t.Fatal("record not stored")
	}
	// manifest_raw must preserve the unknown field for forward-compat.
	if !strings.Contains(string(rec.ManifestRaw), "future_slack_field") {
		t.Errorf("manifest_raw lost unknown field; got %s", rec.ManifestRaw)
	}
}

func TestParseSlackManifestExtractsFields(t *testing.T) {
	got, err := parseSlackManifest(canonicalManifest())
	if err != nil {
		t.Fatal(err)
	}
	if got.DisplayInformation.Name != "gc-oversight" {
		t.Errorf("name = %q, want gc-oversight", got.DisplayInformation.Name)
	}
	if !sliceHasAll(got.OAuthConfig.Scopes.Bot, []string{"commands", "chat:write"}) {
		t.Errorf("bot scopes missing required: %v", got.OAuthConfig.Scopes.Bot)
	}
}

func TestValidateSlackManifestNamesAllMissingScopes(t *testing.T) {
	m := slackManifest{
		DisplayInformation: slackManifestDisplay{Name: "x"},
		OAuthConfig: slackManifestOAuth{
			Scopes: slackManifestScopes{Bot: []string{"chat:write"}},
		},
	}
	err := validateSlackManifest(m)
	if err == nil {
		t.Fatal("expected validation error for missing scopes, got nil")
	}
	for _, want := range []string{"commands", "chat:write.customize", "files:read"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("validation error should name %q; got: %v", want, err)
		}
	}
}

// For each required scope: drop ONLY that scope and assert the validation
// error names it. Catches an implementation that only reports the first
// missing scope, or that has a stale required-scope list.
func TestValidateSlackManifestPerScopeReporting(t *testing.T) {
	all := requiredBotScopes()
	for _, drop := range all {
		t.Run(drop, func(t *testing.T) {
			kept := make([]string, 0, len(all)-1)
			for _, s := range all {
				if s != drop {
					kept = append(kept, s)
				}
			}
			m := slackManifest{
				DisplayInformation: slackManifestDisplay{Name: "x"},
				OAuthConfig: slackManifestOAuth{
					Scopes: slackManifestScopes{Bot: kept},
				},
			}
			err := validateSlackManifest(m)
			if err == nil {
				t.Fatalf("expected error when dropping %q", drop)
			}
			if !strings.Contains(err.Error(), drop) {
				t.Errorf("error did not name dropped scope %q: %v", drop, err)
			}
		})
	}
}

// sliceHasAll reports whether haystack contains every entry in needles.
// Shared by the cmd-package tests; ports the cmd/gc helper of the
// same shape.
func sliceHasAll(haystack, needles []string) bool {
	set := make(map[string]struct{}, len(haystack))
	for _, h := range haystack {
		set[h] = struct{}{}
	}
	for _, n := range needles {
		if _, ok := set[n]; !ok {
			return false
		}
	}
	return true
}

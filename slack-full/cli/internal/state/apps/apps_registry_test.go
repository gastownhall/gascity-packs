package apps

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

// newTestCity creates a minimal city directory (with city.toml marker)
// rooted at t.TempDir() and returns its absolute path. Mirrors the
// minimum shape the rest of cmd/gc city tests rely on.
func newTestCity(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	cityRoot := filepath.Join(dir, "testcity")
	if err := os.MkdirAll(cityRoot, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(cityRoot, "city.toml"),
		[]byte("[workspace]\nname = \"test\"\n"),
		0o644,
	); err != nil {
		t.Fatal(err)
	}
	return cityRoot
}

func TestPathIsCityRooted(t *testing.T) {
	cityRoot := newTestCity(t)
	got := Path(cityRoot)
	want := filepath.Join(cityRoot, ".gc", "slack", "apps.json")
	if got != want {
		t.Errorf("Path(%q) = %q, want %q", cityRoot, got, want)
	}
}

func TestRegistryTolerantLoadOnMissingFile(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)

	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("NewRegistry on missing file: unexpected error: %v", err)
	}
	if got := len(reg.All()); got != 0 {
		t.Errorf("fresh registry: All() len = %d, want 0", got)
	}
	if _, ok := reg.Get("T123", "A456"); ok {
		t.Errorf("fresh registry: Get returned ok=true, want false")
	}
}

func TestRegistrySetAndGet(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}

	rec := Record{
		WorkspaceID: "T123",
		AppID:       "A456",
		DisplayName: "gc-oversight",
		Scopes:      []string{"commands", "chat:write"},
		// SlashCommands left nil intentionally: omitempty + JSON
		// reload produces nil, not []string{}, and this test
		// exercises round-trip semantics on the next read.
		ManifestPath: "/tmp/app.json",
		ManifestRaw:  json.RawMessage(`{"display_information":{"name":"gc-oversight"}}`),
		ImportedAt:   time.Now().UTC(),
	}
	if err := reg.Set(rec); err != nil {
		t.Fatalf("Set: %v", err)
	}

	got, ok := reg.Get("T123", "A456")
	if !ok {
		t.Fatalf("Get(T123,A456) ok=false, want true")
	}
	if got.DisplayName != "gc-oversight" {
		t.Errorf("Get DisplayName = %q, want gc-oversight", got.DisplayName)
	}
	if got.WorkspaceID != "T123" || got.AppID != "A456" {
		t.Errorf("Get composite key mismatch: workspace=%q app=%q", got.WorkspaceID, got.AppID)
	}
}

func TestRegistryRejectsEmptyKey(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	cases := []Record{
		{WorkspaceID: "", AppID: "A456"},
		{WorkspaceID: "T123", AppID: ""},
		{WorkspaceID: "", AppID: ""},
	}
	for _, rec := range cases {
		if err := reg.Set(rec); err == nil {
			t.Errorf("Set(%+v): expected error for empty key, got nil", rec)
		}
	}
}

func TestRegistryPersistsAndReloads(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg1, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	rec := Record{
		WorkspaceID: "T123", AppID: "A456",
		DisplayName: "gc-oversight",
		Scopes:      []string{"commands"},
		ImportedAt:  time.Now().UTC(),
	}
	if err := reg1.Set(rec); err != nil {
		t.Fatal(err)
	}

	// Open a fresh registry pointing at the same file — must see the record.
	reg2, err := NewRegistry(path)
	if err != nil {
		t.Fatalf("reload: %v", err)
	}
	got, ok := reg2.Get("T123", "A456")
	if !ok {
		t.Fatalf("reload Get ok=false, want true")
	}
	if got.DisplayName != "gc-oversight" {
		t.Errorf("reload DisplayName = %q, want gc-oversight", got.DisplayName)
	}
}

func TestRegistryAtomicWriteCleansTmp(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	rec := Record{
		WorkspaceID: "T1", AppID: "A1",
		ImportedAt: time.Now().UTC(),
	}
	if err := reg.Set(rec); err != nil {
		t.Fatal(err)
	}

	// apps.json must exist and be valid JSON.
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read apps.json: %v", err)
	}
	var roundtrip map[string]Record
	if err := json.Unmarshal(data, &roundtrip); err != nil {
		t.Fatalf("apps.json is not valid JSON: %v\ncontents=%s", err, data)
	}

	// No stray *.tmp files in the registry dir after a successful write.
	// (Catches both the conventional "<path>.tmp" suffix and any
	// os.CreateTemp-style randomized name.)
	entries, err := os.ReadDir(filepath.Dir(path))
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		if filepath.Ext(e.Name()) == ".tmp" || strings.Contains(e.Name(), ".tmp") {
			t.Errorf("stray tmp file lingered after successful write: %s", e.Name())
		}
	}
}

func TestRegistryFilePermissions(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := reg.Set(Record{
		WorkspaceID: "T1", AppID: "A1", ImportedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatal(err)
	}

	fi, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if mode := fi.Mode().Perm(); mode != 0o600 {
		t.Errorf("apps.json mode = %o, want 0600", mode)
	}
	dirfi, err := os.Stat(filepath.Dir(path))
	if err != nil {
		t.Fatal(err)
	}
	if mode := dirfi.Mode().Perm(); mode != 0o700 {
		t.Errorf("apps.json parent dir mode = %o, want 0700", mode)
	}
}

func TestRegistryIdempotentOverwrite(t *testing.T) {
	cityRoot := newTestCity(t)
	reg, err := NewRegistry(Path(cityRoot))
	if err != nil {
		t.Fatal(err)
	}
	t0 := time.Now().UTC().Add(-time.Hour)
	t1 := time.Now().UTC()

	if err := reg.Set(Record{
		WorkspaceID: "T1", AppID: "A1", DisplayName: "v1", ImportedAt: t0,
	}); err != nil {
		t.Fatal(err)
	}
	if err := reg.Set(Record{
		WorkspaceID: "T1", AppID: "A1", DisplayName: "v2", ImportedAt: t1,
	}); err != nil {
		t.Fatal(err)
	}

	if got := len(reg.All()); got != 1 {
		t.Errorf("idempotent re-set: All() len = %d, want 1", got)
	}
	got, _ := reg.Get("T1", "A1")
	if got.DisplayName != "v2" {
		t.Errorf("re-set DisplayName = %q, want v2 (overwrite)", got.DisplayName)
	}
	if !got.ImportedAt.Equal(t1) {
		t.Errorf("re-set ImportedAt = %v, want %v (advanced)", got.ImportedAt, t1)
	}
}

func TestRegistryManifestRawRoundTrip(t *testing.T) {
	cityRoot := newTestCity(t)
	path := Path(cityRoot)
	reg, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	original := json.RawMessage(`{"display_information":{"name":"x"},"oauth_config":{"scopes":{"bot":["commands"]}}}`)
	if err := reg.Set(Record{
		WorkspaceID: "T1", AppID: "A1",
		ManifestRaw: original,
		ImportedAt:  time.Now().UTC(),
	}); err != nil {
		t.Fatal(err)
	}

	reg2, err := NewRegistry(path)
	if err != nil {
		t.Fatal(err)
	}
	got, ok := reg2.Get("T1", "A1")
	if !ok {
		t.Fatal("reload Get not ok")
	}

	// Compare semantically (whitespace differences are tolerated by re-decoding).
	var a, b any
	if err := json.Unmarshal(original, &a); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(got.ManifestRaw, &b); err != nil {
		t.Fatalf("persisted manifest_raw not valid JSON: %v\nraw=%s", err, got.ManifestRaw)
	}
	if !reflect.DeepEqual(a, b) {
		t.Errorf("manifest_raw round-trip mismatch:\noriginal=%s\nreloaded=%s", original, got.ManifestRaw)
	}
}

// TestSanitizeForLog verifies the operator-supplied-string sanitizer used
// at every CLI/log boundary touching Record fields (gc-cby.13).
// It must strip bytes that corrupt terminals or downstream log
// aggregation while preserving legitimate Unicode and standard
// whitespace.
func TestSanitizeForLog(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{"plain ascii", "hello world", "hello world"},
		{"tab preserved", "col1\tcol2", "col1\tcol2"},
		{"newline stripped", "line1\nline2", "line1line2"},
		{"carriage return stripped", "first\rsecond", "firstsecond"},
		{"crlf stripped", "a\r\nb", "ab"},
		{"japanese unicode preserved", "日本語アプリ", "日本語アプリ"},
		{"emoji preserved", "rocket \U0001f680", "rocket \U0001f680"},
		{"ansi color CSI stripped", "alert \x1b[31mRED\x1b[0m end", "alert RED end"},
		{"ansi cursor CSI stripped", "x\x1b[2Jy", "xy"},
		{"ansi CSI with ECMA-48 final ~", "fn\x1b[1~key", "fnkey"},
		{"OSC ESC stripped (payload survives, terminal-control defanged)", "\x1b]0;title\x07name", "]0;titlename"},
		{"bare escape stripped", "a\x1bb", "ab"},
		{"NUL stripped", "ab\x00cd", "abcd"},
		{"BEL stripped", "ring\x07ring", "ringring"},
		{"backspace stripped", "ab\x08cd", "abcd"},
		{"DEL stripped", "ab\x7fcd", "abcd"},
		{"invalid utf8 stripped", "valid \xff\xfe end", "valid  end"},
		{"forged log line via newline neutralized", "name\nINFO: signing_secret=sk-evil", "nameINFO: signing_secret=sk-evil"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := SanitizeForLog(tc.in)
			if got != tc.want {
				t.Errorf("SanitizeForLog(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

// TestRecordSafeLogFieldsExcludesSecrets is the structural
// tripwire enforcing the gc-cby.13 deny-list. LogView must
// expose ONLY the allowlisted fields; adding a sensitive field to
// Record later must not silently surface it to logs. The test
// uses reflection on the view's struct fields so it survives JSON-tag
// refactors and only fails on actual struct-shape changes.
func TestRecordSafeLogFieldsExcludesSecrets(t *testing.T) {
	allowed := map[string]bool{
		"WorkspaceID":       true,
		"AppID":             true,
		"DisplayName":       true,
		"ScopeCount":        true,
		"SlashCommandCount": true,
		"ImportedAt":        true,
	}
	view := Record{}.SafeLogFields()
	rt := reflect.TypeOf(view)
	if rt.Kind() != reflect.Struct {
		t.Fatalf("SafeLogFields() must return a struct, got %v", rt.Kind())
	}
	for i := 0; i < rt.NumField(); i++ {
		name := rt.Field(i).Name
		if !allowed[name] {
			t.Errorf("LogView contains disallowed field %q — gc-cby.13 deny-list breach", name)
		}
		delete(allowed, name)
	}
	for name := range allowed {
		t.Errorf("LogView missing required field %q", name)
	}

	// Belt-and-suspenders: assert known-sensitive field names are absent.
	for _, deny := range []string{"SigningSecret", "ManifestRaw", "ManifestPath", "BotUserID"} {
		if _, ok := rt.FieldByName(deny); ok {
			t.Errorf("LogView leaks sensitive field %q", deny)
		}
	}
}

// TestRecordSafeJSONFieldsExcludesSecrets is the parallel
// deny-list tripwire for the --json projection (gc-cby.13). Adding a
// new sensitive field to Record must NOT silently appear in
// the JSON view; this test forces a structural review.
func TestRecordSafeJSONFieldsExcludesSecrets(t *testing.T) {
	allowed := map[string]bool{
		"WorkspaceID":   true,
		"AppID":         true,
		"DisplayName":   true,
		"Scopes":        true,
		"SlashCommands": true,
		"ImportedAt":    true,
	}
	view := Record{}.SafeJSONFields()
	rt := reflect.TypeOf(view)
	if rt.Kind() != reflect.Struct {
		t.Fatalf("SafeJSONFields() must return a struct, got %v", rt.Kind())
	}
	for i := 0; i < rt.NumField(); i++ {
		name := rt.Field(i).Name
		if !allowed[name] {
			t.Errorf("JSONView contains disallowed field %q — gc-cby.13 deny-list breach", name)
		}
		delete(allowed, name)
	}
	for name := range allowed {
		t.Errorf("JSONView missing required field %q", name)
	}
	for _, deny := range []string{"SigningSecret", "ManifestRaw", "ManifestPath", "BotUserID"} {
		if _, ok := rt.FieldByName(deny); ok {
			t.Errorf("JSONView leaks sensitive field %q", deny)
		}
	}
}

// TestRecordSafeJSONFieldsExcludesSigningSecretAtRuntime is the
// runtime check: even with a fully populated post-OAuth record, the
// JSON-marshaled output must not contain "signing_secret".
func TestRecordSafeJSONFieldsExcludesSigningSecretAtRuntime(t *testing.T) {
	rec := Record{
		WorkspaceID:   "T1",
		AppID:         "A1",
		BotUserID:     "U1",
		DisplayName:   "alpha",
		Scopes:        []string{"chat:write"},
		SigningSecret: "sk-VERY-SECRET",
		ManifestPath:  "/tmp/manifest.json",
		ManifestRaw:   json.RawMessage(`{"hidden":"data"}`),
	}
	out, err := json.Marshal(rec.SafeJSONFields())
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if strings.Contains(string(out), "signing_secret") {
		t.Errorf("SafeJSONFields() emits signing_secret: %s", out)
	}
	if strings.Contains(string(out), "sk-VERY-SECRET") {
		t.Errorf("SafeJSONFields() leaks signing-secret value: %s", out)
	}
	if strings.Contains(string(out), "manifest_raw") || strings.Contains(string(out), "manifest_path") {
		t.Errorf("SafeJSONFields() leaks manifest fields: %s", out)
	}
	if strings.Contains(string(out), "bot_user_id") {
		t.Errorf("SafeJSONFields() leaks bot_user_id: %s", out)
	}
}

// TestRecordSafeLogFieldsSanitizesDisplayName confirms hostile
// display-name content is neutralized before reaching any printer.
func TestRecordSafeLogFieldsSanitizesDisplayName(t *testing.T) {
	rec := Record{
		WorkspaceID: "T1",
		AppID:       "A1",
		DisplayName: "evil\x1b[31m\x00name",
		Scopes:      []string{"chat:write", "files:write"},
	}
	view := rec.SafeLogFields()
	if strings.ContainsRune(view.DisplayName, 0x1b) {
		t.Errorf("SafeLogFields().DisplayName still contains ESC: %q", view.DisplayName)
	}
	if strings.ContainsRune(view.DisplayName, 0x00) {
		t.Errorf("SafeLogFields().DisplayName still contains NUL: %q", view.DisplayName)
	}
	if view.ScopeCount != 2 {
		t.Errorf("ScopeCount = %d, want 2", view.ScopeCount)
	}
	if view.SlashCommandCount != 0 {
		t.Errorf("SlashCommandCount = %d, want 0", view.SlashCommandCount)
	}
}

// TestRegistryLoadRejectsOversizedFile pins the size cap on the
// writer-side registry. Without LimitReader, an attacker (or a corrupt
// file) could force a multi-gigabyte allocation before any size check
// fires. Defense-in-depth against operator-controlled or hostile
// filesystem state (gc-cby.32). The error message must mention the
// size violation and the path so operators can identify the problem
// from the log.
func TestRegistryLoadRejectsOversizedFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "apps.json")
	payload := strings.Repeat("x", MaxBytes+1)
	if err := os.WriteFile(path, []byte(payload), 0o600); err != nil {
		t.Fatalf("seed oversized file: %v", err)
	}
	_, err := NewRegistry(path)
	if err == nil {
		t.Fatal("NewRegistry on oversized file: want error, got nil")
	}
	if !strings.Contains(err.Error(), "exceeds") {
		t.Errorf("error %q does not mention size cap", err)
	}
	if !strings.Contains(err.Error(), path) {
		t.Errorf("error %q does not mention path", err)
	}
}

package main

import (
	"bytes"
	"context"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// fixedRand returns a deterministic 16-byte source so generated state
// values are stable across runs and tests can assert on them directly.
type fixedRand struct{ b []byte }

func (f *fixedRand) Read(p []byte) (int, error) {
	if len(f.b) < len(p) {
		return 0, io.ErrUnexpectedEOF
	}
	copy(p, f.b[:len(p)])
	return len(p), nil
}

func newTestOAuthConfig(t *testing.T, slackBase, cityPath string) oauthConfig {
	t.Helper()
	return oauthConfig{
		clientID:      "test-client-id",
		clientSecret:  "test-client-secret",
		redirectURI:   "https://example.invalid/slack/oauth/callback",
		scopes:        []string{"chat:write", "im:history"},
		signingSecret: "test-signing-secret",
		cityPath:      cityPath,
		slackBaseURL:  slackBase,
		now:           func() time.Time { return time.Unix(1700000000, 0).UTC() },
		rand:          &fixedRand{b: bytes.Repeat([]byte{0xab}, 16)},
	}
}

// TestNewOAuthState — happy path returns hex-encoded 16 bytes.
func TestNewOAuthState(t *testing.T) {
	got, err := newOAuthState(&fixedRand{b: bytes.Repeat([]byte{0x01}, 16)})
	if err != nil {
		t.Fatalf("newOAuthState: %v", err)
	}
	want := hex.EncodeToString(bytes.Repeat([]byte{0x01}, 16))
	if got != want {
		t.Errorf("newOAuthState = %q, want %q", got, want)
	}
}

// TestNewOAuthStateRandFailure — surfaces a short reader as an error
// rather than returning a degraded short state.
func TestNewOAuthStateRandFailure(t *testing.T) {
	if _, err := newOAuthState(&fixedRand{b: []byte{0x01}}); err == nil {
		t.Fatal("expected error from short rand reader, got nil")
	}
}

// TestBuildSlackAuthorizeURL — required params are present and
// scope is comma-joined per Slack's v2 API.
func TestBuildSlackAuthorizeURL(t *testing.T) {
	cfg := newTestOAuthConfig(t, "https://slack.test", "")
	got, err := buildSlackAuthorizeURL(cfg, "abc123")
	if err != nil {
		t.Fatalf("buildSlackAuthorizeURL: %v", err)
	}
	u, err := url.Parse(got)
	if err != nil {
		t.Fatalf("parse url: %v", err)
	}
	if u.Path != "/oauth/v2/authorize" {
		t.Errorf("path = %q, want /oauth/v2/authorize", u.Path)
	}
	q := u.Query()
	if q.Get("client_id") != "test-client-id" {
		t.Errorf("client_id = %q", q.Get("client_id"))
	}
	if q.Get("scope") != "chat:write,im:history" {
		t.Errorf("scope = %q, want comma-joined", q.Get("scope"))
	}
	if q.Get("state") != "abc123" {
		t.Errorf("state = %q, want abc123", q.Get("state"))
	}
	if q.Get("redirect_uri") != "https://example.invalid/slack/oauth/callback" {
		t.Errorf("redirect_uri = %q", q.Get("redirect_uri"))
	}
}

func TestBuildSlackAuthorizeURLMissingClientID(t *testing.T) {
	cfg := newTestOAuthConfig(t, "", "")
	cfg.clientID = ""
	if _, err := buildSlackAuthorizeURL(cfg, "s"); err == nil {
		t.Fatal("expected error when client_id is empty")
	}
}

// TestHandleOAuthStartRedirects — start handler issues a 302 to
// slack.com with state cookie set.
func TestHandleOAuthStartRedirects(t *testing.T) {
	cfg := newTestOAuthConfig(t, "https://slack.test", "")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/start", nil)
	handleOAuthStart(cfg)(rec, req)

	if rec.Code != http.StatusFound {
		t.Fatalf("status = %d, want 302; body=%s", rec.Code, rec.Body.String())
	}
	loc := rec.Header().Get("Location")
	if !strings.HasPrefix(loc, "https://slack.test/oauth/v2/authorize?") {
		t.Errorf("Location = %q, want slack authorize URL", loc)
	}
	cookies := rec.Result().Cookies()
	var seen bool
	for _, c := range cookies {
		if c.Name == oauthStateCookie {
			seen = true
			if c.Value == "" {
				t.Error("state cookie value is empty")
			}
			if !c.HttpOnly {
				t.Error("state cookie should be HttpOnly")
			}
		}
	}
	if !seen {
		t.Errorf("state cookie %q not set; got %d cookies", oauthStateCookie, len(cookies))
	}
}

func TestHandleOAuthStartRejectsNonGET(t *testing.T) {
	cfg := newTestOAuthConfig(t, "https://slack.test", "")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/slack/oauth/start", nil)
	handleOAuthStart(cfg)(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want 405", rec.Code)
	}
}

// slackOAuthMock returns an httptest.Server that simulates Slack's
// oauth.v2.access endpoint. Responds with `resp` JSON when called.
type slackOAuthMock struct {
	gotForm           url.Values
	gotPath           string
	respStatus        int
	respBody          string
	respBodyJSON      slackOAuthAccessResponse
	useStructuredJSON bool
}

func newSlackOAuthMock(t *testing.T) (*slackOAuthMock, *httptest.Server) {
	t.Helper()
	m := &slackOAuthMock{respStatus: http.StatusOK}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		m.gotPath = r.URL.Path
		if err := r.ParseForm(); err != nil {
			t.Errorf("mock: ParseForm: %v", err)
		}
		m.gotForm = r.PostForm
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(m.respStatus)
		if m.useStructuredJSON {
			_ = json.NewEncoder(w).Encode(m.respBodyJSON)
		} else {
			_, _ = w.Write([]byte(m.respBody))
		}
	}))
	t.Cleanup(srv.Close)
	return m, srv
}

func TestHandleOAuthCallbackHappyPath(t *testing.T) {
	cityDir := t.TempDir()
	mock, mockSrv := newSlackOAuthMock(t)
	mock.useStructuredJSON = true
	mock.respBodyJSON = slackOAuthAccessResponse{
		OK:          true,
		AppID:       "A0123456",
		AccessToken: "xoxb-fake-token",
		BotUserID:   "U0123BOT",
		Scope:       "chat:write,im:history,channels:history",
	}
	mock.respBodyJSON.Team.ID = "T9999999"
	mock.respBodyJSON.Team.Name = "Acme Corp"

	cfg := newTestOAuthConfig(t, mockSrv.URL, cityDir)

	regPath := filepath.Join(cityDir, ".gc", "slack", "apps.json")
	reg, err := newAppsRegistry(regPath)
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}

	recordOAuthState(cfg.now, "expected-state")
	req := httptest.NewRequest(http.MethodGet,
		"/slack/oauth/callback?code=test-code&state=expected-state", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "expected-state"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, body=%s", rec.Code, rec.Body.String())
	}

	// Mock verifies it received the code + creds.
	if mock.gotPath != "/api/oauth.v2.access" {
		t.Errorf("mock got path %q, want /api/oauth.v2.access", mock.gotPath)
	}
	if mock.gotForm.Get("code") != "test-code" {
		t.Errorf("mock form code = %q", mock.gotForm.Get("code"))
	}
	if mock.gotForm.Get("client_id") != "test-client-id" {
		t.Errorf("mock form client_id = %q", mock.gotForm.Get("client_id"))
	}
	if mock.gotForm.Get("client_secret") != "test-client-secret" {
		t.Errorf("mock form client_secret = %q (must match cfg)", mock.gotForm.Get("client_secret"))
	}

	// Apps registry has the new record.
	got := reg.GetByTeamID("T9999999")
	if len(got) != 1 {
		t.Fatalf("apps registry GetByTeamID(T9999999) = %d records, want 1", len(got))
	}
	rec0 := got[0]
	if rec0.AppID != "A0123456" {
		t.Errorf("rec.AppID = %q", rec0.AppID)
	}
	if rec0.BotUserID != "U0123BOT" {
		t.Errorf("rec.BotUserID = %q", rec0.BotUserID)
	}
	if rec0.SigningSecret != "test-signing-secret" {
		t.Errorf("rec.SigningSecret = %q, want stamp from cfg.signingSecret", rec0.SigningSecret)
	}
	if got, want := strings.Join(rec0.Scopes, ","), "chat:write,im:history,channels:history"; got != want {
		t.Errorf("rec.Scopes = %q, want %q", got, want)
	}

	// install.env exists at expected path with bot token + 0600 perms.
	envPath := filepath.Join(cityDir, ".gc", "slack", "install.env")
	info, err := os.Stat(envPath)
	if err != nil {
		t.Fatalf("stat install.env: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("install.env perm = %o, want 0600", perm)
	}
	envBytes, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read install.env: %v", err)
	}
	envContents := string(envBytes)
	if !strings.Contains(envContents, "SLACK_BOT_TOKEN='xoxb-fake-token'") {
		t.Errorf("install.env missing SLACK_BOT_TOKEN; contents=%s", envContents)
	}
	if !strings.Contains(envContents, "SLACK_WORKSPACE_ID='T9999999'") {
		t.Errorf("install.env missing SLACK_WORKSPACE_ID; contents=%s", envContents)
	}
	if !strings.Contains(envContents, "SLACK_APP_ID='A0123456'") {
		t.Errorf("install.env missing SLACK_APP_ID; contents=%s", envContents)
	}

	// Bot token is NOT echoed in the success body.
	if strings.Contains(rec.Body.String(), "xoxb-fake-token") {
		t.Errorf("success page leaked bot token: %s", rec.Body.String())
	}
}

func TestHandleOAuthCallbackMissingState(t *testing.T) {
	cfg := newTestOAuthConfig(t, "https://slack.test", t.TempDir())
	reg, err := newAppsRegistry(filepath.Join(t.TempDir(), "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=c", nil)
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", rec.Code)
	}
}

func TestHandleOAuthCallbackMissingCookie(t *testing.T) {
	cfg := newTestOAuthConfig(t, "https://slack.test", t.TempDir())
	reg, err := newAppsRegistry(filepath.Join(t.TempDir(), "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=c&state=s", nil)
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "CSRF") {
		t.Errorf("body = %q, want CSRF mention", rec.Body.String())
	}
}

func TestHandleOAuthCallbackStateMismatch(t *testing.T) {
	cfg := newTestOAuthConfig(t, "https://slack.test", t.TempDir())
	reg, err := newAppsRegistry(filepath.Join(t.TempDir(), "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=c&state=expected", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "different"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400; body=%s", rec.Code, rec.Body.String())
	}
}

func TestHandleOAuthCallbackSlackError(t *testing.T) {
	cityDir := t.TempDir()
	mock, mockSrv := newSlackOAuthMock(t)
	mock.useStructuredJSON = true
	mock.respBodyJSON = slackOAuthAccessResponse{OK: false, Error: "invalid_code"}
	cfg := newTestOAuthConfig(t, mockSrv.URL, cityDir)
	reg, err := newAppsRegistry(filepath.Join(cityDir, "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}

	recordOAuthState(cfg.now, "s")
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=bad&state=s", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "s"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want 502; body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "invalid_code") {
		t.Errorf("body = %q, want slack error code", rec.Body.String())
	}
	// On slack-side error, no apps record is persisted.
	if got := reg.GetByTeamID(""); len(got) != 0 {
		t.Errorf("apps registry should be empty on slack error, got %d records", len(got))
	}
}

func TestHandleOAuthCallbackUserCancelled(t *testing.T) {
	// Slack redirects with ?error=access_denied when user clicks Cancel.
	cfg := newTestOAuthConfig(t, "https://slack.test", t.TempDir())
	reg, err := newAppsRegistry(filepath.Join(t.TempDir(), "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?error=access_denied", nil)
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", rec.Code)
	}
}

func TestHandleOAuthCallbackIncompleteSlackResponse(t *testing.T) {
	// Slack returns OK but missing required fields (defensive — should
	// not happen in practice but guards against API drift).
	cityDir := t.TempDir()
	mock, mockSrv := newSlackOAuthMock(t)
	mock.useStructuredJSON = true
	mock.respBodyJSON = slackOAuthAccessResponse{OK: true} // empty team/app/token
	cfg := newTestOAuthConfig(t, mockSrv.URL, cityDir)
	reg, err := newAppsRegistry(filepath.Join(cityDir, "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	recordOAuthState(cfg.now, "s")
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=c&state=s", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "s"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want 502; body=%s", rec.Code, rec.Body.String())
	}
}

func TestHandleOAuthCallbackHTTPError(t *testing.T) {
	cityDir := t.TempDir()
	mock, mockSrv := newSlackOAuthMock(t)
	mock.respStatus = http.StatusInternalServerError
	mock.respBody = "slack down"
	cfg := newTestOAuthConfig(t, mockSrv.URL, cityDir)
	reg, err := newAppsRegistry(filepath.Join(cityDir, "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}
	recordOAuthState(cfg.now, "s")
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=c&state=s", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "s"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want 502; body=%s", rec.Code, rec.Body.String())
	}
}

func TestWriteInstallEnvAtomicAnd0600(t *testing.T) {
	cityDir := t.TempDir()
	envPath, err := writeInstallEnv(cityDir, "T1", "A1", "xoxb-tok")
	if err != nil {
		t.Fatalf("writeInstallEnv: %v", err)
	}
	want := filepath.Join(cityDir, ".gc", "slack", "install.env")
	if envPath != want {
		t.Errorf("envPath = %q, want %q", envPath, want)
	}
	info, err := os.Stat(envPath)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("perm = %o, want 0600", perm)
	}
}

func TestWriteInstallEnvEmptyCityPath(t *testing.T) {
	if _, err := writeInstallEnv("", "T1", "A1", "tok"); err == nil {
		t.Fatal("expected error on empty cityPath")
	}
}

func TestShellQuoteEscapesSingleQuotes(t *testing.T) {
	in := "a'b"
	got := shellQuote(in)
	want := `'a'\''b'`
	if got != want {
		t.Errorf("shellQuote(%q) = %q, want %q", in, got, want)
	}
}

func TestTruncateForLog(t *testing.T) {
	short := "short"
	if got := truncateForLog(short); got != short {
		t.Errorf("short truncated: %q", got)
	}
	long := strings.Repeat("x", 1024)
	got := truncateForLog(long)
	if !strings.HasSuffix(got, "...[truncated]") {
		t.Errorf("long not truncated: %q", got[:64])
	}
	if len(got) > 300 {
		t.Errorf("truncated len = %d, want <= 300", len(got))
	}
}

// TestExchangeSlackOAuthCodeNetworkError — exchanged via a closed
// httptest.Server returns a real error rather than a degraded
// "ok=false" success.
func TestExchangeSlackOAuthCodeNetworkError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		hj, ok := w.(http.Hijacker)
		if !ok {
			t.Fatal("hijacker not available")
		}
		conn, _, _ := hj.Hijack()
		_ = conn.Close()
	}))
	defer srv.Close()

	cfg := newTestOAuthConfig(t, srv.URL, t.TempDir())
	_, err := exchangeSlackOAuthCode(context.Background(), cfg, "code")
	if err == nil {
		t.Fatal("expected network error, got nil")
	}
}

// Sanity: our shellQuote roundtrips through bash without interpretation.
// Defensive — if the quoting function ever drifts, install.env could
// inject arbitrary env. We don't shell out in tests, but we assert the
// invariant that single-quoted segments only break on `'` and the
// escape pattern is exactly four chars `'\”`.
func TestShellQuoteHasNoUnescapedSingleQuote(t *testing.T) {
	in := "a'b'c"
	got := shellQuote(in)
	// Strip the leading/trailing `'`. Inside, every single quote must
	// be the start of `'\''`.
	if !strings.HasPrefix(got, "'") || !strings.HasSuffix(got, "'") {
		t.Fatalf("not single-quoted: %q", got)
	}
	inner := got[1 : len(got)-1]
	// Replace all valid escape sequences with placeholder, then assert
	// no bare quotes remain.
	cleaned := strings.ReplaceAll(inner, `'\''`, "X")
	if strings.ContainsRune(cleaned, '\'') {
		t.Errorf("shellQuote left unescaped single-quote: input=%q output=%q", in, got)
	}
}

// Compile-time assertion that handleOAuthStart/handleOAuthCallback
// satisfy http.HandlerFunc — protects against signature drift if the
// helpers ever start returning errors directly.
var _ http.HandlerFunc = handleOAuthStart(oauthConfig{})
var _ http.HandlerFunc = handleOAuthCallback(oauthConfig{}, nil)

// Defensive: the success page does not use html/template, so a
// hostile workspace name cannot inject arbitrary text into the
// output. Set a name with HTML metacharacters and assert the body
// content-type is plain text.
func TestHandleOAuthCallbackSuccessIsPlainText(t *testing.T) {
	cityDir := t.TempDir()
	mock, mockSrv := newSlackOAuthMock(t)
	mock.useStructuredJSON = true
	mock.respBodyJSON = slackOAuthAccessResponse{
		OK: true, AppID: "A1", AccessToken: "xoxb-1", BotUserID: "U1",
	}
	mock.respBodyJSON.Team.ID = "T1"
	mock.respBodyJSON.Team.Name = "<script>alert(1)</script>"

	cfg := newTestOAuthConfig(t, mockSrv.URL, cityDir)
	reg, err := newAppsRegistry(filepath.Join(cityDir, "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}

	recordOAuthState(cfg.now, "s")
	req := httptest.NewRequest(http.MethodGet, "/slack/oauth/callback?code=c&state=s", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "s"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if got := rec.Header().Get("Content-Type"); !strings.HasPrefix(got, "text/plain") {
		t.Errorf("Content-Type = %q, want text/plain prefix", got)
	}
	body := rec.Body.String()
	// gc-cby.42: success page must NOT echo the filesystem path. Adapter
	// log line carries it for the operator with shell access. Mentioning
	// the bare filename is fine; leaking the absolute path is not.
	if strings.Contains(body, cityDir) {
		t.Errorf("success page leaks filesystem path %q: %q", cityDir, body)
	}
	if strings.Contains(body, "/.gc/slack/") {
		t.Errorf("success page leaks slack install path fragment: %q", body)
	}
}

// TestRecordOAuthStateSingleUse — gc-cby.41: a state nonce can only
// be consumed once. Replaying the same callback (same code+state) is
// rejected at the server-side store check, even if the cookie still
// holds the value.
func TestRecordOAuthStateSingleUse(t *testing.T) {
	cityDir := t.TempDir()
	mock, mockSrv := newSlackOAuthMock(t)
	mock.useStructuredJSON = true
	mock.respBodyJSON = slackOAuthAccessResponse{
		OK: true, AppID: "A1", AccessToken: "xoxb-1", BotUserID: "U1",
	}
	mock.respBodyJSON.Team.ID = "T1"
	mock.respBodyJSON.Team.Name = "Acme"
	cfg := newTestOAuthConfig(t, mockSrv.URL, cityDir)
	reg, err := newAppsRegistry(filepath.Join(cityDir, "apps.json"))
	if err != nil {
		t.Fatalf("newAppsRegistry: %v", err)
	}

	recordOAuthState(cfg.now, "single-use-state")

	// First request: should succeed.
	req := httptest.NewRequest(http.MethodGet,
		"/slack/oauth/callback?code=c1&state=single-use-state", nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "single-use-state"})
	rec := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("first call: status=%d body=%s", rec.Code, rec.Body.String())
	}

	// Replay (same state, fresh request): nonce was consumed, must reject.
	req2 := httptest.NewRequest(http.MethodGet,
		"/slack/oauth/callback?code=c2&state=single-use-state", nil)
	req2.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: "single-use-state"})
	rec2 := httptest.NewRecorder()
	handleOAuthCallback(cfg, reg)(rec2, req2)
	if rec2.Code != http.StatusBadRequest {
		t.Fatalf("replay: status=%d, want 400; body=%s", rec2.Code, rec2.Body.String())
	}
	if !strings.Contains(rec2.Body.String(), "consumed") {
		t.Errorf("replay error should mention nonce consumption: %q", rec2.Body.String())
	}
}

// TestConsumeOAuthStateExpired — a nonce older than oauthStateTTL
// is rejected even though it's present in the store.
func TestConsumeOAuthStateExpired(t *testing.T) {
	now := time.Now()
	frozen := func() time.Time { return now }
	recordOAuthState(frozen, "old-nonce")
	// Move the clock past TTL.
	advanced := now.Add(oauthStateTTL + time.Second)
	if consumeOAuthState(func() time.Time { return advanced }, "old-nonce") {
		t.Errorf("expired nonce was accepted; want rejected")
	}
}

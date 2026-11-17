package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestStripMentions(t *testing.T) {
	tests := []struct {
		in   string
		want string
	}{
		{"<at>gc</at> status please", "status please"},
		{"  <at>gc</at>   hello", "hello"},
		{"<at>gc</at> ping <at>Ada Lovelace</at> about it", "ping about it"},
		{"no mention here", "no mention here"},
		{"<at>gc</at>", ""},
		{"   ", ""},
		{"text then <at>gc</at>", "text then"},
		{"<at>multi\nline</at> deploy", "deploy"},
	}
	for _, tc := range tests {
		if got := stripMentions(tc.in); got != tc.want {
			t.Errorf("stripMentions(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestTeamsKind(t *testing.T) {
	tests := []struct{ in, want string }{
		{"personal", "dm"},
		{"Personal", "dm"},
		{"groupChat", "room"},
		{"channel", "room"},
		{"", "room"},
	}
	for _, tc := range tests {
		if got := teamsKind(tc.in); got != tc.want {
			t.Errorf("teamsKind(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestMentionsBot(t *testing.T) {
	bot := channelAccount{ID: "28:bot-id"}
	mention := func(id string) entity { return entity{Type: "mention", Mentioned: channelAccount{ID: id}} }
	tests := []struct {
		name string
		act  activity
		want bool
	}{
		{"bot mentioned", activity{Recipient: bot, Entities: []entity{mention("28:bot-id")}}, true},
		{"someone else mentioned", activity{Recipient: bot, Entities: []entity{mention("29:human")}}, false},
		{"no entities", activity{Recipient: bot}, false},
		{"non-mention entity", activity{Recipient: bot, Entities: []entity{{Type: "clientInfo"}}}, false},
		{"empty mentioned id", activity{Recipient: channelAccount{}, Entities: []entity{mention("")}}, false},
	}
	for _, tc := range tests {
		if got := mentionsBot(tc.act); got != tc.want {
			t.Errorf("%s: mentionsBot = %v, want %v", tc.name, got, tc.want)
		}
	}
}

func TestValidServiceURL(t *testing.T) {
	good := []string{
		"https://smba.trafficmanager.net/emea/",
		"https://smba.trafficmanager.net/emea",
		"https://smba.trafficmanager.net/amer/abc123",
	}
	for _, in := range good {
		got, err := validServiceURL(in)
		if err != nil {
			t.Errorf("validServiceURL(%q) unexpected error: %v", in, err)
			continue
		}
		if !strings.HasSuffix(got, "/") || strings.HasSuffix(got, "//") {
			t.Errorf("validServiceURL(%q) = %q, want exactly one trailing slash", in, got)
		}
	}
	bad := []string{
		"",
		"http://smba.trafficmanager.net/emea/",
		"smba.trafficmanager.net/emea/",
		"https://",
		"https://evil.example/?x=1",
		"https://evil.example/#frag",
		"ftp://smba.trafficmanager.net/",
	}
	for _, in := range bad {
		if _, err := validServiceURL(in); err == nil {
			t.Errorf("validServiceURL(%q) accepted, want error", in)
		}
	}
}

func TestSameServiceURL(t *testing.T) {
	if !sameServiceURL("https://a/x/", "https://a/x") {
		t.Fatal("trailing slash should not matter")
	}
	if sameServiceURL("https://a/x", "https://b/x") {
		t.Fatal("different hosts must not match")
	}
}

func TestConversationTable(t *testing.T) {
	tbl := newConversationTable("")
	if _, ok := tbl.lookup("c1", ""); ok {
		t.Fatal("unknown conversation with no fallback should not resolve")
	}
	tbl.remember("c1", "https://smba/emea/")
	if got, ok := tbl.lookup("c1", ""); !ok || got != "https://smba/emea/" {
		t.Fatalf("remembered lookup = %q,%v", got, ok)
	}
	if got, _ := tbl.lookup("c1", "https://override/"); got != "https://override/" {
		t.Fatalf("override should win, got %q", got)
	}
	withFallback := newConversationTable("https://fallback/")
	if got, ok := withFallback.lookup("never-seen", ""); !ok || got != "https://fallback/" {
		t.Fatalf("fallback lookup = %q,%v", got, ok)
	}
}

func TestLoadConfigFromEnv(t *testing.T) {
	base := map[string]string{
		"TEAMS_APP_ID":       "11111111-2222-3333-4444-555555555555",
		"TEAMS_APP_PASSWORD": "secret",
		"TEAMS_TENANT_ID":    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
		"GC_CITY_NAME":       "mycity",
	}
	clone := func(extra map[string]string) func(string) string {
		m := map[string]string{}
		for k, v := range base {
			m[k] = v
		}
		for k, v := range extra {
			m[k] = v
		}
		return func(k string) string { return m[k] }
	}

	t.Run("defaults", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(nil))
		if err != nil {
			t.Fatal(err)
		}
		if cfg.publicListen != defaultPublicListen || cfg.internalListen != defaultInternalListen {
			t.Fatalf("listen defaults wrong: %+v", cfg)
		}
		if cfg.provider != "teams" || cfg.inboundTarget != "mayor" || cfg.appType != "multi-tenant" {
			t.Fatalf("defaults wrong: %+v", cfg)
		}
		if cfg.tokenAuthority() != "botframework.com" {
			t.Fatalf("multi-tenant authority = %q", cfg.tokenAuthority())
		}
		if cfg.internalCallbackURL != "http://127.0.0.1:8778" {
			t.Fatalf("callback = %q", cfg.internalCallbackURL)
		}
		if !cfg.registerOnStart {
			t.Fatal("registerOnStart should default true")
		}
	})

	t.Run("single-tenant authority", func(t *testing.T) {
		cfg, err := loadConfigFromEnv(clone(map[string]string{"TEAMS_APP_TYPE": "Single-Tenant"}))
		if err != nil {
			t.Fatal(err)
		}
		if cfg.tokenAuthority() != base["TEAMS_TENANT_ID"] {
			t.Fatalf("single-tenant authority = %q", cfg.tokenAuthority())
		}
	})

	t.Run("bad app type", func(t *testing.T) {
		if _, err := loadConfigFromEnv(clone(map[string]string{"TEAMS_APP_TYPE": "whatever"})); err == nil {
			t.Fatal("expected error")
		}
	})

	for _, missing := range []string{"TEAMS_APP_ID", "TEAMS_APP_PASSWORD", "TEAMS_TENANT_ID", "GC_CITY_NAME"} {
		t.Run("missing "+missing, func(t *testing.T) {
			_, err := loadConfigFromEnv(clone(map[string]string{missing: ""}))
			if err == nil || !strings.Contains(err.Error(), missing) {
				t.Fatalf("expected error naming %s, got %v", missing, err)
			}
		})
	}

	t.Run("city name with slash", func(t *testing.T) {
		if _, err := loadConfigFromEnv(clone(map[string]string{"GC_CITY_NAME": "a/b"})); err == nil {
			t.Fatal("expected error")
		}
	})

	t.Run("bad fallback service url", func(t *testing.T) {
		if _, err := loadConfigFromEnv(clone(map[string]string{"TEAMS_SERVICE_URL": "http://plain/"})); err == nil {
			t.Fatal("expected error")
		}
	})

	t.Run("proxy_process needs prefix", func(t *testing.T) {
		_, err := loadConfigFromEnv(clone(map[string]string{"GC_SERVICE_SOCKET": "/tmp/x.sock"}))
		if err == nil {
			t.Fatal("expected error without GC_SERVICE_URL_PREFIX")
		}
		cfg, err := loadConfigFromEnv(clone(map[string]string{
			"GC_SERVICE_SOCKET":     "/tmp/x.sock",
			"GC_SERVICE_URL_PREFIX": "/v0/city/mycity/svc/teams-mini/",
			"GC_API_BASE_URL":       "http://gc:9443/",
		}))
		if err != nil {
			t.Fatal(err)
		}
		if cfg.internalCallbackURL != "http://gc:9443/v0/city/mycity/svc/teams-mini" {
			t.Fatalf("callback = %q", cfg.internalCallbackURL)
		}
	})
}

// captureGC is a stub gc API that records inbound posts.
type captureGC struct {
	mu       sync.Mutex
	inbound  []externalInboundMessage
	srv      *httptest.Server
	received chan struct{}
}

func newCaptureGC(t *testing.T) *captureGC {
	t.Helper()
	c := &captureGC{received: make(chan struct{}, 16)}
	c.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/extmsg/inbound") {
			http.NotFound(w, r)
			return
		}
		var body struct {
			Message externalInboundMessage `json:"message"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		c.mu.Lock()
		c.inbound = append(c.inbound, body.Message)
		c.mu.Unlock()
		c.received <- struct{}{}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(c.srv.Close)
	return c
}

func (c *captureGC) wait(t *testing.T) externalInboundMessage {
	t.Helper()
	select {
	case <-c.received:
	case <-time.After(5 * time.Second):
		t.Fatal("gc never received the inbound message")
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.inbound[len(c.inbound)-1]
}

func (c *captureGC) count() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.inbound)
}

func testConfig(gcBase string) config {
	return config{
		gcAPIBase:     gcBase,
		cityName:      "mycity",
		provider:      "teams",
		tenantID:      "tenant-1",
		appID:         "app-1",
		inboundTarget: "mayor",
	}
}

func channelMention(text string) activity {
	act := activity{
		Type:       "message",
		ID:         "1700000000001",
		ServiceURL: "https://smba.trafficmanager.net/emea/",
		Text:       text,
		From:       channelAccount{ID: "29:user", Name: "Ada"},
		Recipient:  channelAccount{ID: "28:bot"},
		Conversation: conversationInfo{
			ID:               "19:abc@thread.tacv2;messageid=1699",
			ConversationType: "channel",
		},
		Entities: []entity{{Type: "mention", Mentioned: channelAccount{ID: "28:bot"}}},
	}
	act.ChannelData.Tenant.ID = "tenant-1"
	return act
}

func TestBridgeActivity(t *testing.T) {
	gc := newCaptureGC(t)
	cfg := testConfig(gc.srv.URL)

	t.Run("channel mention is bridged", func(t *testing.T) {
		convs := newConversationTable("")
		bridgeActivity(cfg, convs, channelMention("<at>gc</at> status?"))
		got := gc.wait(t)
		if got.Text != "status?" {
			t.Errorf("text = %q", got.Text)
		}
		if got.Conversation.Kind != "room" || got.Conversation.ConversationID != "19:abc@thread.tacv2;messageid=1699" {
			t.Errorf("conversation = %+v", got.Conversation)
		}
		if got.Conversation.AccountID != "tenant-1" || got.Conversation.Provider != "teams" || got.Conversation.ScopeID != "mycity" {
			t.Errorf("conversation = %+v", got.Conversation)
		}
		if got.Actor.ID != "29:user" || got.Actor.DisplayName != "Ada" {
			t.Errorf("actor = %+v", got.Actor)
		}
		if got.ExplicitTarget != "mayor" || got.DedupKey != "teams-1700000000001" {
			t.Errorf("target/dedup = %q/%q", got.ExplicitTarget, got.DedupKey)
		}
		if u, ok := convs.lookup("19:abc@thread.tacv2;messageid=1699", ""); !ok || u != "https://smba.trafficmanager.net/emea/" {
			t.Errorf("serviceUrl not remembered: %q %v", u, ok)
		}
	})

	t.Run("personal chat needs no mention", func(t *testing.T) {
		act := channelMention("hello mayor")
		act.ID = "2"
		act.Entities = nil
		act.Conversation = conversationInfo{ID: "a:1personal", ConversationType: "personal"}
		bridgeActivity(cfg, newConversationTable(""), act)
		got := gc.wait(t)
		if got.Conversation.Kind != "dm" || got.Text != "hello mayor" {
			t.Errorf("got %+v", got)
		}
	})

	t.Run("display name falls back to id", func(t *testing.T) {
		act := channelMention("<at>gc</at> hi")
		act.ID = "3"
		act.From.Name = ""
		bridgeActivity(cfg, newConversationTable(""), act)
		if got := gc.wait(t); got.Actor.DisplayName != "29:user" {
			t.Errorf("display name = %q", got.Actor.DisplayName)
		}
	})

	dropped := []struct {
		name string
		mut  func(*activity)
	}{
		{"non-message activity", func(a *activity) { a.Type = "conversationUpdate" }},
		{"other tenant", func(a *activity) { a.ChannelData.Tenant.ID = "tenant-2" }},
		{"other tenant via conversation", func(a *activity) {
			a.ChannelData.Tenant.ID = ""
			a.Conversation.TenantID = "tenant-2"
		}},
		{"room without mention", func(a *activity) { a.Entities = nil }},
		{"room mentioning someone else", func(a *activity) {
			a.Entities = []entity{{Type: "mention", Mentioned: channelAccount{ID: "29:other"}}}
		}},
		{"own echo", func(a *activity) { a.From.ID = a.Recipient.ID }},
		{"empty after strip", func(a *activity) { a.Text = "<at>gc</at>   " }},
		{"no sender", func(a *activity) { a.From.ID = "" }},
		{"no conversation", func(a *activity) { a.Conversation.ID = "" }},
		{"http serviceUrl", func(a *activity) { a.ServiceURL = "http://smba.trafficmanager.net/emea/" }},
	}
	for _, tc := range dropped {
		t.Run("drops "+tc.name, func(t *testing.T) {
			before := gc.count()
			act := channelMention("<at>gc</at> status?")
			tc.mut(&act)
			bridgeActivity(cfg, newConversationTable(""), act)
			time.Sleep(50 * time.Millisecond)
			if gc.count() != before {
				t.Fatalf("activity was bridged, want dropped")
			}
		})
	}
}

func TestHandleActivitiesRejectsBadAuth(t *testing.T) {
	gc := newCaptureGC(t)
	cfg := testConfig(gc.srv.URL)
	// A verifier pointed at an unreachable OpenID document: any token fails
	// before signature checks, which is all this test needs.
	verifier := newTokenVerifier("http://127.0.0.1:1/nope", cfg.appID)
	h := handleActivities(cfg, verifier, newConversationTable(""))

	body, _ := json.Marshal(channelMention("<at>gc</at> hi"))
	for _, auth := range []string{"", "Basic abc", "Bearer not.a.jwt", "Bearer a.b"} {
		req := httptest.NewRequest(http.MethodPost, "/api/messages", strings.NewReader(string(body)))
		if auth != "" {
			req.Header.Set("Authorization", auth)
		}
		rec := httptest.NewRecorder()
		h(rec, req)
		if rec.Code != http.StatusUnauthorized {
			t.Errorf("auth %q: status %d, want 401", auth, rec.Code)
		}
	}
	req := httptest.NewRequest(http.MethodGet, "/api/messages", nil)
	rec := httptest.NewRecorder()
	h(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET status %d, want 405", rec.Code)
	}
	if gc.count() != 0 {
		t.Fatal("nothing should have reached gc")
	}
}

// fakeBotFramework stands in for both the Entra token endpoint and a
// regional Bot Framework service.
type fakeBotFramework struct {
	srv        *httptest.Server
	mu         sync.Mutex
	tokenCalls int
	posts      []struct {
		path string
		auth string
		body map[string]any
	}
}

func newFakeBotFramework(t *testing.T) *fakeBotFramework {
	t.Helper()
	f := &fakeBotFramework{}
	mux := http.NewServeMux()
	mux.HandleFunc("/botframework.com/oauth2/v2.0/token", func(w http.ResponseWriter, r *http.Request) {
		_ = r.ParseForm()
		f.mu.Lock()
		f.tokenCalls++
		f.mu.Unlock()
		if r.Form.Get("client_id") != "app-1" || r.Form.Get("client_secret") != "pw" || r.Form.Get("scope") != botFrameworkScope {
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "invalid_client", "error_description": "bad creds"})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"access_token": "tok-1", "expires_in": 3600})
	})
	mux.HandleFunc("/emea/v3/conversations/", func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var body map[string]any
		_ = json.Unmarshal(raw, &body)
		f.mu.Lock()
		f.posts = append(f.posts, struct {
			path string
			auth string
			body map[string]any
		}{r.URL.Path, r.Header.Get("Authorization"), body})
		f.mu.Unlock()
		_ = json.NewEncoder(w).Encode(map[string]string{"id": "act-99"})
	})
	f.srv = httptest.NewServer(mux)
	t.Cleanup(f.srv.Close)
	return f
}

func TestPostMessage(t *testing.T) {
	bf := newFakeBotFramework(t)
	cfg := testConfig("http://127.0.0.1:1")
	cfg.appPassword = "pw"
	cfg.appType = "multi-tenant"
	cfg.loginBase = bf.srv.URL
	tokens := newTokenSource(cfg)
	convs := newConversationTable("")
	h := handlePostMessage(cfg, convs, tokens)

	call := func(body string) (int, map[string]any) {
		req := httptest.NewRequest(http.MethodPost, "/post-message", strings.NewReader(body))
		rec := httptest.NewRecorder()
		h(rec, req)
		var out map[string]any
		_ = json.Unmarshal(rec.Body.Bytes(), &out)
		return rec.Code, out
	}

	// httptest serves plain http, and validServiceURL insists on https, so
	// the fake's URL is registered directly in the table (as a verified
	// inbound would have) rather than passed through validation.
	convs.remember("conv-1", bf.srv.URL+"/emea/")

	t.Run("posts a new message", func(t *testing.T) {
		code, out := call(`{"conversation":"conv-1","text":"build is green"}`)
		if code != http.StatusOK || out["ok"] != true || out["id"] != "act-99" {
			t.Fatalf("code=%d out=%v", code, out)
		}
		bf.mu.Lock()
		defer bf.mu.Unlock()
		p := bf.posts[len(bf.posts)-1]
		if p.path != "/emea/v3/conversations/conv-1/activities" {
			t.Errorf("path = %q", p.path)
		}
		if p.auth != "Bearer tok-1" {
			t.Errorf("auth = %q", p.auth)
		}
		if p.body["type"] != "message" || p.body["text"] != "build is green" {
			t.Errorf("body = %v", p.body)
		}
	})

	t.Run("posts a reply", func(t *testing.T) {
		code, _ := call(`{"conversation":"conv-1","text":"done","reply_to":"act-7"}`)
		if code != http.StatusOK {
			t.Fatalf("code=%d", code)
		}
		bf.mu.Lock()
		defer bf.mu.Unlock()
		if p := bf.posts[len(bf.posts)-1]; p.path != "/emea/v3/conversations/conv-1/activities/act-7" {
			t.Errorf("path = %q", p.path)
		}
	})

	t.Run("token is cached", func(t *testing.T) {
		bf.mu.Lock()
		calls := bf.tokenCalls
		bf.mu.Unlock()
		if calls != 1 {
			t.Fatalf("token fetched %d times across two posts, want 1", calls)
		}
	})

	t.Run("unknown conversation without fallback", func(t *testing.T) {
		code, out := call(`{"conversation":"never","text":"x"}`)
		if code != http.StatusBadRequest || !strings.Contains(out["error"].(string), "serviceUrl") {
			t.Fatalf("code=%d out=%v", code, out)
		}
	})

	t.Run("validation", func(t *testing.T) {
		for _, body := range []string{
			`{"text":"x"}`,
			`{"conversation":"conv-1"}`,
			`{"conversation":"conv-1","text":"  "}`,
			`{"conversation":"conv-1","text":"x","service_url":"http://plain/"}`,
			`not json`,
		} {
			if code, _ := call(body); code != http.StatusBadRequest {
				t.Errorf("%s: code=%d, want 400", body, code)
			}
		}
		code, _ := call(`{"conversation":"conv-1","text":"` + strings.Repeat("x", teamsMaxMessageLength+1) + `"}`)
		if code != http.StatusBadRequest {
			t.Errorf("oversize text: code=%d, want 400", code)
		}
	})

	t.Run("bad credentials surface", func(t *testing.T) {
		badCfg := cfg
		badCfg.appPassword = "wrong"
		h := handlePostMessage(badCfg, convs, newTokenSource(badCfg))
		req := httptest.NewRequest(http.MethodPost, "/post-message", strings.NewReader(`{"conversation":"conv-1","text":"x"}`))
		rec := httptest.NewRecorder()
		h(rec, req)
		if rec.Code != http.StatusBadGateway || !strings.Contains(rec.Body.String(), "invalid_client") {
			t.Fatalf("code=%d body=%s", rec.Code, rec.Body.String())
		}
	})
}

func TestTokenSourceRefreshesNearExpiry(t *testing.T) {
	bf := newFakeBotFramework(t)
	cfg := testConfig("http://127.0.0.1:1")
	cfg.appPassword = "pw"
	cfg.loginBase = bf.srv.URL
	ts := newTokenSource(cfg)
	now := time.Now()
	ts.now = func() time.Time { return now }
	if _, err := ts.get(context.Background()); err != nil {
		t.Fatal(err)
	}
	now = now.Add(3600*time.Second - 30*time.Second) // inside the one-minute refresh margin
	if _, err := ts.get(context.Background()); err != nil {
		t.Fatal(err)
	}
	bf.mu.Lock()
	defer bf.mu.Unlock()
	if bf.tokenCalls != 2 {
		t.Fatalf("token calls = %d, want 2 (refresh near expiry)", bf.tokenCalls)
	}
}

func TestRegisterAdapter(t *testing.T) {
	var got adapterRegisterRequest
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v0/city/mycity/extmsg/adapters" {
			http.NotFound(w, r)
			return
		}
		_ = json.NewDecoder(r.Body).Decode(&got)
		w.WriteHeader(http.StatusCreated)
	}))
	defer srv.Close()
	cfg := testConfig(srv.URL)
	cfg.internalCallbackURL = "http://127.0.0.1:8778"
	if err := registerAdapter(context.Background(), cfg); err != nil {
		t.Fatal(err)
	}
	if got.Provider != "teams" || got.AccountID != "tenant-1" || got.CallbackURL != "http://127.0.0.1:8778" {
		t.Fatalf("registered %+v", got)
	}
	if got.Capabilities.MaxMessageLength != teamsMaxMessageLength || got.Capabilities.SupportsAttachments {
		t.Fatalf("capabilities %+v", got.Capabilities)
	}
}

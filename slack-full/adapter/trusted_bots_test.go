package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync"
	"testing"
	"time"
)

// Fake ids only. Real Slack ids never appear in tests.
const (
	tbSelfApp    = "ASELFAPP1"
	tbTrusted    = "ATRUSTED1"
	tbOther      = "AOTHERAPP1"
	tbTrustedBot = "BTRUSTED1"
	tbTrustedUsr = "UTRUSTEDBOT"
)

// fakeBotResolver scripts bots.info: one result per call, the last repeated.
type fakeBotResolver struct {
	mu      sync.Mutex
	results map[string][]fakeBotResult
	calls   map[string]int
}

type fakeBotResult struct {
	info    companyBotInfo
	outcome botResolveOutcome
}

func newFakeBotResolver() *fakeBotResolver {
	return &fakeBotResolver{results: map[string][]fakeBotResult{}, calls: map[string]int{}}
}

func (f *fakeBotResolver) set(botID string, rs ...fakeBotResult) { f.results[botID] = rs }

func (f *fakeBotResolver) Resolve(botID string) (companyBotInfo, botResolveOutcome) {
	f.mu.Lock()
	defer f.mu.Unlock()
	n := f.calls[botID]
	f.calls[botID]++
	rs := f.results[botID]
	if len(rs) == 0 {
		return companyBotInfo{}, botResolveUnknown
	}
	if n >= len(rs) {
		n = len(rs) - 1
	}
	return rs[n].info, rs[n].outcome
}

func (f *fakeBotResolver) callCount(botID string) int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.calls[botID]
}

func okBot(userID, appID string) fakeBotResult {
	return fakeBotResult{info: companyBotInfo{UserID: userID, AppID: appID}, outcome: botResolveOK}
}

// newTestTrustedBotGate lists tbTrusted with tbSelfApp as the own app, and
// records the sleeps between bots.info retries instead of sleeping.
func newTestTrustedBotGate(r companyAuthorResolver, apps ...string) (*trustedBotGate, *[]time.Duration) {
	if len(apps) == 0 {
		apps = []string{tbTrusted}
	}
	g := newTrustedBotGate(apps, tbSelfApp, "", r)
	var sleeps []time.Duration
	g.sleep = func(d time.Duration) { sleeps = append(sleeps, d) }
	return g, &sleeps
}

// trustedBotMsg is a modern bot post: bot_id, user, app_id and bot_profile.
func trustedBotMsg(appID string) slackMessageEvent {
	return slackMessageEvent{
		Type: "message", Channel: "C1", TS: "100.000001", Text: "press: clock in",
		BotID: tbTrustedBot, User: tbTrustedUsr, AppID: appID,
		BotProfile: json.RawMessage(`{"app_id":"` + appID + `","name":"Press Bot"}`),
	}
}

func TestTrustedBotGateAdmitsListedApp(t *testing.T) {
	r := newFakeBotResolver()
	r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
	g, _ := newTestTrustedBotGate(r)

	actor, ok := g.admit(trustedBotMsg(tbTrusted), tbSelfApp)
	if !ok {
		t.Fatal("listed app was dropped")
	}
	want := trustedBotActor{ID: tbTrustedUsr, DisplayName: "Press Bot", AppID: tbTrusted}
	if actor != want {
		t.Errorf("actor = %+v, want %+v", actor, want)
	}
	if got := r.callCount(tbTrustedBot); got != 1 {
		t.Errorf("bots.info calls = %d, want 1", got)
	}
}

// A bot_message-subtype post with no user and no declared app id is admitted
// on the strength of bots.info alone.
func TestTrustedBotGateAdmitsBotMessageSubtypeVerifiedByBotsInfo(t *testing.T) {
	r := newFakeBotResolver()
	r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
	g, _ := newTestTrustedBotGate(r)

	msg := slackMessageEvent{
		Type: "message", Subtype: "bot_message", Channel: "C1", TS: "100.000002",
		Text: "press", BotID: tbTrustedBot, Username: "press-legacy",
	}
	actor, ok := g.admit(msg, tbSelfApp)
	if !ok {
		t.Fatal("verified bot_message was dropped")
	}
	if actor.ID != tbTrustedUsr || actor.DisplayName != "press-legacy" || actor.AppID != tbTrusted {
		t.Errorf("actor = %+v", actor)
	}
}

func TestTrustedBotGateDropsUnlistedApp(t *testing.T) {
	t.Run("declared app id: no bots.info call", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbOther))
		g, _ := newTestTrustedBotGate(r)
		if _, ok := g.admit(trustedBotMsg(tbOther), tbSelfApp); ok {
			t.Fatal("unlisted app admitted")
		}
		if got := r.callCount(tbTrustedBot); got != 0 {
			t.Errorf("bots.info calls = %d, want 0 (declared unlisted app is dropped up front)", got)
		}
	})
	t.Run("undeclared, bots.info names an unlisted app", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbOther))
		g, _ := newTestTrustedBotGate(r)
		msg := trustedBotMsg("")
		msg.BotProfile = nil
		if _, ok := g.admit(msg, tbSelfApp); ok {
			t.Fatal("unlisted app admitted")
		}
	})
	t.Run("empty allowlist admits no bot", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
		g := newTrustedBotGate(nil, tbSelfApp, "", r)
		if _, ok := g.admit(trustedBotMsg(tbTrusted), tbSelfApp); ok {
			t.Fatal("bot admitted with no allowlist")
		}
		if got := r.callCount(tbTrustedBot); got != 0 {
			t.Errorf("bots.info calls = %d, want 0", got)
		}
	})
	t.Run("nil gate admits no bot", func(t *testing.T) {
		var g *trustedBotGate
		if _, ok := g.admit(trustedBotMsg(tbTrusted), tbSelfApp); ok {
			t.Fatal("nil gate admitted a bot")
		}
	})
}

func TestTrustedBotGateDropsOwnApp(t *testing.T) {
	t.Run("declared own app, even when listed", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbSelfApp))
		g, _ := newTestTrustedBotGate(r, tbTrusted, tbSelfApp)
		if _, ok := g.admit(trustedBotMsg(tbSelfApp), tbSelfApp); ok {
			t.Fatal("own app admitted")
		}
		if got := r.callCount(tbTrustedBot); got != 0 {
			t.Errorf("bots.info calls = %d, want 0", got)
		}
	})
	t.Run("receiving app from the envelope, SLACK_APP_ID unset", func(t *testing.T) {
		r := newFakeBotResolver()
		g := newTrustedBotGate([]string{tbTrusted, tbSelfApp}, "", "", r)
		if _, ok := g.admit(trustedBotMsg(tbSelfApp), tbSelfApp); ok {
			t.Fatal("own app admitted")
		}
	})
	t.Run("undeclared, bots.info resolves to the own app", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbSelfApp))
		g, _ := newTestTrustedBotGate(r, tbTrusted, tbSelfApp)
		msg := trustedBotMsg("")
		msg.BotProfile = nil
		if _, ok := g.admit(msg, tbSelfApp); ok {
			t.Fatal("own app admitted")
		}
	})
	t.Run("own bot user", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
		g := newTrustedBotGate([]string{tbTrusted}, tbSelfApp, tbTrustedUsr, r)
		if _, ok := g.admit(trustedBotMsg(tbTrusted), tbSelfApp); ok {
			t.Fatal("own bot user admitted")
		}
	})
	t.Run("own app id unknown admits no bot", func(t *testing.T) {
		r := newFakeBotResolver()
		r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
		g := newTrustedBotGate([]string{tbTrusted}, "", "", r)
		if _, ok := g.admit(trustedBotMsg(tbTrusted), ""); ok {
			t.Fatal("bot admitted without a loop guard")
		}
	})
	t.Run("SLACK_TRUSTED_BOT_APPS cannot list SLACK_APP_ID", func(t *testing.T) {
		got := parseTrustedBotApps(tbTrusted+","+tbSelfApp, tbSelfApp)
		if !reflect.DeepEqual(got, []string{tbTrusted}) {
			t.Errorf("parsed = %v, want [%s]", got, tbTrusted)
		}
	})
}

func TestTrustedBotGateDropsBotsInfoMismatch(t *testing.T) {
	cases := []struct {
		name   string
		msg    func() slackMessageEvent
		result fakeBotResult
	}{
		{
			name:   "bots.info app differs from the declared app",
			msg:    func() slackMessageEvent { return trustedBotMsg(tbTrusted) },
			result: okBot(tbTrustedUsr, tbOther),
		},
		{
			name:   "bots.info user differs from the event user",
			msg:    func() slackMessageEvent { return trustedBotMsg(tbTrusted) },
			result: okBot("USOMEONEELSE", tbTrusted),
		},
		{
			name: "app_id and bot_profile.app_id disagree",
			msg: func() slackMessageEvent {
				m := trustedBotMsg(tbTrusted)
				m.BotProfile = json.RawMessage(`{"app_id":"` + tbOther + `","name":"Press Bot"}`)
				return m
			},
			result: okBot(tbTrustedUsr, tbTrusted),
		},
		{
			name:   "bot not found",
			msg:    func() slackMessageEvent { return trustedBotMsg(tbTrusted) },
			result: fakeBotResult{outcome: botResolveUnknown},
		},
		{
			name:   "bots.info keeps failing",
			msg:    func() slackMessageEvent { return trustedBotMsg(tbTrusted) },
			result: fakeBotResult{outcome: botResolveTransient},
		},
		{
			name: "no bot_id to verify",
			msg: func() slackMessageEvent {
				m := trustedBotMsg(tbTrusted)
				m.BotID = ""
				m.Subtype = "bot_message"
				return m
			},
			result: okBot(tbTrustedUsr, tbTrusted),
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			r := newFakeBotResolver()
			r.set(tbTrustedBot, tc.result)
			// Both apps listed: the mismatch alone must drop the message.
			g, _ := newTestTrustedBotGate(r, tbTrusted, tbOther)
			if _, ok := g.admit(tc.msg(), tbSelfApp); ok {
				t.Fatal("mismatched bot admitted")
			}
		})
	}
}

func TestTrustedBotGateRetriesTransientBotsInfo(t *testing.T) {
	transient := fakeBotResult{outcome: botResolveTransient}

	r := newFakeBotResolver()
	r.set(tbTrustedBot, transient, okBot(tbTrustedUsr, tbTrusted))
	g, sleeps := newTestTrustedBotGate(r)
	if _, ok := g.admit(trustedBotMsg(tbTrusted), tbSelfApp); !ok {
		t.Fatal("bot dropped after bots.info recovered")
	}
	if !reflect.DeepEqual(*sleeps, []time.Duration{trustedBotResolveBackoff}) {
		t.Errorf("sleeps = %v", *sleeps)
	}

	r = newFakeBotResolver()
	r.set(tbTrustedBot, transient)
	g, sleeps = newTestTrustedBotGate(r)
	if _, ok := g.admit(trustedBotMsg(tbTrusted), tbSelfApp); ok {
		t.Fatal("bot admitted although bots.info never answered")
	}
	if got := r.callCount(tbTrustedBot); got != trustedBotResolveAttempts {
		t.Errorf("bots.info calls = %d, want %d", got, trustedBotResolveAttempts)
	}
	if want := []time.Duration{trustedBotResolveBackoff, 2 * trustedBotResolveBackoff}; !reflect.DeepEqual(*sleeps, want) {
		t.Errorf("sleeps = %v, want %v", *sleeps, want)
	}
}

func TestTrustedBotGateKeepsSubtypeFilter(t *testing.T) {
	r := newFakeBotResolver()
	r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
	g, _ := newTestTrustedBotGate(r)
	for _, st := range []string{"message_changed", "message_deleted", "channel_join", "file_share", "thread_broadcast"} {
		msg := trustedBotMsg(tbTrusted)
		msg.Subtype = st
		if _, ok := g.admit(msg, tbSelfApp); ok {
			t.Errorf("subtype %q admitted", st)
		}
	}
	if got := r.callCount(tbTrustedBot); got != 0 {
		t.Errorf("bots.info calls = %d, want 0", got)
	}
}

func TestTrustedBotGateDropLogRate(t *testing.T) {
	read, restore := captureLog(t)
	defer restore()

	r := newFakeBotResolver()
	r.set(tbTrustedBot, okBot(tbTrustedUsr, tbOther))
	g, _ := newTestTrustedBotGate(r, tbTrusted, tbOther)
	now := time.Unix(1_700_000_000, 0)
	g.now = func() time.Time { return now }

	unlisted := trustedBotMsg("AUNLISTED1")
	g.admit(unlisted, tbSelfApp)
	g.admit(unlisted, tbSelfApp)
	if got := strings.Count(read(), "app=AUNLISTED1"); got != 1 {
		t.Fatalf("unlisted drops logged %d times within the hour, want 1:\n%s", got, read())
	}
	now = now.Add(trustedBotDropLogInterval)
	g.admit(unlisted, tbSelfApp)
	if got := strings.Count(read(), "app=AUNLISTED1"); got != 2 {
		t.Fatalf("unlisted drops logged %d times after an hour, want 2", got)
	}
	if !strings.Contains(read(), `inbound dropped: bot message chan=C1 ts=100.000001 bot_id=BTRUSTED1 app=AUNLISTED1 bot="Press Bot"`) {
		t.Errorf("drop line shape changed:\n%s", read())
	}

	// A listed app's message that fails verification is logged every time.
	mismatch := trustedBotMsg(tbTrusted)
	g.admit(mismatch, tbSelfApp)
	g.admit(mismatch, tbSelfApp)
	if got := strings.Count(read(), "does not match bots.info app"); got != 2 {
		t.Errorf("verification drops logged %d times, want 2", got)
	}

	// The adapter's own posts are expected and never logged.
	before := read()
	g.admit(trustedBotMsg(tbSelfApp), tbSelfApp)
	if read() != before {
		t.Errorf("own-app drop was logged: %s", strings.TrimPrefix(read(), before))
	}
}

func TestParseTrustedBotApps(t *testing.T) {
	read, restore := captureLog(t)
	defer restore()

	got := parseTrustedBotApps(" ATRUSTED1, AOTHERAPP1\nnot-an-id ATRUSTED1\ta1lower ", "")
	if want := []string{"ATRUSTED1", "AOTHERAPP1"}; !reflect.DeepEqual(got, want) {
		t.Errorf("parsed = %v, want %v", got, want)
	}
	if strings.Count(read(), "SLACK_TRUSTED_BOT_APPS: skipping") != 2 {
		t.Errorf("want a warning for each malformed entry:\n%s", read())
	}
	if got := parseTrustedBotApps("", ""); got != nil {
		t.Errorf("empty = %v, want nil", got)
	}
}

func TestLoadConfigTrustedBotApps(t *testing.T) {
	env := baseSlackEnv()
	env["SLACK_APP_ID"] = tbSelfApp
	env["SLACK_TRUSTED_BOT_APPS"] = tbTrusted + "," + tbSelfApp
	cfg, err := loadConfigFromEnv(stubEnv(env))
	if err != nil {
		t.Fatalf("loadConfigFromEnv: %v", err)
	}
	if !reflect.DeepEqual(cfg.trustedBotApps, []string{tbTrusted}) {
		t.Errorf("trustedBotApps = %v, want [%s]", cfg.trustedBotApps, tbTrusted)
	}
}

// TestProcessSlackEventTrustedBot drives the legacy path end to end: a listed
// bot's message is posted inbound as a bot actor; the adapter's own post and
// an unlisted bot's are not; a human message is unchanged.
func TestProcessSlackEventTrustedBot(t *testing.T) {
	var mu sync.Mutex
	var actors []externalActor
	gcStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		if strings.Contains(r.URL.Path, "/extmsg/inbound") {
			var req struct {
				Message externalInboundMessage `json:"message"`
			}
			_ = json.Unmarshal(raw, &req)
			mu.Lock()
			actors = append(actors, req.Message.Actor)
			mu.Unlock()
		}
		w.WriteHeader(http.StatusAccepted)
	}))
	t.Cleanup(gcStub.Close)

	r := newFakeBotResolver()
	r.set(tbTrustedBot, okBot(tbTrustedUsr, tbTrusted))
	gate, _ := newTestTrustedBotGate(r)
	cfg := config{
		gcAPIBase:   gcStub.URL,
		cityName:    "test-city",
		provider:    "slack",
		accountID:   "T1",
		dispatchSem: defaultTestDispatchSem,
		trustedBots: gate,
	}
	send := func(msg slackMessageEvent) []externalActor {
		t.Helper()
		mu.Lock()
		actors = nil
		mu.Unlock()
		raw, _ := json.Marshal(msg)
		env := slackEventEnvelope{Type: "event_callback", APIAppID: tbSelfApp, Event: raw}
		processSlackEvent(cfg, nil, nil, nil, nil, nil, env, func() {})
		mu.Lock()
		defer mu.Unlock()
		return append([]externalActor(nil), actors...)
	}

	read, restore := captureLog(t)
	got := send(trustedBotMsg(tbTrusted))
	logs := read()
	restore()
	want := []externalActor{{ID: tbTrustedUsr, DisplayName: "Press Bot", IsBot: true}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("listed bot: posted actors = %+v, want %+v", got, want)
	}
	if !strings.Contains(logs, "inbound: chan=C1 user="+tbTrustedUsr) || !strings.Contains(logs, `bot="Press Bot" app=`+tbTrusted) {
		t.Errorf("admitted bot inbound line missing:\n%s", logs)
	}

	if got := send(trustedBotMsg(tbSelfApp)); len(got) != 0 {
		t.Errorf("own app: posted %+v, want nothing", got)
	}
	if got := send(trustedBotMsg(tbOther)); len(got) != 0 {
		t.Errorf("unlisted app: posted %+v, want nothing", got)
	}

	human := slackMessageEvent{Type: "message", Channel: "C1", User: "UHUMAN1", TS: "100.000003", Text: "hi"}
	if got, want := send(human), []externalActor{{ID: "UHUMAN1", DisplayName: "UHUMAN1"}}; !reflect.DeepEqual(got, want) {
		t.Errorf("human: posted %+v, want %+v", got, want)
	}
}

func TestCheckTrustedBotScope(t *testing.T) {
	cases := []struct {
		scopes string
		want   bool
		warn   bool
	}{
		{scopes: "chat:write,users:read,channels:history", want: true},
		{scopes: "chat:write, users:read", want: true},
		{scopes: "chat:write,users:read.email", want: false, warn: true},
		{scopes: "", want: true},
	}
	for _, tc := range cases {
		t.Run(tc.scopes, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/auth.test" || r.Header.Get("Authorization") != "Bearer xoxb-test" {
					http.Error(w, "unexpected request", http.StatusBadRequest)
					return
				}
				if tc.scopes != "" {
					w.Header().Set("X-OAuth-Scopes", tc.scopes)
				}
				_, _ = w.Write([]byte(`{"ok":true}`))
			}))
			defer srv.Close()
			prev := slackAPIBase
			slackAPIBase = srv.URL
			defer func() { slackAPIBase = prev }()
			read, restore := captureLog(t)
			defer restore()

			if got := checkTrustedBotScope(srv.Client(), "xoxb-test"); got != tc.want {
				t.Errorf("checkTrustedBotScope = %v, want %v", got, tc.want)
			}
			if warned := strings.Contains(read(), "lacks the users:read scope"); warned != tc.warn {
				t.Errorf("warned = %v, want %v: %s", warned, tc.warn, read())
			}
		})
	}
}

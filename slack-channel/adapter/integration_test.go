package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

// TestSmokeVerbRoundTrip is the acceptance smoke test: it runs the real
// bash verb wrappers against a live adapter (internal mux over TCP) with
// fake Slack + gc backends, then drives an inbound event through the public
// mux. It exercises the full Tier-2 loop:
//
//	bind-room  → channel bound to a session
//	inbound    → bound session receives bridge-mail (via fake gc)
//	publish    → message lands in the channel (via fake Slack)
//	react      → reaction on the latest inbound message
//
// It needs sh/jq/curl on PATH; it skips cleanly when they are absent.
func TestSmokeVerbRoundTrip(t *testing.T) {
	for _, bin := range []string{"sh", "jq", "curl"} {
		if _, err := exec.LookPath(bin); err != nil {
			t.Skipf("%s not on PATH; skipping verb smoke test", bin)
		}
	}

	// Fake Slack: records chat.postMessage + reactions.add, always OK.
	var slackMu sync.Mutex
	var posts []slackPostMessageReq
	var reactions []slackReactionsAddReq
	slack := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		slackMu.Lock()
		defer slackMu.Unlock()
		switch {
		case strings.HasSuffix(r.URL.Path, "/chat.postMessage"):
			var req slackPostMessageReq
			_ = json.NewDecoder(r.Body).Decode(&req)
			posts = append(posts, req)
			_ = json.NewEncoder(w).Encode(slackPostMessageResp{OK: true, TS: "200.1", Channel: req.Channel})
		case strings.HasSuffix(r.URL.Path, "/reactions.add"):
			var req slackReactionsAddReq
			_ = json.NewDecoder(r.Body).Decode(&req)
			reactions = append(reactions, req)
			_ = json.NewEncoder(w).Encode(slackReactionsAddResp{OK: true})
		default:
			t.Errorf("unexpected slack path %s", r.URL.Path)
		}
	}))
	defer slack.Close()

	// Fake gc: records extmsg inbound deliveries.
	var gcMu sync.Mutex
	var inbound []externalInboundMessage
	gc := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var wrap struct {
			Message externalInboundMessage `json:"message"`
		}
		_ = json.NewDecoder(r.Body).Decode(&wrap)
		gcMu.Lock()
		inbound = append(inbound, wrap.Message)
		gcMu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	defer gc.Close()

	cfg := config{
		cityName:      "smokecity",
		provider:      "slack",
		workspaceID:   "T123",
		botToken:      "xoxb-smoke",
		signingSecret: "smoke-secret",
		inboundTarget: "mayor",
		slackAPIBase:  slack.URL,
		gcAPIBase:     gc.URL,
		registryDir:   t.TempDir(),
	}
	srv, err := newServer(cfg)
	if err != nil {
		t.Fatalf("newServer: %v", err)
	}

	internalMux := http.NewServeMux()
	internalMux.HandleFunc("POST /publish", srv.handlePublish())
	internalMux.HandleFunc("POST /publish-to-channel", srv.handlePublishToChannel())
	internalMux.HandleFunc("POST /reply-current", srv.handleReplyCurrent())
	internalMux.HandleFunc("POST /react", srv.handleReact())
	internalMux.HandleFunc("POST /bindings", srv.handleBind())
	internal := httptest.NewServer(internalMux)
	defer internal.Close()

	publicMux := http.NewServeMux()
	publicMux.HandleFunc("/slack/events", srv.handleSlackEvents())
	public := httptest.NewServer(publicMux)
	defer public.Close()

	commandsDir, err := filepath.Abs("../commands")
	if err != nil {
		t.Fatal(err)
	}
	runVerb := func(verb string, args ...string) (string, error) {
		cmd := exec.Command("sh", append([]string{filepath.Join(commandsDir, verb+".sh")}, args...)...)
		cmd.Env = append(os.Environ(),
			"GC_CITY_NAME=smokecity",
			"GC_SESSION_ID=sess-pl",
			"SLACK_CHANNEL_ADAPTER_URL="+internal.URL,
		)
		out, err := cmd.CombinedOutput()
		return string(out), err
	}

	// 1. bind-room: bind C1 to sess-pl.
	if out, err := runVerb("bind-room", "C1", "sess-pl"); err != nil {
		t.Fatalf("bind-room failed: %v\n%s", err, out)
	}
	if _, ok := srv.bindingForChannel("C1"); !ok {
		t.Fatal("binding not persisted by bind-room verb")
	}

	// 2. inbound: a human posts in C1 → sess-pl receives bridge-mail.
	ev := slackMessageEvent{Type: "message", User: "U9", Text: "status?", Channel: "C1", TS: "100.1"}
	raw, _ := json.Marshal(slackEventEnvelope{Type: "event_callback", Event: mustJSON(ev)})
	ts := strconv.FormatInt(time.Now().Unix(), 10)
	req, _ := http.NewRequest(http.MethodPost, public.URL+"/slack/events", strings.NewReader(string(raw)))
	req.Header.Set("X-Slack-Request-Timestamp", ts)
	req.Header.Set("X-Slack-Signature", signSlack(cfg.signingSecret, ts, raw))
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("inbound POST: %v", err)
	}
	_ = resp.Body.Close()
	waitFor(t, func() bool {
		gcMu.Lock()
		defer gcMu.Unlock()
		return len(inbound) == 1 && inbound[0].ExplicitTarget == "sess-pl" && inbound[0].Text == "status?"
	}, "bound session did not receive inbound bridge-mail")

	// 3. publish: sess-pl publishes back into its bound channel.
	if out, err := runVerb("publish", "--body", "build is green"); err != nil {
		t.Fatalf("publish failed: %v\n%s", err, out)
	}
	slackMu.Lock()
	if len(posts) != 1 || posts[0].Channel != "C1" || posts[0].Text != "build is green" {
		t.Errorf("publish did not land in channel: %+v", posts)
	}
	slackMu.Unlock()

	// 4. react: reaction on the latest inbound message ts.
	if out, err := runVerb("react", "--emoji", "white_check_mark"); err != nil {
		t.Fatalf("react failed: %v\n%s", err, out)
	}
	slackMu.Lock()
	if len(reactions) != 1 || reactions[0].Timestamp != "100.1" || reactions[0].Name != "white_check_mark" {
		t.Errorf("react did not target latest inbound: %+v", reactions)
	}
	slackMu.Unlock()
}

func mustJSON(v any) []byte {
	b, _ := json.Marshal(v)
	return b
}

func waitFor(t *testing.T, cond func() bool, msg string) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal(msg)
}

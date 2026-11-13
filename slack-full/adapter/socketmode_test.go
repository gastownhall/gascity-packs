package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/coder/websocket"
)

// scriptedConn is a socketConn that replays a fixed sequence of frames and
// records everything written back, so the envelope loop can be exercised
// without a server.
type scriptedConn struct {
	mu     sync.Mutex
	frames [][]byte
	next   int
	writes [][]byte
	closed bool
	// blockAfterScript, when set, makes Read block on ctx instead of
	// returning io.EOF once the script is exhausted — used to model a
	// connection that stays open.
	blockAfterScript bool
	// pingErr, when set, makes Ping fail — a wedged connection.
	pingErr error
	pings   int
}

func (s *scriptedConn) Read(ctx context.Context) ([]byte, error) {
	s.mu.Lock()
	if s.next < len(s.frames) {
		frame := s.frames[s.next]
		s.next++
		s.mu.Unlock()
		return frame, nil
	}
	s.mu.Unlock()
	if s.blockAfterScript {
		<-ctx.Done()
		return nil, ctx.Err()
	}
	return nil, io.EOF
}

func (s *scriptedConn) Write(_ context.Context, data []byte) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.writes = append(s.writes, append([]byte(nil), data...))
	return nil
}

func (s *scriptedConn) Ping(_ context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.pings++
	return s.pingErr
}

func (s *scriptedConn) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.closed = true
	return nil
}

func (s *scriptedConn) written() [][]byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([][]byte(nil), s.writes...)
}

// ackedIDs decodes every ack frame written to conn.
func ackedIDs(t *testing.T, conn *scriptedConn) []string {
	t.Helper()
	var ids []string
	for _, w := range conn.written() {
		var ack map[string]string
		if err := json.Unmarshal(w, &ack); err != nil {
			t.Fatalf("ack is not JSON: %v (%s)", err, w)
		}
		ids = append(ids, ack["envelope_id"])
	}
	return ids
}

// deliveredPayload is one call to a recording socketDeliverFunc.
type deliveredPayload struct {
	payload     []byte
	retryNum    int
	retryReason string
}

// recordingDeliver returns a socketDeliverFunc answering status, and the
// channel each delivery is reported on.
func recordingDeliver(status int) (socketDeliverFunc, chan deliveredPayload) {
	got := make(chan deliveredPayload, 16)
	return func(payload []byte, retryNum int, retryReason string) int {
		got <- deliveredPayload{payload: append([]byte(nil), payload...), retryNum: retryNum, retryReason: retryReason}
		return status
	}, got
}

// newTestTransport builds a transport with the production timers and the
// given sink. Tests that need scaled-down timers overwrite .timings.
func newTestTransport(deliver socketDeliverFunc) *socketModeTransport {
	return &socketModeTransport{
		appToken: "xapp-1-A-abc",
		apiBase:  "http://127.0.0.1:1",
		timings:  defaultSocketTimings(),
		deliver:  deliver,
	}
}

// messagePayload is the Events API body for a human channel message, the same
// bytes the HTTP path would receive.
func messagePayload(t *testing.T, eventID, channel, ts, text string) []byte {
	t.Helper()
	event, err := json.Marshal(slackMessageEvent{
		Type:        "message",
		User:        "U99",
		Text:        text,
		Channel:     channel,
		TS:          ts,
		ChannelType: "channel",
	})
	if err != nil {
		t.Fatalf("marshal event: %v", err)
	}
	payload, err := json.Marshal(slackEventEnvelope{
		Type:     "event_callback",
		TeamID:   "T01234567",
		APIAppID: "A0SWITCH",
		EventID:  eventID,
		Event:    event,
	})
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}
	return payload
}

// eventsAPIFrame wraps a payload in a Socket Mode envelope.
func eventsAPIFrame(t *testing.T, envelopeID string, payload []byte, retryAttempt int) []byte {
	t.Helper()
	frame, err := json.Marshal(socketEnvelope{
		Type:         "events_api",
		EnvelopeID:   envelopeID,
		Payload:      payload,
		RetryAttempt: retryAttempt,
	})
	if err != nil {
		t.Fatalf("marshal envelope: %v", err)
	}
	return frame
}

func TestLoadConfigSocketModeSelector(t *testing.T) {
	env := baseSlackEnv()
	env["SLACK_APP_TOKEN"] = "xapp-1-A-abc"
	// Socket Mode does not consult the signing secret. slack-full already
	// treats it as optional (the apps registry can supply it), and an app
	// token must not change that.
	delete(env, "SLACK_SIGNING_SECRET")
	cfg, err := loadConfigFromEnv(stubEnv(env))
	if err != nil {
		t.Fatalf("socket-mode config rejected: %v", err)
	}
	if !cfg.socketMode() {
		t.Error("socketMode() = false with SLACK_APP_TOKEN set")
	}
	if cfg.appToken != "xapp-1-A-abc" {
		t.Errorf("appToken = %q", cfg.appToken)
	}

	cfg, err = loadConfigFromEnv(stubEnv(baseSlackEnv()))
	if err != nil {
		t.Fatalf("http-only config rejected: %v", err)
	}
	if cfg.socketMode() {
		t.Error("socketMode() = true without SLACK_APP_TOKEN")
	}
}

func TestLoadConfigRejectsBotTokenAsAppToken(t *testing.T) {
	env := baseSlackEnv()
	env["SLACK_APP_TOKEN"] = "xoxb-not-an-app-token"
	_, err := loadConfigFromEnv(stubEnv(env))
	if err == nil || !strings.Contains(err.Error(), "xapp-") {
		t.Errorf("err = %v, want a message naming the xapp- prefix", err)
	}
}

func TestOpenSocketConnectionURL(t *testing.T) {
	var gotAuth, gotPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true,"url":"wss://wss-primary.slack.com/link/?ticket=abc"}`))
	}))
	defer srv.Close()

	url, err := openSocketConnectionURL(context.Background(), srv.URL, "xapp-1-A-abc")
	if err != nil {
		t.Fatalf("openSocketConnectionURL: %v", err)
	}
	if url != "wss://wss-primary.slack.com/link/?ticket=abc" {
		t.Errorf("url = %q", url)
	}
	// The app-level token, not the bot token, authenticates this call.
	if gotAuth != "Bearer xapp-1-A-abc" {
		t.Errorf("Authorization = %q", gotAuth)
	}
	if gotPath != "/apps.connections.open" {
		t.Errorf("path = %q", gotPath)
	}
}

func TestOpenSocketConnectionURLSurfacesScopeHint(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"ok":false,"error":"invalid_auth"}`))
	}))
	defer srv.Close()

	_, err := openSocketConnectionURL(context.Background(), srv.URL, "xapp-1-A-abc")
	if err == nil {
		t.Fatal("want error on ok:false")
	}
	// The overwhelmingly common cause is a missing scope; the message should
	// say so rather than leaving the operator with a bare invalid_auth.
	if !strings.Contains(err.Error(), "invalid_auth") || !strings.Contains(err.Error(), "connections:write") {
		t.Errorf("err = %v, want invalid_auth plus the connections:write hint", err)
	}
}

// TestPumpSocketDeliversThenAcks pins the ack order that differs from
// slack-channel: the envelope reaches the shared event path first, and the
// ack is written only after that path has answered.
func TestPumpSocketDeliversThenAcks(t *testing.T) {
	conn := &scriptedConn{}
	var writesAtDelivery = -1
	var got []byte
	tr := newTestTransport(func(payload []byte, _ int, _ string) int {
		writesAtDelivery = len(conn.written())
		got = append([]byte(nil), payload...)
		return http.StatusOK
	})
	payload := messagePayload(t, "Ev1", "C42", "1700000000.0001", "deploy please")
	conn.frames = [][]byte{
		[]byte(`{"type":"hello","num_connections":1}`),
		eventsAPIFrame(t, "env-1", payload, 0),
	}

	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v, want io.EOF at end of script", err)
	}
	if string(got) != string(payload) {
		t.Errorf("delivered payload = %s, want the envelope payload byte-for-byte", got)
	}
	if writesAtDelivery != 0 {
		t.Errorf("%d frames written before delivery, want the ack to follow it", writesAtDelivery)
	}
	if ids := ackedIDs(t, conn); len(ids) != 1 || ids[0] != "env-1" {
		t.Errorf("acks = %v, want exactly [env-1] (hello is not acked)", ids)
	}
	if !conn.closed {
		t.Error("pumpSocket returned without closing the connection")
	}
}

// TestPumpSocketWithholdsAckOnRetryableAnswer: a 5xx from the event path (the
// company gateway's closed barrier or failed receipt write) must leave the
// envelope unacked so Slack redelivers it, as it retries a 503 over HTTP. A
// later envelope on the same connection is still processed.
func TestPumpSocketWithholdsAckOnRetryableAnswer(t *testing.T) {
	statuses := []int{http.StatusServiceUnavailable, http.StatusOK}
	calls := 0
	tr := newTestTransport(func([]byte, int, string) int {
		s := statuses[calls]
		calls++
		return s
	})
	conn := &scriptedConn{frames: [][]byte{
		eventsAPIFrame(t, "env-503", messagePayload(t, "Ev1", "C42", "1.1", "first"), 0),
		eventsAPIFrame(t, "env-ok", messagePayload(t, "Ev2", "C42", "1.2", "second"), 0),
	}}
	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v", err)
	}
	if calls != 2 {
		t.Fatalf("delivered %d envelopes, want 2", calls)
	}
	if ids := ackedIDs(t, conn); len(ids) != 1 || ids[0] != "env-ok" {
		t.Errorf("acks = %v, want only env-ok (the 503 must stay unacked)", ids)
	}
}

// TestPumpSocketAcksAndDropsInteractivity: interactive and slash_commands
// envelopes are not carried by this transport. They are acked so Slack does
// not retry, and never reach the events path.
func TestPumpSocketAcksAndDropsInteractivity(t *testing.T) {
	deliver, got := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	conn := &scriptedConn{frames: [][]byte{
		[]byte(`{"type":"interactive","envelope_id":"env-i","payload":{"type":"block_actions"}}`),
		[]byte(`{"type":"slash_commands","envelope_id":"env-s","payload":{"command":"/gc"}}`),
	}}
	read, cleanup := captureLog(t)
	t.Cleanup(cleanup)
	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v", err)
	}
	if ids := ackedIDs(t, conn); len(ids) != 2 {
		t.Errorf("acks = %v, want both envelopes acked", ids)
	}
	select {
	case d := <-got:
		t.Fatalf("non-events_api envelope reached the events path: %s", d.payload)
	default:
	}
	if !strings.Contains(read(), "/slack/interactions only") {
		t.Errorf("drop not explained in the log:\n%s", read())
	}
}

func TestPumpSocketPassesRedeliveryHints(t *testing.T) {
	deliver, got := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	frame, err := json.Marshal(socketEnvelope{
		Type:         "events_api",
		EnvelopeID:   "env-r",
		Payload:      messagePayload(t, "Ev1", "C42", "1.1", "again"),
		RetryAttempt: 2,
		RetryReason:  "timeout",
	})
	if err != nil {
		t.Fatal(err)
	}
	conn := &scriptedConn{frames: [][]byte{frame}}
	_ = tr.pumpSocket(context.Background(), conn, nil)
	d := <-got
	if d.retryNum != 2 || d.retryReason != "timeout" {
		t.Errorf("retry hints = (%d, %q), want (2, \"timeout\")", d.retryNum, d.retryReason)
	}
}

func TestPumpSocketDrainsAfterDisconnect(t *testing.T) {
	deliver, got := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	conn := &scriptedConn{frames: [][]byte{
		[]byte(`{"type":"disconnect","reason":"refresh_requested"}`),
		eventsAPIFrame(t, "env-2", messagePayload(t, "Ev2", "C42", "1.2", "still here"), 0),
	}}

	// A warned-about close is orderly, not an error: envelopes already in
	// flight are still delivered and acked, and the supervisor reconnects
	// without logging a failure.
	if err := tr.pumpSocket(context.Background(), conn, nil); err != nil {
		t.Fatalf("pumpSocket err = %v, want nil after a disconnect warning", err)
	}
	if writes := conn.written(); len(writes) != 1 {
		t.Errorf("wrote %d frames, want the in-flight envelope acked during drain", len(writes))
	}
	select {
	case <-got:
	default:
		t.Fatal("envelope received during drain was never delivered")
	}
}

func TestPumpSocketSkipsUndecodableFrame(t *testing.T) {
	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	conn := &scriptedConn{frames: [][]byte{[]byte(`{not json`)}}
	// A malformed frame must not kill the connection — the next envelope on
	// the same socket should still be read.
	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v, want the loop to continue to EOF", err)
	}
	if len(conn.written()) != 0 {
		t.Error("acked an undecodable frame")
	}
}

func TestPumpSocketStopsOnContextCancel(t *testing.T) {
	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	conn := &scriptedConn{blockAfterScript: true}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- tr.pumpSocket(ctx, conn, nil) }()
	cancel()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("pumpSocket ignored context cancellation")
	}
}

func TestSocketAckEscapesEnvelopeID(t *testing.T) {
	// Envelope ids are Slack-supplied; a hand-concatenated ack would let a
	// crafted id break out of the JSON.
	ack := socketAck(`abc","injected":"x`)
	var decoded map[string]string
	if err := json.Unmarshal(ack, &decoded); err != nil {
		t.Fatalf("ack is not valid JSON: %v (%s)", err, ack)
	}
	if _, injected := decoded["injected"]; injected {
		t.Errorf("envelope id escaped its field: %s", ack)
	}
	if decoded["envelope_id"] != `abc","injected":"x` {
		t.Errorf("envelope_id = %q", decoded["envelope_id"])
	}
}

// fakeSlackSocket stands up the two Slack endpoints Socket Mode touches: a
// WebSocket server running handle for each connection, and an
// apps.connections.open endpoint that hands back its ws:// URL.
func fakeSlackSocket(t *testing.T, handle func(n int, c *websocket.Conn, ctx context.Context)) (apiURL string) {
	t.Helper()
	var mu sync.Mutex
	connections := 0
	wsSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		defer func() { _ = c.CloseNow() }()
		ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
		defer cancel()
		mu.Lock()
		connections++
		n := connections
		mu.Unlock()
		handle(n, c, ctx)
	}))
	apiSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"ok":true,"url":"ws` + strings.TrimPrefix(wsSrv.URL, "http") + `"}`))
	}))
	t.Cleanup(wsSrv.Close)
	t.Cleanup(apiSrv.Close)
	return apiSrv.URL
}

// TestSocketModeEndToEnd drives the real transport: a WebSocket server stands
// in for Slack, and the adapter negotiates, connects, delivers, and acks over
// an actual connection rather than the scripted stub.
func TestSocketModeEndToEnd(t *testing.T) {
	acked := make(chan string, 1)
	payload := messagePayload(t, "Ev-e2e", "C42", "1.3", "ship it")
	apiURL := fakeSlackSocket(t, func(_ int, c *websocket.Conn, ctx context.Context) {
		if err := c.Write(ctx, websocket.MessageText, []byte(`{"type":"hello"}`)); err != nil {
			return
		}
		if err := c.Write(ctx, websocket.MessageText, eventsAPIFrame(t, "env-e2e", payload, 0)); err != nil {
			return
		}
		_, data, err := c.Read(ctx)
		if err != nil {
			return
		}
		var ack map[string]string
		_ = json.Unmarshal(data, &ack)
		acked <- ack["envelope_id"]
	})

	deliver, got := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	tr.apiBase = apiURL

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if _, err := tr.runSocketConnection(ctx, nil); err != nil {
		t.Fatalf("runSocketConnection: %v", err)
	}
	select {
	case id := <-acked:
		if id != "env-e2e" {
			t.Errorf("ack envelope_id = %q, want env-e2e", id)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("no ack reached the server over a real connection")
	}
	select {
	case d := <-got:
		if string(d.payload) != string(payload) {
			t.Errorf("delivered payload = %s", d.payload)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("event never delivered")
	}
}

// TestRunSocketModeReconnectsAfterDisconnect exercises the supervisor over a
// real transport: the first connection is told to go away, and the adapter
// must dial a second one and keep delivering. Reconnect is the steady state in
// Socket Mode — Slack recycles connections routinely — so this is the path
// that matters most in production.
func TestRunSocketModeReconnectsAfterDisconnect(t *testing.T) {
	payload := messagePayload(t, "Ev-after", "C42", "1.4", "after reconnect")
	apiURL := fakeSlackSocket(t, func(n int, c *websocket.Conn, ctx context.Context) {
		if err := c.Write(ctx, websocket.MessageText, []byte(`{"type":"hello"}`)); err != nil {
			return
		}
		if n == 1 {
			// Warn, then go away as Slack does after its grace period.
			_ = c.Write(ctx, websocket.MessageText, []byte(`{"type":"disconnect","reason":"refresh_requested"}`))
			return
		}
		// The replacement connection carries the event that must not be lost.
		_ = c.Write(ctx, websocket.MessageText, eventsAPIFrame(t, "env-after-reconnect", payload, 0))
		<-ctx.Done()
	})

	deliver, got := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	tr.apiBase = apiURL

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go func() { _ = tr.run(ctx) }()

	select {
	case d := <-got:
		if string(d.payload) != string(payload) {
			t.Errorf("delivered payload = %s", d.payload)
		}
	case <-time.After(20 * time.Second):
		t.Fatal("adapter never reconnected after the disconnect")
	}
}

// TestRunSocketModeReconnectsAfterConnectFailure: a failed
// apps.connections.open (Slack down, token revoked mid-flight) is retried with
// backoff rather than ending the supervisor.
func TestRunSocketModeReconnectsAfterConnectFailure(t *testing.T) {
	payload := messagePayload(t, "Ev-retry", "C42", "1.5", "second try")
	var mu sync.Mutex
	opens := 0
	wsAPI := fakeSlackSocket(t, func(_ int, c *websocket.Conn, ctx context.Context) {
		_ = c.Write(ctx, websocket.MessageText, []byte(`{"type":"hello"}`))
		_ = c.Write(ctx, websocket.MessageText, eventsAPIFrame(t, "env-retry", payload, 0))
		<-ctx.Done()
	})
	apiSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		opens++
		n := opens
		mu.Unlock()
		if n == 1 {
			http.Error(w, "upstream unavailable", http.StatusServiceUnavailable)
			return
		}
		// Proxy the second open to the working fake.
		resp, err := http.Post(wsAPI+"/apps.connections.open", "application/x-www-form-urlencoded", nil)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadGateway)
			return
		}
		defer func() { _ = resp.Body.Close() }()
		_, _ = io.Copy(w, resp.Body)
	}))
	t.Cleanup(apiSrv.Close)

	deliver, got := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	tr.apiBase = apiSrv.URL
	tr.timings.backoffMin = 10 * time.Millisecond

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go func() { _ = tr.run(ctx) }()

	select {
	case <-got:
	case <-time.After(10 * time.Second):
		t.Fatal("supervisor gave up after one failed apps.connections.open")
	}
	mu.Lock()
	defer mu.Unlock()
	if opens < 2 {
		t.Errorf("apps.connections.open called %d times, want a retry after the failure", opens)
	}
}

// TestPumpSocketSurvivesIdleConnection is a regression test carried over
// from slack-channel. Bounding each Read with an idle deadline tore down
// healthy connections on quiet workspaces: Slack's keepalives are WebSocket
// pings, answered inside the library without ever waking a read, so silence
// is the normal state of a working connection.
func TestPumpSocketSurvivesIdleConnection(t *testing.T) {
	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	conn := &scriptedConn{blockAfterScript: true} // never sends anything
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	done := make(chan error, 1)
	go func() { done <- tr.pumpSocket(ctx, conn, nil) }()

	select {
	case err := <-done:
		t.Fatalf("pumpSocket gave up on an idle but healthy connection: %v", err)
	case <-time.After(500 * time.Millisecond):
		// Still reading, which is correct.
	}
}

// TestPumpSocketTearsDownWedgedConnection drives the production keepalive
// wiring: a connection Slack has stopped answering must be abandoned.
func TestPumpSocketTearsDownWedgedConnection(t *testing.T) {
	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	tr.timings.pingInterval = time.Millisecond
	// Reads block forever, as a wedged connection does: only the keepalive can
	// end this pump.
	conn := &scriptedConn{blockAfterScript: true, pingErr: errors.New("no pong")}

	done := make(chan error, 1)
	go func() { done <- tr.pumpSocket(context.Background(), conn, nil) }()

	select {
	case err := <-done:
		if err == nil {
			t.Error("pumpSocket reported a clean end for a wedged connection")
		}
	case <-time.After(5 * time.Second):
		t.Fatal("pumpSocket read forever from a connection Slack had stopped answering")
	}
	conn.mu.Lock()
	closed := conn.closed
	conn.mu.Unlock()
	if !closed {
		t.Error("wedged connection was left open")
	}
}

func TestKeepaliveClosesWedgedConnection(t *testing.T) {
	conn := &scriptedConn{blockAfterScript: true, pingErr: errors.New("no pong")}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	closed := make(chan struct{})
	var once sync.Once
	go keepaliveSocket(ctx, conn, time.Millisecond, func() { once.Do(func() { close(closed) }) })

	select {
	case <-closed:
	case <-time.After(5 * time.Second):
		t.Fatal("unanswered ping did not close the connection")
	}
}

func TestKeepaliveStopsWithContext(t *testing.T) {
	conn := &scriptedConn{blockAfterScript: true}
	ctx, cancel := context.WithCancel(context.Background())
	var mu sync.Mutex
	closedCount := 0
	done := make(chan struct{})
	go func() {
		keepaliveSocket(ctx, conn, time.Millisecond, func() {
			mu.Lock()
			closedCount++
			mu.Unlock()
		})
		close(done)
	}()
	time.Sleep(20 * time.Millisecond)
	cancel()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		t.Fatal("keepalive ignored context cancellation")
	}
	mu.Lock()
	defer mu.Unlock()
	// Healthy pings must never trip the close path.
	if closedCount != 0 {
		t.Errorf("closeConn called %d times on a healthy connection", closedCount)
	}
	conn.mu.Lock()
	defer conn.mu.Unlock()
	if conn.pings == 0 {
		t.Error("keepalive never pinged")
	}
}

func TestPumpSocketWarnsBeforeDraining(t *testing.T) {
	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	conn := &scriptedConn{frames: [][]byte{
		[]byte(`{"type":"disconnect","reason":"warning"}`),
		[]byte(`{"type":"disconnect","reason":"warning"}`),
	}}

	warnings := 0
	if err := tr.pumpSocket(context.Background(), conn, func() { warnings++ }); err != nil {
		t.Fatalf("pumpSocket err = %v", err)
	}
	// The warning must fire so the supervisor can dial a replacement while
	// this connection is still draining. A repeat warning is not a second
	// reconnect.
	if warnings != 1 {
		t.Errorf("onWarning fired %d times, want exactly 1", warnings)
	}
}

// TestPumpSocketBoundsDrain pins the drain bound: Read never returns on its
// own here, which leaves the drain timer as the only way out.
func TestPumpSocketBoundsDrain(t *testing.T) {
	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	tr.timings.drainGrace = 25 * time.Millisecond
	conn := &scriptedConn{
		frames:           [][]byte{[]byte(`{"type":"disconnect","reason":"warning"}`)},
		blockAfterScript: true,
	}

	start := time.Now()
	done := make(chan error, 1)
	go func() { done <- tr.pumpSocket(context.Background(), conn, nil) }()

	select {
	case err := <-done:
		if err != nil {
			t.Errorf("drain ended with err = %v, want nil (an elapsed drain is expected, not a failure)", err)
		}
		if elapsed := time.Since(start); elapsed < tr.timings.drainGrace {
			t.Errorf("drain ended after %s, before the %s grace", elapsed, tr.timings.drainGrace)
		}
	case <-time.After(5 * time.Second):
		t.Fatalf("a warned connection whose close never landed drained past %s", tr.timings.drainGrace)
	}
}

// TestDefaultSocketTimingsMatchConstants pins the production timer set to
// literal durations, and pins that the production constructor wires it. Every
// other test injects its own timings, so without this a production interval
// could drift — or be zeroed — with the whole suite green.
func TestDefaultSocketTimingsMatchConstants(t *testing.T) {
	want := socketTimings{
		pingInterval: 30 * time.Second,
		drainGrace:   10 * time.Second,
		backoffMin:   1 * time.Second,
		backoffMax:   30 * time.Second,
		minLifetime:  30 * time.Second,
	}
	if got := defaultSocketTimings(); got != want {
		t.Errorf("defaultSocketTimings() = %+v, want %+v", got, want)
	}
	tr := newSocketModeTransport("xapp-1-A-abc", nil)
	if tr.timings != want {
		t.Errorf("newSocketModeTransport timings = %+v, want %+v", tr.timings, want)
	}
	if tr.apiBase != slackAPIBase {
		t.Errorf("newSocketModeTransport apiBase = %q, want slackAPIBase %q", tr.apiBase, slackAPIBase)
	}
}

func TestSettleBackoffResetsOnlyAfterMinLifetime(t *testing.T) {
	tm := socketTimings{backoffMin: time.Second, backoffMax: 30 * time.Second, minLifetime: 30 * time.Second}
	for _, tc := range []struct {
		name     string
		backoff  time.Duration
		lifetime time.Duration
		want     time.Duration
	}{
		{"outlived the minimum", 8 * time.Second, 30 * time.Second, time.Second},
		{"long-lived", 30 * time.Second, time.Hour, time.Second},
		{"died immediately", 8 * time.Second, 0, 8 * time.Second},
		{"just short of the minimum", 8 * time.Second, 29 * time.Second, 8 * time.Second},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if got := settleBackoff(tc.backoff, tc.lifetime, tm); got != tc.want {
				t.Errorf("settleBackoff(%s, %s) = %s, want %s", tc.backoff, tc.lifetime, got, tc.want)
			}
		})
	}
}

func TestNextBackoffDoublesToCap(t *testing.T) {
	tm := socketTimings{backoffMin: time.Second, backoffMax: 30 * time.Second}
	for _, tc := range []struct{ in, want time.Duration }{
		{time.Second, 2 * time.Second},
		{8 * time.Second, 16 * time.Second},
		{16 * time.Second, 30 * time.Second}, // 32s clamped
		{30 * time.Second, 30 * time.Second},
	} {
		if got := nextBackoff(tc.in, tm); got != tc.want {
			t.Errorf("nextBackoff(%s) = %s, want %s", tc.in, got, tc.want)
		}
	}
}

// TestRunSocketModePacesWarnedReconnect drives the supervisor against a server
// that warns every connection the moment it opens — the shape two adapters
// sharing one app token produce as they displace each other. Redials must be
// paced and escalate, not run at network speed.
func TestRunSocketModePacesWarnedReconnect(t *testing.T) {
	var mu sync.Mutex
	var dials []time.Time
	stop := make(chan struct{})
	dialed := make(chan struct{}, 16)

	wsSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		dials = append(dials, time.Now())
		mu.Unlock()
		select {
		case dialed <- struct{}{}:
		default:
		}

		c, err := websocket.Accept(w, r, nil)
		if err != nil {
			return
		}
		defer func() { _ = c.CloseNow() }()
		ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
		defer cancel()

		if err := c.Write(ctx, websocket.MessageText, []byte(`{"type":"hello"}`)); err != nil {
			return
		}
		if err := c.Write(ctx, websocket.MessageText, []byte(`{"type":"disconnect","reason":"link_disabled"}`)); err != nil {
			return
		}
		// Hold the connection open so the supervisor takes the warned arm,
		// not the done arm.
		select {
		case <-stop:
		case <-ctx.Done():
		}
	}))
	apiSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"ok":true,"url":"ws` + strings.TrimPrefix(wsSrv.URL, "http") + `"}`))
	}))

	deliver, _ := recordingDeliver(http.StatusOK)
	tr := newTestTransport(deliver)
	tr.apiBase = apiSrv.URL
	tr.timings = socketTimings{
		backoffMin: 40 * time.Millisecond,
		backoffMax: 5 * time.Second,
		// No connection here reaches minLifetime, so each successor must carry
		// the escalating delay.
		minLifetime:  time.Hour,
		pingInterval: time.Hour,
		drainGrace:   time.Hour,
	}

	ctx, cancel := context.WithCancel(context.Background())
	// Unwind inside out: release the handlers, stop the supervisor redialling,
	// then close the servers, so nothing touches t after this test returns.
	defer wsSrv.Close()
	defer apiSrv.Close()
	defer cancel()
	defer close(stop)

	go func() { _ = tr.run(ctx) }()

	const wantDials = 4
	for i := 0; i < wantDials; i++ {
		select {
		case <-dialed:
		case <-time.After(10 * time.Second):
			t.Fatalf("only %d of %d dials arrived", i, wantDials)
		}
	}

	mu.Lock()
	got := append([]time.Time(nil), dials...)
	mu.Unlock()
	gaps := make([]time.Duration, 0, len(got)-1)
	for i := 1; i < len(got); i++ {
		gaps = append(gaps, got[i].Sub(got[i-1]))
	}
	for i, gap := range gaps {
		if gap < tr.timings.backoffMin {
			t.Errorf("redial %d came %s after the previous one, inside the %s floor: gaps=%v", i+1, gap, tr.timings.backoffMin, gaps)
		}
	}
	if last := gaps[len(gaps)-1]; last < 3*tr.timings.backoffMin {
		t.Errorf("last redial gap %s did not escalate past 3x the %s floor: gaps=%v", last, tr.timings.backoffMin, gaps)
	}
}

// TestSocketEventDelivererPresentsEventsPOST: the deliverer presents the
// payload to the shared handler as the POST the Events API would have made,
// with redelivery hints in the X-Slack-Retry-* headers the company gateway
// reads, and reports the handler's status.
func TestSocketEventDelivererPresentsEventsPOST(t *testing.T) {
	var gotMethod, gotPath, gotRetryNum, gotRetryReason string
	var gotBody []byte
	status := http.StatusServiceUnavailable
	serve := func(w http.ResponseWriter, r *http.Request, body []byte, _ *AgentApps) {
		gotMethod, gotPath = r.Method, r.URL.Path
		gotRetryNum = r.Header.Get("X-Slack-Retry-Num")
		gotRetryReason = r.Header.Get("X-Slack-Retry-Reason")
		gotBody = body
		if status != 0 {
			w.WriteHeader(status)
		}
	}
	deliver := socketEventDeliverer(serve, func() *AgentApps { return nil })

	payload := messagePayload(t, "Ev1", "C42", "1.1", "hi")
	if got := deliver(payload, 3, "timeout"); got != http.StatusServiceUnavailable {
		t.Errorf("status = %d, want the handler's 503", got)
	}
	if gotMethod != http.MethodPost || gotPath != "/slack/events" {
		t.Errorf("request = %s %s, want POST /slack/events", gotMethod, gotPath)
	}
	if gotRetryNum != "3" || gotRetryReason != "timeout" {
		t.Errorf("retry headers = (%q, %q), want (\"3\", \"timeout\")", gotRetryNum, gotRetryReason)
	}
	if string(gotBody) != string(payload) {
		t.Errorf("body = %s", gotBody)
	}

	// A first delivery carries no retry headers, and a handler that writes
	// nothing answered 200.
	status = 0
	if got := deliver(payload, 0, ""); got != http.StatusOK {
		t.Errorf("status = %d, want 200 for a handler that wrote nothing", got)
	}
	if gotRetryNum != "" || gotRetryReason != "" {
		t.Errorf("first delivery carried retry headers (%q, %q)", gotRetryNum, gotRetryReason)
	}
}

// TestSocketEnvelopeReachesLegacyDispatchUnsigned drives a socket envelope
// through the real shared handler into legacy dispatch. The payload carries no
// signature, and the same unsigned bytes POSTed to /slack/events are still
// rejected: verification is skipped for socket envelopes only.
func TestSocketEnvelopeReachesLegacyDispatchUnsigned(t *testing.T) {
	gc := newFakeGC(t)
	cfg := config{
		gcAPIBase:       gc.server.URL,
		cityName:        "test-city",
		provider:        "slack",
		accountID:       "T01234567",
		slackSigningKey: "secret",
		dispatchSem:     make(chan struct{}, 8),
	}
	aliasReg := newTestHandleAliasRegistry(t)
	serve := serveVerifiedSlackEvents(cfg, aliasReg, nil, nil, nil, nil)
	tr := newTestTransport(socketEventDeliverer(serve, cfg.companyGateway.agentAppsSnapshot))

	payload := messagePayload(t, "Ev1", "C_LEGACY", "1700000000.000500", "over the socket")
	conn := &scriptedConn{frames: [][]byte{eventsAPIFrame(t, "env-1", payload, 0)}}
	if err := tr.pumpSocket(context.Background(), conn, nil); !errors.Is(err, io.EOF) {
		t.Fatalf("pumpSocket err = %v", err)
	}
	if ids := ackedIDs(t, conn); len(ids) != 1 || ids[0] != "env-1" {
		t.Errorf("acks = %v, want [env-1]", ids)
	}
	waitUntil(t, func() bool { return gc.inboundCalls() == 1 })

	req := httptest.NewRequest(http.MethodPost, "/slack/events", strings.NewReader(string(payload)))
	w := httptest.NewRecorder()
	handleSlackEvents(cfg, aliasReg, nil, nil, nil, nil)(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Errorf("unsigned HTTP POST status = %d, want 401 (HTTP verification unchanged)", w.Code)
	}
}

func TestSocketModeHealthzDetail(t *testing.T) {
	prev := socketModeEnabled.Load()
	t.Cleanup(func() { socketModeEnabled.Store(prev) })

	socketModeEnabled.Store(false)
	if got := socketModeHealthzDetail(); got != "" {
		t.Errorf("detail with Socket Mode off = %q, want empty", got)
	}
	socketModeEnabled.Store(true)
	got := socketModeHealthzDetail()
	for _, want := range []string{"socket_mode=on\n", "socket_mode_connections=", "socket_mode_envelopes_total=", "inbound_event_duplicates_total="} {
		if !strings.Contains(got, want) {
			t.Errorf("detail %q missing %q", got, want)
		}
	}
}

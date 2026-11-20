// Socket Mode transport — an ingress-free inbound path that runs alongside
// the public /slack/events listener.
//
// Socket Mode replaces Slack's inbound HTTP webhook with an outbound
// WebSocket the adapter opens to Slack. Nothing has to reach the adapter
// from the internet, so inbound delivery no longer depends on a TLS
// terminator, a tunnel, or a Funnel ingress path staying healthy.
//
// The transport is selected by SLACK_APP_TOKEN. When it is set the adapter
// opens a Socket Mode connection for the app that owns the token. Unlike
// slack-channel and slack-mini, the public listener keeps running either
// way, for three reasons:
//
//   - Registered agent apps (company-rooms Phase 4 DMs and group DMs) each
//     deliver over HTTP with their own signing secret. An app-level token
//     belongs to one app, so it cannot carry their traffic.
//   - The OAuth install routes (/slack/oauth/*) and /slack/interactions
//     live on the same listener.
//   - HTTP stays as the fallback. Slack stops POSTing an app's events to
//     its Request URL while Socket Mode is enabled on that app, so this does
//     not double-deliver. If an operator turns Socket Mode off again in the
//     app settings, delivery returns to the listener with no adapter
//     restart.
//
// Both transports feed one path. A socket envelope's payload is the same
// JSON the Events API would have POSTed, so it is handed to
// serveVerifiedSlackEvents, the handler /slack/events runs after it checks
// the signature. Company-room admission, DM and group-DM gating, legacy
// fanout, aliases and launcher mode therefore behave identically on both
// transports. The only step skipped is the HMAC check, and only for socket
// envelopes (see "Authenticity" below).
//
// A delivery can still arrive twice: a Slack redelivery of an envelope whose
// ack was lost, or the same event over both transports while Socket Mode is
// being switched on or off. inboundEventDedup (event_dedup.go) absorbs those
// by (api_app_id, event_id) before dispatch, for both transports.
//
// This is a port of slack-channel/adapter/socketmode.go (itself a port of
// slack-mini's transport). The connection lifecycle — supervision, paced
// redial, keepalive, drain on disconnect warning — is line-for-line the
// same. Two things differ:
//
//   - The ack waits for the shared handler's answer instead of preceding
//     it. The handler's HTTP status decides: anything below 500 is acked,
//     and a 5xx (the company gateway's retryable answer for a closed startup
//     barrier or a failed receipt write) is left unacked so Slack redelivers,
//     exactly as it retries a 503 on the HTTP path. The handler does no
//     network I/O before answering (legacy dispatch and company delivery are
//     both asynchronous), so the answer comes well inside Slack's 3s window.
//   - Interactivity and slash commands are not handled over this transport.
//     The shipped manifest disables interactivity, and slash commands still
//     need /slack/interactions. Such envelopes are acked and dropped with a
//     log line rather than silently ignored.
//
// Wire protocol (https://api.slack.com/apis/socket-mode):
//
//  1. POST apps.connections.open with the app-level token → a single-use
//     wss:// URL, valid for ~30s.
//  2. Dial it. Slack sends {"type":"hello"} on success.
//  3. Each event arrives as an envelope: {"envelope_id":…,"type":"events_api",
//     "payload":{…}}. The payload is byte-identical to the HTTP webhook body.
//  4. Ack every envelope with {"envelope_id":…} within 3s or Slack redelivers.
//  5. {"type":"disconnect"} warns the connection is going away, ~10s before
//     it closes, so a replacement can be opened before events are missed.
//
// Authenticity differs from the HTTP path and is worth being explicit about:
// there is no signing secret and no HMAC. The trust boundary is the TLS
// connection the adapter itself opened using its app-level token — an
// attacker cannot inject envelopes without already holding that token. This
// is Slack's designed model for Socket Mode, not a relaxation of the HTTP
// path, which keeps verifying signatures exactly as before.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/coder/websocket"
)

const (
	// socketAckTimeout bounds the ack write. Slack redelivers an envelope
	// that is not acked within 3s, so a write that cannot complete well
	// inside that window is better abandoned than left blocking the reader.
	socketAckTimeout = 2 * time.Second

	// Liveness is checked by pinging Slack, not by bounding reads. A healthy
	// Socket Mode connection can sit idle indefinitely — no traffic in bound
	// channels means no data messages — and Slack's own keepalive pings are
	// answered inside the WebSocket library without ever waking a read. A
	// read deadline would therefore tear down perfectly good connections on
	// any quiet workspace. A ping that goes unanswered is the real signal
	// that a connection is wedged in a way TCP has not noticed yet.
	socketPingInterval = 30 * time.Second
	socketPingTimeout  = 10 * time.Second

	// socketOpenTimeout bounds apps.connections.open plus the WebSocket
	// handshake. The URL Slack returns expires in ~30s.
	socketOpenTimeout = 30 * time.Second

	// Reconnect backoff after a failed or lost connection. Reset once a
	// connection has lasted socketMinLifetime (see settleBackoff).
	socketBackoffMin = 1 * time.Second
	socketBackoffMax = 30 * time.Second

	// socketMinLifetime is how long a connection must survive before its
	// successor is allowed to start from socketBackoffMin again. Resetting on
	// establishment alone lets a server that accepts a connection and drops or
	// disowns it immediately be redialled at the floor forever; making a
	// connection prove itself first is what escalates the delay in exactly that
	// case. Slack recycles healthy connections on a far longer cadence, so
	// ordinary refreshes still reset the backoff.
	socketMinLifetime = 30 * time.Second

	// socketDrainGrace is how long a connection that announced a disconnect
	// keeps reading after its replacement is live, so in-flight envelopes
	// still get acked instead of being redelivered.
	socketDrainGrace = 10 * time.Second

	// maxSocketMessage caps a single inbound WebSocket message, mirroring
	// the 1 MiB body cap on the HTTP path.
	maxSocketMessage = 1 << 20 // 1 MiB
)

// socketTimings groups the connection-lifecycle timers. Production uses
// defaultSocketTimings(); tests overwrite socketModeTransport.timings with a
// scaled-down copy so the same code paths can be driven in milliseconds.
//
// socketPingTimeout, socketAckTimeout and socketOpenTimeout stay constants
// deliberately: nothing drives them, and a knob no test turns is only a
// wider surface.
type socketTimings struct {
	pingInterval time.Duration
	drainGrace   time.Duration
	backoffMin   time.Duration
	backoffMax   time.Duration
	// minLifetime is how long a connection must last before its successor is
	// allowed to start from backoffMin again.
	minLifetime time.Duration
}

// defaultSocketTimings is the production timer set.
func defaultSocketTimings() socketTimings {
	return socketTimings{
		pingInterval: socketPingInterval,
		drainGrace:   socketDrainGrace,
		backoffMin:   socketBackoffMin,
		backoffMax:   socketBackoffMax,
		minLifetime:  socketMinLifetime,
	}
}

// socketEnvelope is the Socket Mode frame wrapping each delivery. Payload is
// the same JSON body the Events API would have POSTed to /slack/events.
type socketEnvelope struct {
	Type         string          `json:"type"`
	EnvelopeID   string          `json:"envelope_id,omitempty"`
	Payload      json.RawMessage `json:"payload,omitempty"`
	Reason       string          `json:"reason,omitempty"`
	RetryAttempt int             `json:"retry_attempt,omitempty"`
	RetryReason  string          `json:"retry_reason,omitempty"`
}

// socketConn is the WebSocket surface this file needs, extracted so the
// envelope loop can be tested against a scripted connection without standing
// up a server. realSocketConn is the only production implementation.
type socketConn interface {
	Read(ctx context.Context) ([]byte, error)
	Write(ctx context.Context, data []byte) error
	// Ping sends a WebSocket ping and waits for the matching pong, which is
	// how liveness is established on a connection that may legitimately carry
	// no data for hours.
	Ping(ctx context.Context) error
	Close() error
}

type realSocketConn struct{ c *websocket.Conn }

func (r realSocketConn) Read(ctx context.Context) ([]byte, error) {
	_, data, err := r.c.Read(ctx)
	return data, err
}

func (r realSocketConn) Write(ctx context.Context, data []byte) error {
	return r.c.Write(ctx, websocket.MessageText, data)
}

func (r realSocketConn) Ping(ctx context.Context) error { return r.c.Ping(ctx) }

func (r realSocketConn) Close() error {
	// CloseNow over a handshaked close: the peer is Slack and the connection
	// is being discarded either way, so waiting on a close reply only delays
	// the redial.
	return r.c.CloseNow()
}

// socketDeliverFunc hands one events_api payload to the shared event path
// and returns the HTTP status that path answered with. retryNum and
// retryReason carry the envelope's redelivery hints, which the HTTP path
// reads from the X-Slack-Retry-* headers.
type socketDeliverFunc func(payload []byte, retryNum int, retryReason string) int

// socketModeTransport is one adapter's Socket Mode client. slack-channel
// hangs these methods off its server type; slack-full has no such type (its
// handlers are closures over config), so the transport carries its own
// state: the token, the API base it negotiates against, the timers, and the
// sink envelopes are delivered to.
type socketModeTransport struct {
	appToken string
	// apiBase is the Slack Web API root for apps.connections.open. Captured
	// from slackAPIBase at construction, so a test can point one transport
	// at a fake without swapping the package-level var under its peers.
	apiBase string
	timings socketTimings
	deliver socketDeliverFunc
}

// newSocketModeTransport builds the production transport.
func newSocketModeTransport(appToken string, deliver socketDeliverFunc) *socketModeTransport {
	return &socketModeTransport{
		appToken: appToken,
		apiBase:  slackAPIBase,
		timings:  defaultSocketTimings(),
		deliver:  deliver,
	}
}

// socketModeLive counts open Socket Mode connections (normally 1; 2 during a
// drain overlap). socketEnvelopesTotal counts events_api envelopes handed to
// the shared event path. Both surface on /healthz when Socket Mode is on.
var (
	socketModeEnabled    atomic.Bool
	socketModeLive       atomic.Int64
	socketEnvelopesTotal atomic.Uint64
)

// socketModeHealthzDetail is the /healthz block for this transport, plus the
// cross-transport duplicate counter (event_dedup.go) that matters once two
// transports can carry one event. Empty when Socket Mode is off, so an
// HTTP-only adapter's output is unchanged.
func socketModeHealthzDetail() string {
	if !socketModeEnabled.Load() {
		return ""
	}
	return fmt.Sprintf("socket_mode=on\nsocket_mode_connections=%d\nsocket_mode_envelopes_total=%d\ninbound_event_duplicates_total=%d\n",
		socketModeLive.Load(), socketEnvelopesTotal.Load(), inboundEventDuplicatesTotal.Load())
}

// run supervises the Socket Mode connection until ctx is done, redialing
// with capped exponential backoff. It returns only when ctx is cancelled;
// every other failure is a reconnect, because losing the socket is the
// expected steady state (Slack recycles connections routinely) rather than a
// fatal condition.
func (t *socketModeTransport) run(ctx context.Context) error {
	backoff := t.timings.backoffMin
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}

		next, err := t.superviseConnection(ctx, backoff)
		if err != nil {
			return err
		}
		backoff = next
	}
}

// superviseConnection runs exactly one connection's lifecycle: dial it, wait
// for it to end (or to be warned about), pace the delay before the next dial,
// and return the backoff that dial should start from. A non-nil error means the
// supervisor should stop — only shutdown produces one, which is what makes
// run's loop return solely on cancellation.
func (t *socketModeTransport) superviseConnection(ctx context.Context, backoff time.Duration) (time.Duration, error) {
	tm := t.timings
	warned := make(chan struct{}, 1)
	done, err := t.runSocketConnection(ctx, func() {
		select {
		case warned <- struct{}{}:
		default: // already warned; one signal is enough
		}
	})
	if err != nil {
		if ctx.Err() != nil {
			return backoff, ctx.Err()
		}
		log.Printf("socket mode: connect failed: %v (retrying in %s)", err, backoff)
		return paceRedial(ctx, backoff, tm)
	}
	connectedAt := time.Now()

	select {
	case <-ctx.Done():
		return backoff, ctx.Err()

	case <-warned:
		// Slack warned this socket is closing, ~10s ahead. The replacement
		// is dialled while the old connection keeps draining and acking in
		// its own goroutine — that overlap is the entire reason Slack sends
		// the warning early. The drained connection closes itself; nothing
		// here needs to wait for it.
		//
		// The dial is paced all the same. A connection that lasted a normal
		// lifetime resets the delay to backoffMin first, which fits inside
		// the warning's ~10s lead and keeps the overlap; only a connection
		// warned moments after it opened — the connection-limit churn two
		// adapters sharing one app token produce — carries an escalating
		// delay here.
		backoff = settleBackoff(backoff, time.Since(connectedAt), tm)
		log.Printf("socket mode: opening replacement connection in %s", backoff)
		return paceRedial(ctx, backoff, tm)

	case connErr := <-done:
		if ctx.Err() != nil {
			return backoff, ctx.Err()
		}
		backoff = settleBackoff(backoff, time.Since(connectedAt), tm)
		if connErr != nil {
			log.Printf("socket mode: connection ended: %v (reconnecting in %s)", connErr, backoff)
		} else {
			log.Printf("socket mode: connection closed (reconnecting in %s)", backoff)
		}
		return paceRedial(ctx, backoff, tm)
	}
}

// paceRedial waits out the current delay and returns the delay the dial after
// it should use. Shutdown during the wait is reported as an error, which stops
// the supervisor rather than redialling into a cancelled context.
func paceRedial(ctx context.Context, backoff time.Duration, tm socketTimings) (time.Duration, error) {
	if waitErr := sleepFor(ctx, backoff); waitErr != nil {
		return backoff, waitErr
	}
	return nextBackoff(backoff, tm), nil
}

// settleBackoff picks the delay before the next dial from how long the
// connection that just ended lasted. A connection that survived
// tm.minLifetime proved the endpoint healthy, so its successor starts from the
// floor again; one that died sooner keeps the escalating delay, which is what
// stops a dial-OK → instant-death cycle from redialling at the floor forever.
func settleBackoff(backoff, lifetime time.Duration, tm socketTimings) time.Duration {
	if lifetime >= tm.minLifetime {
		return tm.backoffMin
	}
	return backoff
}

// nextBackoff doubles the reconnect delay, capped.
func nextBackoff(backoff time.Duration, tm socketTimings) time.Duration {
	backoff *= 2
	if backoff > tm.backoffMax {
		return tm.backoffMax
	}
	return backoff
}

// sleepFor waits for d, returning early with ctx.Err() if the context is
// cancelled first.
func sleepFor(ctx context.Context, d time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(d):
		return nil
	}
}

// runSocketConnection dials one connection and pumps it in the background,
// returning a channel that yields the pump's outcome. Dialing is synchronous
// so the caller can distinguish "could not connect" (back off) from "was
// connected and then ended" (reconnect promptly); pumping is not, so the
// caller can react to a disconnect warning without waiting for the drain.
// onWarning fires when Slack announces an impending close.
func (t *socketModeTransport) runSocketConnection(ctx context.Context, onWarning func()) (<-chan error, error) {
	conn, err := dialSocketMode(ctx, t.apiBase, t.appToken)
	if err != nil {
		return nil, err
	}
	done := make(chan error, 1)
	go func() {
		socketModeLive.Add(1)
		defer socketModeLive.Add(-1)
		done <- t.pumpSocket(ctx, conn, onWarning)
	}()
	return done, nil
}

// dialSocketMode negotiates a connection URL and opens it.
func dialSocketMode(ctx context.Context, apiBase, appToken string) (socketConn, error) {
	openCtx, cancel := context.WithTimeout(ctx, socketOpenTimeout)
	defer cancel()

	wsURL, err := openSocketConnectionURL(openCtx, apiBase, appToken)
	if err != nil {
		return nil, err
	}
	// Dial through http.DefaultClient rather than a bare TLS dial so
	// HTTP_PROXY/HTTPS_PROXY are honoured — the adapter is expected to run
	// on exactly the kind of restricted network that needs an egress proxy.
	c, _, err := websocket.Dial(openCtx, wsURL, &websocket.DialOptions{
		HTTPClient: http.DefaultClient,
	})
	if err != nil {
		return nil, fmt.Errorf("dial socket mode: %w", err)
	}
	c.SetReadLimit(maxSocketMessage)
	log.Printf("socket mode: connected")
	return realSocketConn{c: c}, nil
}

// appsConnectionsOpenResp is the apps.connections.open reply.
type appsConnectionsOpenResp struct {
	OK    bool   `json:"ok"`
	URL   string `json:"url,omitempty"`
	Error string `json:"error,omitempty"`
}

// openSocketConnectionURL calls apps.connections.open, which is the only
// endpoint that accepts the app-level (xapp-) token rather than the bot
// token.
func openSocketConnectionURL(ctx context.Context, apiBase, appToken string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, apiBase+"/apps.connections.open", nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+appToken)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("apps.connections.open: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxSocketMessage))
	if err != nil {
		return "", fmt.Errorf("read apps.connections.open response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("apps.connections.open http %d: %s", resp.StatusCode, sanitizeSlackErrorBody(body))
	}
	var out appsConnectionsOpenResp
	if err := json.Unmarshal(body, &out); err != nil {
		return "", fmt.Errorf("decode apps.connections.open response: %w", err)
	}
	if !out.OK {
		// invalid_auth here almost always means the token is a bot token or
		// is missing the connections:write scope; say so rather than making
		// the operator look it up.
		return "", fmt.Errorf("apps.connections.open: %s (app-level token needs the connections:write scope)", out.Error)
	}
	if out.URL == "" {
		return "", errors.New("apps.connections.open returned no url")
	}
	return out.URL, nil
}

// pumpSocket reads envelopes until the connection ends, delivering each one
// to the shared event path and acking it once that path has answered.
func (t *socketModeTransport) pumpSocket(ctx context.Context, conn socketConn, onWarning func()) error {
	defer func() { _ = conn.Close() }()

	// connCtx bounds this connection specifically: the keepalive cancels it
	// when Slack stops answering pings, and the drain timer cancels it when a
	// warned-about connection has had long enough to finish. Reads block on
	// it with no deadline of their own — see socketPingInterval.
	connCtx, closeConn := context.WithCancel(ctx)
	defer closeConn()
	go keepaliveSocket(connCtx, conn, t.timings.pingInterval, closeConn)

	// A disconnect warning arrives ~10s before Slack drops the socket. Rather
	// than tear down immediately (which loses whatever is in flight), the
	// caller is signalled to open a replacement while this loop keeps
	// draining and acking on the doomed connection.
	draining := false

	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}

		data, err := conn.Read(connCtx)
		if err != nil {
			return pumpReadErr(ctx, err, draining)
		}

		var env socketEnvelope
		if err := json.Unmarshal(data, &env); err != nil {
			log.Printf("socket mode: undecodable frame: %v", err)
			continue
		}

		switch env.Type {
		case "hello":
			continue
		case "disconnect":
			log.Printf("socket mode: disconnect requested (reason=%s), draining", env.Reason)
			if !draining {
				draining = true
				startDrain(t.timings, closeConn, onWarning)
			}
			continue
		}

		// Delivered on the read loop, before the ack: the shared handler's
		// status decides whether to ack (see the file comment). It returns
		// as soon as admission is decided — dispatch itself runs in its own
		// goroutine on both transports — so envelopes queued behind this one
		// are not held for a slow gc.
		if !t.handleSocketEnvelope(env) {
			continue
		}
		if ackErr := ackEnvelope(ctx, conn, env.EnvelopeID); ackErr != nil {
			return ackErr
		}
	}
}

// pumpReadErr maps a failed connection read to the pump's return value. A read
// that fails while draining is the expected end of a warned-about connection,
// not a fault; a read that fails during shutdown reports the shutdown.
func pumpReadErr(ctx context.Context, readErr error, draining bool) error {
	if draining {
		// Expected: the warned-about close finally landed, or the drain
		// window elapsed.
		return nil
	}
	if ctx.Err() != nil {
		return ctx.Err()
	}
	return readErr
}

// startDrain begins the drain of a connection Slack has announced it will
// close: the window is bounded, and the supervisor is signalled to dial the
// replacement that overlaps it.
func startDrain(tm socketTimings, closeConn func(), onWarning func()) {
	// Bound the drain: if Slack never actually closes, this connection must
	// not linger next to its replacement.
	time.AfterFunc(tm.drainGrace, closeConn)
	if onWarning != nil {
		onWarning()
	}
}

// ackEnvelope acknowledges one envelope. Envelopes that carry no id (hello,
// disconnect) are not acked, matching Slack's protocol.
func ackEnvelope(ctx context.Context, conn socketConn, envelopeID string) error {
	if envelopeID == "" {
		return nil
	}
	ackCtx, ackCancel := context.WithTimeout(ctx, socketAckTimeout)
	ackErr := conn.Write(ackCtx, socketAck(envelopeID))
	ackCancel()
	if ackErr != nil {
		// Acking is what stops redelivery, so a failed ack means the
		// connection is no longer usable — redial and let Slack redeliver
		// rather than processing on a dead socket. The redelivery is
		// absorbed by the event dedup.
		return fmt.Errorf("ack envelope %s: %w", envelopeID, ackErr)
	}
	return nil
}

// keepaliveSocket pings Slack on a fixed interval and closes the connection
// when a ping goes unanswered. This is the liveness check for a transport
// whose healthy state is silence: without it, a connection dropped in a way
// that never reaches TCP (a NAT timeout, a proxy reaping an idle tunnel)
// would leave the adapter reading forever from a socket Slack has forgotten.
func keepaliveSocket(ctx context.Context, conn socketConn, interval time.Duration, closeConn func()) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			pingCtx, cancel := context.WithTimeout(ctx, socketPingTimeout)
			err := conn.Ping(pingCtx)
			cancel()
			if err != nil {
				if ctx.Err() != nil {
					return // shutting down; not a ping failure
				}
				log.Printf("socket mode: keepalive ping failed: %v", err)
				closeConn()
				return
			}
		}
	}
}

// socketAck builds the ack frame for an envelope.
func socketAck(envelopeID string) []byte {
	// Marshal rather than concatenate: envelope ids are Slack-supplied and
	// must not be able to break out of the JSON they are embedded in.
	b, err := json.Marshal(map[string]string{"envelope_id": envelopeID})
	if err != nil {
		// Unreachable for a map[string]string, but never emit a malformed ack.
		return []byte(`{}`)
	}
	return b
}

// handleSocketEnvelope delivers one non-control envelope and reports whether
// it should be acked. Only a retryable (5xx) answer from the shared event
// path withholds the ack.
func (t *socketModeTransport) handleSocketEnvelope(env socketEnvelope) bool {
	switch env.Type {
	case "events_api":
	case "interactive", "slash_commands":
		// Slack routes these over the socket too once Socket Mode is on.
		// slack-full's interactivity handler expects a signed form POST and
		// a synchronous response body, which this transport does not carry.
		// Ack so Slack does not retry, and say why the click or command did
		// nothing.
		log.Printf("socket mode: %s envelope dropped — slack-full serves interactivity and slash commands on /slack/interactions only", env.Type)
		return true
	default:
		log.Printf("socket mode: ignoring envelope type=%q", env.Type)
		return true
	}
	if len(env.Payload) == 0 {
		return true
	}
	socketEnvelopesTotal.Add(1)
	if env.RetryAttempt > 0 {
		// The event dedup absorbs a redelivery of something already handled;
		// log it because a persistent retry count means acks are not landing
		// in time.
		log.Printf("socket mode: redelivered envelope (attempt %d, reason=%q)", env.RetryAttempt, env.RetryReason)
	}
	status := t.deliver(env.Payload, env.RetryAttempt, env.RetryReason)
	if status >= http.StatusInternalServerError {
		log.Printf("socket mode: event path answered %d; leaving envelope %s unacked so Slack redelivers", status, env.EnvelopeID)
		return false
	}
	return true
}

// socketEventDeliverer adapts serve (the post-verification /slack/events
// handler) to the socket transport. Each payload is presented as the POST the
// Events API would have made, with the envelope's redelivery hints in the
// headers the company gateway reads, and the handler's status is captured for
// the ack decision. agentApps is resolved once per envelope, as the HTTP
// handler resolves it once per request.
func socketEventDeliverer(serve verifiedEventServer, agentApps func() *AgentApps) socketDeliverFunc {
	return func(payload []byte, retryNum int, retryReason string) int {
		req, err := http.NewRequest(http.MethodPost, "/slack/events", bytes.NewReader(payload))
		if err != nil {
			// Unreachable for a constant method and path.
			log.Printf("socket mode: build request: %v", err)
			return http.StatusInternalServerError
		}
		req.Header.Set("Content-Type", "application/json")
		if retryNum > 0 {
			req.Header.Set("X-Slack-Retry-Num", strconv.Itoa(retryNum))
			if retryReason != "" {
				req.Header.Set("X-Slack-Retry-Reason", retryReason)
			}
		}
		rec := &bufferedResponse{header: http.Header{}}
		serve(rec, req, payload, agentApps())
		if rec.code == 0 {
			return http.StatusOK
		}
		return rec.code
	}
}

// bufferedResponse is the minimal http.ResponseWriter the socket transport
// hands the shared event handler. Only the status matters: a socket ack has
// no body for events_api envelopes.
type bufferedResponse struct {
	header http.Header
	code   int
	body   strings.Builder
}

func (b *bufferedResponse) Header() http.Header { return b.header }

func (b *bufferedResponse) WriteHeader(code int) {
	if b.code == 0 {
		b.code = code
	}
}

func (b *bufferedResponse) Write(p []byte) (int, error) {
	if b.code == 0 {
		b.code = http.StatusOK
	}
	return b.body.Write(p)
}

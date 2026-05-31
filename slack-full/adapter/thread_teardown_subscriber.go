package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// threadBindingDropper is the subset of *threadSessionRegistry the
// teardown subscriber needs. Defining it as a small interface here
// (where it is consumed) lets tests inject a fake without dragging in
// disk persistence, per "accept interfaces" idiom. cby.5.4.
type threadBindingDropper interface {
	// RemoveBySessionID drops the binding for the given session and
	// returns the (channelID, threadTS) pair that was dropped. ok is
	// false when no binding existed for sessionID (idempotent no-op).
	RemoveBySessionID(sessionID string) (channelID, threadTS string, ok bool)
}

// teardownSubscriberConfig captures the small set of dials the
// subscriber needs. Carved off of adapter config so tests can pass
// an httptest.Server URL and tight backoff intervals without wiring
// the whole adapter config struct.
type teardownSubscriberConfig struct {
	// gcAPIBase is the base URL for the gc HTTP API (no trailing
	// slash). The subscriber appends /v0/city/{cityName}/events/stream.
	gcAPIBase string
	// cityName is the gc city to subscribe to. Must be non-empty;
	// the subscriber returns immediately if it isn't.
	cityName string
	// initialBackoff is the first sleep on a failed connect or read.
	// Defaults to 1 second when zero.
	initialBackoff time.Duration
	// maxBackoff caps exponential growth. Defaults to 30 seconds when
	// zero.
	maxBackoff time.Duration
	// readHeaderTimeout bounds the HTTP request header read. Defaults
	// to 30 seconds when zero. The body itself streams indefinitely
	// until ctx is canceled or the connection drops.
	readHeaderTimeout time.Duration
}

// teardownEnvelope is the minimal SSE wire decode shape. Fields not
// needed for thread-binding teardown (workflow projection, actor,
// subject, ts, message) are intentionally omitted: a forward-compatible
// JSON decoder ignores unknown fields by default. type and payload are
// the only two fields the subscriber uses.
type teardownEnvelope struct {
	Type    string                 `json:"type"`
	Payload teardownSessionPayload `json:"payload"`
}

// teardownSessionPayload mirrors the fields the subscriber needs from
// internal/api.SessionLifecyclePayload. Defined locally because the
// adapter is a separate Go module that doesn't import gascity packages
// (its go.mod has no gascity dependency, by design — adapters talk to
// gc only via the HTTP wire).
type teardownSessionPayload struct {
	SessionID string `json:"session_id"`
	Template  string `json:"template,omitempty"`
	Reason    string `json:"reason,omitempty"`
}

const (
	defaultTeardownInitialBackoff = 1 * time.Second
	defaultTeardownMaxBackoff     = 30 * time.Second
	defaultTeardownHeaderTimeout  = 30 * time.Second
)

// runThreadTeardownSubscriber dials gc's /v0/city/{cityName}/events/stream
// SSE endpoint and tears down thread bindings (and their bootstrapped
// aliases) for terminal session lifecycle events (session.stopped,
// session.crashed). It returns when ctx is canceled.
//
// Wire contract: gc emits each event as
//
//	event: event
//	id: <seq>
//	data: <eventStreamEnvelope JSON>
//	\n
//
// where the JSON envelope has `type` and `payload` fields. For terminal
// session events, the payload is a SessionLifecyclePayload with a
// canonical SessionID — see internal/api/event_payloads.go (gc-zl1).
//
// On read errors or malformed frames the subscriber logs and reconnects
// with exponential backoff (1s → 30s + jitter). Successful event flush
// resets the backoff. The goroutine exits within a small timeout of
// ctx.Done().
func runThreadTeardownSubscriber(ctx context.Context, cfg teardownSubscriberConfig, threadReg threadBindingDropper, aliasReg *handleAliasRegistry) {
	if cfg.gcAPIBase == "" || cfg.cityName == "" {
		log.Printf("thread teardown subscriber: gcAPIBase=%q cityName=%q both required; subscriber disabled",
			cfg.gcAPIBase, cfg.cityName)
		return
	}
	if threadReg == nil {
		log.Printf("thread teardown subscriber: threadReg nil; subscriber disabled")
		return
	}
	if cfg.initialBackoff <= 0 {
		cfg.initialBackoff = defaultTeardownInitialBackoff
	}
	if cfg.maxBackoff <= 0 {
		cfg.maxBackoff = defaultTeardownMaxBackoff
	}
	if cfg.readHeaderTimeout <= 0 {
		cfg.readHeaderTimeout = defaultTeardownHeaderTimeout
	}

	// PathEscape cityName so URL-significant characters cannot alter
	// routing on the gc API side (sec-S-06). cityName is operator-supplied
	// via GC_CITY_NAME and gc-cby.29 rejects /?#% at startup, but the
	// per-call escape keeps the wire format correct regardless and matches
	// the cby-set-c dispatch paths and the cby.28 register/inbound paths.
	// Local var named `target` (not `url`) so the net/url import is not
	// shadowed. gc-cby.48.
	target := fmt.Sprintf("%s/v0/city/%s/events/stream",
		strings.TrimRight(cfg.gcAPIBase, "/"), url.PathEscape(cfg.cityName))

	backoff := cfg.initialBackoff
	for {
		if ctx.Err() != nil {
			return
		}

		processed, runErr := streamTeardownEvents(ctx, target, cfg.readHeaderTimeout, threadReg, aliasReg)
		if ctx.Err() != nil {
			return
		}

		// On a clean processing of at least one event since the last
		// reconnect, reset the backoff — this is the documented
		// "successful event flush after reconnect" reset.
		if processed > 0 {
			backoff = cfg.initialBackoff
		}

		if runErr != nil {
			log.Printf("thread teardown subscriber: stream %s: %v (sleep %s before reconnect)",
				target, runErr, backoff.Round(time.Millisecond))
		}

		// Sleep with jitter, respecting context.
		jitter := time.Duration(rand.Int63n(int64(backoff)/4 + 1))
		sleep := backoff + jitter
		select {
		case <-ctx.Done():
			return
		case <-time.After(sleep):
		}
		backoff *= 2
		if backoff > cfg.maxBackoff {
			backoff = cfg.maxBackoff
		}
	}
}

// streamTeardownEvents dials the SSE endpoint once and processes frames
// until the connection closes or ctx is canceled. Returns the number of
// terminal-session events processed and the error that ended the stream
// (nil on a clean ctx cancellation).
func streamTeardownEvents(ctx context.Context, target string, headerTimeout time.Duration, threadReg threadBindingDropper, aliasReg *handleAliasRegistry) (int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return 0, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("X-GC-Request", "gc-slack-adapter-teardown")

	// http.Client without overall Timeout — the body must stream
	// indefinitely. ResponseHeaderTimeout bounds just the headers.
	client := &http.Client{
		Transport: &http.Transport{
			ResponseHeaderTimeout: headerTimeout,
		},
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("connect: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return 0, fmt.Errorf("status %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}

	reader := bufio.NewReader(resp.Body)
	processed := 0

	// SSE frames are separated by blank lines. We accumulate `data:`
	// lines into a single payload and dispatch on the blank-line
	// terminator.
	var dataBuf strings.Builder
	for {
		if ctx.Err() != nil {
			return processed, nil
		}
		line, err := reader.ReadString('\n')
		if err != nil {
			if ctx.Err() != nil {
				return processed, nil
			}
			if err == io.EOF {
				return processed, fmt.Errorf("connection closed (EOF)")
			}
			return processed, fmt.Errorf("read frame: %w", err)
		}
		line = strings.TrimRight(line, "\r\n")
		if line == "" {
			// End of frame.
			if dataBuf.Len() > 0 {
				if handleTeardownFrame(dataBuf.String(), threadReg, aliasReg) {
					processed++
				}
				dataBuf.Reset()
			}
			continue
		}
		// Comments (": keep-alive"), `event:`, `id:` lines — ignore
		// for our purposes; we only need the JSON in `data:`.
		if strings.HasPrefix(line, "data:") {
			payload := strings.TrimPrefix(line, "data:")
			payload = strings.TrimPrefix(payload, " ")
			if dataBuf.Len() > 0 {
				dataBuf.WriteByte('\n')
			}
			dataBuf.WriteString(payload)
		}
	}
}

// handleTeardownFrame decodes one SSE data payload and tears down a
// thread binding if the event is a terminal session lifecycle event for
// a session we own. Returns true iff the frame parsed cleanly into a
// known event type (regardless of whether it dropped a binding) — used
// only to track whether we've seen a clean flush since reconnect.
func handleTeardownFrame(data string, threadReg threadBindingDropper, aliasReg *handleAliasRegistry) bool {
	var env teardownEnvelope
	if err := json.Unmarshal([]byte(data), &env); err != nil {
		log.Printf("thread teardown subscriber: skip malformed envelope (%v)", err)
		return false
	}
	if env.Type != "session.stopped" && env.Type != "session.crashed" {
		// Not a terminal session lifecycle event we care about, but
		// it is a clean parse — count it as flushed.
		return true
	}
	sessionID := strings.TrimSpace(env.Payload.SessionID)
	if sessionID == "" {
		log.Printf("thread teardown subscriber: skip %s with empty session_id payload", env.Type)
		return true
	}

	channelID, threadTS, ok := threadReg.RemoveBySessionID(sessionID)
	if !ok {
		// Adapter never bound this session to a thread; nothing to
		// do. Common for sessions spawned outside the launcher path.
		return true
	}

	// Unwind the alias bootstrap installed by dispatchRoomLaunch when
	// the session was first created. There may be multiple handles
	// pointing at this session; drop them all.
	if aliasReg != nil {
		handles := aliasReg.findHandlesBySessionID(sessionID)
		for _, h := range handles {
			if _, err := aliasReg.Delete(h); err != nil {
				log.Printf("thread teardown subscriber: aliasReg.Delete handle=%q session=%q: %v",
					h, sessionID, err)
			}
		}
		log.Printf("thread teardown subscriber: dropped binding handles=%v channel=%s thread=%s session=%s event=%s",
			handles, channelID, threadTS, sessionID, env.Type)
	} else {
		log.Printf("thread teardown subscriber: dropped binding channel=%s thread=%s session=%s event=%s",
			channelID, threadTS, sessionID, env.Type)
	}
	return true
}

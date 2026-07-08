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
	"net/url"
	"strings"
	"time"
)

// postInbound bridges a verified Slack message into gc's extmsg inbound.
func (s *server) postInbound(ctx context.Context, msg externalInboundMessage) error {
	body, err := json.Marshal(map[string]any{"message": msg})
	if err != nil {
		return err
	}
	target := fmt.Sprintf("%s/v0/city/%s/extmsg/inbound", s.cfg.gcAPIBase, url.PathEscape(s.cfg.cityName))
	if err := s.postJSON(ctx, target, body); err != nil {
		return fmt.Errorf("post inbound: %w", err)
	}
	return nil
}

// registerAdapter self-registers as an extmsg adapter so gc accepts this
// provider's inbound messages.
func (s *server) registerAdapter(ctx context.Context) error {
	body, err := json.Marshal(adapterRegisterRequest{
		Provider:    s.cfg.provider,
		AccountID:   s.cfg.workspaceID,
		Name:        "slack-channel-adapter",
		CallbackURL: s.cfg.internalCallbackURL,
		Capabilities: adapterCapabilities{
			SupportsChildConversations: false,
			SupportsAttachments:        false,
			MaxMessageLength:           40000, // Slack's chat.postMessage limit
		},
	})
	if err != nil {
		return err
	}
	target := fmt.Sprintf("%s/v0/city/%s/extmsg/adapters", s.cfg.gcAPIBase, url.PathEscape(s.cfg.cityName))
	return s.postJSON(ctx, target, body)
}

// retryPolicy bounds the startup registration backoff. The overall deadline
// is carried by the ctx passed to registerAdapterWithRetry.
type retryPolicy struct {
	initialBackoff time.Duration
	maxBackoff     time.Duration
}

// registerAdapterWithRetry registers the adapter, retrying with exponential
// backoff while the failure is transient. On a supervisor/city restart the
// adapter can come up before the city has finished adopting sessions, so the
// first /extmsg/adapters call returns 404 "city not found or not running":
// exiting on that (the previous behaviour) silently killed all Slack comms
// until a manual restart. Each attempt is bounded by gcCallTimeout; the loop
// gives up only when ctx is cancelled (the overall deadline), returning the
// last error so the caller can fail loudly once the city is genuinely
// unreachable. A non-transient error (malformed request, auth) returns
// immediately — backoff cannot fix a misconfiguration.
func (s *server) registerAdapterWithRetry(ctx context.Context, p retryPolicy) error {
	backoff := p.initialBackoff
	for attempt := 1; ; attempt++ {
		callCtx, cancel := context.WithTimeout(ctx, gcCallTimeout)
		err := s.registerAdapter(callCtx)
		cancel()
		if err == nil {
			if attempt > 1 {
				log.Printf("register adapter: succeeded on attempt %d", attempt)
			}
			return nil
		}
		if !registrationRetryable(err) {
			return err
		}
		log.Printf("register adapter: attempt %d failed (city not ready?), retrying in %s: %v", attempt, backoff, err)
		select {
		case <-ctx.Done():
			return fmt.Errorf("city unreachable after %d attempts: %w", attempt, err)
		case <-time.After(backoff):
		}
		backoff = min(backoff*2, p.maxBackoff)
	}
}

// registrationRetryable reports whether a failed registration should be
// retried. A 404 means the city has not finished starting and a 5xx means gc
// itself is restarting — both clear once startup completes. A transport
// error (no HTTP response: the gc API socket is not up yet) is likewise
// transient during a restart. Any other 4xx (malformed request, auth) is a
// real misconfiguration that backoff cannot fix, so it fails fast.
func registrationRetryable(err error) bool {
	var se *statusError
	if errors.As(err, &se) {
		return se.StatusCode == http.StatusNotFound || se.StatusCode >= 500
	}
	return true
}

// postJSON POSTs a JSON body to a gc API endpoint and treats any >=400
// status as an error, surfacing the response body for diagnostics. ctx
// bounds the call so callers can enforce a timeout.
func (s *server) postJSON(ctx context.Context, target string, body []byte) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-GC-Request", "gc-slack-channel-adapter")
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return &statusError{
			StatusCode: resp.StatusCode,
			Status:     resp.Status,
			Body:       strings.TrimSpace(string(respBody)),
		}
	}
	return nil
}

// statusError is returned by postJSON when the gc API responds with a >=400
// status. It carries the status code so callers (startup registration) can
// distinguish a transient "city not ready" 404 from a permanent failure,
// while its message preserves the status line + body for diagnostics.
type statusError struct {
	StatusCode int
	Status     string // HTTP status line, e.g. "404 Not Found"
	Body       string
}

func (e *statusError) Error() string {
	if e.Body == "" {
		return e.Status
	}
	return e.Status + ": " + e.Body
}

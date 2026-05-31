package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
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
		return fmt.Errorf("%s: %s", resp.Status, strings.TrimSpace(string(respBody)))
	}
	return nil
}

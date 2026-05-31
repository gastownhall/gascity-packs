package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// slackCall POSTs req as JSON to a Slack web API method and decodes the
// response into *Resp. It applies the bot token, a per-call timeout, and
// surfaces any non-2xx HTTP status as an error. The two outbound Slack
// calls (chat.postMessage, reactions.add) differ only in method, request,
// and response type, so they share this body.
func slackCall[Resp any](ctx context.Context, s *server, method string, req any) (*Resp, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(ctx, slackPostTimeout)
	defer cancel()
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, s.cfg.slackAPIBase+method, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Authorization", "Bearer "+s.cfg.botToken)
	httpReq.Header.Set("Content-Type", "application/json; charset=utf-8")
	resp, err := s.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("post %s: %w", method, err)
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read slack response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("slack http %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}
	var out Resp
	if err := json.Unmarshal(respBody, &out); err != nil {
		return nil, fmt.Errorf("decode slack response: %w", err)
	}
	return &out, nil
}

// postToSlack posts a message via chat.postMessage. Identity fields
// (username/icon_url/icon_emoji) on req are forwarded verbatim — the caller
// injects them from the identity registry.
func (s *server) postToSlack(ctx context.Context, req slackPostMessageReq) (*slackPostMessageResp, error) {
	return slackCall[slackPostMessageResp](ctx, s, "/chat.postMessage", req)
}

// addReaction adds an emoji reaction via reactions.add. The emoji name is
// forwarded verbatim minus surrounding colons (callers may send "eyes" or
// ":eyes:").
func (s *server) addReaction(ctx context.Context, channel, timestamp, emoji string) (*slackReactionsAddResp, error) {
	return slackCall[slackReactionsAddResp](ctx, s, "/reactions.add", slackReactionsAddReq{
		Channel:   channel,
		Name:      strings.Trim(emoji, ":"),
		Timestamp: timestamp,
	})
}

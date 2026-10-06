package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"sync"
)

// handleSlackEvents verifies and acks Slack Events API deliveries, then
// routes each verified message in its own goroutine. It answers the
// one-time url_verification handshake inline.
func (s *server) handleSlackEvents() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, maxInboundBody))
		if err != nil {
			http.Error(w, "read body", http.StatusBadRequest)
			return
		}
		ts := r.Header.Get("X-Slack-Request-Timestamp")
		sig := r.Header.Get("X-Slack-Signature")
		if !verifySlackSignature(s.cfg.signingSecret, ts, body, sig) {
			log.Printf("slack signature verify FAILED")
			http.Error(w, "invalid signature", http.StatusUnauthorized)
			return
		}

		var env slackEventEnvelope
		if err := json.Unmarshal(body, &env); err != nil {
			http.Error(w, fmt.Sprintf("decode: %v", err), http.StatusBadRequest)
			return
		}

		if env.Type == "url_verification" && env.Challenge != "" {
			w.Header().Set("Content-Type", "text/plain")
			_, _ = w.Write([]byte(env.Challenge))
			return
		}

		// Ack immediately so Slack does not retry, then route.
		w.WriteHeader(http.StatusOK)
		go s.routeEvent(env)
	}
}

// routeEvent decodes a Slack event and fans it out to the gc sessions that
// should receive it. Tier 2 widens Tier 1's app_mention-only path to plain
// message.* events delivered in bound channels:
//
//   - A message in a channel with a binding → every bound session.
//   - A message whose body leads with "@handle[:]" matching a registered
//     alias → the aliased session (with the handle token stripped),
//     regardless of binding.
//   - An app_mention in a channel with neither a binding nor a matching
//     alias → the default inbound target (preserving Tier 1's "talk to
//     mayor from any channel").
//   - A plain message with no binding and no alias → dropped (Tier 2 does
//     not firehose every channel message at the mayor).
//
// Bot, system, and edited messages are dropped to avoid echo loops, as are
// events carrying another workspace's team_id.
func (s *server) routeEvent(env slackEventEnvelope) {
	if !s.admitEvent(env) {
		return
	}
	var msg slackMessageEvent
	if err := json.Unmarshal(env.Event, &msg); err != nil {
		log.Printf("decode slack event: %v", err)
		return
	}
	if msg.Type != "app_mention" && msg.Type != "message" {
		return
	}
	if msg.BotID != "" || msg.Subtype != "" || msg.User == "" {
		return
	}

	baseText := msg.Text
	if msg.Type == "app_mention" {
		baseText = stripLeadingMention(msg.Text)
	}

	// targets maps a destination session to the text it should receive.
	// A later rule overwrites an earlier one for the same session, so an
	// explicit alias address wins over a plain channel-binding delivery.
	targets := map[string]string{}
	if binding, ok := s.bindingForChannel(msg.Channel); ok {
		for _, sid := range binding.SessionIDs {
			targets[sid] = baseText
		}
	}
	if handle, rest := parseLeadingHandle(baseText); handle != "" {
		if alias, ok := s.aliasFor(handle); ok && alias.SessionID != "" {
			targets[alias.SessionID] = rest
		}
	}
	if len(targets) == 0 && msg.Type == "app_mention" {
		targets[s.cfg.inboundTarget] = baseText
	}
	if len(targets) == 0 {
		return
	}

	// Deliver to all targets concurrently: the gc POSTs are independent
	// (distinct explicit_target + dedup_key) and each is bounded by
	// gcCallTimeout, so a slow gc bounds total fan-out latency to ~one
	// timeout rather than N×timeout for an N-session binding.
	kind := slackKindFromChannelType(msg.ChannelType, msg.Channel)
	var wg sync.WaitGroup
	for sid, text := range targets {
		if strings.TrimSpace(text) == "" {
			continue
		}
		wg.Add(1)
		go func(target, body string) {
			defer wg.Done()
			s.deliverInbound(msg, target, body, kind)
		}(sid, text)
	}
	wg.Wait()
}

// admitEvent reports whether an event envelope should be routed at all. Both
// checks are transport-independent, which is why they live at the funnel
// rather than in either transport.
//
// slack-mini keeps the same two checks inline at the top of bridgeEvent. They
// are extracted here because Tier 2's funnel does considerably more below
// them — bindings, aliases, the app_mention fallback, and the fan-out — and
// the guard must not push that body past its complexity budget. Extracting
// the admission tests rather than the routing arms keeps the diff against
// mini's bridgeEvent readable: the guard is still the first thing either
// funnel does.
func (s *server) admitEvent(env slackEventEnvelope) bool {
	if env.Type != "event_callback" || len(env.Event) == 0 {
		return false
	}
	// Drop events from another workspace. Neither transport establishes which
	// workspace an event belongs to — Socket Mode has no signature at all, and
	// the HTTP path's HMAC proves only that Slack sent it for this app, not
	// that it came from this team — yet every delivery below is stamped with
	// cfg.workspaceID as its account id, and a channel id from a second
	// workspace can collide with a binding belonging to this one. An app
	// installed in a second workspace would therefore file that workspace's
	// messages under this one. The guard sits here, at the funnel both
	// transports feed, so neither can be missed.
	//
	// An absent team_id is allowed through: Slack sends one on every
	// event_callback, so this only affects hand-built payloads.
	if env.TeamID != "" && env.TeamID != s.cfg.workspaceID {
		log.Printf("dropping event from unexpected team %s (want %s)", env.TeamID, s.cfg.workspaceID)
		return false
	}
	return true
}

// deliverInbound POSTs one extmsg inbound addressed to target and records
// it as the session's latest inbound for reply-current/react. The DedupKey
// is per-target so the same Slack message fanned out to N sessions is not
// collapsed into one by gc's dedup.
func (s *server) deliverInbound(msg slackMessageEvent, target, text, kind string) {
	threadTS := msg.ThreadTS
	if threadTS == "" {
		threadTS = msg.TS
	}
	inbound := externalInboundMessage{
		ProviderMessageID: msg.TS,
		Conversation: conversationRef{
			ScopeID:        s.cfg.cityName,
			Provider:       s.cfg.provider,
			AccountID:      s.cfg.workspaceID,
			ConversationID: msg.Channel,
			Kind:           kind,
		},
		Actor: externalActor{
			ID:          msg.User,
			DisplayName: msg.User, // resolving a display name needs users.info — out of Tier 2 scope
		},
		Text:             text,
		ExplicitTarget:   target,
		ReplyToMessageID: msg.ThreadTS,
		DedupKey:         "slack-" + msg.TS + "-" + target,
		ReceivedAt:       s.now().UTC(),
	}
	ctx, cancel := context.WithTimeout(context.Background(), gcCallTimeout)
	defer cancel()
	if err := s.postInbound(ctx, inbound); err != nil {
		log.Printf("inbound POST failed (target=%s): %v", target, err)
		return
	}
	s.recordInbound(target, inboundRef{
		channelID: msg.Channel,
		messageTS: msg.TS,
		threadTS:  threadTS,
	})
	log.Printf("inbound: chan=%s user=%s ts=%s target=%s text=%dch",
		msg.Channel, msg.User, msg.TS, target, len(text))
}

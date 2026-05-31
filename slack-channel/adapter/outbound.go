package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
)

// --- request bodies (one per outbound verb wrapper) -----------------------

type publishRequest struct {
	SessionID string `json:"session_id"`
	Body      string `json:"body"`
	ReplyTo   string `json:"reply_to,omitempty"`
}

type publishToChannelRequest struct {
	SessionID string `json:"session_id,omitempty"`
	ChannelID string `json:"channel_id"`
	ThreadTS  string `json:"thread_ts,omitempty"`
	Body      string `json:"body"`
}

type replyCurrentRequest struct {
	SessionID     string `json:"session_id"`
	Body          string `json:"body"`
	ReplyTo       string `json:"reply_to,omitempty"`
	ThreadCurrent bool   `json:"thread_current,omitempty"`
}

type reactRequest struct {
	SessionID      string `json:"session_id,omitempty"`
	ConversationID string `json:"conversation_id,omitempty"`
	MessageID      string `json:"message_id,omitempty"`
	Emoji          string `json:"emoji"`
}

// applyIdentity injects a session's registered username/avatar override
// into a chat.postMessage request. It returns the applied username (for the
// response/log), or "" when the session has no identity override.
func (s *server) applyIdentity(req *slackPostMessageReq, sessionID string) string {
	if sessionID == "" {
		return ""
	}
	id, ok := s.identityFor(sessionID)
	if !ok {
		return ""
	}
	req.Username = id.Username
	req.IconURL = id.IconURL
	req.IconEmoji = id.IconEmoji
	return id.Username
}

// post sends a chat.postMessage and writes a uniform receipt. channel and
// text are required by the caller; identity is applied from sessionID.
func (s *server) post(w http.ResponseWriter, r *http.Request, sessionID, channel, text, threadTS string) {
	req := slackPostMessageReq{Channel: channel, Text: text, ThreadTS: threadTS}
	identityApplied := s.applyIdentity(&req, sessionID)
	resp, err := s.postToSlack(r.Context(), req)
	if err != nil {
		writeJSONError(w, http.StatusBadGateway, err.Error())
		return
	}
	if !resp.OK {
		writeJSONError(w, http.StatusBadGateway, "slack: "+resp.Error)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":               true,
		"ts":               resp.TS,
		"channel":          resp.Channel,
		"identity_applied": identityApplied,
	})
}

// handlePublish posts into the single channel a session is bound to. A
// session bound to zero channels (run bind-dm/bind-room first) or to more
// than one (ambiguous — use publish-to-channel) is a fail-fast error.
func (s *server) handlePublish() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req publishRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		if strings.TrimSpace(req.SessionID) == "" {
			writeJSONError(w, http.StatusBadRequest, "session_id is required")
			return
		}
		if strings.TrimSpace(req.Body) == "" {
			writeJSONError(w, http.StatusBadRequest, "body is required")
			return
		}
		channels := s.channelsForSession(req.SessionID)
		switch {
		case len(channels) == 0:
			writeJSONError(w, http.StatusBadRequest,
				fmt.Sprintf("session %q has no channel binding; run bind-dm or bind-room first", req.SessionID))
			return
		case len(channels) > 1:
			writeJSONError(w, http.StatusBadRequest,
				fmt.Sprintf("session %q is bound to multiple channels (%s); use publish-to-channel --channel to disambiguate",
					req.SessionID, strings.Join(channels, ", ")))
			return
		}
		log.Printf("publish: session=%s channel=%s reply_to=%s", req.SessionID, channels[0], req.ReplyTo)
		s.post(w, r, req.SessionID, channels[0], req.Body, req.ReplyTo)
	}
}

// handlePublishToChannel posts directly to a channel by id, bypassing the
// binding lookup. The session id (if supplied) still drives the identity
// override.
func (s *server) handlePublishToChannel() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req publishToChannelRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		if strings.TrimSpace(req.ChannelID) == "" {
			writeJSONError(w, http.StatusBadRequest, "channel_id is required")
			return
		}
		if strings.TrimSpace(req.Body) == "" {
			writeJSONError(w, http.StatusBadRequest, "body is required")
			return
		}
		log.Printf("publish-to-channel: session=%s channel=%s thread_ts=%s", req.SessionID, req.ChannelID, req.ThreadTS)
		s.post(w, r, req.SessionID, req.ChannelID, req.Body, req.ThreadTS)
	}
}

// handleReplyCurrent replies into the conversation of the latest inbound
// message delivered to the session. With --thread-current it threads under
// that message; with an explicit reply-to it threads under that ts; with
// neither it posts unthreaded into the same channel. Falls back to the
// session's single binding when no inbound has been seen this process.
func (s *server) handleReplyCurrent() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req replyCurrentRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		if strings.TrimSpace(req.SessionID) == "" {
			writeJSONError(w, http.StatusBadRequest, "session_id is required")
			return
		}
		if strings.TrimSpace(req.Body) == "" {
			writeJSONError(w, http.StatusBadRequest, "body is required")
			return
		}
		if req.ReplyTo != "" && req.ThreadCurrent {
			writeJSONError(w, http.StatusBadRequest, "reply_to and thread_current are mutually exclusive")
			return
		}

		var channel, threadTS string
		if ref, ok := s.latestInbound(req.SessionID); ok {
			channel = ref.channelID
			switch {
			case req.ReplyTo != "":
				threadTS = req.ReplyTo
			case req.ThreadCurrent:
				threadTS = ref.threadTS
			}
		} else {
			// No inbound seen this process — fall back to the session's
			// single channel binding so a fresh adapter can still reply.
			channels := s.channelsForSession(req.SessionID)
			if len(channels) != 1 {
				writeJSONError(w, http.StatusBadRequest,
					"no recent inbound for this session and no single channel binding; use publish-to-channel")
				return
			}
			channel = channels[0]
			threadTS = req.ReplyTo // thread_current has no message to thread under here
		}
		log.Printf("reply-current: session=%s channel=%s thread_ts=%s", req.SessionID, channel, threadTS)
		s.post(w, r, req.SessionID, channel, req.Body, threadTS)
	}
}

// handleReact adds an emoji reaction. Explicit mode names channel+ts
// directly; otherwise it reacts on the latest inbound message delivered to
// the session. already_reacted is treated as success (the emoji is on the
// message either way).
func (s *server) handleReact() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req reactRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		emoji := strings.Trim(req.Emoji, ":")
		if emoji == "" {
			writeJSONError(w, http.StatusBadRequest, "emoji is required")
			return
		}

		explicit := req.ConversationID != "" || req.MessageID != ""
		var channel, ts string
		if explicit {
			if req.ConversationID == "" || req.MessageID == "" {
				writeJSONError(w, http.StatusBadRequest, "conversation_id and message_id must be passed together")
				return
			}
			channel, ts = req.ConversationID, req.MessageID
		} else {
			if strings.TrimSpace(req.SessionID) == "" {
				writeJSONError(w, http.StatusBadRequest, "session_id is required when conversation_id/message_id are not given")
				return
			}
			ref, ok := s.latestInbound(req.SessionID)
			if !ok {
				writeJSONError(w, http.StatusBadRequest,
					"no recent inbound for this session; pass conversation_id and message_id explicitly")
				return
			}
			channel, ts = ref.channelID, ref.messageTS
		}

		log.Printf("react: channel=%s ts=%s emoji=%s", channel, ts, emoji)
		resp, err := s.addReaction(r.Context(), channel, ts, emoji)
		if err != nil {
			writeJSONError(w, http.StatusBadGateway, err.Error())
			return
		}
		if !resp.OK && resp.Error != "already_reacted" {
			writeJSONError(w, http.StatusBadGateway, "slack: "+resp.Error)
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"ok":      true,
			"channel": channel,
			"ts":      ts,
			"emoji":   emoji,
		})
	}
}

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
)

// parseDoubleHandlePrefix is the launcher-mode counterpart to
// parseHandlePrefix. It matches ONLY when the configured prefix appears
// doubled at the start of the trimmed text — e.g. with prefix "@",
// the input "@@new please ack" yields handle="new", remainder="please ack",
// ok=true.
//
// The launcher branch (cby.5) uses `@@<handle>` to mean "spawn a new
// session bound to this Slack thread, addressed by <handle>." Keeping a
// dedicated parser for the doubled form lets the dispatcher check it
// BEFORE the existing single-`@` alias path without mutating
// parseHandlePrefix (which is in production for the cross-channel alias
// dispatcher and must keep its current semantics — gc-cby.5.b architect
// risk #3).
//
// Semantics, mirroring parseHandlePrefix where possible:
//
//   - Leading whitespace is tolerated; the doubled prefix must appear at
//     the start of the trimmed text.
//   - The handle is the longest run of [A-Za-z0-9_-] immediately following
//     the doubled prefix.
//   - The handle must terminate at end-of-string, a colon, or whitespace.
//     A bare `@@bad/handle` returns ok=false (not an address token).
//   - The remainder has at most one leading separator (`:`, space, tab,
//     newline) trimmed plus one leading whitespace trimmed, matching
//     parseHandlePrefix.
//
// Cases that return ("", "", false):
//
//   - empty prefix
//   - single-prefix text ("@new …") — that is the existing alias path
//   - triple-prefix text ("@@@x") — conservatively rejected; a "@@@"
//     head is almost certainly a Slack escape or typo, not an address
//     token. (cby.5.b documented this choice.)
//   - "@@" with no handle, "@@:foo" with empty handle
//   - prefix not at the start of the trimmed text
//
// On any non-match the returned strings are empty so the caller cannot
// accidentally consume input from a miss.
func parseDoubleHandlePrefix(text, prefix string) (handle, remainder string, ok bool) {
	if prefix == "" {
		return "", "", false
	}
	doubled := prefix + prefix
	trimmed := strings.TrimLeft(text, " \t")
	if !strings.HasPrefix(trimmed, doubled) {
		return "", "", false
	}
	rest := trimmed[len(doubled):]

	// Reject triple-prefix: "@@@" must NOT match the doubled parser.
	// A user who typed three prefixes is not asking for a launcher
	// dispatch; treat the head as malformed and let the caller fall
	// through to the single-`@` path or no-match.
	if strings.HasPrefix(rest, prefix) {
		return "", "", false
	}

	// Scan the longest run of valid handle characters at the start.
	handleEnd := 0
	for i := 0; i < len(rest); i++ {
		r := rest[i]
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
			(r >= '0' && r <= '9') || r == '-' || r == '_' {
			handleEnd = i + 1
		} else {
			break
		}
	}
	if handleEnd == 0 {
		return "", "", false
	}
	candidate := rest[:handleEnd]
	body := rest[handleEnd:]

	if body == "" {
		return candidate, "", true
	}
	sep := body[0]
	switch sep {
	case ':':
		body = body[1:]
	case ' ', '\t', '\n':
		// whitespace separator — leave it; the next trim handles it
	default:
		// Anything else (e.g. "@@name.foo") means this isn't an
		// address token. parseHandlePrefix takes the same stance.
		return "", "", false
	}
	if len(body) > 0 && (body[0] == ' ' || body[0] == '\t' || body[0] == '\n') {
		body = body[1:]
	}
	return candidate, body, true
}

// handleDoubleHandleDispatch is the launcher-mode dispatch branch
// (cby.5). When parseDoubleHandlePrefix matches an inbound's text, the
// dispatcher routes here BEFORE any single-`@` alias check or
// postInbound call.
//
// Two outcomes:
//
//  1. Pre-claimed: the handle already exists in the alias registry
//     (i.e. some long-lived session has registered itself under that
//     name via /handle-alias). Launching a new thread-bound session
//     under the same handle would split traffic. Emit an ephemeral
//     telling the user to drop a `@` and address the existing session
//     directly. No spawn, no inbound POST.
//
//  2. Free for a new launcher: emit a placeholder ephemeral telling
//     the user the launcher mode recognized the handle. cby.5.3 will
//     replace this stub with the actual AcquireOrCreate call against
//     threadReg using a real spawn closure (POST /v0/.../sessions). We
//     intentionally do NOT call AcquireOrCreate here — that's 5.3's
//     wiring, mirroring how cby.18.1 stubbed the dispatch shape before
//     cby.18.3 wired the subprocess flow.
//
// teamID is the Slack workspace id from the surrounding event envelope
// (slackEventEnvelope.TeamID). It is logged but not yet used to route
// per-workspace tokens — when 5.3 wires the spawn, it will pick the
// per-workspace bot token from the apps registry by team_id.
//
// threadReg is non-nil at the call site (the caller checks for nil
// before parsing). It is captured here so 5.3 can wire the
// AcquireOrCreate call without touching this function's signature.
func handleDoubleHandleDispatch(cfg config, aliasReg *handleAliasRegistry, threadReg *threadSessionRegistry, roomLaunchReg *roomLaunchMappingRegistry, msg slackMessageEvent, teamID, handle, remainder string) {
	if aliasReg != nil {
		if existingSessionID, ok := aliasReg.Get(handle); ok {
			body := fmt.Sprintf(
				"@@%s is bound to an existing session — message that session directly with @%s instead. (session %s)",
				handle, handle, existingSessionID,
			)
			if err := postSlackEphemeral(cfg.slackBotToken, msg.Channel, msg.User, msg.ThreadTS, body); err != nil {
				log.Printf("launcher dispatch (pre-claimed): postEphemeral channel=%s user=%s handle=%q: %v",
					msg.Channel, msg.User, handle, err)
			}
			log.Printf("launcher dispatch: pre-claimed handle=%q session=%s team=%s channel=%s user=%s",
				handle, existingSessionID, teamID, msg.Channel, msg.User)
			return
		}
	}

	dispatchRoomLaunch(cfg, aliasReg, threadReg, roomLaunchReg, msg, teamID, handle, remainder)
}

// slackPostEphemeralReq is the chat.postEphemeral request shape we
// send. Subset of the documented Slack API:
//
//	https://api.slack.com/methods/chat.postEphemeral
//
// Only the fields the launcher branch actually populates are listed
// here; we intentionally do NOT carry blocks/attachments through this
// helper because the launcher ephemeral is plain text.
type slackPostEphemeralReq struct {
	Channel  string `json:"channel"`
	User     string `json:"user"`
	Text     string `json:"text"`
	ThreadTS string `json:"thread_ts,omitempty"`
}

// slackPostEphemeralResp is the response shape we care about. Slack
// returns ok=false with an `error` string on failure.
type slackPostEphemeralResp struct {
	OK    bool   `json:"ok"`
	Error string `json:"error,omitempty"`
}

// postSlackEphemeral posts a plain-text ephemeral message visible only
// to user in channel. threadTS is optional — when set the ephemeral
// appears inside the thread, which is the natural surface for a
// launcher-mode reply (the user posted `@@<handle>` in a thread).
//
// Errors include both transport failures and Slack-side ok=false
// responses; callers log and continue (best-effort delivery, like the
// alias dispatcher).
func postSlackEphemeral(token, channel, user, threadTS, text string) error {
	if token == "" {
		return fmt.Errorf("slack bot token is empty")
	}
	if channel == "" || user == "" {
		return fmt.Errorf("channel and user are required (got channel=%q user=%q)", channel, user)
	}
	body, err := json.Marshal(slackPostEphemeralReq{
		Channel:  channel,
		User:     user,
		Text:     text,
		ThreadTS: threadTS,
	})
	if err != nil {
		return fmt.Errorf("marshal postEphemeral: %w", err)
	}
	req, err := http.NewRequest(http.MethodPost, slackAPIBase+"/chat.postEphemeral", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build postEphemeral request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json; charset=utf-8")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("postEphemeral transport: %w", err)
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("postEphemeral read response: %w", err)
	}
	var sr slackPostEphemeralResp
	if err := json.Unmarshal(respBody, &sr); err != nil {
		return fmt.Errorf("decode postEphemeral response: %w (body=%s)", err, string(respBody))
	}
	if !sr.OK {
		return fmt.Errorf("postEphemeral ok=false: %s", sr.Error)
	}
	return nil
}

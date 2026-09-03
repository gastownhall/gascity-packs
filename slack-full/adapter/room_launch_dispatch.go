package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
)

// roomLaunchHTTPTimeout caps the HTTP round-trips the launcher path
// makes to gc. The session-create endpoint returns 202 within
// milliseconds (only the agent boot is deferred), and the
// session-message endpoint enqueues the payload synchronously. A 10s
// ceiling is generous for both — anything longer is almost certainly
// a wedged controller and should surface as an error ephemeral.
const roomLaunchHTTPTimeout = 10 * time.Second

// roomLaunchSessionCreateRequest mirrors internal/api.sessionCreateRequest
// for the subset of fields the launcher path populates. We deliberately
// do NOT carry an initial Message — the gc handler rejects async
// session creation with a non-empty message ("message is not supported
// with async session creation; create the session, then POST
// /v0/session/{id}/messages"). The remainder lands on /messages
// AFTER the create call returns the session id.
type roomLaunchSessionCreateRequest struct {
	Kind  string `json:"kind"`
	Name  string `json:"name"`
	Title string `json:"title,omitempty"`
}

// roomLaunchSessionCreateResponse mirrors the relevant subset of
// internal/api.sessionResponse — the launcher only needs the new
// session id. The handler writes HTTP 202 with the populated body;
// agent boot is deferred to the controller's reconciler tick.
type roomLaunchSessionCreateResponse struct {
	ID string `json:"id"`
}

// dispatchRoomLaunch implements the spawn-and-route flow for
// `@@<handle>` posts in launcher-enabled channels (gc-cby.5.3).
//
// Sequence:
//
//  1. Look up the channel's launcher binding. On miss → ephemeral
//     instructing the operator to run `gc slack enable-room-launch`.
//  2. Resolve the thread root TS: a top-level post becomes its own
//     thread root (msg.TS); an in-thread reply uses msg.ThreadTS.
//     This is the convergence key for all subsequent posts in the
//     thread.
//  3. Call threadReg.AcquireOrCreate with a closure that POSTs
//     /v0/sessions to gc. The handler returns HTTP 202 with
//     {"id": "..."} synchronously; only agent process boot is
//     deferred. On hit, the closure does not run — the existing
//     session id is returned.
//  4. On created==true: register the handle in aliasReg so subsequent
//     single-`@<handle>` posts route to the new session via the
//     existing alias dispatch path (no special thread-routing logic
//     required). Then post the remainder verbatim to
//     /v0/session/{id}/messages.
//  5. On created==false: just post the remainder to the existing
//     session. Skip the alias registration — it was set when the
//     session was originally spawned.
//
// All user-controlled strings are run through neutralizeMarkupBoundaries
// before they enter Slack-bound or session-bound text (cby.17 / cby.33
// hardening, mirrored from rig_dispatch.go).
//
// Errors at any leg are surfaced via best-effort ephemeral so the user
// sees the failure in-channel rather than the message vanishing.
func dispatchRoomLaunch(
	cfg config,
	aliasReg *handleAliasRegistry,
	threadReg *threadSessionRegistry,
	roomLaunchReg *roomLaunchMappingRegistry,
	msg slackMessageEvent,
	teamID, handle, remainder string,
) (concluded bool) {
	if roomLaunchReg == nil {
		emitRoomLaunchNotEnabledEphemeral(cfg, msg, handle)
		return true
	}
	pool, ok := roomLaunchReg.LookupPoolTemplate(teamID, msg.Channel)
	if !ok {
		emitRoomLaunchNotEnabledEphemeral(cfg, msg, handle)
		return true
	}

	// Thread-root resolution: a top-level `@@new-handle ...` post has
	// thread_ts == "" — its own TS becomes the thread root. An
	// in-thread reply carries thread_ts pointing at the root. Slack's
	// canonical thread identifier is the root's ts, so we converge
	// every subsequent `@<handle>` reply on that key.
	threadTS := msg.ThreadTS
	if threadTS == "" {
		threadTS = msg.TS
	}

	sessionID, boundHandle, created, err := threadReg.AcquireOrCreate(msg.Channel, threadTS, handle, func() (string, error) {
		return roomLaunchSpawnSession(cfg, pool, handle, msg)
	})
	if err != nil {
		log.Printf("launcher dispatch: spawn failed handle=%q channel=%s thread=%s pool=%q: %v",
			handle, msg.Channel, threadTS, pool, err)
		body := fmt.Sprintf(
			"launcher spawn for @@%s could not start a session: %s",
			neutralizeMarkupBoundaries(handle),
			neutralizeMarkupBoundaries(err.Error()),
		)
		if err := postSlackEphemeral(cfg.slackBotToken, msg.Channel, msg.User, msg.ThreadTS, body); err != nil {
			log.Printf("launcher dispatch: ephemeral after spawn failure: %v", err)
		}
		// Transient: the session never spawned — a Slack redelivery
		// should retry the launcher forward (codex r6).
		return false
	}

	// Reserve the alias BEFORE the first-message round trip (codex
	// r13): postSessionMessage can take seconds, and a user's
	// `@<handle>` follow-up processed in that window used to miss the
	// alias lookup and fall through to the channel-bound path — which
	// the launcher session is not on — losing the follow-up. The
	// reservation is rolled back below if the first post fails,
	// BEFORE this function returns false and the caller releases the
	// event's dedup claim, so a woken redelivery sees no alias and
	// correctly re-enters the launcher path (the codex r7 concern
	// about the pre-claimed branch swallowing the un-posted remainder).
	//
	// Gated on the handle being unclaimed rather than on `created`
	// alone (codex r8): a retry after a failed first message
	// re-acquires the existing thread session (created=false) and
	// must still bind the handle it advertises in the acknowledgement
	// below. But ONLY when the stored binding was created for this
	// same handle (codex r9): a DIFFERENT `@@handle` converging on an
	// existing thread session must not register its unclaimed handle
	// globally onto that old session — that would route every later
	// `@handle` post anywhere to the wrong session and permanently
	// block the handle from launching its own.
	aliasReserved := false
	if aliasReg != nil && (created || boundHandle == handle) {
		if _, claimed := aliasReg.Get(handle); !claimed {
			// Reserved even when Set returns an error (codex r15): Set
			// inserts into the in-memory map BEFORE persisting, so a
			// persistence failure still leaves a live reservation that
			// the rollback below must be able to undo — otherwise a
			// parked redelivery would see the handle pre-claimed and
			// commit without ever re-posting the remainder.
			aliasReserved = true
			if err := aliasReg.Set(handle, sessionID); err != nil {
				log.Printf("launcher dispatch: aliasReg.Set handle=%q session=%s: %v",
					handle, sessionID, err)
				// Continue — alias bootstrap is best-effort. The user
				// can re-register manually via /handle-alias if needed.
			}
		}
	}

	// Post the remainder as the session's first/next message via the
	// shared session-message helper. The receiving session sees the
	// raw remainder so the user's first message reads naturally; we
	// don't wrap in a system-reminder envelope here because the
	// launcher path is the user's direct conversational entry point,
	// not an out-of-band cross-channel notification (which is what
	// the alias dispatcher is for).
	if err := postSessionMessage(cfg, sessionID, remainder, "gc-slack-adapter-launcher"); err != nil {
		log.Printf("launcher dispatch: post session message handle=%q session=%s: %v",
			handle, sessionID, err)
		// Roll the reservation back before the caller releases the
		// dedup claim (codex r13): a woken redelivery must re-enter
		// the launcher path (which re-posts the remainder), not the
		// pre-claimed alias branch (which would commit without ever
		// posting it — codex r7). Deleted only while it still points
		// at OUR session, so a racing re-registration is never
		// clobbered.
		if aliasReserved {
			// Compare-and-delete under one registry lock (codex r15):
			// a racing re-registration installed between a separate
			// Get and Delete would otherwise be removed too.
			if _, err := aliasReg.DeleteIf(handle, sessionID); err != nil {
				log.Printf("launcher dispatch: rollback aliasReg.DeleteIf handle=%q: %v", handle, err)
			}
		}
		body := fmt.Sprintf(
			"launcher started session %s for @@%s but the first message could not be delivered: %s",
			neutralizeMarkupBoundaries(sessionID),
			neutralizeMarkupBoundaries(handle),
			neutralizeMarkupBoundaries(err.Error()),
		)
		if err := postSlackEphemeral(cfg.slackBotToken, msg.Channel, msg.User, msg.ThreadTS, body); err != nil {
			log.Printf("launcher dispatch: ephemeral after message failure: %v", err)
		}
		// Transient: the session exists but never got the message — a
		// redelivery re-acquires the same thread session and re-posts.
		return false
	}

	// Acknowledge to the user. Different wording for spawn vs. reuse so
	// the user can tell whether their `@@<handle>` minted a new
	// session or converged on an existing thread session.
	var ackText string
	if created {
		ackText = fmt.Sprintf(
			"Spawned new launcher session for @@%s (session %s); replies in this thread will route via @%s.",
			neutralizeMarkupBoundaries(handle),
			neutralizeMarkupBoundaries(sessionID),
			neutralizeMarkupBoundaries(handle),
		)
	} else {
		ackText = fmt.Sprintf(
			"Posted to existing thread session for @@%s (session %s).",
			neutralizeMarkupBoundaries(handle),
			neutralizeMarkupBoundaries(sessionID),
		)
	}
	if err := postSlackEphemeral(cfg.slackBotToken, msg.Channel, msg.User, msg.ThreadTS, ackText); err != nil {
		log.Printf("launcher dispatch: ack ephemeral: %v", err)
	}
	log.Printf("launcher dispatch: handle=%q session=%s created=%v team=%s channel=%s thread=%s pool=%q",
		handle, sessionID, created, teamID, msg.Channel, threadTS, pool)
	return true
}

// emitRoomLaunchNotEnabledEphemeral surfaces the actionable fix-it for
// a `@@<handle>` post in a channel the operator has not yet wired
// through `gc slack enable-room-launch`. Best-effort delivery — if
// Slack returns an error, we log and move on (consistent with every
// other slack-pack ephemeral path).
func emitRoomLaunchNotEnabledEphemeral(cfg config, msg slackMessageEvent, handle string) {
	body := fmt.Sprintf(
		"channel is not enabled for launcher mode; run `gc slack enable-room-launch %s --launcher <pool>` to bind a launcher pool, then retry @@%s.",
		neutralizeMarkupBoundaries(msg.Channel),
		neutralizeMarkupBoundaries(handle),
	)
	if err := postSlackEphemeral(cfg.slackBotToken, msg.Channel, msg.User, msg.ThreadTS, body); err != nil {
		log.Printf("launcher dispatch: not-enabled ephemeral channel=%s user=%s handle=%q: %v",
			msg.Channel, msg.User, handle, err)
	}
}

// roomLaunchSpawnSession POSTs /v0/sessions to gc and returns the new
// session id. The endpoint is documented to write HTTP 202 with the
// full sessionResponse body synchronously (only the agent boot is
// deferred to the controller's reconciler tick), so we don't need to
// wait on any boot event before returning.
//
// Title is derived from the user's remainder for dashboard display,
// truncated to keep convoy summaries readable.
func roomLaunchSpawnSession(cfg config, pool, handle string, msg slackMessageEvent) (string, error) {
	if cfg.gcAPIBase == "" {
		return "", fmt.Errorf("GC_API_BASE_URL is empty; cannot spawn launcher session")
	}
	title := fmt.Sprintf("[slack/%s by %s] @@%s",
		neutralizeMarkupBoundaries(msg.Channel),
		neutralizeMarkupBoundaries(msg.User),
		neutralizeMarkupBoundaries(handle),
	)
	if len(title) > rigDispatchTitleMaxLen {
		title = title[:rigDispatchTitleMaxLen]
	}
	payload, err := json.Marshal(roomLaunchSessionCreateRequest{
		Kind:  "agent",
		Name:  pool,
		Title: title,
	})
	if err != nil {
		return "", fmt.Errorf("marshal session create: %w", err)
	}
	target := strings.TrimRight(cfg.gcAPIBase, "/") + "/v0/sessions"
	req, err := http.NewRequest(http.MethodPost, target, bytes.NewReader(payload))
	if err != nil {
		return "", fmt.Errorf("build session-create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-GC-Request", "gc-slack-adapter-launcher")

	client := &http.Client{Timeout: roomLaunchHTTPTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("session-create transport: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("session-create %s: %s", resp.Status, strings.TrimSpace(string(body)))
	}
	var decoded roomLaunchSessionCreateResponse
	if err := json.Unmarshal(body, &decoded); err != nil {
		return "", fmt.Errorf("decode session-create response (%q): %w", string(body), err)
	}
	if decoded.ID == "" {
		return "", fmt.Errorf("session-create returned empty id (body=%q)", string(body))
	}
	return decoded.ID, nil
}

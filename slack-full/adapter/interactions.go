package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// channelMappingDiskRecord is the byte-for-byte mirror of
// cmd/gc.slackChannelMappingRecord (cmd/gc/slack_channel_mapping.go).
// Keep the JSON tags in lockstep with the Go writer; the on-disk file
// at <cityPath>/.gc/slack/channel_mappings.json is the only contract
// between gc and this adapter.
type channelMappingDiskRecord struct {
	WorkspaceID string    `json:"workspace_id"`
	ChannelID   string    `json:"channel_id"`
	TargetKind  string    `json:"target_kind"` // "rig" or "session"
	TargetID    string    `json:"target_id"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

const (
	channelMappingTargetKindRig     = "rig"
	channelMappingTargetKindSession = "session"
)

// channelMappingRegistry is a read-mostly in-memory view of the
// channel_mappings.json file written by `gc slack map-channel`. The
// adapter loads it once at startup and re-reads it on SIGHUP via
// Stage/Commit (gc-cby.23); it does NOT fsnotify-watch the file —
// a watcher introduces races against in-flight Slack interactions,
// and the slash-command latency budget (Slack's 3s) is too tight to
// retry.
type channelMappingRegistry struct {
	mu       sync.RWMutex
	byKey    map[string]channelMappingDiskRecord
	diskPath string
}

// channelMappingSnapshot is a parsed-but-not-yet-committed view of
// channel_mappings.json. nil snapshot is the "file is absent" sentinel;
// Commit on nil is a no-op (operators clear by writing `{}`, not `rm`).
type channelMappingSnapshot struct {
	byKey map[string]channelMappingDiskRecord
}

func channelMappingKey(workspaceID, channelID string) string {
	return workspaceID + ":" + channelID
}

// newChannelMappingRegistry opens the registry at diskPath. A missing
// file yields an empty registry (tolerant load). A file with a record
// carrying an unknown target_kind is rejected at startup so a corrupt
// upstream write cannot silently be served as policy.
func newChannelMappingRegistry(diskPath string) (*channelMappingRegistry, error) {
	r := &channelMappingRegistry{
		byKey:    make(map[string]channelMappingDiskRecord),
		diskPath: diskPath,
	}
	if err := r.load(); err != nil {
		return nil, fmt.Errorf("load channel mapping registry from %s: %w", diskPath, err)
	}
	return r, nil
}

// Get returns the record for (workspaceID, channelID), plus a bool
// indicating whether one is registered.
func (r *channelMappingRegistry) Get(workspaceID, channelID string) (channelMappingDiskRecord, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	rec, ok := r.byKey[channelMappingKey(workspaceID, channelID)]
	return rec, ok
}

// Len returns the number of records currently loaded. Read-locked so
// callers (e.g. startup logs) don't race with concurrent Set in tests.
func (r *channelMappingRegistry) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.byKey)
}

// Set is provided for tests only. Production reads only — operator
// writes go through `gc slack map-channel`.
func (r *channelMappingRegistry) Set(rec channelMappingDiskRecord) error {
	if rec.WorkspaceID == "" || rec.ChannelID == "" {
		return fmt.Errorf("channel mapping: workspace_id and channel_id required")
	}
	if rec.TargetKind != channelMappingTargetKindRig &&
		rec.TargetKind != channelMappingTargetKindSession {
		return fmt.Errorf("channel mapping: target_kind %q must be %q or %q",
			rec.TargetKind, channelMappingTargetKindRig, channelMappingTargetKindSession)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.byKey[channelMappingKey(rec.WorkspaceID, rec.ChannelID)] = rec
	return r.saveLocked()
}

// maxRegistryBytes caps the size of the JSON registry file we'll
// load off disk. Channel mappings are a few hundred records of a
// fixed shape; 10 MiB is several orders of magnitude over a healthy
// install. A file beyond that is either corrupt or hostile and must
// not be loaded.
const maxRegistryBytes = 10 << 20 // 10 MiB

// parseChannelMappingRegistry reads diskPath into a ready-to-commit
// snapshot. A missing file returns (nil, nil) — "no change" sentinel for
// SIGHUP semantics. Records with unknown target_kind are rejected at
// parse time so a corrupt write can't be served as policy.
func parseChannelMappingRegistry(diskPath string) (*channelMappingSnapshot, error) {
	if diskPath == "" {
		return nil, nil
	}
	f, err := openRegistryFile(diskPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxRegistryBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", diskPath, err)
	}
	if int64(len(data)) > maxRegistryBytes {
		return nil, fmt.Errorf("registry file %s exceeds %d bytes", diskPath, maxRegistryBytes)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var stored map[string]channelMappingDiskRecord
	if err := dec.Decode(&stored); err != nil {
		return nil, fmt.Errorf("decode channel mapping store: %w", err)
	}
	for key, rec := range stored {
		if rec.TargetKind != channelMappingTargetKindRig &&
			rec.TargetKind != channelMappingTargetKindSession {
			return nil, fmt.Errorf("channel mapping store: record %q has invalid target_kind %q (must be %q or %q)",
				key, rec.TargetKind, channelMappingTargetKindRig, channelMappingTargetKindSession)
		}
	}
	if stored == nil {
		stored = make(map[string]channelMappingDiskRecord)
	}
	return &channelMappingSnapshot{byKey: stored}, nil
}

// load is the constructor-time helper — called pre-publish, no lock needed.
func (r *channelMappingRegistry) load() error {
	snap, err := parseChannelMappingRegistry(r.diskPath)
	if err != nil {
		return err
	}
	if snap != nil {
		r.byKey = snap.byKey
	}
	return nil
}

// Stage parses the on-disk file into a snapshot ready for atomic Commit.
// nil snapshot + nil error = file absent, preserve live state.
func (r *channelMappingRegistry) Stage() (*channelMappingSnapshot, error) {
	return parseChannelMappingRegistry(r.diskPath)
}

// Commit atomically swaps the in-memory snapshot under the write lock.
// nil snapshot is a no-op.
func (r *channelMappingRegistry) Commit(snap *channelMappingSnapshot) {
	if snap == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.byKey = snap.byKey
}

// Reload combines Stage and Commit; per-registry test convenience.
// Production reload uses reloadAllRegistries for all-or-nothing semantics.
func (r *channelMappingRegistry) Reload() error {
	snap, err := r.Stage()
	if err != nil {
		return err
	}
	r.Commit(snap)
	return nil
}

func (r *channelMappingRegistry) saveLocked() error {
	if r.diskPath == "" {
		return nil
	}
	dir := filepath.Dir(r.diskPath)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("mkdir channel mapping store dir %q: %w", dir, err)
	}
	data, err := json.MarshalIndent(r.byKey, "", "  ")
	if err != nil {
		return fmt.Errorf("encode channel mapping store: %w", err)
	}
	return writeFile0600(r.diskPath, data)
}

// writeFile0600 atomically writes data to path with 0o600 perms.
// Uses os.CreateTemp so two concurrent writers in the same directory
// (in tests) don't clobber each other's temp file before the rename.
// Helper exposed so tests can seed a corrupt file at the same perms
// the production writer would use.
func writeFile0600(path string, data []byte) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("mkdir %q: %w", dir, err)
	}
	f, err := os.CreateTemp(dir, filepath.Base(path)+"-*.tmp")
	if err != nil {
		return fmt.Errorf("create temp in %q: %w", dir, err)
	}
	tmpName := f.Name()
	cleanup := func() { _ = os.Remove(tmpName) }
	if err := f.Chmod(0o600); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("chmod %q: %w", tmpName, err)
	}
	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("write %q: %w", tmpName, err)
	}
	if err := f.Close(); err != nil {
		cleanup()
		return fmt.Errorf("close %q: %w", tmpName, err)
	}
	if err := os.Rename(tmpName, path); err != nil {
		cleanup()
		return fmt.Errorf("rename %q -> %q: %w", tmpName, path, err)
	}
	return nil
}

// parseTeamIDFromInteractionsBody extracts the Slack team id from a
// /slack/interactions POST body to drive per-app signing-secret
// lookup. Two body shapes occur:
//
//  1. Slash-command form: top-level field `team_id=T01234567`.
//  2. Block-action / view-submission: top-level field `payload=<JSON>`
//     where the JSON contains `{"team":{"id":"T01234567",...},...}`.
//
// Returns "" on any decode failure or missing field. The body is
// unsigned at this point in the pipeline; the caller treats "" as
// "fall through to env fallback" inside lookupSigningSecrets.
//
// Body size is already capped upstream at 1 MiB by io.LimitReader.
func parseTeamIDFromInteractionsBody(body []byte) string {
	form, err := url.ParseQuery(string(body))
	if err != nil {
		return ""
	}
	if t := form.Get("team_id"); t != "" {
		return t
	}
	payload := form.Get("payload")
	if payload == "" {
		return ""
	}
	var p struct {
		Team struct {
			ID string `json:"id"`
		} `json:"team"`
	}
	if err := json.Unmarshal([]byte(payload), &p); err != nil {
		return ""
	}
	return p.Team.ID
}

// slackInteractionResponse is the ephemeral envelope Slack expects on
// a slash-command HTTP response.
type slackInteractionResponse struct {
	ResponseType string `json:"response_type"`
	Text         string `json:"text"`
}

// writeEphemeral writes status with an ephemeral JSON body. Errors
// from Encode are logged but not surfaced — the slash-command response
// is best-effort and Slack treats any 2xx with empty body as success.
func writeEphemeral(w http.ResponseWriter, status int, text string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(slackInteractionResponse{
		ResponseType: "ephemeral",
		Text:         text,
	}); err != nil {
		log.Printf("slack interactions: encode response: %v", err)
	}
}

// handleSlackInteractions serves POST /slack/interactions — the
// public webhook for Slack slash-command, block-action, and
// view-submission payloads. HMAC-verified with cfg.slackSigningKey.
// Slash commands and block_actions resolve through resolveChannelTarget
// — per-channel `map-channel` bindings (cby.3) are overrides on top of
// the rig→{channels} default (cby.4); channel mapping wins.
// view_submission has no channel context and routes via the modal
// opener's view.private_metadata = `{"session_id":"..."}` contract.
//
// Slack's 3-second response deadline means dispatch to gc happens in a
// goroutine; the HTTP response is always immediate. Errors from the
// goroutine are logged.
func handleSlackInteractions(cfg config, mapReg *channelMappingRegistry, rigReg *rigMappingRegistry) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
		if err != nil {
			http.Error(w, "read body", http.StatusBadRequest)
			return
		}
		// Pre-parse team_id from the (still-unsigned) body to choose
		// which signing secret(s) to trial-verify against. Body is
		// either a slash-command form (top-level team_id field) or a
		// payload= JSON form (payload.team.id). See gc-cby.16.
		teamID := parseTeamIDFromInteractionsBody(body)
		secrets := lookupSigningSecrets(cfg.appsRegistry, cfg.slackSigningKey, teamID)
		if !verifySlackSignatureMulti(secrets, r.Header.Get("X-Slack-Request-Timestamp"), body, r.Header.Get("X-Slack-Signature")) {
			log.Printf("slack interactions: signature verify FAILED team_id=%q candidates=%d", clipTeamIDForLog(teamID), len(secrets))
			http.Error(w, "invalid signature", http.StatusUnauthorized)
			return
		}

		form, err := url.ParseQuery(string(body))
		if err != nil {
			log.Printf("slack interactions: parse form: %v", err)
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		if len(form) == 0 {
			http.Error(w, "empty form body", http.StatusBadRequest)
			return
		}

		// Detect block-action / view-submission payloads. Slack sends
		// these as a single `payload=<JSON>` field; slash commands set
		// `command` instead.
		if payloadStr := form.Get("payload"); payloadStr != "" && form.Get("command") == "" {
			handleInteractionPayload(w, cfg, mapReg, rigReg, payloadStr)
			return
		}

		teamID = form.Get("team_id")
		channelID := form.Get("channel_id")
		// channel_name is the human-readable Slack channel name
		// (e.g. "oversight-platform"). Slack's slash-command POST
		// always includes it; consumed by the gc-px8.9 pattern-
		// resolver tier in resolveChannelTargetWithName. Empty-string
		// fallback keeps us safe against forged payloads or future
		// Slack changes — patterns are then inert.
		channelName := form.Get("channel_name")
		command := form.Get("command")
		text := form.Get("text")
		userID := form.Get("user_id")
		triggerID := form.Get("trigger_id")

		if teamID == "" {
			log.Printf("slack interactions: missing team_id in slash-command form")
			http.Error(w, "team_id mismatch", http.StatusUnauthorized)
			return
		}
		if cfg.accountID != "" && teamID != cfg.accountID {
			log.Printf("slack interactions: team_id %q does not match configured workspace %q", teamID, cfg.accountID)
			http.Error(w, "team_id mismatch", http.StatusUnauthorized)
			return
		}
		if cfg.accountID == "" {
			log.Printf("slack interactions: SLACK_WORKSPACE_ID is empty; accepting team_id=%q without verification (single-tenant deployment)", teamID)
		}

		if command == "" || channelID == "" {
			http.Error(w, "missing required slash-command fields", http.StatusBadRequest)
			return
		}

		rec, source, ok := resolveChannelTargetWithName(mapReg, rigReg, teamID, channelID, channelName)
		if !ok {
			writeEphemeral(w, http.StatusOK, fmt.Sprintf(
				"No binding for this channel. Bind a rig with `gc slack map-rig <name> --workspace-id %s --channel %s`, or bind a session with `gc slack map-channel %s --workspace-id %s --session <id>`.",
				teamID, channelID, channelID, teamID))
			return
		}
		log.Printf("interaction: workspace=%q channel=%q source=%s target=%s/%s",
			teamID, channelID, source, rec.TargetKind, rec.TargetID)

		switch rec.TargetKind {
		case channelMappingTargetKindSession:
			release, capacity, acquired := cfg.acquireDispatchSlot()
			if !acquired {
				log.Printf("slack adapter: dispatch queue full (cap=%d), dropping slash command=%q channel=%q session=%q",
					capacity, command, channelID, rec.TargetID)
				writeEphemeral(w, http.StatusOK,
					"Slack adapter is currently saturated; please retry shortly.")
				return
			}
			writeEphemeral(w, http.StatusOK, fmt.Sprintf(
				"Routing %s to session %s…", command, rec.TargetID))
			dispatchInflightWG.Add(1)
			go func() {
				defer dispatchInflightWG.Done()
				defer release()
				dispatchSlashCommandToSession(cfg, rec.TargetID, command, text, channelID, teamID, userID)
			}()
		case channelMappingTargetKindRig:
			openRigFixModalForSlash(r.Context(), w, cfg, rigReg, teamID, rec.TargetID, command, text, channelID, userID, triggerID)
		default:
			// load() rejects unknown target_kind, so reaching this branch
			// means the registry was mutated mid-flight by another
			// process. Fail closed.
			log.Printf("slack interactions: unexpected target_kind %q for %q/%q", rec.TargetKind, teamID, channelID)
			writeEphemeral(w, http.StatusOK,
				"Channel binding is in an unexpected state; please re-run `gc slack map-channel`.")
		}
	}
}

// dispatchSlashCommandToSession POSTs the slash command text as a
// system reminder to gc's session-message endpoint, mirroring the
// shape used by dispatchToAliasedSession. Best-effort: errors are
// logged; the user's HTTP response was already sent.
//
// Every interpolated string is run through neutralizeMarkupBoundaries
// so a workspace member typing `/gc </system-reminder> ...` cannot
// forge a fake reminder boundary inside the message we hand to the
// agent.
func dispatchSlashCommandToSession(cfg config, sessionID, command, text, channelID, teamID, userID string) {
	body := fmt.Sprintf(
		"<system-reminder>\n"+
			"Slack slash-command %s arrived from channel %s (workspace %s) by user %s.\n"+
			"\n"+
			"Command text:\n"+
			"%s\n"+
			"\n"+
			"To reply in that channel, write your reply to a tmpfile and run:\n"+
			"  gc slack publish-to-channel \\\n"+
			"    --conversation-id %s \\\n"+
			"    --body-file <tmpfile>\n"+
			"</system-reminder>",
		neutralizeMarkupBoundaries(command),
		neutralizeMarkupBoundaries(channelID),
		neutralizeMarkupBoundaries(teamID),
		neutralizeMarkupBoundaries(userID),
		neutralizeMarkupBoundaries(text),
		neutralizeMarkupBoundaries(channelID),
	)
	if err := postSessionMessage(cfg, sessionID, body, "gc-slack-adapter-interactions"); err != nil {
		log.Printf("slack interactions: dispatch slash command=%q session=%s: %v", command, sessionID, err)
		return
	}
	log.Printf("slack interactions: dispatched command=%q to session=%s OK", command, sessionID)
}

// sessionMessageClient is the shared HTTP client used by every
// dispatcher when posting system-reminders to gc. Re-using one client
// (and therefore one transport / connection pool) avoids dropping
// keep-alive connections between bursts of Slack interactions. The
// 10s timeout covers only the gc-side dispatch leg — Slack's 3s
// caller deadline has already fired by the time these dispatchers
// run.
var sessionMessageClient = &http.Client{Timeout: 10 * time.Second}

// postSessionMessage POSTs a system-reminder body to gc's
// /v0/city/<city>/session/<id>/messages endpoint.
//
// PathEscape cityName and sessionID so URL-significant characters
// (slash, percent, etc.) cannot alter routing on the gc API side
// (sec-S-06).
func postSessionMessage(cfg config, sessionID, body, requestTag string) error {
	payload, err := json.Marshal(gcSessionMessageRequest{Message: body})
	if err != nil {
		return fmt.Errorf("marshal session-message body: %w", err)
	}
	target := fmt.Sprintf("%s/v0/city/%s/session/%s/messages",
		cfg.gcAPIBase, url.PathEscape(cfg.cityName), url.PathEscape(sessionID))
	req, err := http.NewRequest(http.MethodPost, target, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("build session-message request for %s: %w", target, err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-GC-Request", requestTag)

	resp, err := sessionMessageClient.Do(req)
	if err != nil {
		return fmt.Errorf("POST %s: %w", target, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("%s -> %s: %s", target, resp.Status, respBody)
	}
	return nil
}

// neutralizeMarkupBoundaries injects a zero-width space (U+200B) after
// every '<' in user-controlled input so a Slack workspace member
// cannot forge a `</system-reminder>` (or any other XML-style tag)
// inside a reminder body and confuse a downstream agent's tag parser.
// The agent sees visually identical content; a strict tag-boundary
// matcher cannot match the resulting "<​…>" sequence.
//
// Applied to every interpolated user-controlled field before it
// enters a system-reminder template. Fully idempotent: f(f(x)) == f(x)
// for all inputs. A '<' that is already followed by U+200B (because a
// prior pass neutralized it, or the byte sequence happens to appear in
// raw input) is not double-padded. This protects against latent bugs
// where a future refactor double-applies the function on the same
// value.
func neutralizeMarkupBoundaries(s string) string {
	if !strings.Contains(s, "<") {
		return s
	}
	const zwsp = "​"
	var b strings.Builder
	b.Grow(len(s) + strings.Count(s, "<")*len(zwsp))
	for i := 0; i < len(s); i++ {
		b.WriteByte(s[i])
		if s[i] == '<' && !strings.HasPrefix(s[i+1:], zwsp) {
			b.WriteString(zwsp)
		}
	}
	return b.String()
}

// handleInteractionPayload decodes and routes block_actions /
// view_submission payloads received as a `payload=<JSON>` form field.
// Signature verification has already happened upstream; this function
// re-applies the cfg.accountID workspace gate against the decoded
// team_id (the slash-command branch's gate runs against form.team_id;
// payload-branch reads payload.team.id, a different field).
func handleInteractionPayload(w http.ResponseWriter, cfg config, mapReg *channelMappingRegistry, rigReg *rigMappingRegistry, payloadStr string) {
	var p slackInteractionPayload
	if err := json.Unmarshal([]byte(payloadStr), &p); err != nil {
		log.Printf("slack interactions: decode payload JSON: %v", err)
		http.Error(w, "bad payload json", http.StatusBadRequest)
		return
	}

	if p.Team.ID == "" {
		log.Printf("slack interactions: payload missing team.id (type=%q)", p.Type)
		http.Error(w, "team_id required", http.StatusUnauthorized)
		return
	}
	if cfg.accountID != "" && p.Team.ID != cfg.accountID {
		log.Printf("slack interactions: payload.team.id %q does not match configured workspace %q",
			p.Team.ID, cfg.accountID)
		http.Error(w, "team_id mismatch", http.StatusUnauthorized)
		return
	}
	if cfg.accountID == "" {
		log.Printf("slack interactions: SLACK_WORKSPACE_ID is empty; accepting payload team_id=%q without verification (single-tenant deployment)",
			p.Team.ID)
	}

	switch p.Type {
	case interactionTypeBlockActions:
		handleBlockActionsPayload(w, cfg, mapReg, rigReg, &p)
	case interactionTypeViewSubmission:
		handleViewSubmissionPayload(w, cfg, rigReg, &p)
	default:
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"unsupported interaction type=%q. slack-pack supports block_actions and view_submission today; other Slack interaction types (shortcut, message_action, view_closed, block_suggestion) are tracked under the gc-cby epic.",
			p.Type))
	}
}

// handleBlockActionsPayload routes a block_actions payload through the
// same channel-binding flow used for slash commands. Channel context
// resolves payload.channel.id, falling back to payload.container.channel_id
// (set when Slack omits the top-level channel object — common for
// shared/forwarded message reposts and threaded replies).
func handleBlockActionsPayload(w http.ResponseWriter, cfg config, mapReg *channelMappingRegistry, rigReg *rigMappingRegistry, p *slackInteractionPayload) {
	if len(p.Actions) == 0 {
		// Slack sends empty actions[] during view-restoration. Acknowledge
		// silently — no ephemeral spam, no dispatch.
		log.Printf("slack interactions: block_actions empty actions[] team=%q user=%q view=%q (state restoration; ignored)",
			p.Team.ID, p.User.ID, p.View.ID)
		w.WriteHeader(http.StatusOK)
		return
	}

	channelID := p.Channel.ID
	if channelID == "" {
		channelID = p.Container.ChannelID
	}
	if channelID == "" {
		log.Printf("slack interactions: block_actions has no channel context team=%q user=%q (likely from app home)",
			p.Team.ID, p.User.ID)
		writeEphemeral(w, http.StatusOK,
			"Block-action received but no channel context (interaction did not originate from a channel-bound message). slack-pack routes block-actions via the channel binding the message was sent in.")
		return
	}

	rec, source, ok := resolveChannelTarget(mapReg, rigReg, p.Team.ID, channelID)
	if !ok {
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"No binding for this channel. Bind a rig with `gc slack map-rig <name> --workspace-id %s --channel %s`, or bind a session with `gc slack map-channel %s --workspace-id %s --session <id>`.",
			p.Team.ID, channelID, channelID, p.Team.ID))
		return
	}
	log.Printf("interaction: workspace=%q channel=%q source=%s target=%s/%s type=block_actions",
		p.Team.ID, channelID, source, rec.TargetKind, rec.TargetID)

	switch rec.TargetKind {
	case channelMappingTargetKindSession:
		release, capacity, acquired := cfg.acquireDispatchSlot()
		if !acquired {
			log.Printf("slack adapter: dispatch queue full (cap=%d), dropping block_actions team=%q channel=%q session=%q",
				capacity, p.Team.ID, channelID, rec.TargetID)
			writeEphemeral(w, http.StatusOK,
				"Slack adapter is currently saturated; please retry shortly.")
			return
		}
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"Routing block-action to session %s…", rec.TargetID))
		dispatchInflightWG.Add(1)
		go func() {
			defer dispatchInflightWG.Done()
			defer release()
			dispatchBlockActionsToSession(cfg, rec.TargetID, channelID, p)
		}()
	case channelMappingTargetKindRig:
		dispatchBlockActionsToRig(w, cfg, rigReg, p.Team.ID, rec.TargetID, channelID, p)
	default:
		log.Printf("slack interactions: unexpected target_kind %q for %q/%q", rec.TargetKind, p.Team.ID, channelID)
		writeEphemeral(w, http.StatusOK,
			"Channel binding is in an unexpected state; please re-run `gc slack map-channel`.")
	}
}

// handleViewSubmissionPayload routes a view_submission payload by
// inspecting view.private_metadata. Two metadata shapes are
// recognized:
//
//  1. `{"kind":"rig_fix",…}` (gc-cby.18.4) — written by
//     openRigFixModalForSlash. Routes to dispatchRigFixFromViewSubmission
//     which mints a bead in the rig workdir and dispatches via gc sling.
//  2. `{"session_id":"..."}` (gc-cby.17 legacy) — modal opened by an
//     external session that wants the submission forwarded as a
//     system-reminder.
//
// Modals carry no channel context, so the opener is responsible for
// stuffing the target into private_metadata when it calls views.open.
// Any decode failure (missing, malformed, unknown fields, oversized
// values) responds with `{"response_action":"clear"}` so Slack closes
// the modal stack and the user knows the submission did not process.
// The accountID gate has already fired in the caller.
func handleViewSubmissionPayload(w http.ResponseWriter, cfg config, rigReg *rigMappingRegistry, p *slackInteractionPayload) {
	if meta, ok := decodeRigDispatchMetadata(p.View.PrivateMetadata); ok {
		dispatchRigFixFromViewSubmission(w, cfg, rigReg, meta, p)
		return
	}
	sessionID, ok := decodePrivateMetadata(p.View.PrivateMetadata)
	if !ok {
		log.Printf("slack interactions: view_submission private_metadata invalid team=%q user=%q callback=%q (clearing modal)",
			p.Team.ID, p.User.ID, p.View.CallbackID)
		writeViewClear(w)
		return
	}

	release, capacity, acquired := cfg.acquireDispatchSlot()
	if !acquired {
		log.Printf("slack adapter: dispatch queue full (cap=%d), dropping view_submission team=%q session=%q",
			capacity, p.Team.ID, sessionID)
		writeViewClear(w)
		return
	}
	// Respond `{}` synchronously so Slack closes only the current view
	// in the stack. The dispatch goroutine fires after the response.
	// The semaphore slot acquired above is intentionally lent across
	// the goroutine boundary — `defer release()` returns it when the
	// dispatch completes, regardless of which path inside dispatch
	// returns.
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte("{}")); err != nil {
		log.Printf("slack interactions: write view_submission ack: %v", err)
	}
	log.Printf("interaction: workspace=%q user=%q target=session/%s type=view_submission callback=%q",
		p.Team.ID, p.User.ID, sessionID, p.View.CallbackID)
	dispatchInflightWG.Add(1)
	go func() {
		defer dispatchInflightWG.Done()
		defer release()
		dispatchViewSubmissionToSession(cfg, sessionID, p)
	}()
}

// decodePrivateMetadata enforces the gc-cby.17 contract: view.private_metadata
// MUST be a JSON string of the form `{"session_id":"..."}`. Strict decode
// (DisallowUnknownFields) prevents app authors from smuggling extra
// routing knobs the handler hasn't sanctioned. Length cap defends
// against a runaway-length session_id that could distort downstream
// URL building or storage.
func decodePrivateMetadata(raw string) (string, bool) {
	if strings.TrimSpace(raw) == "" {
		return "", false
	}
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.DisallowUnknownFields()
	var pm slackPrivateMetadata
	if err := dec.Decode(&pm); err != nil {
		return "", false
	}
	if pm.SessionID == "" {
		return "", false
	}
	if len(pm.SessionID) > maxPrivateMetadataSessionIDLen {
		return "", false
	}
	return pm.SessionID, true
}

// writeViewClear responds {"response_action":"clear"} (Slack closes
// the entire view stack). Used when the handler cannot route the
// view_submission — the user sees the modal disappear and knows the
// submit did not process.
func writeViewClear(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte(`{"response_action":"clear"}`)); err != nil {
		log.Printf("slack interactions: write view clear: %v", err)
	}
}

// writeViewSubmissionErrors responds with response_action=errors so
// Slack keeps the modal open and surfaces a per-block error message to
// the user. Used when submission cannot proceed for a recoverable
// reason (e.g. dispatch saturation) — the user sees the cause and can
// retry without re-typing.
func writeViewSubmissionErrors(w http.ResponseWriter, errors map[string]string) {
	body := map[string]any{
		"response_action": "errors",
		"errors":          errors,
	}
	b, err := json.Marshal(body)
	if err != nil {
		log.Printf("slack interactions: encode view errors: %v", err)
		writeViewClear(w)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write(b); err != nil {
		log.Printf("slack interactions: write view errors: %v", err)
	}
}

// dispatchBlockActionsToSession POSTs a system-reminder describing the
// block_actions interaction to gc's session-message endpoint. Best-
// effort: errors are logged; the user's HTTP response was already sent.
//
// One system-reminder per payload (not per action). Slack's actions[]
// is typically length 1, but multi_*_select finalizations can carry
// 2+ entries with the same action_id — bundling them in one message
// keeps the agent's view of the interaction atomic.
func dispatchBlockActionsToSession(cfg config, sessionID, channelID string, p *slackInteractionPayload) {
	var buf strings.Builder
	fmt.Fprintf(&buf,
		"<system-reminder>\n"+
			"Slack block_actions arrived from channel %s (workspace %s) by user %s.\n"+
			"trigger_id: %s\n"+
			"\n"+
			"actions:\n",
		neutralizeMarkupBoundaries(channelID),
		neutralizeMarkupBoundaries(p.Team.ID),
		neutralizeMarkupBoundaries(p.User.ID),
		neutralizeMarkupBoundaries(p.TriggerID))
	for i, a := range p.Actions {
		fmt.Fprintf(&buf, "  %d. action_id=%s block_id=%s type=%s value=%q",
			i+1,
			neutralizeMarkupBoundaries(a.ActionID),
			neutralizeMarkupBoundaries(a.BlockID),
			neutralizeMarkupBoundaries(a.Type),
			neutralizeMarkupBoundaries(a.Value))
		if a.SelectedOption != nil && a.SelectedOption.Value != "" {
			fmt.Fprintf(&buf, " selected_option=%q",
				neutralizeMarkupBoundaries(a.SelectedOption.Value))
		}
		if a.SelectedDate != "" {
			fmt.Fprintf(&buf, " selected_date=%q",
				neutralizeMarkupBoundaries(a.SelectedDate))
		}
		buf.WriteByte('\n')
	}
	if p.ResponseURL != "" {
		// response_url is valid for ~30min and 5 uses (Slack contract).
		// Pass it to the agent verbatim — the agent decides whether to
		// post to it; Go does no judgment about that here.
		fmt.Fprintf(&buf, "\nresponse_url (valid ~30min, up to 5 uses): %s\n",
			neutralizeMarkupBoundaries(p.ResponseURL))
	}
	fmt.Fprintf(&buf,
		"\nTo reply in that channel, write your reply to a tmpfile and run:\n"+
			"  gc slack publish-to-channel \\\n"+
			"    --conversation-id %s \\\n"+
			"    --body-file <tmpfile>\n"+
			"</system-reminder>",
		neutralizeMarkupBoundaries(channelID))
	body := buf.String()
	if err := postSessionMessage(cfg, sessionID, body, "gc-slack-adapter-interactions-block"); err != nil {
		log.Printf("slack interactions: dispatch block_actions to session=%s: %v", sessionID, err)
		return
	}
	log.Printf("slack interactions: dispatched block_actions to session=%s OK", sessionID)
}

// dispatchViewSubmissionToSession POSTs a system-reminder describing
// the modal submission (callback_id + view.state.values) to gc.
// Best-effort: errors are logged; the user's HTTP response was already
// sent.
//
// view_submission carries no top-level response_url per Slack's wire
// contract — per-block response_urls live under view.state when the
// modal opener sets response_url_enabled on an input block. Those are
// part of the JSON-encoded view.state.values blob below; nothing
// extra to forward here.
//
// The view.state.values JSON is HTML-safe by virtue of
// encoding/json's default escaping (`<`, `>`, `&` become `<`,
// `>`, `&`); the other fields go through
// neutralizeMarkupBoundaries.
func dispatchViewSubmissionToSession(cfg config, sessionID string, p *slackInteractionPayload) {
	valuesJSON, err := json.MarshalIndent(p.View.State.Values, "", "  ")
	if err != nil {
		valuesJSON = []byte("(unable to marshal view.state.values)")
	}

	body := fmt.Sprintf(
		"<system-reminder>\n"+
			"Slack view_submission arrived from user %s (workspace %s).\n"+
			"callback_id: %s\n"+
			"trigger_id: %s\n"+
			"\n"+
			"view.state.values:\n%s\n"+
			"</system-reminder>",
		neutralizeMarkupBoundaries(p.User.ID),
		neutralizeMarkupBoundaries(p.Team.ID),
		neutralizeMarkupBoundaries(p.View.CallbackID),
		neutralizeMarkupBoundaries(p.TriggerID),
		valuesJSON,
	)
	if err := postSessionMessage(cfg, sessionID, body, "gc-slack-adapter-interactions-view"); err != nil {
		log.Printf("slack interactions: dispatch view_submission to session=%s: %v", sessionID, err)
		return
	}
	log.Printf("slack interactions: dispatched view_submission callback=%q to session=%s OK", p.View.CallbackID, sessionID)
}

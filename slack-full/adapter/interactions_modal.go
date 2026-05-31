package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Modal-backed summary/context capture for rig slash-command intake.
// gc-cby.18.4 — when a slash command lands in a rig-bound channel, the
// adapter calls Slack's `views.open` API to surface a modal collecting
// a one-line summary plus optional markdown context BEFORE creating
// the bead. The captured fields land on the bead title and a
// `gc sling --var context_markdown=...` argument so the agent picking
// the work has more than the raw slash text.
//
// Why a modal instead of dispatching the raw slash text:
//   - Slash text is single-line, untyped, and often a one-word trigger
//     ("/gc") that the user expects to drive a richer interaction. The
//     modal gives the user a place to describe the work without
//     learning a slash-flag DSL.
//   - The captured `context_markdown` is forwarded to the model verbatim
//     via --var, keeping ZFC: Go is plumbing, the agent decides.
//
// Wire reference (Slack docs, May 2026):
//   - views.open:                 https://api.slack.com/methods/views.open
//   - block_kit input element:    https://api.slack.com/reference/block-kit/block-elements#input

// rigFixModalCallbackID identifies the modal on submission. Stable
// across releases — view_submission handler routes on it (combined
// with the kind in private_metadata).
const rigFixModalCallbackID = "gc_rig_fix_modal"

// metadataKindRigFix is the discriminator embedded in
// view.private_metadata to distinguish rig-fix submissions from the
// legacy session-message submissions handled by gc-cby.17.
const metadataKindRigFix = "rig_fix"

// Modal block + action ids. The view_submission handler reads
// view.state.values[block_id][action_id].value to recover the user's
// input — these constants are the contract.
const (
	rigFixModalSummaryBlockID  = "summary_block"
	rigFixModalSummaryActionID = "summary_input"
	rigFixModalContextBlockID  = "context_block"
	rigFixModalContextActionID = "context_input"
)

// rigFixModalSummaryMaxLen caps the summary input. Slack's
// plain_text_input enforces a max_length on its own when set; we
// mirror that here for the bead title (cf. rigDispatchTitleMaxLen).
const rigFixModalSummaryMaxLen = 150

// slackRigDispatchMetadata is the contract carried in
// view.private_metadata when the slash-command rig branch opens the
// modal. The view_submission handler decodes this strictly: any extra
// field, missing kind, or malformed JSON routes to clear-modal.
//
// Kind is the discriminator — exactly "rig_fix" today. RigName is the
// authoritative routing key (lookups go through rigReg at submission
// time, not the embedded SlingTarget/FixFormula). SlingTarget and
// FixFormula are carried for diagnostics only; the submission handler
// re-resolves them from the registry to defeat metadata staleness if
// the rig was remapped between open and submit.
//
// OriginalCommandText is the slash command's `text` argument verbatim —
// surfaced to the agent (via system-reminder or --var context) so the
// model has the user's original phrasing alongside the modal-captured
// summary.
type slackRigDispatchMetadata struct {
	Kind                string `json:"kind"`
	WorkspaceID         string `json:"workspace_id"`
	RigName             string `json:"rig_name"`
	SlingTarget         string `json:"sling_target"`
	FixFormula          string `json:"fix_formula"`
	ChannelID           string `json:"channel_id"`
	UserID              string `json:"user_id"`
	OriginalCommand     string `json:"original_command"`
	OriginalCommandText string `json:"original_command_text"`
}

// maxRigDispatchMetadataLen caps the encoded private_metadata size.
// Slack lets openers stuff up to 3000 bytes; we cap well below that
// since the embedded ids are short and a runaway value indicates
// either misuse or a hostile opener.
const maxRigDispatchMetadataLen = 2500

// encodeRigDispatchMetadata serializes meta to a compact JSON string
// suitable for view.private_metadata. Returns the encoded length so
// callers can refuse to call views.open with an oversized payload.
func encodeRigDispatchMetadata(meta slackRigDispatchMetadata) (string, error) {
	if meta.Kind == "" {
		meta.Kind = metadataKindRigFix
	}
	b, err := json.Marshal(meta)
	if err != nil {
		return "", fmt.Errorf("encode rig dispatch metadata: %w", err)
	}
	if len(b) > maxRigDispatchMetadataLen {
		return "", fmt.Errorf("rig dispatch metadata exceeds %d bytes (got %d)",
			maxRigDispatchMetadataLen, len(b))
	}
	return string(b), nil
}

// decodeRigDispatchMetadata parses the private_metadata string set by
// the slash-command flow. Strict decode (DisallowUnknownFields)
// prevents app authors from smuggling extra routing knobs the handler
// hasn't sanctioned. Returns (meta, true) only when the kind matches
// metadataKindRigFix — any other shape (legacy session_id, malformed,
// unknown kind) returns (_, false) so the caller falls back to the
// existing routing path.
func decodeRigDispatchMetadata(raw string) (slackRigDispatchMetadata, bool) {
	if strings.TrimSpace(raw) == "" {
		return slackRigDispatchMetadata{}, false
	}
	if len(raw) > maxRigDispatchMetadataLen {
		return slackRigDispatchMetadata{}, false
	}
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.DisallowUnknownFields()
	var meta slackRigDispatchMetadata
	if err := dec.Decode(&meta); err != nil {
		return slackRigDispatchMetadata{}, false
	}
	if meta.Kind != metadataKindRigFix {
		return slackRigDispatchMetadata{}, false
	}
	if meta.RigName == "" || meta.WorkspaceID == "" {
		return slackRigDispatchMetadata{}, false
	}
	return meta, true
}

// slackPlainText is Slack's plain_text composition object. Used for
// titles, button labels, input labels, and placeholders.
type slackPlainText struct {
	Type string `json:"type"` // always "plain_text"
	Text string `json:"text"`
}

// slackModalInput is the Slack `plain_text_input` element. MaxLength
// is omitted from the wire when zero (Slack accepts no cap as the
// absence of the field).
type slackModalInput struct {
	Type        string         `json:"type"` // always "plain_text_input"
	ActionID    string         `json:"action_id"`
	MaxLength   int            `json:"max_length,omitempty"`
	Multiline   bool           `json:"multiline,omitempty"`
	Placeholder slackPlainText `json:"placeholder"`
}

// slackModalBlock is a Slack `input` block holding a label and a single
// element. Optional flag omitted when false (Slack default is required).
type slackModalBlock struct {
	Type     string          `json:"type"` // always "input"
	BlockID  string          `json:"block_id"`
	Optional bool            `json:"optional,omitempty"`
	Label    slackPlainText  `json:"label"`
	Element  slackModalInput `json:"element"`
}

// slackModalView is the typed shape of the Slack `views.open` view
// payload for the rig-fix modal. Replaces the prior `map[string]any`
// per AGENTS.md typed-wire principle.
type slackModalView struct {
	Type            string            `json:"type"` // always "modal"
	CallbackID      string            `json:"callback_id"`
	PrivateMetadata string            `json:"private_metadata"`
	Title           slackPlainText    `json:"title"`
	Submit          slackPlainText    `json:"submit"`
	Close           slackPlainText    `json:"close"`
	Blocks          []slackModalBlock `json:"blocks"`
}

// truncateRunes caps s at maxRunes runes (not bytes). Used for Slack's
// modal-title 24-character limit and similar UI caps where the
// underlying contract is in characters, not bytes. Byte-slicing a
// multibyte UTF-8 codepoint at the boundary produces invalid output.
func truncateRunes(s string, maxRunes int) string {
	rs := []rune(s)
	if len(rs) > maxRunes {
		return string(rs[:maxRunes])
	}
	return s
}

// buildRigFixModalView assembles the Slack views.open `view` payload.
// The block layout is two plain_text_inputs:
//
//  1. summary (single-line, required, max 150 chars) — drives the
//     bead title.
//  2. context_markdown (multi-line, optional) — forwarded to gc sling
//     via --var context_markdown=<value>.
//
// title_text is a short modal header derived from the rig name so the
// user sees which rig will receive the work.
//
// Returns a JSON-encoded view object; callers pass this verbatim to
// the views.open API call.
func buildRigFixModalView(meta slackRigDispatchMetadata, privateMetadata string) ([]byte, error) {
	// Slack caps modal titles at 24 characters. Cap by runes so a
	// multibyte rig name doesn't produce invalid UTF-8 at the boundary.
	titleText := truncateRunes("gc rig: "+meta.RigName, 24)

	view := slackModalView{
		Type:            "modal",
		CallbackID:      rigFixModalCallbackID,
		PrivateMetadata: privateMetadata,
		Title:           slackPlainText{Type: "plain_text", Text: titleText},
		Submit:          slackPlainText{Type: "plain_text", Text: "Dispatch"},
		Close:           slackPlainText{Type: "plain_text", Text: "Cancel"},
		Blocks: []slackModalBlock{
			{
				Type:    "input",
				BlockID: rigFixModalSummaryBlockID,
				Label:   slackPlainText{Type: "plain_text", Text: "Summary"},
				Element: slackModalInput{
					Type:        "plain_text_input",
					ActionID:    rigFixModalSummaryActionID,
					MaxLength:   rigFixModalSummaryMaxLen,
					Placeholder: slackPlainText{Type: "plain_text", Text: "One-line description of the work"},
				},
			},
			{
				Type:     "input",
				BlockID:  rigFixModalContextBlockID,
				Optional: true,
				Label:    slackPlainText{Type: "plain_text", Text: "Context (markdown)"},
				Element: slackModalInput{
					Type:        "plain_text_input",
					ActionID:    rigFixModalContextActionID,
					Multiline:   true,
					Placeholder: slackPlainText{Type: "plain_text", Text: "Optional: links, logs, repro steps"},
				},
			},
		},
	}
	b, err := json.Marshal(view)
	if err != nil {
		return nil, fmt.Errorf("encode rig fix modal view: %w", err)
	}
	return b, nil
}

// slackViewsOpenRequest is the JSON envelope Slack's views.open API
// expects. We keep View as a json.RawMessage so we don't double-marshal.
type slackViewsOpenRequest struct {
	TriggerID string          `json:"trigger_id"`
	View      json.RawMessage `json:"view"`
}

// slackViewsOpenResponse mirrors the shape of the views.open response
// fields the handler reads. Slack returns more fields than this; we
// model only what we need to log+surface.
type slackViewsOpenResponse struct {
	OK    bool   `json:"ok"`
	Error string `json:"error,omitempty"`
}

// viewsOpenTimeout bounds the views.open call. Slack's trigger_id is
// valid for ~3 seconds; we cap below that so a stalled connection
// can't block the slash handler past the trigger-id deadline.
const viewsOpenTimeout = 2500 * time.Millisecond

// viewsOpenMaxResponseBytes caps the response body read so a hostile
// or misconfigured upstream can't bloat handler memory.
const viewsOpenMaxResponseBytes = 1 << 20

// callViewsOpen posts the trigger_id + view JSON to Slack's views.open
// API using the configured bot token. Returns the parsed response or
// an error wrapping any transport / decode failure. A 2xx response
// with `ok:false` becomes a typed error including Slack's error code.
//
// Slack's trigger_id is valid for ~3 seconds — callers must invoke
// this synchronously inside the slash-command HTTP handler to stay
// inside that window. Uses a dedicated client with viewsOpenTimeout
// rather than http.DefaultClient (which has no timeout) so a stalled
// upstream cannot hang the handler past the deadline.
func callViewsOpen(ctx context.Context, token, triggerID string, view []byte) (*slackViewsOpenResponse, error) {
	body, err := json.Marshal(slackViewsOpenRequest{TriggerID: triggerID, View: view})
	if err != nil {
		return nil, fmt.Errorf("encode views.open request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		slackAPIBase+"/views.open", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build views.open request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json; charset=utf-8")

	client := &http.Client{Timeout: viewsOpenTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("POST views.open: %w", err)
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, viewsOpenMaxResponseBytes))
	if err != nil {
		return nil, fmt.Errorf("read views.open response: %w", err)
	}
	var sr slackViewsOpenResponse
	if err := json.Unmarshal(respBody, &sr); err != nil {
		return nil, fmt.Errorf("decode views.open response: %w (body=%s)", err, string(respBody))
	}
	if !sr.OK {
		return &sr, fmt.Errorf("views.open returned ok=false error=%q", sr.Error)
	}
	return &sr, nil
}

// extractModalInput returns the user-supplied value for one
// plain_text_input on a view_submission's view.state.values. Missing
// blocks and missing actions yield "" so optional fields don't error.
func extractModalInput(values map[string]map[string]json.RawMessage, blockID, actionID string) string {
	block, ok := values[blockID]
	if !ok {
		return ""
	}
	raw, ok := block[actionID]
	if !ok {
		return ""
	}
	var elem struct {
		Value string `json:"value"`
	}
	if err := json.Unmarshal(raw, &elem); err != nil {
		return ""
	}
	return elem.Value
}

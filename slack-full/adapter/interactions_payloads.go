package main

import "encoding/json"

// Slack interaction payload types modelled by gc-cby.17.
//
// We model only the fields the handler routes on or forwards into a
// system-reminder. The full Slack schema is intentionally NOT
// reproduced here: Slack adds fields without notice, our wire is a
// natural-language summary not a JSON passthrough, and the agent reads
// the system-reminder and decides — Bitter Lesson + ZFC. Anything not
// captured below is silently ignored.
//
// Wire references (Slack docs, May 2026):
//   - block_actions:    https://api.slack.com/reference/interaction-payloads/block-actions
//   - view_submission:  https://api.slack.com/reference/interaction-payloads/views

// slackInteractionPayload is a union over block_actions and
// view_submission. Type drives the branch in handleSlackInteractions;
// fields not relevant to a given type stay zero-valued.
type slackInteractionPayload struct {
	Type        string                    `json:"type"`
	Team        slackInteractionTeam      `json:"team"`
	User        slackInteractionUser      `json:"user"`
	TriggerID   string                    `json:"trigger_id"`
	ResponseURL string                    `json:"response_url"`
	Channel     slackInteractionChannel   `json:"channel"`
	Container   slackInteractionContainer `json:"container"`
	Actions     []slackInteractionAction  `json:"actions"`
	View        slackInteractionView      `json:"view"`
}

type slackInteractionTeam struct {
	ID string `json:"id"`
}

type slackInteractionUser struct {
	ID string `json:"id"`
}

type slackInteractionChannel struct {
	ID string `json:"id"`
}

// slackInteractionContainer mirrors Slack's `container` envelope on
// block_actions. ChannelID is the fallback when the top-level
// `channel` object is omitted (common for actions originating from
// shared/forwarded message reposts).
type slackInteractionContainer struct {
	ChannelID string `json:"channel_id"`
}

// slackInteractionAction is one entry in the block_actions actions[].
// Slack typically sends length 1 but multi_*_select finalizations can
// produce multiple entries with the same action_id.
type slackInteractionAction struct {
	ActionID       string                       `json:"action_id"`
	BlockID        string                       `json:"block_id"`
	Type           string                       `json:"type"`
	Value          string                       `json:"value"`
	SelectedOption *slackInteractionSelectedOpt `json:"selected_option,omitempty"`
	SelectedDate   string                       `json:"selected_date,omitempty"`
}

type slackInteractionSelectedOpt struct {
	Value string `json:"value"`
}

// slackInteractionView is the modal envelope on view_submission. The
// state.values shape is `{block_id: {action_id: <input value object>}}`;
// we keep it as raw JSON because the agent reads it as documentation,
// not as routing keys.
type slackInteractionView struct {
	ID              string                    `json:"id"`
	CallbackID      string                    `json:"callback_id"`
	PrivateMetadata string                    `json:"private_metadata"`
	State           slackInteractionViewState `json:"state"`
}

type slackInteractionViewState struct {
	Values map[string]map[string]json.RawMessage `json:"values"`
}

// slackPrivateMetadata is the contract gc-cby.17 imposes on modal
// openers: view.private_metadata MUST be a JSON string of this shape.
// Any other shape (missing, malformed, extra fields, oversized
// session_id) routes to {"response_action":"clear"} so the modal
// closes and the user sees the submission did not process.
type slackPrivateMetadata struct {
	SessionID string `json:"session_id"`
}

// maxPrivateMetadataSessionIDLen caps the session_id supplied via
// view.private_metadata. Slack lets openers stuff up to 3000 bytes
// into private_metadata — we cap well below that since session IDs
// in this codebase are short hashes (e.g. "gc-2568") and any
// runaway-length value is either a misuse or hostile.
const maxPrivateMetadataSessionIDLen = 200

const (
	interactionTypeBlockActions   = "block_actions"
	interactionTypeViewSubmission = "view_submission"
)

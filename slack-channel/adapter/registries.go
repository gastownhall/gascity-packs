package main

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// --- channel bindings -----------------------------------------------------

// channelBinding is one record in channel_mappings.json. It binds a Slack
// channel (or DM) to one or more gc sessions. A non-mention message
// arriving in a bound channel is delivered to every listed session. The
// JSON object key is the composite "<workspace_id>:<channel_id>".
type channelBinding struct {
	WorkspaceID string   `json:"workspace_id"`
	ChannelID   string   `json:"channel_id"`
	Kind        string   `json:"kind"`
	SessionIDs  []string `json:"session_ids"`
	CreatedAt   string   `json:"created_at"`
	UpdatedAt   string   `json:"updated_at"`
}

// identity is one record in identities.json. It overrides the visible
// username/avatar a session posts under (Slack chat:write.customize). The
// JSON object key is the session id.
type identity struct {
	SessionID string `json:"session_id"`
	Username  string `json:"username,omitempty"`
	IconURL   string `json:"icon_url,omitempty"`
	IconEmoji string `json:"icon_emoji,omitempty"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
}

// handleAlias is one record in handle_aliases.json. It maps an
// address-by-handle token ("@mayor:") to a session so a human can address
// that session from any channel, regardless of channel binding. The JSON
// object key is the handle. Single-workspace at Tier 2 — aliases are not
// scoped per workspace.
type handleAlias struct {
	Handle    string `json:"handle"`
	SessionID string `json:"session_id"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
}

// bindingKey builds the composite primary key for a channel binding.
func bindingKey(workspaceID, channelID string) string {
	return workspaceID + ":" + channelID
}

var (
	validKinds  = map[string]bool{"dm": true, "room": true}
	handleRE    = regexp.MustCompile(`^[a-z0-9_-]+$`)
	sessionIDRE = regexp.MustCompile(`^[^\s]+$`) // any non-empty, whitespace-free token
)

// sortedDedupSessions returns the input session ids trimmed, with empties
// and duplicates removed, in sorted order. Sorting makes the on-disk
// representation stable so idempotent re-binds produce no diff.
func sortedDedupSessions(in []string) []string {
	seen := make(map[string]bool, len(in))
	out := make([]string, 0, len(in))
	for _, s := range in {
		s = strings.TrimSpace(s)
		if s == "" || seen[s] {
			continue
		}
		seen[s] = true
		out = append(out, s)
	}
	sort.Strings(out)
	return out
}

// validateBinding checks a channel binding request. It returns the
// cleaned session-id slice on success.
func validateBinding(workspaceID, channelID, kind string, sessionIDs []string) ([]string, error) {
	if strings.TrimSpace(workspaceID) == "" {
		return nil, fmt.Errorf("workspace_id is required")
	}
	if strings.TrimSpace(channelID) == "" {
		return nil, fmt.Errorf("channel_id is required")
	}
	if !validKinds[kind] {
		return nil, fmt.Errorf("kind must be one of dm, room (got %q)", kind)
	}
	cleaned := sortedDedupSessions(sessionIDs)
	if len(cleaned) == 0 {
		return nil, fmt.Errorf("at least one session_id is required")
	}
	for _, s := range cleaned {
		if !sessionIDRE.MatchString(s) {
			return nil, fmt.Errorf("session_id must not contain whitespace: %q", s)
		}
	}
	return cleaned, nil
}

// validateIdentity checks an identity override request. icon_url and
// icon_emoji are mutually exclusive, and at least one identity field must
// be present (an all-empty identity is meaningless).
func validateIdentity(sessionID, username, iconURL, iconEmoji string) error {
	if strings.TrimSpace(sessionID) == "" {
		return fmt.Errorf("session_id is required")
	}
	if iconURL != "" && iconEmoji != "" {
		return fmt.Errorf("icon_url and icon_emoji are mutually exclusive")
	}
	if username == "" && iconURL == "" && iconEmoji == "" {
		return fmt.Errorf("at least one of username, icon_url, icon_emoji is required")
	}
	return nil
}

// normalizeHandle lowercases and strips a leading '@' from a handle.
func normalizeHandle(handle string) string {
	return strings.ToLower(strings.TrimPrefix(strings.TrimSpace(handle), "@"))
}

// validateHandle checks a handle-alias request and returns the normalized
// handle.
func validateHandle(handle, sessionID string) (string, error) {
	h := normalizeHandle(handle)
	if h == "" {
		return "", fmt.Errorf("handle is required")
	}
	if !handleRE.MatchString(h) {
		return "", fmt.Errorf("handle must match [a-z0-9_-]+ (got %q)", h)
	}
	if !sessionIDRE.MatchString(strings.TrimSpace(sessionID)) {
		return "", fmt.Errorf("session_id is required and must not contain whitespace")
	}
	return h, nil
}

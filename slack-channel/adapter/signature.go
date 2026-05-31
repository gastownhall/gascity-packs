package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// verifySlackSignature validates Slack's v0 HMAC request signature and
// rejects timestamps whose absolute age exceeds the replay window — both
// stale (past) and far-future. Fails closed on any missing field or parse
// error.
func verifySlackSignature(secret, ts string, body []byte, sig string) bool {
	if secret == "" || ts == "" || sig == "" {
		return false
	}
	tsInt, err := strconv.ParseInt(ts, 10, 64)
	if err != nil {
		return false
	}
	// Reject when the absolute age exceeds the replay window — both stale
	// (past) and far-future timestamps. time.Since yields a negative
	// duration for future timestamps, so a one-sided ">" check would
	// silently accept them.
	age := time.Since(time.Unix(tsInt, 0))
	if age < 0 {
		age = -age
	}
	if age > slackReplayWindow {
		return false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte("v0:" + ts + ":"))
	_, _ = mac.Write(body)
	expected := "v0=" + hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(sig))
}

// leadingMentionRE matches one or more leading Slack user-mention tokens
// (`<@U…>`) and surrounding whitespace. Slack delivers app_mention text
// with the bot mention inline (e.g. "<@U0BOT> status?"); stripping it
// yields the human-meant message body.
var leadingMentionRE = regexp.MustCompile(`^\s*(?:<@[A-Z0-9]+>\s*)+`)

func stripLeadingMention(text string) string {
	return strings.TrimSpace(leadingMentionRE.ReplaceAllString(text, ""))
}

// slackKindFromChannelType maps a Slack channel_type onto a gc
// ConversationKind, falling back to the channel-id prefix.
func slackKindFromChannelType(channelType, channelID string) string {
	switch channelType {
	case "channel", "group", "mpim":
		return "room"
	case "im":
		return "dm"
	}
	if len(channelID) > 0 {
		switch channelID[0] {
		case 'C', 'G':
			return "room"
		case 'D':
			return "dm"
		}
	}
	return "dm"
}

// handleAliasRE matches a leading address-by-handle token: "@<handle>"
// optionally followed by a colon, then the rest of the message. Handles
// are lowercase letters, digits, '_' and '-'. The capture groups are the
// handle and the remaining text. Mirrors the alias syntax documented for
// `gc slack-channel handle-alias`.
var handleAliasRE = regexp.MustCompile(`^@([a-z0-9_-]+):?\s*(.*)$`)

// parseLeadingHandle extracts a leading "@handle[:]" address token. It
// returns the lowercased handle and the remaining message text, or
// ("", text) when the text does not begin with a handle token.
func parseLeadingHandle(text string) (handle, rest string) {
	m := handleAliasRE.FindStringSubmatch(strings.TrimSpace(text))
	if m == nil {
		return "", text
	}
	return m[1], strings.TrimSpace(m[2])
}

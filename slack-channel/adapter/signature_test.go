package main

import (
	"strconv"
	"testing"
	"time"
)

func TestVerifySlackSignature(t *testing.T) {
	const secret = "shhh"
	body := []byte(`{"type":"event_callback"}`)
	now := strconv.FormatInt(time.Now().Unix(), 10)
	stale := strconv.FormatInt(time.Now().Add(-10*time.Minute).Unix(), 10)
	future := strconv.FormatInt(time.Now().Add(10*time.Minute).Unix(), 10)
	valid := signSlack(secret, now, body)

	tests := []struct {
		name   string
		secret string
		ts     string
		sig    string
		want   bool
	}{
		{"valid", secret, now, valid, true},
		{"wrong secret", "nope", now, valid, false},
		{"tampered body sig", secret, now, signSlack(secret, now, []byte("other")), false},
		{"stale timestamp", secret, stale, signSlack(secret, stale, body), false},
		{"far-future timestamp", secret, future, signSlack(secret, future, body), false},
		{"non-numeric timestamp", secret, "abc", valid, false},
		{"empty secret", "", now, valid, false},
		{"empty ts", secret, "", valid, false},
		{"empty sig", secret, now, "", false},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if got := verifySlackSignature(tc.secret, tc.ts, body, tc.sig); got != tc.want {
				t.Fatalf("verifySlackSignature = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestStripLeadingMention(t *testing.T) {
	tests := []struct{ in, want string }{
		{"<@U0BOT> status please", "status please"},
		{"  <@U0BOT>   hello", "hello"},
		{"<@U0BOT> <@U1OPS> deploy", "deploy"},
		{"no mention here", "no mention here"},
		{"<@U0BOT>", ""},
		{"   ", ""},
		{"text then <@U0BOT>", "text then <@U0BOT>"},
	}
	for _, tc := range tests {
		if got := stripLeadingMention(tc.in); got != tc.want {
			t.Errorf("stripLeadingMention(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestSlackKindFromChannelType(t *testing.T) {
	tests := []struct{ ctype, cid, want string }{
		{"channel", "C123", "room"},
		{"group", "G123", "room"},
		{"mpim", "C123", "room"},
		{"im", "D123", "dm"},
		{"", "C123", "room"},
		{"", "G123", "room"},
		{"", "D123", "dm"},
		{"", "", "dm"},
	}
	for _, tc := range tests {
		if got := slackKindFromChannelType(tc.ctype, tc.cid); got != tc.want {
			t.Errorf("slackKindFromChannelType(%q,%q) = %q, want %q", tc.ctype, tc.cid, got, tc.want)
		}
	}
}

func TestParseLeadingHandle(t *testing.T) {
	tests := []struct {
		in         string
		wantHandle string
		wantRest   string
	}{
		{"@mayor: deploy now", "mayor", "deploy now"},
		{"@cos ship it", "cos", "ship it"},
		{"@build-bot:status", "build-bot", "status"},
		{"no handle here", "", "no handle here"},
		{"email me a@b.com", "", "email me a@b.com"},
		{"@MixedCase: hi", "", "@MixedCase: hi"}, // uppercase not a valid handle char
		{"@mayor:", "mayor", ""},
	}
	for _, tc := range tests {
		h, rest := parseLeadingHandle(tc.in)
		if h != tc.wantHandle || rest != tc.wantRest {
			t.Errorf("parseLeadingHandle(%q) = (%q,%q), want (%q,%q)", tc.in, h, rest, tc.wantHandle, tc.wantRest)
		}
	}
}

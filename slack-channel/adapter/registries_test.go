package main

import (
	"reflect"
	"strings"
	"testing"
)

func TestSortedDedupSessions(t *testing.T) {
	got := sortedDedupSessions([]string{" s2 ", "s1", "s2", "", "  ", "s1"})
	want := []string{"s1", "s2"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("sortedDedupSessions = %v, want %v", got, want)
	}
}

func TestValidateBinding(t *testing.T) {
	t.Run("ok", func(t *testing.T) {
		got, err := validateBinding("T1", "C1", "room", []string{"b", "a", "a"})
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !reflect.DeepEqual(got, []string{"a", "b"}) {
			t.Errorf("cleaned = %v", got)
		}
	})
	bad := []struct {
		name          string
		ws, ch, kind  string
		sessions      []string
		wantErrSubstr string
	}{
		{"no workspace", "", "C1", "room", []string{"a"}, "workspace_id"},
		{"no channel", "T1", "", "room", []string{"a"}, "channel_id"},
		{"bad kind", "T1", "C1", "thread", []string{"a"}, "kind must be"},
		{"no sessions", "T1", "C1", "room", []string{"", "  "}, "at least one session_id"},
		{"whitespace session", "T1", "C1", "room", []string{"a b"}, "must not contain whitespace"},
	}
	for _, tc := range bad {
		t.Run(tc.name, func(t *testing.T) {
			_, err := validateBinding(tc.ws, tc.ch, tc.kind, tc.sessions)
			if err == nil || !strings.Contains(err.Error(), tc.wantErrSubstr) {
				t.Fatalf("err = %v, want substring %q", err, tc.wantErrSubstr)
			}
		})
	}
}

func TestValidateIdentity(t *testing.T) {
	if err := validateIdentity("s1", "PL", "", ""); err != nil {
		t.Errorf("username-only should be valid: %v", err)
	}
	if err := validateIdentity("s1", "", "https://x/y.png", ""); err != nil {
		t.Errorf("icon_url-only should be valid: %v", err)
	}
	cases := []struct {
		name                                  string
		session, username, iconURL, iconEmoji string
		want                                  string
	}{
		{"no session", "", "PL", "", "", "session_id"},
		{"both icons", "s1", "", "u", "e", "mutually exclusive"},
		{"all empty", "s1", "", "", "", "at least one"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			err := validateIdentity(tc.session, tc.username, tc.iconURL, tc.iconEmoji)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("err = %v, want %q", err, tc.want)
			}
		})
	}
}

func TestValidateHandle(t *testing.T) {
	h, err := validateHandle("@Mayor", "s1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if h != "mayor" {
		t.Errorf("normalized handle = %q, want mayor", h)
	}
	if _, err := validateHandle("bad handle", "s1"); err == nil {
		t.Error("expected error for handle with space")
	}
	if _, err := validateHandle("mayor", "  "); err == nil {
		t.Error("expected error for empty session")
	}
	if _, err := validateHandle("@", "s1"); err == nil {
		t.Error("expected error for bare @")
	}
}

func TestNormalizeHandle(t *testing.T) {
	tests := map[string]string{
		"@Mayor": "mayor",
		" COS ":  "cos",
		"build":  "build",
	}
	for in, want := range tests {
		if got := normalizeHandle(in); got != want {
			t.Errorf("normalizeHandle(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestBindingKey(t *testing.T) {
	if got := bindingKey("T1", "C9"); got != "T1:C9" {
		t.Errorf("bindingKey = %q", got)
	}
}

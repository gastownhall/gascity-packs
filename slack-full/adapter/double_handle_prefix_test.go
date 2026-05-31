package main

import "testing"

// TestParseDoubleHandlePrefix exercises the launcher-mode address parser
// added in cby.5.2. Distinct from parseHandlePrefix (single-`@`),
// parseDoubleHandlePrefix matches ONLY when the prefix appears doubled
// at the start of the trimmed text (e.g. "@@new ..."). Single-prefix
// strings ("@new ...") and triple-prefix strings ("@@@x") MUST NOT
// match — the first because that is the existing alias-dispatch path,
// the second because a "@@@" head is almost certainly a Slack escape
// or typo, not an address token. Mirroring parseHandlePrefix exactly
// here would couple the two parsers; we instead spell out the doubled
// shape and reject anything richer.
func TestParseDoubleHandlePrefix(t *testing.T) {
	cases := []struct {
		name          string
		text          string
		prefix        string
		wantHandle    string
		wantRemainder string
		wantOK        bool
	}{
		{
			name:          "doubled prefix with space remainder",
			text:          "@@new please ack",
			prefix:        "@",
			wantHandle:    "new",
			wantRemainder: "please ack",
			wantOK:        true,
		},
		{
			name:          "doubled prefix with colon-space remainder",
			text:          "@@ops: status?",
			prefix:        "@",
			wantHandle:    "ops",
			wantRemainder: "status?",
			wantOK:        true,
		},
		{
			name:          "doubled prefix with colon-no-space remainder",
			text:          "@@ops:hello",
			prefix:        "@",
			wantHandle:    "ops",
			wantRemainder: "hello",
			wantOK:        true,
		},
		{
			name:          "doubled prefix no remainder",
			text:          "@@new",
			prefix:        "@",
			wantHandle:    "new",
			wantRemainder: "",
			wantOK:        true,
		},
		{
			name:          "leading whitespace permitted",
			text:          "  @@lead hi",
			prefix:        "@",
			wantHandle:    "lead",
			wantRemainder: "hi",
			wantOK:        true,
		},
		{
			name:          "single prefix does not match",
			text:          "@new please ack",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "triple prefix is rejected (not a doubled head)",
			text:          "@@@triple",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "doubled prefix with empty handle",
			text:          "@@",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "doubled prefix with only colon",
			text:          "@@: foo",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "doubled prefix not at start",
			text:          "hello @@new x",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "plain text",
			text:          "plain text",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty prefix returns false",
			text:          "@@new x",
			prefix:        "",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "invalid char immediately after handle is rejected",
			text:          "@@bad/handle x",
			prefix:        "@",
			wantHandle:    "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "underscore and digits permitted in handle",
			text:          "@@team_42 hello",
			prefix:        "@",
			wantHandle:    "team_42",
			wantRemainder: "hello",
			wantOK:        true,
		},
		{
			name:          "hyphen permitted in handle",
			text:          "@@launcher-001 ping",
			prefix:        "@",
			wantHandle:    "launcher-001",
			wantRemainder: "ping",
			wantOK:        true,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			gotHandle, gotRem, gotOK := parseDoubleHandlePrefix(tc.text, tc.prefix)
			if gotHandle != tc.wantHandle || gotRem != tc.wantRemainder || gotOK != tc.wantOK {
				t.Errorf("parseDoubleHandlePrefix(%q, %q) = (%q, %q, %v); want (%q, %q, %v)",
					tc.text, tc.prefix, gotHandle, gotRem, gotOK,
					tc.wantHandle, tc.wantRemainder, tc.wantOK)
			}
		})
	}
}

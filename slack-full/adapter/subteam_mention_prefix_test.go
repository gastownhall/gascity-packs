package main

import "testing"

// TestParseSubteamMentionPrefix exercises the Slack User Group ("subteam")
// mention parser. The parser must recognize BOTH token shapes Slack
// emits:
//
//	Labeled:    <!subteam^TEAMID|@handle>
//	Unlabeled:  <!subteam^TEAMID>
//
// The labeled form yields a non-empty handle (the gc address-by-handle
// dispatcher matches by handle against the runtime aliasReg). The
// unlabeled form yields an empty handle but a non-empty subteam ID
// (the dispatcher matches by subteam ID against the operator-edited
// subteamAliasMap). In both shapes the trailing remainder has any
// leading `:` and a single leading whitespace byte trimmed, mirroring
// parseHandlePrefix's separator rules.
func TestParseSubteamMentionPrefix(t *testing.T) {
	cases := []struct {
		name          string
		text          string
		wantHandle    string
		wantSubteamID string
		wantRemainder string
		wantOK        bool
	}{
		// --- labeled form (gpk-2zi shape, unchanged behavior) -----------
		{
			name:          "labeled token with space remainder",
			text:          "<!subteam^S012|@mayor> please ack",
			wantHandle:    "mayor",
			wantSubteamID: "S012",
			wantRemainder: "please ack",
			wantOK:        true,
		},
		{
			name:          "labeled token with colon-space remainder",
			text:          "<!subteam^S012|@mayor>: status?",
			wantHandle:    "mayor",
			wantSubteamID: "S012",
			wantRemainder: "status?",
			wantOK:        true,
		},
		{
			name:          "labeled token with colon-no-space remainder",
			text:          "<!subteam^S012|@cos>:hello",
			wantHandle:    "cos",
			wantSubteamID: "S012",
			wantRemainder: "hello",
			wantOK:        true,
		},
		{
			name:          "labeled token no remainder",
			text:          "<!subteam^S012|@mayor>",
			wantHandle:    "mayor",
			wantSubteamID: "S012",
			wantRemainder: "",
			wantOK:        true,
		},
		{
			name:          "leading whitespace permitted (labeled)",
			text:          "  <!subteam^S012|@lead> hi",
			wantHandle:    "lead",
			wantSubteamID: "S012",
			wantRemainder: "hi",
			wantOK:        true,
		},
		{
			name:          "label with dash",
			text:          "<!subteam^S012|@gc-pl> x",
			wantHandle:    "gc-pl",
			wantSubteamID: "S012",
			wantRemainder: "x",
			wantOK:        true,
		},
		{
			name:          "label with underscore",
			text:          "<!subteam^S012|@probe_pl> x",
			wantHandle:    "probe_pl",
			wantSubteamID: "S012",
			wantRemainder: "x",
			wantOK:        true,
		},
		{
			name:          "newline separator after closer (labeled)",
			text:          "<!subteam^S012|@mayor>\nfoo",
			wantHandle:    "mayor",
			wantSubteamID: "S012",
			wantRemainder: "foo",
			wantOK:        true,
		},
		{
			name:          "tab separator after closer (labeled)",
			text:          "<!subteam^S012|@mayor>\tfoo",
			wantHandle:    "mayor",
			wantSubteamID: "S012",
			wantRemainder: "foo",
			wantOK:        true,
		},
		{
			name:          "TEAMID with non-alphanumeric characters tolerated",
			text:          "<!subteam^S-abc.123|@mayor> ok",
			wantHandle:    "mayor",
			wantSubteamID: "S-abc.123",
			wantRemainder: "ok",
			wantOK:        true,
		},

		// --- unlabeled form (gpk-hmr.2 new behavior) -------------------
		{
			name:          "unlabeled token with space remainder",
			text:          "<!subteam^S0B4MUNDZCH> please ack",
			wantHandle:    "",
			wantSubteamID: "S0B4MUNDZCH",
			wantRemainder: "please ack",
			wantOK:        true,
		},
		{
			name:          "unlabeled token with colon-space remainder",
			text:          "<!subteam^S0B4MUNDZCH>: status?",
			wantHandle:    "",
			wantSubteamID: "S0B4MUNDZCH",
			wantRemainder: "status?",
			wantOK:        true,
		},
		{
			name:          "unlabeled token with colon-no-space remainder",
			text:          "<!subteam^S0123ABCD>:hello",
			wantHandle:    "",
			wantSubteamID: "S0123ABCD",
			wantRemainder: "hello",
			wantOK:        true,
		},
		{
			name:          "unlabeled token no remainder",
			text:          "<!subteam^S0123ABCD>",
			wantHandle:    "",
			wantSubteamID: "S0123ABCD",
			wantRemainder: "",
			wantOK:        true,
		},
		{
			name:          "leading whitespace permitted (unlabeled)",
			text:          "  <!subteam^S0123ABCD> hi",
			wantHandle:    "",
			wantSubteamID: "S0123ABCD",
			wantRemainder: "hi",
			wantOK:        true,
		},
		{
			name:          "newline separator after closer (unlabeled)",
			text:          "<!subteam^S0123ABCD>\nfoo",
			wantHandle:    "",
			wantSubteamID: "S0123ABCD",
			wantRemainder: "foo",
			wantOK:        true,
		},

		// --- labeled form without `@` (gpk-ee3 new behavior) -----------
		// Slack omits the `@` in the label when a human types a User
		// Group mention (e.g. `@zelda-pl` expands to `<!subteam^Sxxx|zelda-pl>`).
		// The label is treated as the handle, identical to the `@`-form.
		{
			name:          "label without leading at sign accepted",
			text:          "<!subteam^S012|mayor> hi",
			wantHandle:    "mayor",
			wantSubteamID: "S012",
			wantRemainder: "hi",
			wantOK:        true,
		},
		{
			name:          "label without at sign, dash handle, no remainder",
			text:          "<!subteam^S0XXX|zelda-pl>",
			wantHandle:    "zelda-pl",
			wantSubteamID: "S0XXX",
			wantRemainder: "",
			wantOK:        true,
		},
		{
			name:          "label without at sign, colon-space remainder",
			text:          "<!subteam^S0XXX|zelda-pl>: deploy now",
			wantHandle:    "zelda-pl",
			wantSubteamID: "S0XXX",
			wantRemainder: "deploy now",
			wantOK:        true,
		},
		{
			name:          "label without at sign, invalid char rejected",
			text:          "<!subteam^S0XXX|foo bar> hi",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},

		// --- rejected shapes -------------------------------------------
		{
			name:          "empty label (bare pipe) rejected",
			text:          "<!subteam^S012|> hi",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty label in labeled form rejected",
			text:          "<!subteam^S012|@> hi",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "label with invalid char rejected",
			text:          "<!subteam^S012|@bad.handle> hi",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "label with slash rejected",
			text:          "<!subteam^S012|@bad/handle> hi",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "missing closer rejected",
			text:          "<!subteam^S012|@mayor please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty subteam ID labeled rejected",
			text:          "<!subteam^|@mayor> please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty subteam ID unlabeled rejected",
			text:          "<!subteam^> please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "user mention (not subteam) does not match",
			text:          "<@U0123|mayor> please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "channel mention (not subteam) does not match",
			text:          "<#C0123|general> please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "token not at start does not match",
			text:          "hello <!subteam^S012|@mayor> please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "plain text does not match",
			text:          "plain text with no token",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "empty input does not match",
			text:          "",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
		{
			name:          "single-at prefix (not a subteam token) does not match",
			text:          "@mayor please ack",
			wantHandle:    "",
			wantSubteamID: "",
			wantRemainder: "",
			wantOK:        false,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			gotHandle, gotSubteamID, gotRemainder, gotOK := parseSubteamMentionPrefix(tc.text)
			if gotOK != tc.wantOK {
				t.Errorf("ok = %v, want %v", gotOK, tc.wantOK)
			}
			if gotHandle != tc.wantHandle {
				t.Errorf("handle = %q, want %q", gotHandle, tc.wantHandle)
			}
			if gotSubteamID != tc.wantSubteamID {
				t.Errorf("subteamID = %q, want %q", gotSubteamID, tc.wantSubteamID)
			}
			if gotRemainder != tc.wantRemainder {
				t.Errorf("remainder = %q, want %q", gotRemainder, tc.wantRemainder)
			}
		})
	}
}

package main

import (
	"net/url"
	"testing"
)

// TestReadBackPublishedMessageAcceptsSlackEmojiConversion pins the gf-4c9
// round-2 gate finding at publish_readback.go:298 (gf-jr0 finding 3c): an
// unkeyed publish is confirmed by a text compare folded through
// slackNormalizeText, and that fold knew Slack's entity escaping and URL
// auto-linking but not its documented Unicode-to-colon emoji conversion
// (https://docs.slack.dev/messaging/formatting-message-text/#emoji), so
// "Done 🎉" read back as "Done :tada:" and a delivered message was reported
// a permanent failure. publish-to-channel takes the unkeyed path by default,
// so this was the founder-facing publish path. The fold now treats emoji —
// Unicode or shortcode, with skin tones, keycaps, flags and ZWJ sequences —
// as the same lossy class as escaping: equal on both sides, never a reason
// to refuse; text that differs beyond the emoji is still refused.
//
// Round 3 (gf-pu2 finding 3d; the gf-jr0 vs-main gate's Major at :185 and
// the packs Fable read's reproduction): the shortcode fold required a
// non-alphanumeric boundary while the Unicode fold was unconditional, so an
// emoji glued to a word ("Done🎉", stored as "Done:tada:") still read back as
// a permanent failure and the caller re-posted. A shortcode now folds by its
// NAME alone — a Slack standard emoji name, from the bundled table — wherever
// it stands; a shortcode-shaped token Slack has no emoji for stays in the
// compare glued or not, and a URI of any scheme is compared as typed.
func TestReadBackPublishedMessageAcceptsSlackEmojiConversion(t *testing.T) {
	tests := []struct {
		name    string
		posted  string
		stored  string
		wantErr bool
	}{
		{name: "party popper to :tada:", posted: "Done 🎉", stored: "Done :tada:"},
		{name: "thumbs up with a skin tone", posted: "Deploy 👍🏽 ok", stored: "Deploy :+1::skin-tone-4: ok"},
		{name: "keycap digit", posted: "Step 1️⃣ done", stored: "Step :one: done"},
		{name: "flag (regional indicators)", posted: "Region 🇺🇸 up", stored: "Region :us: up"},
		{name: "ZWJ family sequence", posted: "Team 👨‍👩‍👧 ship", stored: "Team :man-woman-girl: ship"},
		{name: "emoji beside an escaped entity", posted: "R&D ✅ merged <ok>", stored: "R&amp;D :white_check_mark: merged &lt;ok&gt;"},
		{name: "shortcode posted, shortcode stored", posted: "Done :tada:", stored: "Done :tada:"},
		{name: "verbatim Unicode echo", posted: "Done 🎉", stored: "Done 🎉"},
		{name: "colon-delimited time beside an emoji", posted: "Deploy at 12:30:45 ✅", stored: "Deploy at 12:30:45 :white_check_mark:"},
		{name: "adjacent shortcode runs", posted: "a 🎉 ✅ b", stored: "a :tada: :white_check_mark: b"},
		{name: "a changed timestamp is not an emoji", posted: "Deploy at 12:30:45", stored: "Deploy at 12:59:45", wantErr: true},
		{name: "a keyboard symbol is not an emoji", posted: "Press ⌘Q", stored: "Press Q", wantErr: true},
		{name: "a code namespace is not a shortcode run", posted: "Use std::vector::iterator", stored: "Use std::map::iterator", wantErr: true},
		{name: "a slice expression is not a shortcode", posted: "items[:2:]", stored: "items[:4:]", wantErr: true},
		{name: "digit-only shortcodes Slack has", posted: "💯 👍", stored: ":100: :+1:"},
		{name: "a code namespace beside an emoji", posted: "Use std::vector::iterator ✅", stored: "Use std::vector::iterator :white_check_mark:"},
		{name: "music accidentals are not emoji", posted: "Play C♯", stored: "Play C♭", wantErr: true},
		{name: "a joiner in Devanagari is text", posted: "क्\u200dष", stored: "क्ष", wantErr: true},
		{name: "a joiner in Devanagari beside an emoji", posted: "क्\u200dष ✅", stored: "क्\u200dष :white_check_mark:"},
		{name: "a text-style variation selector on a letter is text", posted: "a\ufe0e b", stored: "a b", wantErr: true},
		{name: "a music note beside an emoji", posted: "♪ shipped 🎉", stored: "♪ shipped :tada:"},
		{name: "box drawing is not an emoji", posted: "┌─┐ frame", stored: " frame", wantErr: true},
		{name: "Braille is not an emoji", posted: "Braille ⠁⠃", stored: "Braille ", wantErr: true},
		{name: "a keyboard symbol beside an emoji", posted: "Press ⌘Q ✅", stored: "Press ⌘Q :white_check_mark:"},
		{name: "a changed ratio is not an emoji", posted: "Ratio 1:2:3", stored: "Ratio 1:4:3", wantErr: true},
		{name: "different text beyond the emoji", posted: "Done 🎉", stored: "Done :tada: and more", wantErr: true},
		{name: "truncated body", posted: "Done 🎉 see the thread", stored: "Done :tada:", wantErr: true},
		{name: "a named slice bound inside a code span is code", posted: "Use `items[:start:]`", stored: "Use `items[:end:]`", wantErr: true},
		{name: "a numeric slice bound that is an emoji name inside a code span is code", posted: "Use `items[:100:]`", stored: "Use `items[]`", wantErr: true},
		{name: "a shortcode inside a code block is text", posted: "```\nx[:tada:]\n```", stored: "```\nx[]\n```", wantErr: true},
		{name: "a code span beside an emoji", posted: "Run `items[:start:]` ✅", stored: "Run `items[:start:]` :white_check_mark:"},
		{name: "a shortcode inside a code span stays literal on both sides", posted: "Type `:tada:` to cheer", stored: "Type `:tada:` to cheer"},
		{name: "an unclosed backtick is not a code span", posted: "a ` 🎉", stored: "a ` :tada:"},
		{name: "a colon-delimited path segment of a bare URL is text", posted: "See https://example.com/:customer_id:/orders", stored: "See https://example.com//orders", wantErr: true},
		{name: "a changed URL segment that reads like a shortcode", posted: "See https://example.com/:customer_id:/orders", stored: "See https://example.com/:order_id:/orders", wantErr: true},
		{name: "a bare URL beside an emoji", posted: "See https://example.com/:customer_id:/orders 🎉", stored: "See https://example.com/:customer_id:/orders :tada:"},
		{name: "an auto-linked URL beside an emoji", posted: "See https://example.com/:customer_id:/orders 🎉", stored: "See <https://example.com/:customer_id:/orders> :tada:"},
		// Round 3: an emoji glued to a word folds on both sides.
		{name: "an emoji glued to the word before it", posted: "Done🎉", stored: "Done:tada:"},
		{name: "a thumbs up glued to a word", posted: "LGTM👍", stored: "LGTM:+1:"},
		{name: "a rocket glued to a version", posted: "v2🚀 shipped", stored: "v2:rocket: shipped"},
		{name: "an emoji glued to the word after it", posted: "🎉Done", stored: ":tada:Done"},
		{name: "a skin-toned emoji glued to a word", posted: "ship👍🏽now", stored: "ship:+1::skin-tone-4:now"},
		{name: "glued emoji with different text beyond it", posted: "Done🎉", stored: "Done:tada: more", wantErr: true},
		// Round 3: a shortcode-shaped token Slack has no emoji for is text, glued or not.
		{name: "a named slice bound in prose is text", posted: "items[:start_index:]", stored: "items[:end_index:]", wantErr: true},
		{name: "a dropped named slice bound in prose is refused", posted: "items[:start_index:]", stored: "items[]", wantErr: true},
		{name: "a colon-delimited word run is text", posted: "key:value:other", stored: "key:other:other", wantErr: true},
		{name: "a standalone unknown shortcode stays literal on both sides", posted: "ping :not_an_emoji_name: ok", stored: "ping :not_an_emoji_name: ok"},
		// Round 3: a URI of any scheme is compared as typed, even when a segment is an emoji name.
		{name: "an s3 path segment that is an emoji name is text", posted: "see s3://bucket/:id:/x", stored: "see s3://bucket//x", wantErr: true},
		{name: "a changed s3 path segment is refused", posted: "see s3://bucket/:id:/x", stored: "see s3://bucket/:ok:/x", wantErr: true},
		{name: "an s3 URI beside an emoji", posted: "see s3://bucket/:id:/x 🎉", stored: "see s3://bucket/:id:/x :tada:"},
		// Round 4 (gf-xid; the lane's codex rounds 3 and 4 on the Opus read's
		// minor): the shortcode scan stays non-overlapping, left to right. A
		// chain of colon-joined words around an emoji is ambiguous in BOTH
		// orientations — the stored `key:value:ok:white_check_mark:` (posted
		// `key:value:ok✅`) and the stored `:white_check_mark:ok:` (posted
		// `✅ok:`) share the shape `:a:b:` with the emoji at opposite ends —
		// and a local rule that folds one symmetrically breaks the other.
		// These rows pin the pairs the non-overlapping scan folds the same
		// on both sides. matchReadbackMessage also uses the original token
		// boundaries for the glued-after-a-colon-word case (gp-obim).
		{name: "an emoji glued after a chain ending in an emoji-named word", posted: "key:value:ok✅", stored: "key:value:ok:white_check_mark:"},
		{name: "an emoji glued before a colon-suffixed emoji-named word", posted: "✅ok:", stored: ":white_check_mark:ok:"},
		{name: "two Unicode emoji glued together", posted: "🆗✅", stored: ":ok::white_check_mark:"},
		{name: "a changed clock time before a glued emoji is refused", posted: "Done at 10:30🎉", stored: "Done at 10:45:tada:", wantErr: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			newSlackReadbackServer(t, "/conversations.history", func(url.Values) {}, mustJSON(t, map[string]any{
				"ok":       true,
				"messages": []map[string]string{{"ts": "1700.001", "text": test.stored}},
			}))
			err := readBackPublishedMessage(nil, "xoxb-test", readbackTarget(test.posted))
			if (err != nil) != test.wantErr {
				t.Fatalf("readBackPublishedMessage = %v, wantErr %v (posted %q, stored %q)", err, test.wantErr, test.posted, test.stored)
			}
		})
	}
}

// TestSlackNormalizeTextFoldsEmojiSymmetrically pins the fold itself: the
// Unicode form and Slack's colon form of the same emoji normalize to the
// same text, and a shortcode-looking token inside ordinary text is folded
// the same on both sides rather than compared literally.
func TestSlackNormalizeTextFoldsEmojiSymmetrically(t *testing.T) {
	pairs := [][2]string{
		{"Done 🎉", "Done :tada:"},
		{"👍🏽", ":+1::skin-tone-4:"},
		{"1️⃣ first", ":one: first"},
		{"🇺🇸", ":us:"},
		{"👨‍👩‍👧", ":man-woman-girl:"},
		{"ok ©", "ok :copyright:"},
		{"Done🎉", "Done:tada:"},
		{"🎉Done", ":tada:Done"},
		{"LGTM👍🏽", "LGTM:+1::skin-tone-4:"},
	}
	for _, p := range pairs {
		if a, b := slackNormalizeText(p[0]), slackNormalizeText(p[1]); a != b {
			t.Errorf("slackNormalizeText(%q) = %q, slackNormalizeText(%q) = %q; want equal", p[0], a, p[1], b)
		}
	}
	if a, b := slackNormalizeText("Done 🎉"), slackNormalizeText("Done :tada: and more"); a == b {
		t.Errorf("text beyond the emoji folded away: %q", a)
	}
	// Colon-delimited text that is not an emoji stays in the compare (the
	// lane's codex round 1): two timestamps must not fold to one string.
	if a, b := slackNormalizeText("Deploy at 12:30:45"), slackNormalizeText("Deploy at 12:59:45"); a == b {
		t.Errorf("two different timestamps folded to the same text %q", a)
	}
	if got := slackNormalizeText("Deploy at 12:30:45"); got != "Deploy at 12:30:45" {
		t.Errorf("a timestamp was folded: %q", got)
	}
	// Symbols Slack stores as typed are not emoji and stay (the lane's codex
	// round 2): ⌘, box drawing, Braille, arrows other than the emoji ones.
	for _, kept := range []string{"Press ⌘Q", "┌─┐", "⠁⠃", "a → b", "x ≠ y", "std::vector::iterator", "C♯ C♭ ♪", "☖ ♔", "क्\u200dष", "a\ufe0e b", "items[:2:]", "x[1:2:3]", "`items[:start:]`", "`x[:100:]`", "```\n:tada:\n```", "`:tada:` outside", "https://example.com/:customer_id:/orders", "http://h/:a: tail", "items[:start_index:]", "key:value:other", "s3://bucket/:id:/x", "git+ssh://host/:ok:/repo", ":not_an_emoji_name:"} {
		if got := slackNormalizeText(kept); got != kept {
			t.Errorf("slackNormalizeText(%q) = %q, want it unchanged", kept, got)
		}
	}
}

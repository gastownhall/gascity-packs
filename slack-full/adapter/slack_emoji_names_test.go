package main

import (
	"slices"
	"testing"
)

// TestSlackStandardEmojiNamesIsASortedUniqueTable pins the shape the lookup
// relies on (slices.BinarySearch needs a sorted slice) and that the generated
// table is Slack's: the names Slack stores for the emoji the read-back tests
// post are in it, and the shortcode-shaped tokens those tests keep as text are
// not.
func TestSlackStandardEmojiNamesIsASortedUniqueTable(t *testing.T) {
	if !slices.IsSorted(slackStandardEmojiNames) {
		t.Fatal("slackStandardEmojiNames is not sorted; regenerate it with slack-full/scripts/gen_slack_emoji_names.py")
	}
	if len(slices.Compact(slices.Clone(slackStandardEmojiNames))) != len(slackStandardEmojiNames) {
		t.Fatal("slackStandardEmojiNames carries a duplicate")
	}
	if len(slackStandardEmojiNames) < 1500 {
		t.Fatalf("slackStandardEmojiNames has %d names; Slack's table has well over 1500", len(slackStandardEmojiNames))
	}
	for _, name := range []string{"tada", "+1", "-1", "100", "1234", "thumbsup", "skin-tone-2", "skin-tone-6", "one", "hash", "us", "flag-us", "man-woman-girl", "white_check_mark", "copyright", "rocket", "id", "ok", "a"} {
		if !slackIsStandardEmojiName(name) {
			t.Errorf("%q is a Slack standard emoji name and must be in the table", name)
		}
	}
	for _, name := range []string{"start_index", "end_index", "vector", "iterator", "customer_id", "order_id", "value", "other", "not_an_emoji_name", "30", "2", "", "TADA", "tada:"} {
		if slackIsStandardEmojiName(name) {
			t.Errorf("%q is not a Slack standard emoji name and must not be in the table", name)
		}
	}
}

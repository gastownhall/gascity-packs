package main

import (
	"encoding/json"
	"regexp"
	"sort"
	"strings"
	"sync/atomic"
)

// Composer attribution on the inbound payload.
//
// A Slack message's speaker (`user`) is not its composer. An app can post
// under a user's id with a user token, and a "Sent using <@U…>" context
// block names the app's bot user. The inbound payload used to carry only
// the speaker, so a wake could not tell a person typing from an app posting
// as them without reading the message from Slack again.
//
// A gc that accepts it takes an optional `attribution` map of adapter-defined
// strings on /extmsg/inbound, persists it with the transcript entry, prints
// it in the wake reminder and returns it from the transcript lookup by
// provider_message_id. It is adapter-asserted evidence; what to trust is the
// consumer's decision.
//
// Keys (attributionVersion "1"). A key is present only when Slack set the
// field; the map's presence with attribution_version says the adapter looked,
// so an absent key means Slack had no such field:
//
//	attribution_version  "1"
//	user_id              event `user` (the speaker)
//	app_id               event `app_id`
//	bot_id               event `bot_id`
//	bot_profile_app_id   event `bot_profile.app_id`
//	composer_user_id     the bot user in "Sent using <@U…>" (context blocks or
//	                     text); several distinct ones are comma-joined, sorted
//	subtype              event `subtype`
//
// Display names (`username`, `bot_profile.name`) are never carried: a
// chat:write.customize app can post under any name.
const attributionVersion = "1"

// sentUsingPattern matches the footer Slack apps add when posting for a user.
var sentUsingPattern = regexp.MustCompile(`\*?Sent using\*?\s*<@([A-Z0-9]+)(?:\|[^>]*)?>`)

// slackContextBlock is the subset of a Block Kit block sentUsing reads.
type slackContextBlock struct {
	Type     string `json:"type"`
	Elements []struct {
		Text string `json:"text"`
	} `json:"elements"`
}

// sentUsingComposers returns the distinct bot users named in "Sent using"
// footers, sorted. Context blocks and the plain text are both read.
func sentUsingComposers(msg slackMessageEvent) []string {
	found := map[string]bool{}
	var blocks []slackContextBlock
	if len(msg.Blocks) > 0 && json.Unmarshal(msg.Blocks, &blocks) == nil {
		for _, b := range blocks {
			if b.Type != "context" {
				continue
			}
			for _, e := range b.Elements {
				for _, m := range sentUsingPattern.FindAllStringSubmatch(e.Text, -1) {
					found[m[1]] = true
				}
			}
		}
	}
	for _, m := range sentUsingPattern.FindAllStringSubmatch(msg.Text, -1) {
		found[m[1]] = true
	}
	out := make([]string, 0, len(found))
	for id := range found {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

// attributionBotAppID reads bot_profile.app_id. A chat:write.customize app
// can put any display name in that object, so the name is ignored.
func attributionBotAppID(raw json.RawMessage) string {
	var profile struct {
		AppID string `json:"app_id"`
	}
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &profile)
	}
	return profile.AppID
}

// slackAttribution derives the inbound attribution map from a Slack message
// event. It reads only what the event carries; no Slack API call.
func slackAttribution(msg slackMessageEvent) map[string]string {
	attr := map[string]string{"attribution_version": attributionVersion}
	set := func(key, value string) {
		if value != "" {
			attr[key] = value
		}
	}
	set("user_id", msg.User)
	set("app_id", msg.AppID)
	set("bot_id", msg.BotID)
	set("bot_profile_app_id", attributionBotAppID(msg.BotProfile))
	set("composer_user_id", strings.Join(sentUsingComposers(msg), ","))
	set("subtype", msg.Subtype)
	return attr
}

// attributionLogTag renders the composer fields for the `inbound:` log line:
// ` composer=U… app_id=A… bot_id=B… profile_app=A…`, each only when set.
func attributionLogTag(attr map[string]string) string {
	var b strings.Builder
	for _, kv := range [][2]string{
		{"composer", "composer_user_id"},
		{"app_id", "app_id"},
		{"bot_id", "bot_id"},
		{"profile_app", "bot_profile_app_id"},
	} {
		if v := attr[kv[1]]; v != "" {
			b.WriteString(" " + kv[0] + "=" + v)
		}
	}
	return b.String()
}

// attributionDisabled latches for the life of the process after the first
// old-gc refusal of message.attribution. While set, postInbound omits the
// field so later messages do not pay another 422. It clears only on restart.
var attributionDisabled atomic.Bool

// attributionRejected reports whether gc refused the request because it does
// not know the attribution field. postInbound renders a non-2xx as
// "<status>: <body>" (for example "422 Unprocessable Entity: …"). A 422 or
// 400 whose body names the field is that refusal. Any other 4xx is the
// message's own fault.
func attributionRejected(err error) bool {
	if err == nil {
		return false
	}
	text := err.Error()
	if !strings.Contains(text, "attribution") {
		return false
	}
	return strings.HasPrefix(text, "422 ") || strings.HasPrefix(text, "400 ")
}

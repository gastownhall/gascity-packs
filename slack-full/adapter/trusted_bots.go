package main

import (
	"encoding/json"
	"log"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"
)

// trusted_bots.go — the operator allowlist that lets another Slack app's bot
// reach bound sessions on the legacy (non-company-room) inbound path.
//
// Without it the legacy path drops every bot-authored message, so a bot that
// posts into a bound channel (a scheduler, a press bot, another workspace
// integration) never reaches the session there, and nothing says so. With
// SLACK_TRUSTED_BOT_APPS set, a bot message from a listed app is treated as
// inbound like a human message, with the actor marked is_bot=true.
//
// The gate fails closed:
//
//   - The bot_id is resolved through bots.info (the cached resolver the
//     company path uses) and its app_id must be listed. The event's
//     self-declared app_id and bot_profile.app_id are only a cheap
//     pre-filter and must agree with bots.info; they are never trusted on
//     their own.
//   - The adapter's own app is never admitted, even when listed: its posts
//     come back as bot messages and admitting them would loop. When the own
//     app id is unknown no bot is admitted.
//   - Only plain messages and the bot_message subtype are considered; edits,
//     joins and every other subtype stay dropped.
//   - A bots.info failure that survives a short retry drops the message.
//
// Dropped bot messages are logged once per app per hour, so a bot that is
// being dropped is visible in the adapter log.

// trustedBotDropLogInterval is how often a dropped bot message is logged per
// app (or per bot_id when no app id is known).
const trustedBotDropLogInterval = time.Hour

// trustedBotDropLogMax bounds the drop-log memory. The map is cleared when
// full; that only costs an extra log line per app.
const trustedBotDropLogMax = 1024

// trustedBotResolveAttempts bounds the bots.info lookups for one message.
// Only a transient outcome is retried.
const trustedBotResolveAttempts = 3

// trustedBotResolveBackoff is the sleep before the second lookup; it doubles
// for each later one.
const trustedBotResolveBackoff = 500 * time.Millisecond

// slackAppIDPattern is the shape of a Slack app id.
var slackAppIDPattern = regexp.MustCompile(`^A[A-Z0-9]{2,31}$`)

// parseTrustedBotApps parses SLACK_TRUSTED_BOT_APPS: app ids separated by
// commas or whitespace. A malformed entry, or one naming the adapter's own
// app (selfAppID), is skipped with a warning rather than failing startup;
// skipping an entry only admits less.
func parseTrustedBotApps(raw, selfAppID string) []string {
	var out []string
	seen := map[string]bool{}
	for _, f := range strings.FieldsFunc(raw, func(r rune) bool {
		return r == ',' || r == ' ' || r == '\t' || r == '\n'
	}) {
		id := strings.TrimSpace(f)
		switch {
		case id == "":
			continue
		case !slackAppIDPattern.MatchString(id):
			log.Printf("WARN: SLACK_TRUSTED_BOT_APPS: skipping %q: not a Slack app id (want A followed by upper-case letters and digits)", clipTeamIDForLog(id))
			continue
		case selfAppID != "" && id == selfAppID:
			log.Printf("WARN: SLACK_TRUSTED_BOT_APPS: skipping %s: it is this adapter's own app (SLACK_APP_ID); its posts are never admitted", id)
			continue
		case seen[id]:
			continue
		}
		seen[id] = true
		out = append(out, id)
	}
	return out
}

// trustedBotGate decides whether a bot-authored legacy message is admitted.
// A nil gate admits no bot and logs nothing.
type trustedBotGate struct {
	apps map[string]bool
	// selfAppID / selfBotUserID identify the adapter's own app
	// (SLACK_APP_ID, SLACK_SWITCHBOARD_BOT_USER_ID). The receiving app's
	// api_app_id from each event envelope is checked as well.
	selfAppID     string
	selfBotUserID string
	resolver      companyAuthorResolver
	now           func() time.Time
	sleep         func(time.Duration)

	mu         sync.Mutex
	dropLogged map[string]time.Time
}

func newTrustedBotGate(apps []string, selfAppID, selfBotUserID string, resolver companyAuthorResolver) *trustedBotGate {
	g := &trustedBotGate{
		apps:          make(map[string]bool, len(apps)),
		selfAppID:     selfAppID,
		selfBotUserID: selfBotUserID,
		resolver:      resolver,
		now:           time.Now,
		sleep:         time.Sleep,
		dropLogged:    make(map[string]time.Time),
	}
	for _, a := range apps {
		g.apps[a] = true
	}
	return g
}

// trustedBotActor is the identity of an admitted bot message.
type trustedBotActor struct {
	ID          string
	DisplayName string
	AppID       string
}

// isSlackBotMessage reports whether msg was authored by a bot.
func isSlackBotMessage(msg slackMessageEvent) bool {
	return msg.BotID != "" || msg.Subtype == "bot_message"
}

// slackBotProfile is the subset of a message's bot_profile the gate reads.
type slackBotProfile struct {
	AppID string `json:"app_id"`
	Name  string `json:"name"`
}

func parseSlackBotProfile(raw json.RawMessage) slackBotProfile {
	var bp slackBotProfile
	if len(raw) > 0 {
		_ = json.Unmarshal(raw, &bp)
	}
	return bp
}

// admit returns the actor to post and true when msg, a bot-authored message,
// comes from a trusted app. receivingAppID is the event envelope's
// api_app_id: the app the event was delivered to, which is this adapter's
// own app.
func (g *trustedBotGate) admit(msg slackMessageEvent, receivingAppID string) (trustedBotActor, bool) {
	if g == nil {
		return trustedBotActor{}, false
	}
	// Edits, deletes, joins and the rest stay dropped, as for humans.
	if msg.Subtype != "" && msg.Subtype != "bot_message" {
		return trustedBotActor{}, false
	}
	profile := parseSlackBotProfile(msg.BotProfile)
	declared := msg.AppID
	if declared == "" {
		declared = profile.AppID
	}
	logKey := declared
	if logKey == "" {
		logKey = "bot:" + msg.BotID
	}
	name := botDisplayName(profile, msg)

	if g.isOwn(declared, receivingAppID) || g.isOwnUser(msg.User) {
		return trustedBotActor{}, false // our own post: the loop guard
	}
	if msg.AppID != "" && profile.AppID != "" && msg.AppID != profile.AppID {
		g.logDrop(logKey, msg, name, "app_id and bot_profile.app_id disagree", true)
		return trustedBotActor{}, false
	}
	if len(g.apps) == 0 {
		g.logDrop(logKey, msg, name, "no trusted bot apps configured (SLACK_TRUSTED_BOT_APPS)", false)
		return trustedBotActor{}, false
	}
	if declared != "" && !g.apps[declared] {
		g.logDrop(logKey, msg, name, "app not in SLACK_TRUSTED_BOT_APPS", false)
		return trustedBotActor{}, false
	}
	if g.selfAppID == "" && receivingAppID == "" {
		// Without our own app id the loop guard cannot be checked.
		g.logDrop(logKey, msg, name, "own app id unknown (set SLACK_APP_ID)", false)
		return trustedBotActor{}, false
	}
	if msg.BotID == "" {
		g.logDrop(logKey, msg, name, "no bot_id to verify", false)
		return trustedBotActor{}, false
	}
	if g.resolver == nil {
		g.logDrop(logKey, msg, name, "no bots.info resolver", true)
		return trustedBotActor{}, false
	}

	info, outcome := g.resolve(msg.BotID)
	switch outcome {
	case botResolveTransient:
		g.logDrop(logKey, msg, name, "bots.info unavailable", true)
		return trustedBotActor{}, false
	case botResolveUnknown:
		g.logDrop(logKey, msg, name, "bots.info: unknown or deleted bot", true)
		return trustedBotActor{}, false
	}
	if g.isOwn(info.AppID, receivingAppID) || g.isOwnUser(info.UserID) {
		return trustedBotActor{}, false
	}
	if info.AppID == "" || !g.apps[info.AppID] {
		g.logDrop(logKey, msg, name, "bots.info app "+info.AppID+" not in SLACK_TRUSTED_BOT_APPS", true)
		return trustedBotActor{}, false
	}
	if declared != "" && declared != info.AppID {
		g.logDrop(logKey, msg, name, "event app_id does not match bots.info app "+info.AppID, true)
		return trustedBotActor{}, false
	}
	if msg.User != "" && info.UserID != "" && msg.User != info.UserID {
		g.logDrop(logKey, msg, name, "event user does not match the bot's user", true)
		return trustedBotActor{}, false
	}

	actorID := info.UserID
	if actorID == "" {
		actorID = msg.User
	}
	if actorID == "" {
		actorID = msg.BotID
	}
	return trustedBotActor{ID: actorID, DisplayName: name, AppID: info.AppID}, true
}

// resolve looks the bot up, retrying a transient outcome a few times.
func (g *trustedBotGate) resolve(botID string) (companyBotInfo, botResolveOutcome) {
	d := trustedBotResolveBackoff
	var info companyBotInfo
	var outcome botResolveOutcome
	for n := 1; ; n++ {
		info, outcome = g.resolver.Resolve(botID)
		if outcome != botResolveTransient || n >= trustedBotResolveAttempts {
			return info, outcome
		}
		g.sleep(d)
		d *= 2
	}
}

func (g *trustedBotGate) isOwn(appID, receivingAppID string) bool {
	return appID != "" && (appID == g.selfAppID || appID == receivingAppID)
}

func (g *trustedBotGate) isOwnUser(userID string) bool {
	return userID != "" && userID == g.selfBotUserID
}

// botDisplayName names the bot for the actor and the logs.
func botDisplayName(profile slackBotProfile, msg slackMessageEvent) string {
	if n := strings.TrimSpace(profile.Name); n != "" {
		return n
	}
	if n := strings.TrimSpace(msg.Username); n != "" {
		return n
	}
	return msg.BotID
}

// logDrop logs a dropped bot message. always=false limits the line to the
// first per key per trustedBotDropLogInterval; always=true is for drops of a
// message from a listed app, or a suspicious one, which are logged each time.
func (g *trustedBotGate) logDrop(key string, msg slackMessageEvent, name, reason string, always bool) {
	if !always {
		now := g.now()
		g.mu.Lock()
		last, seen := g.dropLogged[key]
		if seen && now.Sub(last) < trustedBotDropLogInterval {
			g.mu.Unlock()
			return
		}
		if len(g.dropLogged) >= trustedBotDropLogMax {
			g.dropLogged = make(map[string]time.Time)
		}
		g.dropLogged[key] = now
		g.mu.Unlock()
		reason += " (logged once per app per hour)"
	}
	app := key
	if strings.HasPrefix(key, "bot:") {
		app = "?"
	}
	log.Printf("inbound dropped: bot message chan=%s ts=%s bot_id=%s app=%s bot=%q: %s",
		msg.Channel, msg.TS, msg.BotID, app, name, reason)
}

// trustedBotScope is the bot token scope bots.info needs.
const trustedBotScope = "users:read"

// checkTrustedBotScope reads the bot token's scopes from auth.test and logs
// a warning when users:read is missing: bots.info then fails for every bot
// and no trusted bot message gets through. It reports false only when the
// scopes were read and the scope is missing; an unreadable answer says
// nothing.
func checkTrustedBotScope(client *http.Client, token string) bool {
	req, err := http.NewRequest(http.MethodGet, slackAPIBase+"/auth.test", nil)
	if err != nil {
		return true
	}
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := client.Do(req)
	if err != nil {
		return true
	}
	resp.Body.Close()
	scopes := resp.Header.Get("X-OAuth-Scopes")
	if scopes == "" {
		return true
	}
	for _, sc := range strings.Split(scopes, ",") {
		if strings.TrimSpace(sc) == trustedBotScope {
			return true
		}
	}
	log.Printf("WARN: SLACK_TRUSTED_BOT_APPS is set but the bot token lacks the %s scope: bots.info cannot verify a bot, so every bot message is dropped. Add %s to the app's bot token scopes and reinstall it.", trustedBotScope, trustedBotScope)
	return false
}

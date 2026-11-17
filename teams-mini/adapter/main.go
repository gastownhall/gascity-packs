// gc-teams-mini-adapter — the minimal Microsoft Teams ↔ gc bridge.
//
// The Teams counterpart of slack-mini. This file is the whole adapter bar
// one thing: Bot Framework token verification lives in auth.go, kept
// separate because it is the one part with no Slack analogue (Slack signs
// webhooks with a shared secret; the Bot Framework signs them with a JWT
// against Microsoft's published keys).
//
//   - Inbound: a public HTTPS receiver for the Bot Framework messaging
//     endpoint (/api/messages). Only `message` activities are handled, and
//     in a team channel or group chat only when the bot is @-mentioned.
//     Each is bridged to gc by POSTing /v0/city/{city}/extmsg/inbound,
//     addressed to the mayor session (override with
//     TEAMS_MINI_INBOUND_TARGET).
//
//   - Outbound: a UDS endpoint (/post-message) that posts plain text into
//     a Teams conversation via the Bot Framework REST API, using a token
//     obtained with the app id + password. The pack's
//     commands/post-message.sh wrapper reaches it through gc's
//     /svc/teams-mini reverse proxy. This is the only outbound verb.
//
// Teams has no ingress-free transport: unlike Slack's Socket Mode, the Bot
// Framework always POSTs to a public URL, so a TLS terminator or tunnel in
// front of LISTEN_PUBLIC is required.
//
// Tier 1 keeps NO on-disk state. The adapter remembers each conversation's
// serviceUrl in memory (the Bot Framework requires replies to go back to
// the regional service that delivered the message) so /post-message can
// address a conversation it has seen; TEAMS_SERVICE_URL is the fallback
// for conversations it has not.
//
// Required env:
//
//	TEAMS_APP_ID         Microsoft App ID of the Azure Bot. The audience every
//	                     inbound JWT must carry, and the client id for the
//	                     outbound token.
//	TEAMS_APP_PASSWORD   Client secret of that app registration; used only to
//	                     obtain the outbound token.
//	TEAMS_TENANT_ID      Entra tenant id of the Teams organisation; the extmsg
//	                     account id and the inbound tenant filter.
//	GC_CITY_NAME         gc city the adapter bridges into.
//
// Controller-injected env (proxy_process mode):
//
//	GC_SERVICE_SOCKET      UDS path the internal listener binds. When set, the
//	                       adapter runs as a gc proxy_process service.
//	GC_SERVICE_URL_PREFIX  Reverse-proxy prefix gc routes to this service;
//	                       used to compute the self-registration callback URL.
//	GC_API_BASE_URL        gc API base (default http://127.0.0.1:9443).
//
// Optional env:
//
//	TEAMS_APP_TYPE             "multi-tenant" (default) or "single-tenant".
//	                           Selects the token authority for the outbound
//	                           token: botframework.com for multi-tenant apps,
//	                           the tenant itself for single-tenant apps.
//	TEAMS_SERVICE_URL          Fallback serviceUrl for /post-message when the
//	                           conversation has not been seen since start.
//	LISTEN_PUBLIC              Public bind for /api/messages (default 0.0.0.0:8777).
//	LISTEN_INTERNAL            TCP bind for the internal mux when GC_SERVICE_SOCKET
//	                           is unset (default 127.0.0.1:8778).
//	REGISTER_ON_START          "true" (default) self-registers as an extmsg adapter.
//	ADAPTER_PROVIDER           extmsg provider name (default "teams").
//	TEAMS_MINI_INBOUND_TARGET  Session handle inbound mentions address (default "mayor").
//	TEAMS_OPENID_CONFIG_URL    Bot Framework OpenID configuration document
//	                           (default the public Bot Framework one). Tests only.
//	TEAMS_LOGIN_BASE           Entra token endpoint base
//	                           (default https://login.microsoftonline.com). Tests only.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	defaultPublicListen   = "0.0.0.0:8777"
	defaultInternalListen = "127.0.0.1:8778"
	defaultGCAPIBase      = "http://127.0.0.1:9443"
	defaultProvider       = "teams"
	defaultInboundTarget  = "mayor"

	// defaultOpenIDConfigURL is the Bot Framework's OpenID configuration
	// document, which names the JWKS every inbound token is verified against.
	defaultOpenIDConfigURL = "https://login.botframework.com/v1/.well-known/openidconfiguration"

	// defaultLoginBase is the Entra token endpoint base for the outbound
	// client-credentials token.
	defaultLoginBase = "https://login.microsoftonline.com"

	// botFrameworkScope is the resource the outbound token is minted for.
	botFrameworkScope = "https://api.botframework.com/.default"

	// maxInboundBody caps the /api/messages body read. The body is untrusted
	// until the bearer token is verified, so bounding it limits a
	// memory-amplification vector. Activities are small.
	maxInboundBody = 1 << 20 // 1 MiB

	// teamsMaxMessageLength is the Bot Framework's documented ceiling for a
	// single message activity's text.
	teamsMaxMessageLength = 28000

	teamsPostTimeout = 15 * time.Second
)

// gcCallTimeout bounds outbound calls to the gc API so a stalled gc cannot
// pin an inbound-bridge goroutine (or block startup registration) forever.
const gcCallTimeout = 15 * time.Second

type config struct {
	publicListen        string
	internalListen      string
	serviceSocket       string
	gcAPIBase           string
	internalCallbackURL string
	cityName            string
	provider            string
	tenantID            string
	appID               string
	appPassword         string
	appType             string
	serviceURLFallback  string
	inboundTarget       string
	openIDConfigURL     string
	loginBase           string
	registerOnStart     bool
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	internalDescr := cfg.internalListen
	if cfg.serviceSocket != "" {
		internalDescr = "uds:" + cfg.serviceSocket
	}
	log.Printf("starting gc-teams-mini-adapter inbound=http:%s internal=%s gc=%s city=%s target=%s app_type=%s",
		cfg.publicListen, internalDescr, cfg.gcAPIBase, cfg.cityName, cfg.inboundTarget, cfg.appType)

	verifier := newTokenVerifier(cfg.openIDConfigURL, cfg.appID)
	convs := newConversationTable(cfg.serviceURLFallback)
	tokens := newTokenSource(cfg)

	publicMux := http.NewServeMux()
	publicMux.HandleFunc("/api/messages", handleActivities(cfg, verifier, convs))
	publicMux.HandleFunc("/healthz", handleHealthz)
	publicMux.HandleFunc("/", http.NotFound)

	internalMux := http.NewServeMux()
	internalMux.HandleFunc("POST /post-message", handlePostMessage(cfg, convs, tokens))
	internalMux.HandleFunc("/healthz", handleHealthz)

	publicSrv := &http.Server{
		Addr:              cfg.publicListen,
		Handler:           publicMux,
		ReadHeaderTimeout: 10 * time.Second,
	}
	internalSrv := &http.Server{
		Handler:           internalMux,
		ReadHeaderTimeout: 10 * time.Second,
	}

	if cfg.registerOnStart {
		regCtx, cancel := context.WithTimeout(context.Background(), gcCallTimeout)
		err := registerAdapter(regCtx, cfg)
		cancel()
		if err != nil {
			log.Fatalf("register adapter: %v", err)
		}
		log.Printf("registered with gc as provider=%s account=%s callback=%s/post-message",
			cfg.provider, cfg.tenantID, cfg.internalCallbackURL)
	}

	errCh := make(chan error, 2)
	go func() {
		log.Printf("public listener serving on %s (Bot Framework messaging endpoint)", cfg.publicListen)
		errCh <- publicSrv.ListenAndServe()
	}()
	go func() {
		if cfg.serviceSocket != "" {
			log.Printf("internal listener serving on UDS %s (gc proxy_process)", cfg.serviceSocket)
			lis, err := listenUDS(cfg.serviceSocket)
			if err != nil {
				errCh <- err
				return
			}
			errCh <- internalSrv.Serve(lis)
			return
		}
		internalSrv.Addr = cfg.internalListen
		log.Printf("internal listener serving on %s (post-message only)", cfg.internalListen)
		errCh <- internalSrv.ListenAndServe()
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	select {
	case <-stop:
		log.Println("shutting down (signal)")
	case err := <-errCh:
		if !errors.Is(err, http.ErrServerClosed) {
			log.Printf("listener error: %v", err)
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = publicSrv.Shutdown(ctx)
	_ = internalSrv.Shutdown(ctx)
}

func handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("ok\n"))
}

// loadConfig reads the process environment.
func loadConfig() (config, error) { return loadConfigFromEnv(os.Getenv) }

// loadConfigFromEnv builds and validates a config from a getenv function.
// Split out so tests can supply a fake environment.
func loadConfigFromEnv(getenv func(string) string) (config, error) {
	envOr := func(key, fallback string) string {
		if v := getenv(key); v != "" {
			return v
		}
		return fallback
	}
	cfg := config{
		publicListen:       envOr("LISTEN_PUBLIC", defaultPublicListen),
		internalListen:     envOr("LISTEN_INTERNAL", defaultInternalListen),
		serviceSocket:      getenv("GC_SERVICE_SOCKET"),
		gcAPIBase:          strings.TrimRight(envOr("GC_API_BASE_URL", defaultGCAPIBase), "/"),
		cityName:           getenv("GC_CITY_NAME"),
		provider:           envOr("ADAPTER_PROVIDER", defaultProvider),
		tenantID:           getenv("TEAMS_TENANT_ID"),
		appID:              getenv("TEAMS_APP_ID"),
		appPassword:        getenv("TEAMS_APP_PASSWORD"),
		appType:            strings.ToLower(envOr("TEAMS_APP_TYPE", "multi-tenant")),
		serviceURLFallback: getenv("TEAMS_SERVICE_URL"),
		inboundTarget:      envOr("TEAMS_MINI_INBOUND_TARGET", defaultInboundTarget),
		openIDConfigURL:    envOr("TEAMS_OPENID_CONFIG_URL", defaultOpenIDConfigURL),
		loginBase:          strings.TrimRight(envOr("TEAMS_LOGIN_BASE", defaultLoginBase), "/"),
		registerOnStart:    envOr("REGISTER_ON_START", "true") == "true",
	}

	// proxy_process mode: gc reaches the adapter via GC_API_BASE_URL +
	// GC_SERVICE_URL_PREFIX. gc appends the endpoint path itself, so the
	// registered callback base must not include it.
	if cfg.serviceSocket != "" {
		urlPrefix := strings.TrimRight(getenv("GC_SERVICE_URL_PREFIX"), "/")
		if urlPrefix == "" {
			return cfg, errors.New("GC_SERVICE_SOCKET is set but GC_SERVICE_URL_PREFIX is empty — controller-injected env is incomplete")
		}
		cfg.internalCallbackURL = cfg.gcAPIBase + urlPrefix
	} else {
		// Standalone TCP mode: no controller-injected URL prefix, so derive
		// the callback base from the internal listener. Leaving it empty would
		// self-register an empty callback_url and break gc→adapter callbacks.
		cfg.internalCallbackURL = tcpCallbackURL(cfg.internalListen)
	}

	var missing []string
	if cfg.appID == "" {
		missing = append(missing, "TEAMS_APP_ID")
	}
	if cfg.appPassword == "" {
		missing = append(missing, "TEAMS_APP_PASSWORD")
	}
	if cfg.tenantID == "" {
		missing = append(missing, "TEAMS_TENANT_ID")
	}
	if cfg.cityName == "" {
		missing = append(missing, "GC_CITY_NAME")
	}
	if len(missing) > 0 {
		return cfg, fmt.Errorf("missing required env vars: %s", strings.Join(missing, ", "))
	}
	switch cfg.appType {
	case "multi-tenant", "single-tenant":
	default:
		return cfg, fmt.Errorf("TEAMS_APP_TYPE must be \"multi-tenant\" or \"single-tenant\": %q", cfg.appType)
	}
	// cityName is interpolated into every /v0/city/{city}/... URL. Reject
	// URL-significant characters so a city name cannot alter routing.
	if strings.ContainsAny(cfg.cityName, "/?#%") {
		return cfg, fmt.Errorf("GC_CITY_NAME must not contain '/', '?', '#', or '%%': %q", cfg.cityName)
	}
	// The tenant id is interpolated into the single-tenant token URL and
	// used as a path-free identifier everywhere else; keep it to the GUID
	// alphabet so it cannot alter routing either.
	if strings.ContainsAny(cfg.tenantID, "/?#%") {
		return cfg, fmt.Errorf("TEAMS_TENANT_ID must not contain '/', '?', '#', or '%%': %q", cfg.tenantID)
	}
	if cfg.serviceURLFallback != "" {
		if _, err := validServiceURL(cfg.serviceURLFallback); err != nil {
			return cfg, fmt.Errorf("TEAMS_SERVICE_URL: %w", err)
		}
	}
	return cfg, nil
}

// tokenAuthority is the Entra tenant segment of the outbound token URL.
// Multi-tenant bots authenticate against the botframework.com tenant;
// single-tenant bots against their own.
func (c config) tokenAuthority() string {
	if c.appType == "single-tenant" {
		return c.tenantID
	}
	return "botframework.com"
}

// tcpCallbackURL derives the gc→adapter callback base from the internal
// listener address for standalone (TCP) mode, where there is no
// proxy_process URL prefix. gc appends the endpoint path itself, so the
// returned URL carries no trailing path. A wildcard or empty bind host is
// rewritten to loopback because gc dials a concrete address.
func tcpCallbackURL(internalListen string) string {
	host, port, err := net.SplitHostPort(internalListen)
	if err != nil {
		return "http://" + internalListen
	}
	switch host {
	case "", "0.0.0.0", "::":
		host = "127.0.0.1"
	}
	return "http://" + net.JoinHostPort(host, port)
}

// validServiceURL accepts only absolute https URLs, since the serviceUrl is
// used as the base of every outbound Bot Framework call and arrives from a
// (verified, but still external) inbound activity.
func validServiceURL(raw string) (string, error) {
	u, err := url.Parse(raw)
	if err != nil {
		return "", fmt.Errorf("parse serviceUrl: %w", err)
	}
	if u.Scheme != "https" || u.Host == "" {
		return "", fmt.Errorf("serviceUrl must be an absolute https URL: %q", raw)
	}
	if u.RawQuery != "" || u.Fragment != "" {
		return "", fmt.Errorf("serviceUrl must not carry a query or fragment: %q", raw)
	}
	return strings.TrimRight(u.String(), "/") + "/", nil
}

// --- conversation table ------------------------------------------------------

// conversationTable remembers, in memory only, the serviceUrl each
// conversation was last delivered from. The Bot Framework routes replies
// through the regional service that delivered the inbound activity, so an
// outbound post needs the matching serviceUrl; a conversation the adapter
// has not seen since start falls back to TEAMS_SERVICE_URL.
type conversationTable struct {
	mu       sync.RWMutex
	byConv   map[string]string
	fallback string
}

func newConversationTable(fallback string) *conversationTable {
	return &conversationTable{byConv: map[string]string{}, fallback: fallback}
}

func (t *conversationTable) remember(conversationID, serviceURL string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.byConv[conversationID] = serviceURL
}

// lookup resolves the serviceUrl for a conversation: an explicit override
// wins, then the remembered value, then the configured fallback.
func (t *conversationTable) lookup(conversationID, override string) (string, bool) {
	if override != "" {
		return override, true
	}
	t.mu.RLock()
	defer t.mu.RUnlock()
	if u, ok := t.byConv[conversationID]; ok {
		return u, true
	}
	if t.fallback != "" {
		return t.fallback, true
	}
	return "", false
}

// --- inbound: Bot Framework activities → gc extmsg --------------------------

// activity is the subset of a Bot Framework activity Tier 1 reads.
type activity struct {
	Type         string           `json:"type"`
	ID           string           `json:"id,omitempty"`
	ServiceURL   string           `json:"serviceUrl,omitempty"`
	Text         string           `json:"text,omitempty"`
	ReplyToID    string           `json:"replyToId,omitempty"`
	From         channelAccount   `json:"from"`
	Recipient    channelAccount   `json:"recipient"`
	Conversation conversationInfo `json:"conversation"`
	Entities     []entity         `json:"entities,omitempty"`
	ChannelData  channelData      `json:"channelData,omitempty"`
}

type channelAccount struct {
	ID          string `json:"id,omitempty"`
	Name        string `json:"name,omitempty"`
	AADObjectID string `json:"aadObjectId,omitempty"`
}

type conversationInfo struct {
	ID               string `json:"id,omitempty"`
	ConversationType string `json:"conversationType,omitempty"`
	TenantID         string `json:"tenantId,omitempty"`
}

type entity struct {
	Type      string         `json:"type,omitempty"`
	Mentioned channelAccount `json:"mentioned,omitempty"`
}

type channelData struct {
	Tenant struct {
		ID string `json:"id,omitempty"`
	} `json:"tenant,omitempty"`
}

func handleActivities(cfg config, verifier *tokenVerifier, convs *conversationTable) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		body, err := io.ReadAll(io.LimitReader(r.Body, maxInboundBody))
		if err != nil {
			http.Error(w, "read body", http.StatusBadRequest)
			return
		}
		claims, err := verifier.verify(r.Context(), r.Header.Get("Authorization"))
		if err != nil {
			log.Printf("bot framework token verify FAILED: %v", err)
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		var act activity
		if err := json.Unmarshal(body, &act); err != nil {
			http.Error(w, fmt.Sprintf("decode: %v", err), http.StatusBadRequest)
			return
		}
		// The token's serviceurl claim must match the activity's serviceUrl:
		// a token minted for one regional service cannot be replayed with an
		// activity pointing the adapter's replies somewhere else.
		if claims.ServiceURL != "" && !sameServiceURL(claims.ServiceURL, act.ServiceURL) {
			log.Printf("serviceUrl mismatch: token=%s activity=%s", claims.ServiceURL, act.ServiceURL)
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		// Ack immediately so the Bot Framework does not retry, then bridge.
		w.WriteHeader(http.StatusOK)
		go bridgeActivity(cfg, convs, act)
	}
}

// sameServiceURL compares two serviceUrls ignoring a trailing slash, which
// the Bot Framework is inconsistent about between the claim and the body.
func sameServiceURL(a, b string) bool {
	return strings.TrimRight(a, "/") == strings.TrimRight(b, "/")
}

// bridgeActivity decodes a message activity and POSTs it to gc's extmsg
// inbound. Non-message activities (conversationUpdate, typing, …), bot
// echoes, un-mentioned channel chatter and empty bodies are dropped.
// It runs in its own goroutine; the gc call is bounded by gcCallTimeout so
// a stalled gc cannot leak goroutines under sustained traffic.
func bridgeActivity(cfg config, convs *conversationTable, act activity) {
	if act.Type != "message" {
		return
	}
	// Drop activities from another tenant. A multi-tenant bot can be
	// installed by any organisation, yet every bridged message is stamped
	// with cfg.tenantID as its account id below; without this guard a second
	// tenant's mentions would be filed under this one.
	tenant := act.ChannelData.Tenant.ID
	if tenant == "" {
		tenant = act.Conversation.TenantID
	}
	if tenant != "" && !strings.EqualFold(tenant, cfg.tenantID) {
		log.Printf("dropping activity from unexpected tenant %s (want %s)", tenant, cfg.tenantID)
		return
	}
	if act.From.ID == "" || act.Conversation.ID == "" {
		return
	}
	if act.From.ID == act.Recipient.ID {
		return // our own echo
	}
	kind := teamsKind(act.Conversation.ConversationType)
	if kind == "room" && !mentionsBot(act) {
		return // Tier 1 answers only direct mentions in rooms
	}
	text := stripMentions(act.Text)
	if text == "" {
		return
	}

	serviceURL, err := validServiceURL(act.ServiceURL)
	if err != nil {
		log.Printf("dropping activity %s: %v", act.ID, err)
		return
	}
	convs.remember(act.Conversation.ID, serviceURL)

	displayName := act.From.Name
	if displayName == "" {
		displayName = act.From.ID
	}
	inbound := externalInboundMessage{
		ProviderMessageID: act.ID,
		Conversation: conversationRef{
			ScopeID:        cfg.cityName,
			Provider:       cfg.provider,
			AccountID:      cfg.tenantID,
			ConversationID: act.Conversation.ID,
			Kind:           kind,
		},
		Actor: externalActor{
			ID:          act.From.ID,
			DisplayName: displayName,
		},
		Text:             text,
		ExplicitTarget:   cfg.inboundTarget,
		ReplyToMessageID: act.ReplyToID,
		DedupKey:         "teams-" + act.ID,
		ReceivedAt:       time.Now().UTC(),
	}
	ctx, cancel := context.WithTimeout(context.Background(), gcCallTimeout)
	defer cancel()
	if err := postInbound(ctx, cfg, inbound); err != nil {
		log.Printf("inbound POST failed: %v", err)
		return
	}
	log.Printf("inbound: conv=%s kind=%s user=%s id=%s target=%s text=%dch",
		act.Conversation.ID, kind, act.From.ID, act.ID, cfg.inboundTarget, len(text))
}

// mentionsBot reports whether the activity's mention entities include the
// bot (the activity's recipient). Teams only delivers channel and group
// messages to a bot when it is mentioned, so this mostly guards hand-built
// payloads, but it is the documented contract and cheap to enforce.
func mentionsBot(act activity) bool {
	for _, e := range act.Entities {
		if e.Type == "mention" && e.Mentioned.ID != "" && e.Mentioned.ID == act.Recipient.ID {
			return true
		}
	}
	return false
}

// atTagRE matches Teams' inline mention markup, `<at>Display Name</at>`,
// which arrives in the text wherever a user @-mentioned someone. Stripping
// every occurrence (not just a leading one, as Slack's bridge does) is
// right here because Teams renders the mention as the display name, so a
// message like "<at>gc</at> status for <at>Ada</at>" reads naturally as
// "status for" to the mayor without a stray tag.
var atTagRE = regexp.MustCompile(`(?s)<at>.*?</at>`)

// spaceRunRE collapses the whitespace a removed mention leaves behind.
var spaceRunRE = regexp.MustCompile(`\s{2,}`)

func stripMentions(text string) string {
	out := atTagRE.ReplaceAllString(text, "")
	out = spaceRunRE.ReplaceAllString(out, " ")
	return strings.TrimSpace(out)
}

// teamsKind maps a Teams conversationType onto a gc ConversationKind.
// "personal" is a one-to-one chat with the bot; "groupChat" and "channel"
// are rooms. An absent type is treated as a room so an unmentioned message
// is dropped rather than bridged: the conservative default.
func teamsKind(conversationType string) string {
	if strings.EqualFold(conversationType, "personal") {
		return "dm"
	}
	return "room"
}

// --- gc extmsg wire types (mirrored, wire-compatible only) ----------------

type conversationRef struct {
	ScopeID        string `json:"scope_id"`
	Provider       string `json:"provider"`
	AccountID      string `json:"account_id"`
	ConversationID string `json:"conversation_id"`
	Kind           string `json:"kind"`
}

type externalActor struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	IsBot       bool   `json:"is_bot"`
}

type externalInboundMessage struct {
	ProviderMessageID string          `json:"provider_message_id"`
	Conversation      conversationRef `json:"conversation"`
	Actor             externalActor   `json:"actor"`
	Text              string          `json:"text"`
	ExplicitTarget    string          `json:"explicit_target,omitempty"`
	ReplyToMessageID  string          `json:"reply_to_message_id,omitempty"`
	DedupKey          string          `json:"dedup_key,omitempty"`
	ReceivedAt        time.Time       `json:"received_at"`
}

type adapterCapabilities struct {
	SupportsChildConversations bool `json:"SupportsChildConversations"`
	SupportsAttachments        bool `json:"SupportsAttachments"`
	MaxMessageLength           int  `json:"MaxMessageLength"`
}

type adapterRegisterRequest struct {
	Provider     string              `json:"provider"`
	AccountID    string              `json:"account_id"`
	Name         string              `json:"name,omitempty"`
	CallbackURL  string              `json:"callback_url,omitempty"`
	Capabilities adapterCapabilities `json:"capabilities,omitempty"`
}

// postInbound bridges a verified Teams message into gc.
func postInbound(ctx context.Context, cfg config, msg externalInboundMessage) error {
	body, err := json.Marshal(map[string]any{"message": msg})
	if err != nil {
		return err
	}
	target := fmt.Sprintf("%s/v0/city/%s/extmsg/inbound", cfg.gcAPIBase, url.PathEscape(cfg.cityName))
	if err := postJSON(ctx, target, body); err != nil {
		return fmt.Errorf("post inbound: %w", err)
	}
	return nil
}

// registerAdapter self-registers as an extmsg adapter so gc accepts this
// provider's inbound messages.
func registerAdapter(ctx context.Context, cfg config) error {
	body, err := json.Marshal(adapterRegisterRequest{
		Provider:    cfg.provider,
		AccountID:   cfg.tenantID,
		Name:        "teams-mini-adapter",
		CallbackURL: cfg.internalCallbackURL,
		Capabilities: adapterCapabilities{
			SupportsChildConversations: false,
			SupportsAttachments:        false,
			MaxMessageLength:           teamsMaxMessageLength,
		},
	})
	if err != nil {
		return err
	}
	target := fmt.Sprintf("%s/v0/city/%s/extmsg/adapters", cfg.gcAPIBase, url.PathEscape(cfg.cityName))
	return postJSON(ctx, target, body)
}

// postJSON POSTs a JSON body to a gc API endpoint and treats any >=400
// status as an error, surfacing the response body for diagnostics. ctx
// bounds the call so callers can enforce a timeout.
func postJSON(ctx context.Context, target string, body []byte) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-GC-Request", "gc-teams-mini-adapter")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("%s: %s", resp.Status, strings.TrimSpace(string(respBody)))
	}
	return nil
}

// --- outbound: post-message → Bot Framework conversations API --------------

// postMessageReq is the JSON body the post-message.sh wrapper POSTs to
// /post-message.
type postMessageReq struct {
	Conversation string `json:"conversation"`
	Text         string `json:"text"`
	ReplyTo      string `json:"reply_to,omitempty"`
	ServiceURL   string `json:"service_url,omitempty"`
}

// resourceResponse is the Bot Framework's reply to a posted activity.
type resourceResponse struct {
	ID string `json:"id,omitempty"`
}

func handlePostMessage(cfg config, convs *conversationTable, tokens *tokenSource) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req postMessageReq
		if err := json.NewDecoder(io.LimitReader(r.Body, maxInboundBody)).Decode(&req); err != nil {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("decode: %v", err))
			return
		}
		req.Conversation = strings.TrimSpace(req.Conversation)
		if req.Conversation == "" {
			writeJSONError(w, http.StatusBadRequest, "conversation is required")
			return
		}
		if strings.TrimSpace(req.Text) == "" {
			writeJSONError(w, http.StatusBadRequest, "text is required")
			return
		}
		if len(req.Text) > teamsMaxMessageLength {
			writeJSONError(w, http.StatusBadRequest, fmt.Sprintf("text exceeds %d characters", teamsMaxMessageLength))
			return
		}
		override := ""
		if req.ServiceURL != "" {
			u, err := validServiceURL(req.ServiceURL)
			if err != nil {
				writeJSONError(w, http.StatusBadRequest, err.Error())
				return
			}
			override = u
		}
		serviceURL, ok := convs.lookup(req.Conversation, override)
		if !ok {
			writeJSONError(w, http.StatusBadRequest,
				"no serviceUrl known for this conversation: pass service_url, or set TEAMS_SERVICE_URL")
			return
		}
		token, err := tokens.get(r.Context())
		if err != nil {
			writeJSONError(w, http.StatusBadGateway, "token: "+err.Error())
			return
		}
		id, err := postToTeams(r.Context(), serviceURL, token, req)
		if err != nil {
			writeJSONError(w, http.StatusBadGateway, err.Error())
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok":           true,
			"id":           id,
			"conversation": req.Conversation,
		})
	}
}

func writeJSONError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": msg})
}

// postToTeams posts a message activity into a conversation. With a reply_to
// it is posted as a reply to that activity (a thread reply in a channel);
// otherwise it is a new message in the conversation.
func postToTeams(ctx context.Context, serviceURL, token string, req postMessageReq) (string, error) {
	target := serviceURL + "v3/conversations/" + url.PathEscape(req.Conversation) + "/activities"
	if req.ReplyTo != "" {
		target += "/" + url.PathEscape(req.ReplyTo)
	}
	payload, err := json.Marshal(map[string]any{
		"type":       "message",
		"text":       req.Text,
		"textFormat": "markdown",
	})
	if err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(ctx, teamsPostTimeout)
	defer cancel()
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(payload))
	if err != nil {
		return "", err
	}
	httpReq.Header.Set("Authorization", "Bearer "+token)
	httpReq.Header.Set("Content-Type", "application/json; charset=utf-8")
	resp, err := http.DefaultClient.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("post activity: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, maxInboundBody))
	if err != nil {
		return "", fmt.Errorf("read bot framework response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("bot framework http %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}
	var rr resourceResponse
	if len(respBody) > 0 {
		if err := json.Unmarshal(respBody, &rr); err != nil {
			return "", fmt.Errorf("decode bot framework response: %w", err)
		}
	}
	return rr.ID, nil
}

// --- outbound token ----------------------------------------------------------

// tokenSource mints and caches the client-credentials token the Bot
// Framework REST API requires. One token is shared across posts and
// refreshed a minute before it expires.
type tokenSource struct {
	cfg    config
	mu     sync.Mutex
	token  string
	expiry time.Time
	now    func() time.Time
}

func newTokenSource(cfg config) *tokenSource {
	return &tokenSource{cfg: cfg, now: time.Now}
}

type tokenResponse struct {
	AccessToken string `json:"access_token"`
	ExpiresIn   int    `json:"expires_in"`
	Error       string `json:"error,omitempty"`
	ErrorDescr  string `json:"error_description,omitempty"`
}

func (s *tokenSource) get(ctx context.Context) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.token != "" && s.now().Add(time.Minute).Before(s.expiry) {
		return s.token, nil
	}
	form := url.Values{
		"grant_type":    {"client_credentials"},
		"client_id":     {s.cfg.appID},
		"client_secret": {s.cfg.appPassword},
		"scope":         {botFrameworkScope},
	}
	target := s.cfg.loginBase + "/" + s.cfg.tokenAuthority() + "/oauth2/v2.0/token"
	ctx, cancel := context.WithTimeout(ctx, teamsPostTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("token request: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxInboundBody))
	if err != nil {
		return "", fmt.Errorf("read token response: %w", err)
	}
	var tr tokenResponse
	if err := json.Unmarshal(body, &tr); err != nil {
		return "", fmt.Errorf("decode token response (http %d): %w", resp.StatusCode, err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 || tr.AccessToken == "" {
		msg := tr.Error
		if tr.ErrorDescr != "" {
			msg += ": " + tr.ErrorDescr
		}
		if msg == "" {
			msg = strings.TrimSpace(string(body))
		}
		return "", fmt.Errorf("token request http %d: %s", resp.StatusCode, msg)
	}
	s.token = tr.AccessToken
	s.expiry = s.now().Add(time.Duration(tr.ExpiresIn) * time.Second)
	return s.token, nil
}

// listenUDS binds a Unix domain socket, removing any stale entry first so
// restarts succeed, and tightens it to owner-only.
func listenUDS(path string) (net.Listener, error) {
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("remove stale socket: %w", err)
	}
	lis, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("listen unix %s: %w", path, err)
	}
	if err := os.Chmod(path, 0o600); err != nil {
		_ = lis.Close()
		return nil, fmt.Errorf("chmod uds: %w", err)
	}
	return lis, nil
}

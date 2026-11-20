// Channel and user lookups — G1 (channels) and G2 (user-by-email).
//
// Two read-only outbound helpers on the internal mux:
//
//	GET /channels        name → id map from conversations.list
//	GET /user-id?email=  Slack user id from users.lookupByEmail
//
// Both call the Slack web API with the workspace bot token and cache
// results per process so digest-style callers do not pay a Slack round
// trip per message. G1 paginates through conversations.list and caches
// the full map with a TTL; G2 caches each email → id mapping with a TTL
// and surfaces Slack's users_not_found as HTTP 404 so callers can fall
// back to the plain email address.
//
// Required bot scopes (in addition to Tier 1's base set):
//
//	channels:read, groups:read   for conversations.list (G1)
//	users:read.email              for users.lookupByEmail (G2)
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

// Cache TTLs. Package vars (not consts) so tests can shrink them without
// waiting on production intervals.
var (
	channelCacheTTL = 5 * time.Minute
	userCacheTTL    = 5 * time.Minute
)

const slackLookupTimeout = 15 * time.Second

// channelCache holds one process-wide name → id map with a single expiry.
type channelCache struct {
	mu      sync.Mutex
	entries map[string]string
	expires time.Time
}

func (c *channelCache) get() (map[string]string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.entries == nil || time.Now().After(c.expires) {
		return nil, false
	}
	out := make(map[string]string, len(c.entries))
	for k, v := range c.entries {
		out[k] = v
	}
	return out, true
}

func (c *channelCache) set(entries map[string]string, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries = entries
	c.expires = time.Now().Add(ttl)
}

func (c *channelCache) clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries = nil
	c.expires = time.Time{}
}

// userCacheEntry is one cached email → id mapping with its own expiry so
// entries cached at different times age out independently.
type userCacheEntry struct {
	id      string
	expires time.Time
}

type userCache struct {
	mu      sync.Mutex
	entries map[string]userCacheEntry
}

func (c *userCache) get(email string) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[email]
	if !ok || time.Now().After(e.expires) {
		return "", false
	}
	return e.id, true
}

func (c *userCache) set(email, id string, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.entries == nil {
		c.entries = map[string]userCacheEntry{}
	}
	c.entries[email] = userCacheEntry{id: id, expires: time.Now().Add(ttl)}
}

func (c *userCache) clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries = nil
}

// Process-wide lookup caches. One adapter process serves one workspace,
// so a single map per lookup is the whole key space.
var (
	channelsCache = &channelCache{}
	usersCache    = &userCache{}
)

// clearLookupCaches resets both caches. Tests call it to isolate cases;
// production never calls it.
func clearLookupCaches() {
	channelsCache.clear()
	usersCache.clear()
}

type slackChannel struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

type conversationsListResp struct {
	OK       bool           `json:"ok"`
	Channels []slackChannel `json:"channels"`
	Meta     struct {
		NextCursor string `json:"next_cursor"`
	} `json:"response_metadata"`
	Error string `json:"error,omitempty"`
}

// fetchChannels pages through conversations.list and returns the name → id
// map. Results are cached per process for channelCacheTTL.
func fetchChannels(ctx context.Context, apiBase, token string) (map[string]string, error) {
	if cached, ok := channelsCache.get(); ok {
		return cached, nil
	}
	out := map[string]string{}
	cursor := ""
	for {
		page, next, err := fetchChannelsPage(ctx, apiBase, token, cursor)
		if err != nil {
			return nil, err
		}
		for name, id := range page {
			out[name] = id
		}
		if next == "" {
			break
		}
		cursor = next
	}
	channelsCache.set(out, channelCacheTTL)
	return out, nil
}

func fetchChannelsPage(ctx context.Context, apiBase, token, cursor string) (map[string]string, string, error) {
	u, err := url.Parse(apiBase + "/conversations.list")
	if err != nil {
		return nil, "", err
	}
	q := u.Query()
	// Public + private channels. IMs/MPIMs are not channel lookups and
	// need no extra scopes at this tier.
	q.Set("types", "public_channel,private_channel")
	q.Set("limit", "200")
	if cursor != "" {
		q.Set("cursor", cursor)
	}
	u.RawQuery = q.Encode()

	ctx, cancel := context.WithTimeout(ctx, slackLookupTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, "", fmt.Errorf("get conversations.list: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, "", fmt.Errorf("read conversations.list response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, "", fmt.Errorf("slack http %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	var lr conversationsListResp
	if err := json.Unmarshal(body, &lr); err != nil {
		return nil, "", fmt.Errorf("decode conversations.list response: %w", err)
	}
	if !lr.OK {
		return nil, "", fmt.Errorf("slack: %s", lr.Error)
	}
	page := make(map[string]string, len(lr.Channels))
	for _, ch := range lr.Channels {
		if ch.Name != "" && ch.ID != "" {
			page[ch.Name] = ch.ID
		}
	}
	return page, lr.Meta.NextCursor, nil
}

func handleChannels(cfg config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSONError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		m, err := fetchChannels(r.Context(), cfg.slackAPIBase, cfg.botToken)
		if err != nil {
			writeJSONError(w, http.StatusBadGateway, err.Error())
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "channels": m})
	}
}

type usersLookupByEmailResp struct {
	OK   bool `json:"ok"`
	User struct {
		ID string `json:"id"`
	} `json:"user"`
	Error string `json:"error,omitempty"`
}

// errUserNotFound marks a Slack users_not_found so the handler can map it
// to HTTP 404 (caller falls back to the plain email) instead of 502.
type errUserNotFound struct{ email string }

func (e *errUserNotFound) Error() string { return "slack: users_not_found" }

// fetchUserID resolves one email to a Slack user id via users.lookupByEmail,
// cached per process for userCacheTTL.
func fetchUserID(ctx context.Context, apiBase, token, email string) (string, error) {
	if cached, ok := usersCache.get(email); ok {
		return cached, nil
	}
	u, err := url.Parse(apiBase + "/users.lookupByEmail")
	if err != nil {
		return "", err
	}
	q := u.Query()
	q.Set("email", email)
	u.RawQuery = q.Encode()

	ctx, cancel := context.WithTimeout(ctx, slackLookupTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("get users.lookupByEmail: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read users.lookupByEmail response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("slack http %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	var lr usersLookupByEmailResp
	if err := json.Unmarshal(body, &lr); err != nil {
		return "", fmt.Errorf("decode users.lookupByEmail response: %w", err)
	}
	if !lr.OK {
		if lr.Error == "users_not_found" {
			return "", &errUserNotFound{email: email}
		}
		return "", fmt.Errorf("slack: %s", lr.Error)
	}
	if lr.User.ID == "" {
		return "", fmt.Errorf("slack: users.lookupByEmail returned no user id")
	}
	usersCache.set(email, lr.User.ID, userCacheTTL)
	return lr.User.ID, nil
}

func handleUserID(cfg config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSONError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		email := strings.TrimSpace(r.URL.Query().Get("email"))
		if email == "" {
			writeJSONError(w, http.StatusBadRequest, "email is required")
			return
		}
		id, err := fetchUserID(r.Context(), cfg.slackAPIBase, cfg.botToken, email)
		if err != nil {
			var nf *errUserNotFound
			if errors.As(err, &nf) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusNotFound)
				_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "users_not_found"})
				return
			}
			writeJSONError(w, http.StatusBadGateway, err.Error())
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "id": id, "email": email})
	}
}

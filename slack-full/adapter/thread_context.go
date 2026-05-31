package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Thread-context forwarding for cross-agent visibility on shared
// threads. Two beads compose into one mechanism:
//
//   gc-px8.5 — first-mention preamble: when an inbound carries
//     thread_ts and the targeted agent has not been seen on this
//     (target, channel, thread) before, prepend the prior-replies
//     window so the agent sees decision-making it joined mid-stream.
//
//   gc-px8.6 — cross-agent delta visibility: when the same target
//     is mentioned again on the same thread, prepend only the
//     replies posted since the target's last delivered context, so
//     mayor sees what PL replied between mayor's two mentions, and
//     vice versa, without redundant re-paste of context already
//     conveyed.
//
// The implementation is option B from the gc-px8.6 design: fetch
// conversations.replies on every inbound that carries thread_ts and
// is not the thread parent itself. The cache stores per-(target,
// channel, thread) the ts up-to-which preamble has been delivered;
// the formatter applies that as a lower bound so each agent's
// preamble is the delta of peer activity since its last visit.
// Trade-off: more API calls than gc-px8.5's single-shot policy; one
// fetch per inbound in a thread. Slack's tier-3 limit on
// conversations.replies (50/min) is comfortable for typical
// per-thread cadence.

// defaultThreadContextLimit caps how many thread replies the adapter
// asks Slack for when seeding context. Slack itself silently caps
// conversations.replies at 1000; we want a smaller window so a long-
// running thread doesn't dump a megabyte of history into a single
// bridge-mail body. 20 is generous for the priority-feature use case
// (a freshly-mentioned mayor seeing the recent decision-making) and
// is overrideable via SLACK_THREAD_CONTEXT_LIMIT.
const defaultThreadContextLimit = 20

// threadContextFetchTimeout bounds the conversations.replies HTTP
// round-trip. Slack's API typically responds in well under a second;
// 5s is comfortable headroom and keeps a stuck fetch from blocking
// the dispatch goroutine indefinitely while still holding the
// dispatchSem slot.
const threadContextFetchTimeout = 5 * time.Second

// threadContextCache tracks, per (target, channel, thread_ts) tuple,
// the ts of the most recent thread-context preamble the adapter has
// delivered for that target. The next inbound to the same target in
// the same thread uses that ts as a lower bound on which prior
// replies to include — peer activity newer than the last visit, not
// the entire history again.
//
// Process-lifetime; no eviction. Workload is bounded by the count of
// distinct (target, channel, thread) tuples observed, which is small
// relative to per-message memory budgets. A target value of "" is a
// valid key for channel-bound inbounds without an explicit @handle.
//
// Errors during fetchThreadReplies do NOT advance the cached ts. A
// transient Slack 5xx or missing-scope 401 leaves the lower bound
// unchanged so the next inbound retries the fetch and (if it
// succeeds) still gets the priors that were missed during the error
// window. The trade-off is per-inbound logging on persistently-
// failing threads, which is the right operator signal — silent
// suppression of context loss is worse than a noisy log.
type threadContextCache struct {
	mu            sync.Mutex
	lastDelivered map[string]string
}

func newThreadContextCache() *threadContextCache {
	return &threadContextCache{lastDelivered: make(map[string]string)}
}

// lastDeliveredFor returns the ts up-to-which the adapter has already
// delivered preamble context for the given (target, channel, thread)
// tuple. An empty return means "no preamble delivered yet" — the
// caller should treat all priors as new. Safe for concurrent
// callers. A nil receiver returns "" (no-op cache).
func (c *threadContextCache) lastDeliveredFor(target, channel, threadTS string) string {
	if c == nil {
		return ""
	}
	if channel == "" || threadTS == "" {
		return ""
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.lastDelivered[threadCacheKey(target, channel, threadTS)]
}

// markDelivered records ts as the high-water mark for which preamble
// context has been delivered for (target, channel, thread). Idempotent
// when called with a non-increasing ts: the stored value never
// regresses. Safe for concurrent callers. A nil receiver is a no-op.
func (c *threadContextCache) markDelivered(target, channel, threadTS, ts string) {
	if c == nil {
		return
	}
	if channel == "" || threadTS == "" || ts == "" {
		return
	}
	key := threadCacheKey(target, channel, threadTS)
	c.mu.Lock()
	defer c.mu.Unlock()
	if prev, ok := c.lastDelivered[key]; ok && prev >= ts {
		// Slack ts strings are lexically comparable in canonical
		// 17-char "<seconds>.<microseconds>" form; a regression here
		// would mean a stale handler raced ahead of a newer delivery,
		// which is a no-op for cache semantics.
		return
	}
	c.lastDelivered[key] = ts
}

// threadCacheKey is the cache-map key shape for (target, channel,
// thread). Exposed for direct manipulation in tests; "|" is
// disallowed in Slack ids (channel, ts) and absent from typical
// handles, so the joined form is unambiguous in practice.
func threadCacheKey(target, channel, threadTS string) string {
	return target + "|" + channel + "|" + threadTS
}

// slackThreadMessage is the subset of the conversations.replies
// message shape the adapter consumes when building the preamble.
// Other fields are deliberately ignored to keep the JSON contract
// surface narrow.
type slackThreadMessage struct {
	User string `json:"user"`
	Text string `json:"text"`
	TS   string `json:"ts"`
	// BotID is set when the message came from a bot rather than a
	// human user. Bot-authored messages are skipped from the
	// preamble — they're often the adapter's own outbound replies
	// reflected back, which would create feedback loops if a peer
	// agent re-quoted them.
	BotID string `json:"bot_id,omitempty"`
}

// slackConversationsRepliesResp is the top-level conversations.replies
// JSON response.
type slackConversationsRepliesResp struct {
	OK       bool                 `json:"ok"`
	Error    string               `json:"error,omitempty"`
	Messages []slackThreadMessage `json:"messages,omitempty"`
}

// fetchThreadReplies calls Slack's conversations.replies to retrieve
// messages in the thread rooted at threadTS. limit caps the response
// size; non-positive limits fall back to defaultThreadContextLimit.
//
// Returns the message slice exactly as Slack returned it (oldest-
// first by Slack's contract). The caller filters: drop the current
// message and any later replies before formatting.
func fetchThreadReplies(ctx context.Context, token, channel, threadTS string, limit int) ([]slackThreadMessage, error) {
	if token == "" {
		return nil, fmt.Errorf("slack token empty")
	}
	if channel == "" || threadTS == "" {
		return nil, fmt.Errorf("channel and thread_ts required")
	}
	if limit <= 0 {
		limit = defaultThreadContextLimit
	}
	q := url.Values{}
	q.Set("channel", channel)
	q.Set("ts", threadTS)
	q.Set("limit", strconv.Itoa(limit))

	reqURL := slackAPIBase + "/conversations.replies?" + q.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("build conversations.replies request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("conversations.replies: %w", err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, fmt.Errorf("read conversations.replies body: %w", err)
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("conversations.replies HTTP %d: %s", resp.StatusCode, clipBodyForLog(body))
	}
	var sr slackConversationsRepliesResp
	if err := json.Unmarshal(body, &sr); err != nil {
		return nil, fmt.Errorf("decode conversations.replies: %w (body=%s)", err, clipBodyForLog(body))
	}
	if !sr.OK {
		return nil, fmt.Errorf("conversations.replies not ok: %s", sr.Error)
	}
	return sr.Messages, nil
}

// formatThreadContextPreamble builds the bridge-mail preamble from
// messages in the half-open ts window (sinceTS, currentTS). Slack
// ts strings are lexically comparable when in the same canonical
// "<seconds>.<microseconds>" format.
//
// sinceTS == "" means "no lower bound" — include all priors;
// gc-px8.5's first-mention semantics. A non-empty sinceTS limits
// the preamble to peer activity newer than the target's last
// delivered context — gc-px8.6's cross-agent delta visibility.
//
// Bot-authored and whitespace-only messages are filtered. Returns
// "" when no messages survive filtering — caller MUST treat that as
// no-op so empty/short threads, current-message-only callbacks, and
// replays with no new peer activity carry no preamble overhead.
func formatThreadContextPreamble(replies []slackThreadMessage, currentTS, sinceTS string) string {
	var prior []slackThreadMessage
	for _, m := range replies {
		if m.TS == "" {
			continue
		}
		if currentTS != "" && m.TS >= currentTS {
			continue
		}
		if sinceTS != "" && m.TS <= sinceTS {
			continue
		}
		if m.BotID != "" {
			continue
		}
		if strings.TrimSpace(m.Text) == "" {
			continue
		}
		prior = append(prior, m)
	}
	if len(prior) == 0 {
		return ""
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Thread context (%d earlier message", len(prior))
	if len(prior) != 1 {
		b.WriteByte('s')
	}
	b.WriteString("):\n")
	for _, m := range prior {
		author := m.User
		if author == "" {
			author = "?"
		}
		// Collapse internal newlines to " | " so each prior message
		// stays on a single line — the preamble is meant to be
		// scannable, not a verbatim transcript reproduction.
		text := strings.ReplaceAll(strings.TrimSpace(m.Text), "\n", " | ")
		fmt.Fprintf(&b, "@%s: %s\n", author, text)
	}
	b.WriteString("\n---\n\n")
	return b.String()
}

// clipBodyForLog truncates a Slack response body for inclusion in an
// error message. Slack error bodies are typically tiny; the cap is
// defensive against an unexpectedly large response.
func clipBodyForLog(body []byte) string {
	const maxLen = 256
	if len(body) <= maxLen {
		return string(body)
	}
	return string(body[:maxLen]) + "…"
}

package main

import "sync"

// threadHandleStickiness tracks address-by-handle bindings for Slack
// threads, so a human who addresses an agent via `@<handle>:` (or a
// Slack User Group autocomplete that resolves through subteamAliasMap)
// in the top-level message can carry the conversation in the thread
// without re-tagging every reply.
//
// Semantics:
//
//   - When a top-level inbound resolves to a non-empty target AND that
//     target maps through handleAliasRegistry to a session, the
//     adapter registers (channel, msg.TS) -> target. The thread root
//     of all subsequent replies in that thread will be msg.TS, so this
//     is the right key.
//
//   - When a subsequent inbound is a thread reply (msg.ThreadTS !=
//     "" && msg.ThreadTS != msg.TS), the adapter looks up (channel,
//     msg.ThreadTS) BEFORE parsing the explicit-target prefix. If
//     found, the bound handle is treated as the implicit target for
//     this message, AS IF the human had re-tagged. Explicit re-tags
//     in the thread (e.g. `@other-pl:`) take precedence — the parser
//     runs after this lookup and a non-empty parse overwrites.
//
//   - Registration is overwrite-wins: if a human starts a thread with
//     `@mayor:` then later sends `@gc-pl:` in the same thread, the
//     subsequent thread-stickiness binding flips to gc-pl. (Same
//     intuition as "the most recent explicit address is the active
//     one for the thread.")
//
// In-memory only. Adapter restart clears all bindings — acceptable
// for v1 because thread bindings are inherently ephemeral (a
// multi-hour conversation is rare; restart cadence is rarer). If
// future need calls for persistence, mirror the threadSessionRegistry
// disk pattern.
type threadHandleStickiness struct {
	mu      sync.RWMutex
	byKey   map[threadKey]string // (channel, thread_ts) -> handle
}

// newThreadHandleStickiness returns an empty registry.
func newThreadHandleStickiness() *threadHandleStickiness {
	return &threadHandleStickiness{
		byKey: make(map[threadKey]string),
	}
}

// Bind records a thread -> handle association. Empty channel, threadTS,
// or handle is treated as a no-op rather than an error — there's no
// caller for whom an error reply would do anything useful, and silently
// skipping a malformed bind preserves the rest of the routing path.
func (s *threadHandleStickiness) Bind(channelID, threadTS, handle string) {
	if s == nil || channelID == "" || threadTS == "" || handle == "" {
		return
	}
	key := threadKey{ChannelID: channelID, ThreadTS: threadTS}
	s.mu.Lock()
	s.byKey[key] = handle
	s.mu.Unlock()
}

// Lookup returns the bound handle for (channelID, threadTS) plus a
// presence bool. Cheap RLock; safe to call on the hot inbound path.
func (s *threadHandleStickiness) Lookup(channelID, threadTS string) (handle string, ok bool) {
	if s == nil || channelID == "" || threadTS == "" {
		return "", false
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	h, ok := s.byKey[threadKey{ChannelID: channelID, ThreadTS: threadTS}]
	return h, ok
}

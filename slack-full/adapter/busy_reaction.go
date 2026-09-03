package main

import (
	"sync"
	"time"
)

// Busy-reaction lifecycle (hq-xizo).
//
// Multi-party channel threads are the primary surface for talking to
// agents through this adapter, and Slack Assistant mode — whose
// assistant.threads.setStatus would normally render a "working on it"
// status — is deliberately not used. The channel-native
// replacement: when a targeted inbound is dispatched,
// processSlackEvent adds a busy reaction (BUSY_REACTION, default
// "hourglass") to the inbound Slack message and records the pending
// mark here; when the agent's reply is published back into the same
// conversation/thread, handlePublish looks the mark up and removes
// the reaction via reactions.remove — add on dispatch, remove on
// reply.
//
// Entries are keyed by (conversation id, thread key), where the
// thread key is the inbound's thread_ts when it was a thread reply
// and its own ts when it was a channel-root message. A reply publish
// carries reply_to_message_id equal to exactly that thread key in
// both shapes (replies to a root message thread under the root's own
// ts), so a single lookup form covers both.
//
// The registry is memory-only and best-effort by design: a mark whose
// reply never arrives expires after busyReactionTTL (the entry is
// dropped and the reaction simply stops being removable), and an
// adapter restart forgets pending marks. Nothing here may block or
// fail the dispatch or publish paths.

// busyReactionDefault is the emoji added when BUSY_REACTION is unset.
const busyReactionDefault = "hourglass"

// busyReactionTTL bounds how long a pending busy mark stays
// removable. A reply landing later than this is either a very slow
// agent or a session that died mid-task; in both cases silently
// keeping the map entry forever is worse than leaving a stale
// hourglass on one old message.
const busyReactionTTL = 30 * time.Minute

// busyReactionMaxEntries hard-caps the registry so a pathological
// event stream (many distinct targeted inbounds, no replies) cannot
// grow it without bound. Mirrors dmGateMaxEntries: on overflow,
// expired entries are already swept and the oldest surviving mark is
// evicted — that mark's reaction just stops being removable.
const busyReactionMaxEntries = 4096

// busyStaleMaxPerEntry caps how many orphaned ancestor reactions one
// registry entry retains (codex r7): a stream of overlapping failed
// re-targets on a hot thread would otherwise grow the ancestry — and
// copy it on every displacement — without bound. On overflow the
// OLDEST ancestors drop; their reactions simply stop being removable,
// which is the pre-ancestry behavior.
const busyStaleMaxPerEntry = 16

// mergeStale merges add into existing, deduplicating by message ts
// (first occurrence wins) and capping at busyStaleMaxPerEntry by
// dropping from the front (oldest).
func mergeStale(existing, add []busyTaken) []busyTaken {
	if len(add) == 0 && len(existing) <= busyStaleMaxPerEntry {
		return existing
	}
	seen := map[string]bool{}
	merged := make([]busyTaken, 0, len(existing)+len(add))
	for _, t := range existing {
		if !seen[t.messageTS] {
			seen[t.messageTS] = true
			merged = append(merged, t)
		}
	}
	for _, t := range add {
		if !seen[t.messageTS] {
			seen[t.messageTS] = true
			merged = append(merged, t)
		}
	}
	if len(merged) > busyStaleMaxPerEntry {
		merged = merged[len(merged)-busyStaleMaxPerEntry:]
	}
	return merged
}

// busyReactionAddWait bounds how long the remove side waits for the
// corresponding reactions.add call to finish before issuing
// reactions.remove anyway. It MUST exceed slackAPIClient's timeout
// (30s): the add is bounded by that client, so waiting past it means
// addDone has provably closed and remove-after-add ordering holds; a
// shorter bound would reopen the very race this wait exists to
// prevent (codex r6). The timeout branch is therefore effectively
// unreachable and exists only as a leak backstop.
const busyReactionAddWait = 45 * time.Second

// busyReactionKey identifies one conversation/thread with a pending
// busy mark.
type busyReactionKey struct {
	channel   string
	threadKey string
}

// busyReactionMark is one pending busy reaction: the ts of the Slack
// message the reaction was added to, when it was added (for TTL), and
// the channel the add goroutine closes once its reactions.add call has
// returned. The remove side waits on addDone (bounded by
// busyReactionAddWait) before firing reactions.remove, so a reply that
// lands while the add is still in flight cannot have its remove
// overtaken by the delayed add — which would leave a permanent busy
// emoji on the message.
//
// stale carries orphaned predecessor reactions that still ride under
// this key (codex r6): when a re-target's forward fails while an even
// newer mark owns the key, the failed attempt's restore list merges
// here instead of being lost, so every reaction added under the key
// is eventually removed when the key's current mark concludes.
type busyReactionMark struct {
	messageTS string
	// handle is the parsed target handle the mark was recorded for
	// ("" for legacy/unattributed marks). The remove side matches the
	// publishing session against it (via the alias registry) so agent
	// A's late reply cannot clear agent B's pending affordance in the
	// same thread (codex r11).
	handle  string
	addedAt time.Time
	addDone chan struct{}
	stale   []busyTaken
}

// busyThreadKey derives the registry thread key for an inbound
// message: its thread_ts when it is a thread reply, its own ts when
// it is a channel-root message (a reply to it will thread under that
// same ts).
func busyThreadKey(threadTS, messageTS string) string {
	if threadTS != "" {
		return threadTS
	}
	return messageTS
}

// busyReactionRegistry tracks pending busy marks. Safe for concurrent
// callers; the mutex guards the map only — Slack API calls never run
// under it.
//
// A nil *busyReactionRegistry is inert: mark is a no-op and take
// reports no pending mark, so tests (and a misordered main) degrade
// to "no lifecycle" rather than panicking.
type busyReactionRegistry struct {
	mu      sync.Mutex
	entries map[busyReactionKey]busyReactionMark
	// tombstones records keys a reply recently CONSUMED (take /
	// takeConversation). Restoration paths consult them (codex r8): a
	// displaced mark must not be re-parked under a key whose thread
	// already got its reply while the displacing dispatch was in
	// flight — the reply was that thread's one clearing event, so a
	// restored mark would never be consumed and its reaction would
	// stick forever. Blocked marks are returned to the caller for
	// immediate removal instead. Entries expire after
	// busyTombstoneTTL and are swept opportunistically.
	tombstones map[busyReactionKey]time.Time
	// now is the clock; nil means time.Now. Injectable so tests can
	// drive TTL expiry without sleeping.
	now func() time.Time
}

// busyTombstoneTTL bounds how long a consumed key blocks restoration.
// The races it guards close within one bounded dispatch round trip
// (≤ the 20s gc-forward timeout plus scheduling slack); 5 minutes is
// comfortably past that while keeping the map small.
const busyTombstoneTTL = 5 * time.Minute

// busyTombstoneMaxEntries hard-caps the tombstone map (codex r9):
// every consumed thread writes one, so sustained traffic would grow
// it unboundedly between mark-site sweeps, and traffic stopping would
// strand expired entries. tombstoneLocked sweeps expired entries on
// every insert and evicts the oldest at the cap — an evicted
// tombstone just stops blocking one restoration, the pre-tombstone
// behavior.
const busyTombstoneMaxEntries = 4096

// tombstoneLocked records a consumed key, sweeping expired tombstones
// and enforcing the cap. Called with r.mu held.
func (r *busyReactionRegistry) tombstoneLocked(key busyReactionKey, now time.Time) {
	for k, at := range r.tombstones {
		if now.Sub(at) > busyTombstoneTTL {
			delete(r.tombstones, k)
		}
	}
	r.tombstones[key] = now
	if len(r.tombstones) > busyTombstoneMaxEntries {
		var oldestK busyReactionKey
		var oldestAt time.Time
		first := true
		for k, at := range r.tombstones {
			if first || at.Before(oldestAt) {
				oldestK, oldestAt, first = k, at, false
			}
		}
		if !first {
			delete(r.tombstones, oldestK)
		}
	}
}

func newBusyReactionRegistry() *busyReactionRegistry {
	return &busyReactionRegistry{
		entries:    make(map[busyReactionKey]busyReactionMark),
		tombstones: make(map[busyReactionKey]time.Time),
	}
}

func (r *busyReactionRegistry) clock() time.Time {
	if r.now != nil {
		return r.now()
	}
	return time.Now()
}

// mark records a pending busy reaction on messageTS under
// (channel, threadKey), sweeping expired entries opportunistically
// and evicting the oldest surviving mark if the map is still over
// cap. A re-mark of the same key (human re-tags the agent in the same
// thread before the first reply lands) overwrites — the reaction sits
// on the newest targeted message and the reply clears that one.
//
// busyTaken is one consumed mark: the ts the reaction sits on and the
// channel its add goroutine closes on completion (remove-after-add
// ordering).
type busyTaken struct {
	messageTS string
	handle    string
	addDone   chan struct{}
}

// busyDisplaced is a mark displaced by a re-target, together with the
// registry key it was displaced from — enough to restore it if the
// displacing inbound's forward then fails (codex r5).
type busyDisplaced struct {
	threadKey string
	mark      busyTaken
}

// The returned channel is the mark's addDone: the caller's add
// goroutine MUST close it once its reactions.add call has returned so
// the remove side can order remove-after-add. Always non-nil — a
// nil/invalid-args no-op still returns a fresh channel so the caller
// can close it unconditionally. Any mark this overwrites is silently
// discarded — production code uses markBoth, which surfaces
// superseded marks so their reactions can be cleaned up.
func (r *busyReactionRegistry) mark(channel, threadKey, messageTS string) chan struct{} {
	addDone := make(chan struct{})
	r.markWithDone(channel, threadKey, messageTS, "", addDone)
	return addDone
}

// markBoth records the pending mark under EVERY thread key a reply may
// carry (codex r2). The canonical key is the thread root (thread_ts
// for a thread-reply inbound, own ts for a channel-root one) — but
// reply-current and the alias-dispatch instructions thread replies
// under the inbound's OWN ts (Slack normalizes either form into the
// same thread), so a thread-reply inbound is additionally marked under
// its own ts. Both entries share one addDone; consuming one leaves the
// sibling to expire by TTL, whose eventual redundant reactions.remove
// is benign ("no_reaction" counts as delivered).
//
// superseded returns the marks these writes displaced (a human
// re-targeting the same thread before the first reply lands, codex
// r3): those messages already carry a busy reaction that no registry
// entry points at anymore. Once the displacing inbound's forward
// SUCCEEDS the caller must remove those reactions (TTL expiry only
// deletes metadata, never the Slack-side emoji); if the forward
// fails, the caller restores them via cancelBoth instead (codex r5).
// Deduplicated by message ts and never includes messageTS itself.
func (r *busyReactionRegistry) markBoth(channel, threadTS, messageTS, handle string) (addDone chan struct{}, superseded []busyDisplaced) {
	addDone = make(chan struct{})
	seen := map[string]bool{messageTS: true}
	collect := func(key string, old busyTaken, ok bool) {
		if ok && !seen[old.messageTS] {
			seen[old.messageTS] = true
			superseded = append(superseded, busyDisplaced{threadKey: key, mark: old})
		}
	}
	rootKey := busyThreadKey(threadTS, messageTS)
	for _, old := range r.markWithDone(channel, rootKey, messageTS, handle, addDone) {
		collect(rootKey, old, true)
	}
	if threadTS != "" && threadTS != messageTS {
		for _, old := range r.markWithDone(channel, messageTS, messageTS, handle, addDone) {
			collect(messageTS, old, true)
		}
	}
	return addDone, superseded
}

// markWithDone is the mark implementation with a caller-supplied
// addDone, letting markBoth share one channel across its two entries.
// Returns every displaced pending reaction — the previous mark (when
// its reaction sits on a DIFFERENT message) plus any stale ancestors
// riding on it (codex r6). A re-mark of the SAME message (a retaken
// Slack redelivery re-marking after a failed dispatch, codex r4)
// merges completion channels instead of overwriting — the earlier
// reactions.add may still be in flight and could land after a remove
// that only waited for the newer add — and keeps the previous entry's
// stale ancestors.
func (r *busyReactionRegistry) markWithDone(channel, threadKey, messageTS, handle string, addDone chan struct{}) (displaced []busyTaken) {
	if r == nil || channel == "" || threadKey == "" || messageTS == "" {
		return nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	now := r.clock()
	r.sweepLocked(now)
	key := busyReactionKey{channel: channel, threadKey: threadKey}
	storeDone := addDone
	var keepStale []busyTaken
	if prev, present := r.entries[key]; present {
		switch {
		case prev.messageTS != messageTS:
			displaced = append([]busyTaken{{messageTS: prev.messageTS, handle: prev.handle, addDone: prev.addDone}}, prev.stale...)
		default:
			keepStale = prev.stale
			if prev.addDone != nil && prev.addDone != addDone {
				prevDone := prev.addDone
				merged := make(chan struct{})
				go func() {
					<-prevDone
					<-addDone
					close(merged)
				}()
				storeDone = merged
			}
		}
	}
	r.entries[key] = busyReactionMark{messageTS: messageTS, handle: handle, addedAt: now, addDone: storeDone, stale: keepStale}
	// A fresh targeted inbound re-arms the thread: the next reply is a
	// legitimate clearing event, so any consumed-key tombstone stops
	// applying (tombstones only block RESTORING old marks, codex r8).
	delete(r.tombstones, key)
	if len(r.entries) > busyReactionMaxEntries {
		r.evictOldestLocked()
	}
	return displaced
}

// cancelBoth removes the entries markBoth created for (channel,
// threadTS, messageTS) — the inbound never reached gc, so no reply
// will ever come to clear them — restores any marks that inbound had
// displaced (their agents may still be working and their reactions
// were deliberately NOT removed yet, codex r5), and closes addDone so
// any waiter that already consumed a mark proceeds to its benign
// no-op remove (the reactions.add for a cancelled mark never fires).
// Entries are deleted only while they still point at messageTS, and a
// restore never clobbers a key a racing retry has already re-marked.
// Callers must run this BEFORE releasing the event's dedup claim, so
// a woken redelivery cannot re-mark the timestamp while the old
// attempt's cancellation is still in flight.
func (r *busyReactionRegistry) cancelBoth(channel, threadTS, messageTS string, addDone chan struct{}, restore []busyDisplaced) (blocked []busyTaken) {
	if r != nil && channel != "" && messageTS != "" {
		r.mu.Lock()
		now := r.clock()
		keys := []string{busyThreadKey(threadTS, messageTS)}
		if threadTS != "" && threadTS != messageTS {
			keys = append(keys, messageTS)
		}
		// Restore pool: the marks this failed inbound displaced, plus
		// any stale ancestors that were riding on the cancelled
		// entries themselves (merged there by an even earlier failed
		// re-target, codex r6). Grouped per key.
		perKey := map[string][]busyTaken{}
		for _, d := range restore {
			perKey[d.threadKey] = append(perKey[d.threadKey], d.mark)
		}
		for _, k := range keys {
			key := busyReactionKey{channel: channel, threadKey: k}
			if m, ok := r.entries[key]; ok && m.messageTS == messageTS {
				delete(r.entries, key)
				perKey[k] = append(perKey[k], m.stale...)
			}
		}
		blocked = r.restoreLocked(channel, now, perKey)
		r.mu.Unlock()
	}
	if addDone != nil {
		close(addDone)
	}
	return blocked
}

// restoreLocked re-parks per-key mark pools: an unowned key gets the
// pool's first mark as its entry (rest as stale ancestry); a key a
// racing retry or newer re-target owns is never clobbered — the pool
// merges into its stale ancestry so its conclusion still clears them.
// A key whose thread was CONSUMED by a reply after the displacement
// (live tombstone, codex r8) blocks restoration entirely — that reply
// was the thread's one clearing event, so a restored mark would never
// be consumed; the blocked marks are returned for the caller to
// remove their reactions instead. Ancestry is deduplicated and
// bounded (busyStaleMaxPerEntry). Called with r.mu held.
func (r *busyReactionRegistry) restoreLocked(channel string, now time.Time, perKey map[string][]busyTaken) (blocked []busyTaken) {
	for k, marks := range perKey {
		if len(marks) == 0 {
			continue
		}
		key := busyReactionKey{channel: channel, threadKey: k}
		if at, dead := r.tombstones[key]; dead && now.Sub(at) <= busyTombstoneTTL {
			blocked = append(blocked, marks...)
			continue
		}
		if cur, taken := r.entries[key]; taken {
			cur.stale = mergeStale(cur.stale, marks)
			r.entries[key] = cur
			continue
		}
		r.entries[key] = busyReactionMark{
			messageTS: marks[0].messageTS,
			handle:    marks[0].handle,
			addedAt:   now,
			addDone:   marks[0].addDone,
			stale:     mergeStale(nil, marks[1:]),
		}
	}
	return blocked
}

// restoreDisplaced re-parks marks a failed delivery had displaced
// (codex r7): the displacing message's affordance is being rolled
// back, but the displaced agents may still be working and their
// reactions were deliberately not removed. Marks blocked by a
// consumed-key tombstone are returned — the caller must remove their
// reactions (codex r8).
func (r *busyReactionRegistry) restoreDisplaced(channel string, restore []busyDisplaced) (blocked []busyTaken) {
	if r == nil || channel == "" || len(restore) == 0 {
		return nil
	}
	perKey := map[string][]busyTaken{}
	for _, d := range restore {
		perKey[d.threadKey] = append(perKey[d.threadKey], d.mark)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.restoreLocked(channel, r.clock(), perKey)
}

// takeConversation removes and returns every pending mark in channel,
// deduplicated by message ts (dual-key entries share one message).
// Backs the unthreaded-reply path (codex r3): the documented default
// `gc slack reply-current` posts at channel root with no thread ts,
// so a delivered root publish clears every busy affordance pending in
// that conversation rather than leaving hourglasses stuck forever.
// Expired entries are dropped, not returned.

// splitByAllow partitions marks into those the publisher may clear
// (unattributed, or allow reports a match) and those that must stay
// parked for their own agents (codex r16). A nil allow clears
// everything.
func splitByAllow(marks []busyTaken, allow func(handle string) bool) (want, keep []busyTaken) {
	for _, t := range marks {
		if allow == nil || t.handle == "" || allow(t.handle) {
			want = append(want, t)
		} else {
			keep = append(keep, t)
		}
	}
	return want, keep
}

// allow gates consumption by the mark's target handle (codex r11):
// a live mark whose handle the publisher does not match is left in
// place — untouched, untombstoned — for its own agent's reply (or
// TTL) to clear. A nil allow consumes everything (legacy behavior).
func (r *busyReactionRegistry) takeConversation(channel string, allow func(handle string) bool) []busyTaken {
	if r == nil || channel == "" {
		return nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	now := r.clock()
	seen := map[string]bool{}
	var taken []busyTaken
	for k, m := range r.entries {
		if k.channel != channel {
			continue
		}
		if now.Sub(m.addedAt) > busyReactionTTL {
			delete(r.entries, k)
			r.tombstoneLocked(k, now)
			continue
		}
		// Partition the entry's pool — its own mark plus stale
		// ancestors — per mark (codex r16): overlapping re-targets can
		// leave another agent's orphaned reaction riding in m.stale,
		// and it must neither be cleared by this publisher nor block
		// this publisher's own marks.
		pool := append([]busyTaken{{messageTS: m.messageTS, handle: m.handle, addDone: m.addDone}}, m.stale...)
		want, keep := splitByAllow(pool, allow)
		if len(want) == 0 {
			continue
		}
		delete(r.entries, k)
		if len(keep) > 0 {
			// Re-park the survivors under the key for their own
			// agents' replies (or TTL); the thread is not consumed.
			r.entries[k] = busyReactionMark{
				messageTS: keep[0].messageTS,
				handle:    keep[0].handle,
				addedAt:   now,
				addDone:   keep[0].addDone,
				stale:     mergeStale(nil, keep[1:]),
			}
		} else {
			r.tombstoneLocked(k, now)
		}
		for _, t := range want {
			if !seen[t.messageTS] {
				seen[t.messageTS] = true
				taken = append(taken, t)
			}
		}
	}
	return taken
}

// takeMessage removes the entries markBoth created for (channel,
// threadTS, messageTS) while they still point at messageTS, returning
// that message's pending reaction for removal. Backs the
// alias-delivery-failure path (codex r6): the reactions.add already
// launched but no reply is coming (the addressed session never got
// the message and the bound session stays silent), so the emoji must
// come off now. Stale ancestors riding on a consumed entry are NOT
// removed — their messages' fate is independent — they are re-parked
// under the key so a later conclusion still clears them.
func (r *busyReactionRegistry) takeMessage(channel, threadTS, messageTS string) []busyTaken {
	if r == nil || channel == "" || messageTS == "" {
		return nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	now := r.clock()
	keys := []string{busyThreadKey(threadTS, messageTS)}
	if threadTS != "" && threadTS != messageTS {
		keys = append(keys, messageTS)
	}
	var taken []busyTaken
	seen := map[string]bool{}
	for _, k := range keys {
		key := busyReactionKey{channel: channel, threadKey: k}
		m, ok := r.entries[key]
		if !ok || m.messageTS != messageTS {
			continue
		}
		delete(r.entries, key)
		expired := now.Sub(m.addedAt) > busyReactionTTL
		if !expired && !seen[m.messageTS] {
			seen[m.messageTS] = true
			taken = append(taken, busyTaken{messageTS: m.messageTS, handle: m.handle, addDone: m.addDone})
		}
		if len(m.stale) > 0 && !expired {
			// Re-park the ancestors: first becomes the key's mark,
			// the rest stay stale on it.
			r.entries[key] = busyReactionMark{
				messageTS: m.stale[0].messageTS,
				handle:    m.stale[0].handle,
				addedAt:   now,
				addDone:   m.stale[0].addDone,
				stale:     mergeStale(nil, m.stale[1:]),
			}
		}
	}
	return taken
}

// take removes and returns every pending reaction for (channel,
// threadKey) — the current mark plus any stale ancestors riding on it
// (codex r6) — and also consumes every OTHER entry in the channel
// pointing at the same message (codex r10): markBoth records a
// thread-reply inbound under both its thread root and its own ts, and
// a reply threading under one alias is the clearing event for both;
// leaving the sibling behind would strand it (and any ancestors an
// overlapping failed re-target parked on it) with no later clearing
// event. All consumed keys are tombstoned. An expired entry is
// deleted but NOT returned — the caller must not fire a
// reactions.remove for a mark past its TTL (its stale ancestors
// expire with it).
// allow gates consumption by the mark's target handle (codex r11): a
// live mark whose handle the publisher does not match is left in
// place — untouched, untombstoned — so agent A's late reply into a
// thread re-targeted at agent B cannot strip B's affordance. A nil
// allow consumes unconditionally (legacy behavior).
func (r *busyReactionRegistry) take(channel, threadKey string, allow func(handle string) bool) []busyTaken {
	if r == nil {
		return nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	key := busyReactionKey{channel: channel, threadKey: threadKey}
	m, present := r.entries[key]
	if !present {
		return nil
	}
	now := r.clock()
	seen := map[string]bool{}
	var taken []busyTaken
	// consume partitions one entry's pool per mark (codex r16): marks
	// the publisher owns (or unattributed ones) are collected; another
	// agent's marks — the entry's own or stale ancestors from
	// overlapping re-targets — are re-parked under the key untombstoned
	// so their own replies (or TTL) still clear them. Reports whether
	// anything was consumed.
	consume := func(k busyReactionKey, cm busyReactionMark) bool {
		if now.Sub(cm.addedAt) > busyReactionTTL {
			delete(r.entries, k)
			r.tombstoneLocked(k, now)
			return false
		}
		pool := append([]busyTaken{{messageTS: cm.messageTS, handle: cm.handle, addDone: cm.addDone}}, cm.stale...)
		want, keep := splitByAllow(pool, allow)
		if len(want) == 0 {
			return false
		}
		delete(r.entries, k)
		if len(keep) > 0 {
			r.entries[k] = busyReactionMark{
				messageTS: keep[0].messageTS,
				handle:    keep[0].handle,
				addedAt:   now,
				addDone:   keep[0].addDone,
				stale:     mergeStale(nil, keep[1:]),
			}
		} else {
			r.tombstoneLocked(k, now)
		}
		for _, t := range want {
			if !seen[t.messageTS] {
				seen[t.messageTS] = true
				taken = append(taken, t)
			}
		}
		return true
	}
	if !consume(key, m) {
		return taken
	}
	for k, sib := range r.entries {
		if k.channel != channel || sib.messageTS != m.messageTS {
			continue
		}
		consume(k, sib)
	}
	return taken
}

// pending reports the recorded message ts for (channel, threadKey)
// without consuming or TTL-checking the entry. Test/observability
// helper.
func (r *busyReactionRegistry) pending(channel, threadKey string) (messageTS string, ok bool) {
	if r == nil {
		return "", false
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	m, present := r.entries[busyReactionKey{channel: channel, threadKey: threadKey}]
	if !present {
		return "", false
	}
	return m.messageTS, true
}

// size reports the number of pending marks. Test helper.
func (r *busyReactionRegistry) size() int {
	if r == nil {
		return 0
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.entries)
}

// sweepLocked drops expired marks and tombstones. Called with r.mu held.
func (r *busyReactionRegistry) sweepLocked(now time.Time) {
	for k, m := range r.entries {
		if now.Sub(m.addedAt) > busyReactionTTL {
			delete(r.entries, k)
		}
	}
	for k, at := range r.tombstones {
		if now.Sub(at) > busyTombstoneTTL {
			delete(r.tombstones, k)
		}
	}
}

// evictOldestLocked drops the single oldest mark. Called with r.mu
// held, only on the insert that pushed the map past the cap (expired
// entries were already swept by mark).
func (r *busyReactionRegistry) evictOldestLocked() {
	var oldestKey busyReactionKey
	var oldestAt time.Time
	first := true
	for k, m := range r.entries {
		if first || m.addedAt.Before(oldestAt) {
			oldestKey, oldestAt, first = k, m.addedAt, false
		}
	}
	if !first {
		delete(r.entries, oldestKey)
	}
}

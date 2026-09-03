package main

import (
	"sync"
	"time"
)

// Events API redelivery dedup (hw-94w5k finding #4).
//
// Slack retries any /slack/events delivery it considers unacknowledged
// — the initial POST timing out, a dropped connection, or a non-2xx —
// up to three times (immediately, ~1 minute, ~5 minutes), and every
// retry carries the same event_id. handleSlackEvents acks with a 200
// before processing, but an ack lost in transit still produces a
// retry, and without a seen-set that retry re-forwards the same
// message into the bound session as a duplicate notification
// (observed as byte-identical inbound log pairs).
//
// Entries are two-state so a retry can never be dropped while the
// outcome it would recover from is still undecided (codex r2 P1):
//
//   - in-flight: a delivery is processing. A concurrent redelivery
//     waits on the entry's done channel instead of being discarded —
//     if the first forward fails (forget), the waiter takes over; if
//     it succeeds (commit), the waiter drops as a duplicate.
//   - committed: the event reached gc. Redeliveries within the TTL
//     drop immediately.
//
// Processing failure calls forget, which erases the entry entirely —
// the retry (waiting or future) is then the recovery path.

// eventDedupTTL bounds how long a committed event_id is remembered.
// Slack's last retry fires ~5 minutes after the original delivery;
// 10 minutes covers the ladder with slack for clock skew and queue
// delay while keeping the map small.
const eventDedupTTL = 10 * time.Minute

// eventDedupParkLogInterval paces the "still parked" log line for a
// redelivery waiting on an in-flight claim. The wait itself is
// UNBOUNDED by design (codex r4): the redelivery already returned a
// 200, so Slack will never resend it — dropping it while the owner's
// outcome is undecided would permanently lose the event if that owner
// then fails. Every claim concludes deterministically (the gc forward
// calls are bounded by gcForwardClient and processSlackEvent concludes
// on every return path), so parked goroutines cannot leak; the parked
// waiter holds no dispatch slot (released before parking, re-acquired
// on takeover).
const eventDedupParkLogInterval = 30 * time.Second

// eventDedupMaxEntries hard-caps the seen-set so a pathological event
// flood cannot grow it without bound. At the cap, the oldest committed
// entry is evicted — that event's redeliveries just stop being
// deduplicable, which is the pre-cache behavior. 4096 ids at ~10
// minutes of traffic is far beyond any realistic workspace's rate.
const eventDedupMaxEntries = 4096

// eventDedupEntry is one tracked event_id. committedAt is zero while
// the owning delivery is still processing; done is closed exactly once
// when the entry leaves the in-flight state (commit or forget).
type eventDedupEntry struct {
	committedAt time.Time
	done        chan struct{}
	closed      bool
}

// eventDedupCache tracks Slack event ids across the in-flight →
// committed lifecycle. Safe for concurrent callers. A nil
// *eventDedupCache never dedupes, so tests (and a misordered main)
// degrade to "no dedup" rather than panicking.
type eventDedupCache struct {
	mu      sync.Mutex
	entries map[string]*eventDedupEntry
	// channelLegDone remembers event ids whose postInbound leg
	// SUCCEEDED before a later leg (the alias dispatch) failed and
	// forgot the entry (codex r12). The retaken redelivery must skip
	// the channel leg — core does not consume DedupKey (see
	// docs/phase5-ledger-readiness.md), so re-running postInbound
	// duplicates the bound session's turn — and retry only the alias
	// leg. Markers expire with the same TTL as committed entries and
	// are cleared on commit.
	channelLegDone map[string]time.Time
	ttl            time.Duration
	// now is the clock; nil means time.Now. Injectable so tests can
	// drive TTL expiry without sleeping.
	now func() time.Time
}

func newEventDedupCache(ttl time.Duration) *eventDedupCache {
	return &eventDedupCache{
		entries:        make(map[string]*eventDedupEntry),
		channelLegDone: make(map[string]time.Time),
		ttl:            ttl,
	}
}

// markChannelLegDone records that id's postInbound leg succeeded, so
// a retaken redelivery (after forget) skips it and retries only the
// failed alias leg. Must be called BEFORE forget(id) wakes a parked
// retry.
func (c *eventDedupCache) markChannelLegDone(id string) {
	if c == nil || id == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	now := c.clock()
	for k, at := range c.channelLegDone {
		if now.Sub(at) > c.ttl {
			delete(c.channelLegDone, k)
		}
	}
	c.channelLegDone[id] = now
	if len(c.channelLegDone) > eventDedupMaxEntries {
		for k := range c.channelLegDone {
			delete(c.channelLegDone, k)
			if len(c.channelLegDone) <= eventDedupMaxEntries {
				break
			}
		}
	}
}

// isChannelLegDone reports whether id's channel leg already reached
// gc within the TTL.
func (c *eventDedupCache) isChannelLegDone(id string) bool {
	if c == nil || id == "" {
		return false
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	at, ok := c.channelLegDone[id]
	return ok && c.clock().Sub(at) <= c.ttl
}

func (c *eventDedupCache) clock() time.Time {
	if c.now != nil {
		return c.now()
	}
	return time.Now()
}

// begin claims id for processing. Exactly one of:
//
//   - proceed=true: the caller owns this event and MUST conclude it
//     with commit (success) or forget (failure).
//   - proceed=false, wait=nil: a delivery already committed within the
//     TTL — drop this one as a duplicate.
//   - proceed=false, wait!=nil: another delivery is in flight — wait
//     on the channel (bounded) and call begin again for the verdict.
//
// A nil cache and an empty id always proceed (no dedup, nothing to
// conclude — commit/forget on them are no-ops).
func (c *eventDedupCache) begin(id string) (proceed bool, wait <-chan struct{}) {
	if c == nil || id == "" {
		return true, nil
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	now := c.clock()
	for k, e := range c.entries {
		if !e.committedAt.IsZero() && now.Sub(e.committedAt) > c.ttl {
			delete(c.entries, k)
		}
	}
	if e, ok := c.entries[id]; ok {
		if e.committedAt.IsZero() {
			return false, e.done
		}
		return false, nil
	}
	c.entries[id] = &eventDedupEntry{done: make(chan struct{})}
	if len(c.entries) > eventDedupMaxEntries {
		c.evictOldestLocked()
	}
	return true, nil
}

// commit marks id as successfully processed: redeliveries within the
// TTL now drop, and any waiter re-begins into the committed verdict.
// No-op for unknown ids (evicted under cap pressure, or empty).
func (c *eventDedupCache) commit(id string) {
	if c == nil || id == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[id]
	if !ok {
		return
	}
	e.committedAt = c.clock()
	delete(c.channelLegDone, id)
	if !e.closed {
		e.closed = true
		close(e.done)
	}
}

// forget erases id entirely: processing failed and nothing reached gc,
// so a redelivery (waiting or future) must be treated as brand new —
// it is the only recovery path for the message. No-op for unknown ids.
func (c *eventDedupCache) forget(id string) {
	if c == nil || id == "" {
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[id]
	if !ok {
		return
	}
	delete(c.entries, id)
	if !e.closed {
		e.closed = true
		close(e.done)
	}
}

// size reports the number of tracked ids. Test helper.
func (c *eventDedupCache) size() int {
	if c == nil {
		return 0
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.entries)
}

// evictOldestLocked drops the single oldest committed entry, falling
// back to any entry only if every entry is in-flight (pathological).
// Called with c.mu held, only on the insert that pushed the map past
// the cap (expired entries were already swept by begin).
func (c *eventDedupCache) evictOldestLocked() {
	var oldestID string
	var oldestAt time.Time
	first := true
	for k, e := range c.entries {
		if e.committedAt.IsZero() {
			continue
		}
		if first || e.committedAt.Before(oldestAt) {
			oldestID, oldestAt, first = k, e.committedAt, false
		}
	}
	if first {
		// No committed entries at all: evict an arbitrary in-flight
		// one rather than growing without bound. Its conclusion
		// (commit/forget) becomes a harmless no-op.
		for k, e := range c.entries {
			delete(c.entries, k)
			if !e.closed {
				e.closed = true
				close(e.done)
			}
			return
		}
	}
	delete(c.entries, oldestID)
}

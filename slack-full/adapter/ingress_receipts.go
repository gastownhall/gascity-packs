package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// IngressReceiptStore is the durable ingress ledger for company-room
// events (Slack company-rooms Phase 1b). Every admissible company-room
// POST becomes exactly one receipt on disk before the transport is
// acknowledged; the file system is the deduplication authority across
// Slack redeliveries and adapter restarts.
//
// Durability contract:
//
//   - Admit is the admission linearization point and is claim-and-content
//     atomic. The complete receipt (including the full inner Slack event
//     and outer identifiers, which routing and crash replay both require)
//     is written to a temp file, fsynced, then hard-linked (os.Link) to
//     its origin-keyed final name. os.Link is atomic and fails with
//     EEXIST if the name already exists, so the first writer wins and a
//     redelivery observes the existing receipt. There is no window in
//     which a claim (the final name) exists without its content (the
//     linked inode already holds the fully-fsynced bytes).
//   - Update is a generation-checked atomic rewrite (temp + rename + fsync
//     of file and directory). A lost race is detected via the generation
//     counter (ErrStale) rather than silently overwritten.
//   - Files are 0600 inside a 0700 directory. Filenames derive from the
//     origin through safeStorageID, which hashes long or hostile
//     components so a crafted ts/channel can neither escape the directory
//     nor produce an unbounded name.
//
// A crash between the temp write and the link, or between a rename's
// components, leaves at most a stray "ingress-*.tmp" orphan — never a
// half-written receipt. The orphan is harmless (it is ignored by every
// scan) and swept by the adapter's tmp janitor.
type IngressReceiptStore struct {
	dir string

	// mu serializes all file operations so that Update's read-modify-write
	// is atomic within the process. Cross-process safety rests on os.Link
	// atomicity (Admit) and the generation counter (Update); the delivery
	// workers additionally hold an in-process single-flight claim per
	// receipt id (Phase 1d).
	mu sync.Mutex

	// writeFailures counts failed Admit/Update persistence attempts. It is
	// read without the lock by the gateway status payload and /healthz, so
	// it is an atomic counter rather than a mutex-guarded field.
	writeFailures atomic.Uint64

	// bodyDigestMismatches counts body sidecars whose bytes failed to hash to
	// their receipt's immutable event_digest, observed on the READ path (loadBody
	// verifies the digest; the sweep no longer hashes — m6). Monotonic, read
	// lock-free by /healthz, so a digest-integrity error stays observable even
	// though the existence-only sweep gauge cannot detect it.
	bodyDigestMismatches atomic.Uint64
}

// Receipt status values. Non-terminal receipts (received, routing) are
// still in flight and are returned by Pending; terminal receipts
// (delivered, no_delivery, failed) are the dedup memory swept after
// retention.
const (
	ingressStatusReceived   = "received"
	ingressStatusRouting    = "routing"
	ingressStatusDelivered  = "delivered"
	ingressStatusNoDelivery = "no_delivery"
	ingressStatusFailed     = "failed"
)

// Receipt-level conversation kinds (IngressReceipt.Kind). Empty is the
// room / legacy default carried by every Phase 1-3 receipt; "dm" marks a
// per-agent DM receipt (Phase 4) and "mpim" a group-DM receipt (Phase 4b).
// Each literal is also the wake kind on the target and the current-turn
// pointer kind, so one value spans receipt, target, and pointer. The two
// direct-message kinds form the "dm family" (isDMFamilyKind): they share the
// DM delivery worker, owner-token custody, and dm_bindings wake registry.
const (
	receiptKindDM   = "dm"
	receiptKindMpim = "mpim"
)

// isDMFamilyKind reports whether a receipt/target/pointer kind belongs to the
// direct-message family (per-agent DM or group DM). Every seam that once tested
// Kind == "dm" now tests this predicate (spec §Kind-dispatch inventory): the DM
// worker dispatch, the owner-token ack actor, the dm_bindings redrive
// re-resolution, and the shared degradation counters all cover both kinds.
func isDMFamilyKind(kind string) bool {
	return kind == receiptKindDM || kind == receiptKindMpim
}

// ingressRetentionFloor is the minimum accepted Sweep retention. Terminal
// receipts are the dedup memory for Slack's Delayed Events redelivery
// horizon (hourly retries for 24h), so retention below 24h is rejected —
// sweeping sooner would let a late redelivery re-admit an already-handled
// event.
const ingressRetentionFloor = 24 * time.Hour

// maxIngressReceiptBytes caps the on-disk receipt size accepted at read.
// A Slack event envelope is a few KiB; 4 MiB is several orders of
// magnitude over that and a larger file is presumed corrupt.
const maxIngressReceiptBytes = 4 << 20 // 4 MiB

// maxSafeComponentLen bounds a readable origin component. A longer value
// is hashed rather than embedded verbatim so a hostile ts/channel cannot
// produce an unbounded filename.
const maxSafeComponentLen = 64

// ingressReceiptSchemaBodyRef marks a body-split receipt: its raw inner event
// lives in the bodies/ sidecar (body_ref + event_digest) rather than embedded.
// A receipt with no schema_version is a legacy embedded receipt and stays valid
// forever — readers accept both shapes.
const ingressReceiptSchemaBodyRef = 1

// bodiesDirName is the sidecar subdirectory under the store dir; bodyFileSuffix
// names one body file (<receipt_id>.body.json). Bodies are 0600 inside the 0700
// bodies dir, written atomically BEFORE their receipt in the admission sequence.
const (
	bodiesDirName  = "bodies"
	bodyFileSuffix = ".body.json"
)

// bodyGCGraceWindow age-gates orphan-body GC (m1): a body younger than this is
// never collected, so an in-flight cross-process admission (deploy overlap, or a
// second tool) always has time to link its receipt after its body appears in the
// bodies-dir scan. Comfortably larger than the 60s delivery sweep interval; one
// lstat per rare orphan candidate is the standard janitor-vs-writer mitigation.
const bodyGCGraceWindow = 5 * time.Minute

// redactReconciliationHorizon is the minimum receipt age below which redaction is
// refused. It mirrors the Python outbound INTENT_TTL_SECONDS (24h) — the window
// during which a stuck "posting" intent could still reconcile against this
// receipt's body via _scan_receipt_for_nonce. Truncating the body inside that
// window would erase the only copy of the reconciliation nonce and wedge the
// intent forever (a self-echo goes terminal in seconds but must not be redactable
// until its reconciliation window has closed).
const redactReconciliationHorizon = 24 * time.Hour

// bodyStatus classifies a receipt's body resolution (see loadBody).
type bodyStatus int

const (
	bodyEmbedded bodyStatus = iota // legacy receipt: event is inline in Event
	bodyOK                         // body-split: sidecar present, digest verified
	bodyMissing                    // body-split: sidecar absent (hard integrity error)
	bodyRedacted                   // body-split: sidecar is the redacted tombstone
	bodyMismatch                   // body-split: sidecar bytes hash != event_digest
)

// bodyIntegrityCounts is the sweep-computed body gauge for /healthz:
// company_body_missing folds body-absent and digest-mismatch (both integrity
// errors), company_bodies_redacted counts explicit tombstones.
type bodyIntegrityCounts struct {
	Missing  int
	Redacted int
}

// redactedBodyMarker is the fixed tombstone a redacted body file is truncated
// to. The original event_digest survives so the receipt still proves what the
// body once held (late-redelivery dedup semantics are unchanged).
type redactedBodyMarker struct {
	Redacted    bool   `json:"redacted"`
	EventDigest string `json:"event_digest"`
}

// ErrStale is returned by Update when the on-disk generation differs from
// the caller's receipt generation. The caller re-reads, merges, and
// retries — a lost race is never silently overwritten.
var ErrStale = errors.New("ingress receipts: stale generation")

// ErrReceiptSwept is returned by redactReceiptBody when the receipt (or its body)
// vanished between the caller's read and the mutex-guarded redact — a retention
// pair-delete raced the verb. The admin handler maps it to 404 so the operator is
// told the truth ("terminal and swept") rather than a false 200 (m2).
var ErrReceiptSwept = errors.New("ingress receipts: receipt swept during redact")

// ReceiptOrigin is the canonical dedup key for a company-room event:
// (team_id, channel_id, ts). ts is unique per channel; the observing app
// is never a key input.
type ReceiptOrigin struct {
	TeamID    string `json:"team_id"`
	ChannelID string `json:"channel_id"`
	TS        string `json:"ts"`
}

// TargetDelivery records the per-session delivery state of a receipt.
type TargetDelivery struct {
	Session string `json:"session"`
	// City optionally targets a session in a different gc city than the
	// adapter's own (city-qualified binding); empty = the adapter's city.
	City string `json:"city,omitempty"`
	// Kind is the frozen wake kind: "ambient" | "thread_ambient" | "targeted"
	// (human legs) or "peer_delegation" | "peer_result" | "peer_input"
	// (company-bot legs, Phase 2c). Only peer_delegation / peer_result carry a
	// DelegationKey.
	Kind           string    `json:"kind"`
	Status         string    `json:"status"`          // "pending" | "delivered" | "failed"
	IdempotencyKey string    `json:"idempotency_key"` // ingress:<id>:target:<session>
	Attempts       int       `json:"attempts"`
	UpdatedAt      time.Time `json:"updated_at"`
	Detail         string    `json:"detail,omitempty"`
	// RequestID and EventCursor durably correlate an accepted asynchronous gc
	// session.message request with its terminal event. Once RequestID is set,
	// recovery watches the event stream and must never POST the message again.
	RequestID   string `json:"request_id,omitempty"`
	EventCursor string `json:"event_cursor,omitempty"`
	// Agent is the directory agent name for this target, recorded so the
	// current-turn pointer can be rewritten on redrive without recomputing
	// the route. Empty for a failed-unbound record.
	Agent string `json:"agent,omitempty"`
	// DelegationKey is the delegations-registry filename this peer turn
	// correlates to (set for peer_delegation / peer_result legs only; empty
	// for peer_input and the human ambient/targeted legs).
	DelegationKey string `json:"delegation_key,omitempty"`
	// RosterDriftOverlay marks a targeted leg the live-membership eligibility
	// overlay admitted and ensureTargets resolved through dm_bindings because
	// the agent has no room binding. The current-turn pointer carries it so the
	// reply verb accepts that same session instead of refusing the reply the
	// overlay woke the agent to give.
	RosterDriftOverlay bool `json:"roster_drift_overlay,omitempty"`
}

// IngressReceipt is the durable ingress record. It retains the complete
// inner Slack event so async routing and post-crash replay never depend
// on re-fetching from Slack.
type IngressReceipt struct {
	ID         string `json:"id"` // "in-" + sanitized origin
	Generation int64  `json:"generation"`
	// SchemaVersion marks the receipt format. Absent/0 is a legacy embedded
	// receipt (the inner event is inline in Event); ingressReceiptSchemaBodyRef
	// is a body-split receipt (the event lives in the bodies/ sidecar, named by
	// BodyRef, with EventDigest pinning its bytes). The reader accepts both
	// shapes forever — a legacy receipt is never rewritten, it ages out at
	// retention.
	SchemaVersion int           `json:"schema_version,omitempty"`
	Origin        ReceiptOrigin `json:"origin"`
	EventID       string        `json:"event_id"`
	APIAppID      string        `json:"api_app_id"`
	// Kind is the receipt-level conversation kind: "" (room / legacy,
	// Phases 1-3) or "dm" (per-agent DM, Phase 4). Distinct from
	// TargetDelivery.Kind (the wake kind). Empty on every pre-Phase-4
	// receipt, so the field is omitempty for byte-compatible room receipts.
	Kind string `json:"kind,omitempty"`
	// OwnerAppID is the delivering app's api_app_id for a DM receipt — the
	// single admission owner, joined against company_directory.json
	// agents[].app_id to derive the owner agent at routing time. Empty for
	// room receipts (the switchboard is the implicit owner there).
	OwnerAppID  string    `json:"owner_app_id,omitempty"`
	RetryNum    int       `json:"retry_num"`
	RetryReason string    `json:"retry_reason,omitempty"`
	ReceivedAt  time.Time `json:"received_at"`
	// UpdatedAt is refreshed on Admit and on every Update. The delivery
	// sweep uses it as the claim timestamp for the stale-reclaim window: a
	// "routing" receipt whose UpdatedAt is fresher than the window is a live
	// claim and skipped; a stale one is reclaimed.
	UpdatedAt time.Time `json:"updated_at"`
	Status    string    `json:"status"` // "received" | "routing" | "delivered" | "no_delivery" | "failed"
	// Event is the COMPLETE inner Slack event object as received. On a legacy
	// (pre-split) receipt it is embedded here and routing/crash-replay read it
	// directly. On a body-split receipt (SchemaVersion == ingressReceiptSchemaBodyRef)
	// it is empty — the event lives in the bodies/ sidecar and every reader goes
	// through receiptBody instead. omitempty keeps a body-split receipt from
	// carrying a redundant "event": null.
	Event json.RawMessage `json:"event,omitempty"`
	// BodyRef names the bodies/ sidecar holding this receipt's raw inner event
	// (always the receipt's own id). EventDigest is the sha256 hex of the stored
	// body bytes, immutable for the receipt's life so a late redelivery dedups on
	// the same digest and a redacted body still proves what it once held. Both are
	// empty on a legacy embedded receipt.
	BodyRef     string `json:"body_ref,omitempty"`
	EventDigest string `json:"event_digest,omitempty"`
	// ThreadRootTS is the human root ts derived ONCE at admission (thread_ts when
	// present, else the origin ts). Every root-keyed derivation — the dgser
	// serialization lock, the replay-chain root, the reminder's thread_root_ts,
	// the threaded failure-reply root — reads it through receiptRootTS so a redacted
	// or missing body can no longer collapse a threaded receipt's root to origin.TS
	// and diverge its lock name / rendered root from the pre-redaction value. Empty
	// on a legacy receipt admitted before this field existed; receiptRootTS falls
	// back to body-derivation there (both shapes forever).
	ThreadRootTS string `json:"thread_root_ts,omitempty"`
	// ThreadParticipantAgent records the directory agent whose authenticated
	// company-bot identity authored this message in a thread. It is written only
	// after bots.info-backed corroboration, and lets later untagged human replies
	// derive ambient readers from the durable receipt ledger across restarts.
	// Empty for root posts, humans, unknown bots, switchboard self-events, DMs,
	// and company agents that are not declared members of the room.
	ThreadParticipantAgent string                    `json:"thread_participant_agent,omitempty"`
	Targets                map[string]TargetDelivery `json:"targets,omitempty"`
	Reason                 string                    `json:"reason,omitempty"` // parked/no_delivery/failed detail
	// Hydration is the frozen context bundle (verified human root +
	// bounded untrusted excerpt) fetched ONCE at first delivery so redrives
	// re-render byte-identical reminders under the same Idempotency-Key
	// (Phase 2c). Absent until the first delivery attempt computes it.
	Hydration json.RawMessage `json:"hydration,omitempty"`
	// Synthesis is the frozen snapshot bytes for a peer_result receipt,
	// copied from the claimed record in the same routing commit that freezes
	// targets, so redrives re-render byte-identical reminder synthesis fields
	// even if the record is later pruned (the same frozen-bytes discipline as
	// Hydration). Absent on non-peer_result receipts (Phase 3a).
	Synthesis json.RawMessage `json:"synthesis,omitempty"`
	// RecoveryAttempts / RecoveryNextAt / RecoveryReason track the S7
	// correlation-park backoff (rule 17 parity, Phase 3b): a
	// correlation_pending or ambiguous_pending_delegations park counts one
	// attempt only when a redrive re-ran resolveResultWake and found the
	// posting intent still in flight, and schedules the next eligible pass at
	// min(60s*2^(n-1), 15min). NOTE omitzero on RecoveryNextAt, not omitempty:
	// encoding/json's omitempty never elides a struct, so a zero 0001-01-01
	// timestamp would otherwise pollute every receipt's cross-language wire
	// shape (go.mod is go >= 1.24, omitzero available).
	RecoveryAttempts int       `json:"recovery_attempts,omitempty"`
	RecoveryNextAt   time.Time `json:"recovery_next_at,omitzero"`
	RecoveryReason   string    `json:"recovery_reason,omitempty"`
	// AckState is the visible-ack cursor (Phase 3b, config-gated):
	// "" | "eyes" | "done" | "degraded". Cosmetic — the durable receipt, not
	// the emoji, stays authoritative, so an ack failure never changes status.
	AckState string `json:"ack_state,omitempty"`
}

// NewIngressReceiptStore opens (creating if needed) the receipt directory
// rooted at dir with 0700 permissions. dir must be non-empty; the caller
// resolves it (Phase 1d) from GC_CITY_PATH / SLACK_COMPANY_INGRESS_DIR.
func NewIngressReceiptStore(dir string) (*IngressReceiptStore, error) {
	if strings.TrimSpace(dir) == "" {
		return nil, errors.New("ingress receipts: store dir required")
	}
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, fmt.Errorf("ingress receipts: mkdir %q: %w", dir, err)
	}
	// Reject a symlinked store dir before we operate through it. A
	// same-UID attacker or /tmp squatter who points chat-ingress at another
	// tree would otherwise redirect every receipt write; MkdirAll/Chmod
	// both follow the link. This is the confined-open convention the six
	// atomic registries enforce (openRegistryFile, gc-cby.38), applied to
	// the most security-sensitive durable state in the pack.
	info, err := os.Lstat(dir)
	if err != nil {
		return nil, fmt.Errorf("ingress receipts: lstat %q: %w", dir, err)
	}
	if info.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("ingress receipts: store dir %q is a symlink; refusing to open", dir)
	}
	// Tighten perms in case the directory pre-existed with looser bits.
	if err := os.Chmod(dir, 0o700); err != nil {
		return nil, fmt.Errorf("ingress receipts: chmod %q: %w", dir, err)
	}
	// The bodies/ sidecar holds one raw-event file per receipt. Create it under
	// the same 0700 + no-symlink confinement so a squatter cannot redirect body
	// writes any more than receipt writes.
	bodies := filepath.Join(dir, bodiesDirName)
	if err := os.MkdirAll(bodies, 0o700); err != nil {
		return nil, fmt.Errorf("ingress receipts: mkdir bodies %q: %w", bodies, err)
	}
	binfo, err := os.Lstat(bodies)
	if err != nil {
		return nil, fmt.Errorf("ingress receipts: lstat bodies %q: %w", bodies, err)
	}
	if binfo.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("ingress receipts: bodies dir %q is a symlink; refusing to open", bodies)
	}
	if err := os.Chmod(bodies, 0o700); err != nil {
		return nil, fmt.Errorf("ingress receipts: chmod bodies %q: %w", bodies, err)
	}
	return &IngressReceiptStore{dir: dir}, nil
}

// Admit is the linearization point, claim-and-content atomic. The full
// receipt is written to a temp file in the store directory, fsynced, then
// hard-linked (os.Link) to its final origin-keyed name; the directory is
// fsynced and the temp name removed. os.Link failing with EEXIST means a
// receipt for this origin already exists (a duplicate / redelivery): the
// existing receipt is read and returned with created=false. An existing
// but unparseable receipt file is quarantined (*.corrupt) and the link
// retried once; a persistent failure returns err (the caller answers
// 503). There is no state in which a claim exists without its content.
func (s *IngressReceiptStore) Admit(r *IngressReceipt) (created bool, existing *IngressReceipt, err error) {
	if r == nil {
		return false, nil, errors.New("ingress receipts: nil receipt")
	}
	if err := validateOrigin(r.Origin); err != nil {
		return false, nil, err
	}
	r.ID = receiptID(r.Origin)
	if r.Status == "" {
		r.Status = ingressStatusReceived
	}
	if r.Generation <= 0 {
		r.Generation = 1
	}
	if r.ReceivedAt.IsZero() {
		r.ReceivedAt = time.Now().UTC()
	}
	if r.UpdatedAt.IsZero() {
		r.UpdatedAt = r.ReceivedAt
	}
	normalizeEvent(r)

	// Split the raw inner event out of the receipt: it moves to the bodies/
	// sidecar (referenced by body_ref + event_digest) so the receipt itself
	// stays small and the payload is independently redactable.
	bodyBytes := splitReceiptBody(r)

	data, err := marshalReceipt(r)
	if err != nil {
		return false, nil, err
	}
	finalPath := s.pathForID(r.ID)

	s.mu.Lock()
	defer s.mu.Unlock()

	// Fast path + legacy safety (m3/m5): if a VALID receipt already claims this
	// origin, return it without writing any body. A redelivery against a legacy
	// embedded receipt (BodyRef=="", event inline) would otherwise link a stray
	// sidecar the legacy receipt never references — an unredactable raw-payload
	// copy that lingers to retention — and every routine redelivery would pay a
	// needless body temp-write+fsync+link. A missing name (first admission) or a
	// corrupt file (quarantined+reclaimed by the loop below) falls through to the
	// normal body-then-receipt sequence. The os.Link claim below is still the
	// linearization point, so a concurrent create is caught there, not here.
	if existingR, rerr := s.readReceiptFile(finalPath); rerr == nil {
		return false, existingR, nil
	} else if !errors.Is(rerr, os.ErrNotExist) {
		log.Printf("company: admit found unreadable receipt %q, will quarantine+reclaim: %v", finalPath, rerr)
	}

	// The body is written and durable BEFORE the receipt link: a body without a
	// receipt is a harmless orphan the janitor GCs, whereas a receipt without a
	// body is an integrity error. First-writer-wins via O_EXCL link; writeBodyOnce
	// digest-checks any pre-existing body (a same-origin redelivery or recovered
	// crash orphan) so a divergent orphan is replaced rather than clobbering the
	// admitted receipt's digest.
	if werr := s.writeBodyOnce(r.ID, bodyBytes); werr != nil {
		s.writeFailures.Add(1)
		return false, nil, werr
	}

	quarantined := false
	for {
		tmp, werr := s.writeTempReceipt(data)
		if werr != nil {
			s.writeFailures.Add(1)
			return false, nil, werr
		}
		linkErr := os.Link(tmp, finalPath)
		if linkErr == nil {
			// The claim (final name) now points at the fully-fsynced
			// inode. Durably record the new directory entry before
			// removing our temp alias.
			if serr := fsyncDir(s.dir); serr != nil {
				_ = os.Remove(tmp)
				s.writeFailures.Add(1)
				return false, nil, fmt.Errorf("ingress receipts: fsync dir after link: %w", serr)
			}
			_ = os.Remove(tmp)
			return true, nil, nil
		}
		_ = os.Remove(tmp)
		if !errors.Is(linkErr, os.ErrExist) {
			s.writeFailures.Add(1)
			return false, nil, fmt.Errorf("ingress receipts: link %q: %w", finalPath, linkErr)
		}
		// EEXIST: a receipt already occupies the final name.
		existingR, rerr := s.readReceiptFile(finalPath)
		if rerr == nil {
			return false, existingR, nil
		}
		if errors.Is(rerr, os.ErrNotExist) {
			// The final vanished between our link attempt and the read
			// (a concurrent removal). Retry the link.
			continue
		}
		// Existing receipt is unparseable. Quarantine once and retry.
		if quarantined {
			s.writeFailures.Add(1)
			return false, nil, fmt.Errorf("ingress receipts: persistent corrupt receipt %q: %w", finalPath, rerr)
		}
		if qerr := s.quarantine(finalPath); qerr != nil {
			s.writeFailures.Add(1)
			return false, nil, fmt.Errorf("ingress receipts: quarantine corrupt receipt %q: %w", finalPath, qerr)
		}
		quarantined = true
	}
}

// Update performs a generation-checked atomic rewrite (temp + rename +
// fsync of file and directory — same durability as Admit). If the on-disk
// generation differs from r.Generation, ErrStale is returned; the caller
// re-reads and merges. On success r.Generation is advanced to the value
// written (on-disk generation + 1).
func (s *IngressReceiptStore) Update(r *IngressReceipt) error {
	if r == nil {
		return errors.New("ingress receipts: nil receipt")
	}
	if err := validateOrigin(r.Origin); err != nil {
		return err
	}
	r.ID = receiptID(r.Origin)
	if r.Status == "" {
		r.Status = ingressStatusReceived
	}
	normalizeEvent(r)

	finalPath := s.pathForID(r.ID)

	s.mu.Lock()
	defer s.mu.Unlock()

	onDisk, err := s.readReceiptFile(finalPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("ingress receipts: update missing receipt %q: %w", r.ID, err)
		}
		s.writeFailures.Add(1)
		return fmt.Errorf("ingress receipts: read for update %q: %w", finalPath, err)
	}
	if onDisk.Generation != r.Generation {
		return ErrStale
	}
	r.Generation = onDisk.Generation + 1
	r.UpdatedAt = time.Now().UTC()
	data, err := marshalReceipt(r)
	if err != nil {
		return err
	}
	if err := s.writeReceiptAtomic(finalPath, data); err != nil {
		s.writeFailures.Add(1)
		return err
	}
	return nil
}

// Get returns the receipt for origin, or (nil, nil) if none exists.
func (s *IngressReceiptStore) Get(origin ReceiptOrigin) (*IngressReceipt, error) {
	if err := validateOrigin(origin); err != nil {
		return nil, err
	}
	finalPath := s.pathForID(receiptID(origin))

	s.mu.Lock()
	defer s.mu.Unlock()

	r, err := s.readReceiptFile(finalPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}
	return r, nil
}

// GetByID reads one receipt by its receipt id (the origin-keyed
// "in-…" filename stem). Returns (nil, nil) when the receipt does not exist
// — a terminal receipt swept past retention is gone, which the redrive
// endpoint surfaces as 404. A symlinked/corrupt file is returned as an error
// (never quarantined here — this is a targeted read, not a scan).
func (s *IngressReceiptStore) GetByID(id string) (*IngressReceipt, error) {
	// Defense in depth: never join an id that is not the receipt-id shape into a
	// filesystem path. GetByID is the one id ingress that skips origin-derivation
	// (and thus safeStorageID sanitization), so a hostile id (path separator, NUL,
	// traversal) must be rejected before pathForID. The redrive handler validates
	// the same shape up front and returns 400; this guard covers any other caller.
	if !isReceiptID(id) {
		return nil, fmt.Errorf("ingress receipts: invalid receipt id %q", id)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	r, err := s.readReceiptFile(s.pathForID(id))
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}
	return r, nil
}

// List returns every receipt in the store (terminal and non-terminal),
// ordered by (ReceivedAt, Origin.TS) — the operator-listing scan behind
// GET /internal/company/receipts. A corrupt scan entry is quarantined and
// skipped exactly like Pending; only a directory-listing failure is fatal.
func (s *IngressReceiptStore) List() ([]*IngressReceipt, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	paths, err := s.receiptFiles()
	if err != nil {
		return nil, err
	}
	var out []*IngressReceipt
	for _, p := range paths {
		r, rerr := s.readReceiptFile(p)
		if rerr != nil {
			if errors.Is(rerr, os.ErrNotExist) {
				continue // raced removal
			}
			s.quarantineNonFatal(p, rerr)
			continue
		}
		out = append(out, r)
	}
	sort.SliceStable(out, func(i, j int) bool {
		if !out[i].ReceivedAt.Equal(out[j].ReceivedAt) {
			return out[i].ReceivedAt.Before(out[j].ReceivedAt)
		}
		return out[i].Origin.TS < out[j].Origin.TS
	})
	return out, nil
}

// Pending returns non-terminal receipts ordered by (ReceivedAt,
// Origin.TS). A corrupt receipt file encountered during the scan is
// quarantined (*.corrupt) and skipped — a single bad file never fails the
// scan. Only a directory-listing failure is fatal.
func (s *IngressReceiptStore) Pending() ([]*IngressReceipt, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	paths, err := s.receiptFiles()
	if err != nil {
		return nil, err
	}
	var pending []*IngressReceipt
	for _, p := range paths {
		r, rerr := s.readReceiptFile(p)
		if rerr != nil {
			if errors.Is(rerr, os.ErrNotExist) {
				continue // raced removal
			}
			s.quarantineNonFatal(p, rerr)
			continue
		}
		if isTerminalStatus(r.Status) {
			continue
		}
		pending = append(pending, r)
	}
	sort.SliceStable(pending, func(i, j int) bool {
		if !pending[i].ReceivedAt.Equal(pending[j].ReceivedAt) {
			return pending[i].ReceivedAt.Before(pending[j].ReceivedAt)
		}
		return pending[i].Origin.TS < pending[j].Origin.TS
	})
	return pending, nil
}

// Sweep removes terminal receipts whose ReceivedAt is older than
// retention and returns the count removed. Retention below 24h is
// rejected (terminal receipts are the dedup memory for the Delayed Events
// horizon). Non-terminal receipts are never touched; corrupt scan entries
// are quarantined rather than fatal.
func (s *IngressReceiptStore) Sweep(retention time.Duration) (removed int, err error) {
	if retention < ingressRetentionFloor {
		return 0, fmt.Errorf("ingress receipts: retention %s below %s floor", retention, ingressRetentionFloor)
	}
	now := time.Now()
	cutoff := now.Add(-retention)

	s.mu.Lock()
	defer s.mu.Unlock()

	paths, err := s.receiptFiles()
	if err != nil {
		return 0, err
	}
	live := make(map[string]bool, len(paths))
	readErr := map[string]bool{}
	removedAny := false
	for _, p := range paths {
		r, rerr := s.readReceiptFile(p)
		if rerr != nil {
			if errors.Is(rerr, os.ErrNotExist) {
				continue
			}
			if id, ok := receiptIDFromPath(p); ok {
				readErr[id] = true // exclude from orphan GC: may still be live/repairable
			}
			s.quarantineNonFatal(p, rerr)
			continue
		}
		if !isTerminalStatus(r.Status) {
			live[r.ID] = true
			continue // never sweep in-flight work
		}
		if !r.ReceivedAt.Before(cutoff) {
			live[r.ID] = true
			continue // still within retention
		}
		if derr := os.Remove(p); derr != nil {
			if errors.Is(derr, os.ErrNotExist) {
				continue
			}
			live[r.ID] = true
			log.Printf("WARN: ingress receipts: sweep remove %q: %v", p, derr)
			continue
		}
		s.deleteBody(r) // retention pair-delete
		removed++
		removedAny = true
	}
	if removedAny {
		// Durably record the removed directory entries.
		if serr := fsyncDir(s.dir); serr != nil {
			log.Printf("WARN: ingress receipts: fsync dir after sweep: %v", serr)
		}
	}
	s.gcOrphanBodies(live, readErr, now)
	return removed, nil
}

// SweepAndPending performs the periodic sweep in a single directory scan:
// it removes terminal receipts older than retention, returns the surviving
// non-terminal receipts ordered by (ReceivedAt, Origin.TS), AND returns the
// terminal-within-retention receipts whose visible-ack cursor is stranded on
// "eyes" or "warned" (healNeeded). Folding the ack-heal candidates into this one
// scan avoids a second full-store decode pass per tick under the store mutex
// Admit contends for on the HTTP hot path. Retention below the floor is rejected
// exactly like Sweep; corrupt scan entries are quarantined rather than fatal.
//
// A stranded cursor is one whose terminal reaction (✅/⚠️/remove) never landed
// (rate-limited, or a crash between the finalize commit and the ack commit).
// "warned" is the failed-path intermediate where the threaded reply is already
// posted and only the ⚠️ reaction remains, so healing re-applies the reaction
// WITHOUT re-posting the reply. healNeeded is always collected (cheap on the
// already-decoded receipt); the caller applies it only when acks are enabled.
func (s *IngressReceiptStore) SweepAndPending(retention time.Duration) (pending, healNeeded []*IngressReceipt, removed int, dmCounts dmFamilyReceiptCounts, bodyCounts bodyIntegrityCounts, err error) {
	if retention < ingressRetentionFloor {
		return nil, nil, 0, dmCounts, bodyCounts, fmt.Errorf("ingress receipts: retention %s below %s floor", retention, ingressRetentionFloor)
	}
	now := time.Now()
	cutoff := now.Add(-retention)

	s.mu.Lock()
	defer s.mu.Unlock()

	paths, err := s.receiptFiles()
	if err != nil {
		return nil, nil, 0, dmCounts, bodyCounts, err
	}
	// live tracks receipt ids that survive this sweep, so orphan-body GC below
	// can pair a body with an existing receipt without a second receipt scan.
	// readErr tracks ids whose receipt errored on read this pass — excluded from
	// orphan GC so a transient read fault never destroys a still-live payload.
	live := make(map[string]bool, len(paths))
	readErr := map[string]bool{}
	removedAny := false
	for _, p := range paths {
		r, rerr := s.readReceiptFile(p)
		if rerr != nil {
			if errors.Is(rerr, os.ErrNotExist) {
				continue // raced removal
			}
			if id, ok := receiptIDFromPath(p); ok {
				readErr[id] = true
			}
			s.quarantineNonFatal(p, rerr)
			continue
		}
		if !isTerminalStatus(r.Status) {
			live[r.ID] = true
			pending = append(pending, r)
			dmCounts.tally(r)      // Phase 4 /healthz DM gauge, folded into this scan
			bodyCounts.tally(s, r) // Phase 5 body integrity, folded into the same scan
			continue               // never sweep in-flight work
		}
		if !r.ReceivedAt.Before(cutoff) {
			// Terminal but within retention: not swept. Collect a stranded
			// visible-ack cursor for in-pass healing (fold of the former
			// TerminalAcksNeedingHeal second scan).
			live[r.ID] = true
			if r.AckState == ackStateEyes || r.AckState == ackStateWarned {
				healNeeded = append(healNeeded, r)
			}
			dmCounts.tally(r)      // survives the sweep → counted on the gauge
			bodyCounts.tally(s, r) // still has a body until retention → integrity-checked
			continue
		}
		if derr := os.Remove(p); derr != nil {
			if errors.Is(derr, os.ErrNotExist) {
				continue
			}
			live[r.ID] = true // remove failed → receipt still present, keep its body
			log.Printf("WARN: ingress receipts: sweep remove %q: %v", p, derr)
			continue
		}
		// Retention pair-delete: the receipt is gone, so its body goes with it.
		s.deleteBody(r)
		removed++
		removedAny = true
	}
	if removedAny {
		if serr := fsyncDir(s.dir); serr != nil {
			log.Printf("WARN: ingress receipts: fsync dir after sweep: %v", serr)
		}
	}
	// Orphan-body GC: a body with no surviving receipt (crash orphan, or a body
	// whose pair-delete missed) is collected here in one bodies-dir pass, honoring
	// the affirmative-absence, read-error, and grace-window guards.
	s.gcOrphanBodies(live, readErr, now)
	sort.SliceStable(pending, func(i, j int) bool {
		if !pending[i].ReceivedAt.Equal(pending[j].ReceivedAt) {
			return pending[i].ReceivedAt.Before(pending[j].ReceivedAt)
		}
		return pending[i].Origin.TS < pending[j].Origin.TS
	})
	return pending, healNeeded, removed, dmCounts, bodyCounts, nil
}

// WriteFailures returns the monotonic count of failed Admit/Update
// persistence attempts, surfaced in the gateway status payload and
// /healthz detail as the receipt-store outage paging hook.
func (s *IngressReceiptStore) WriteFailures() uint64 {
	return s.writeFailures.Load()
}

// add folds one receipt status into the per-status tally.
func (c *dmReceiptStatusCounts) add(status string) {
	switch status {
	case ingressStatusReceived:
		c.Received++
	case ingressStatusRouting:
		c.Routing++
	case ingressStatusDelivered:
		c.Delivered++
	case ingressStatusNoDelivery:
		c.NoDelivery++
	case ingressStatusFailed:
		c.Failed++
	}
}

// tally folds one dm-family receipt into the /healthz gauge by kind and status:
// a "dm" receipt into the DM breakdown (company_dm_receipts), an "mpim" receipt
// into the group-DM breakdown (company_mpim_receipts). Non-dm-family receipts
// are ignored. It rides the single SweepAndPending scan (which already decodes
// every receipt) so the gauge costs no extra I/O and no extra time under the
// store mutex the HTTP admission hot path contends for (m8: the former
// DMReceiptStatusCounts second full scan is gone).
func (c *dmFamilyReceiptCounts) tally(r *IngressReceipt) {
	if r == nil {
		return
	}
	switch r.Kind {
	case receiptKindDM:
		c.DM.add(r.Status)
	case receiptKindMpim:
		c.Mpim.add(r.Status)
	}
}

// tally folds one receipt's body integrity into the /healthz body gauge. Legacy
// embedded receipts have no sidecar and are skipped. It rides the single
// SweepAndPending scan via classifyBodyShallow — existence + a bounded tombstone
// probe, NO SHA over the up-to-4-MiB body under the store mutex (m6). An absent
// sidecar is an integrity error (Missing); a tombstone is Redacted. A digest
// mismatch is NOT detectable without hashing and is instead counted on the read
// path (bodyDigestMismatches), so the sweep never pays the per-body hash cost the
// HTTP admission hot path would then queue behind.
func (c *bodyIntegrityCounts) tally(s *IngressReceiptStore, r *IngressReceipt) {
	if r == nil || r.BodyRef == "" {
		return
	}
	switch s.classifyBodyShallow(r) {
	case bodyMissing:
		c.Missing++
	case bodyRedacted:
		c.Redacted++
	}
}

// BodyDigestMismatches returns the monotonic count of read-path body digest
// mismatches, surfaced on /healthz as the integrity paging hook the existence-only
// sweep gauge cannot compute.
func (s *IngressReceiptStore) BodyDigestMismatches() uint64 {
	return s.bodyDigestMismatches.Load()
}

// pathForID returns the on-disk receipt path for a receipt id.
func (s *IngressReceiptStore) pathForID(id string) string {
	return filepath.Join(s.dir, id+".json")
}

// receiptFiles lists the receipt files (*.json) in the store directory,
// skipping temp (*.tmp) and quarantined (*.corrupt) files. A missing
// directory is treated as empty.
func (s *IngressReceiptStore) receiptFiles() ([]string, error) {
	entries, err := os.ReadDir(s.dir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, fmt.Errorf("ingress receipts: scan %q: %w", s.dir, err)
	}
	var out []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if !strings.HasSuffix(name, ".json") {
			continue
		}
		out = append(out, filepath.Join(s.dir, name))
	}
	return out, nil
}

// writeTempReceipt writes data to a fresh 0600 temp file in the store
// directory, fsyncs it, and returns the temp path. The caller either
// links it (Admit) or renames it (Update); on any failure the temp is
// removed before returning.
func (s *IngressReceiptStore) writeTempReceipt(data []byte) (string, error) {
	return s.writeTempIn(s.dir, "ingress-*.tmp", data)
}

// writeTempIn writes data to a fresh 0600 temp file matching pattern in dir,
// fsyncs it, and returns the temp path. It backs both the receipt and body temp
// writers; the caller links or renames the result and removes the temp on
// failure.
func (s *IngressReceiptStore) writeTempIn(dir, pattern string, data []byte) (string, error) {
	f, err := os.CreateTemp(dir, pattern)
	if err != nil {
		return "", fmt.Errorf("ingress receipts: create temp in %q: %w", dir, err)
	}
	tmp := f.Name()
	cleanup := func() { _ = os.Remove(tmp) }
	if err := f.Chmod(0o600); err != nil {
		_ = f.Close()
		cleanup()
		return "", fmt.Errorf("ingress receipts: chmod %q: %w", tmp, err)
	}
	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		cleanup()
		return "", fmt.Errorf("ingress receipts: write %q: %w", tmp, err)
	}
	if err := f.Sync(); err != nil {
		_ = f.Close()
		cleanup()
		return "", fmt.Errorf("ingress receipts: fsync %q: %w", tmp, err)
	}
	if err := f.Close(); err != nil {
		cleanup()
		return "", fmt.Errorf("ingress receipts: close %q: %w", tmp, err)
	}
	return tmp, nil
}

// writeReceiptAtomic rewrites path via temp + rename with an fsync of both
// the file and the directory. Used by Update, which has already verified
// the receipt exists.
func (s *IngressReceiptStore) writeReceiptAtomic(path string, data []byte) error {
	tmp, err := s.writeTempReceipt(data)
	if err != nil {
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("ingress receipts: rename %q -> %q: %w", tmp, path, err)
	}
	if err := fsyncDir(s.dir); err != nil {
		return fmt.Errorf("ingress receipts: fsync dir after rename: %w", err)
	}
	return nil
}

// readReceiptFile reads and decodes a receipt file. A missing file
// surfaces os.ErrNotExist; an oversized or malformed file surfaces a
// decode error the caller treats as corruption.
func (s *IngressReceiptStore) readReceiptFile(path string) (*IngressReceipt, error) {
	// O_NOFOLLOW rejects a receipt file swapped for a symlink (same-UID
	// attacker / /tmp squatter) so a hostile link cannot redirect the
	// durable-ledger read outside the store dir. A symlinked receipt trips
	// ELOOP here and is treated as corrupt (quarantined by the scan callers)
	// rather than followed. Parity with openRegistryFile's symlink guard.
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		// Wrap so callers keep using errors.Is(err, os.ErrNotExist): a bare
		// syscall.ENOENT already satisfies it, and *PathError preserves that.
		return nil, &os.PathError{Op: "open", Path: path, Err: err}
	}
	f := os.NewFile(uintptr(fd), path)
	defer func() { _ = f.Close() }()
	data, err := io.ReadAll(io.LimitReader(f, maxIngressReceiptBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read %q: %w", path, err)
	}
	if int64(len(data)) > maxIngressReceiptBytes {
		return nil, fmt.Errorf("receipt %q exceeds %d bytes", path, maxIngressReceiptBytes)
	}
	var r IngressReceipt
	if err := json.Unmarshal(data, &r); err != nil {
		return nil, fmt.Errorf("decode %q: %w", path, err)
	}
	return &r, nil
}

// bodiesDir is the sidecar subdirectory holding one raw-event file per receipt.
func (s *IngressReceiptStore) bodiesDir() string {
	return filepath.Join(s.dir, bodiesDirName)
}

// bodyPathForID returns the on-disk body path for a receipt id.
func (s *IngressReceiptStore) bodyPathForID(id string) string {
	return filepath.Join(s.bodiesDir(), id+bodyFileSuffix)
}

// writeBodyOnce writes the body sidecar for id, first-writer-wins. The bytes are
// fsynced to a temp file, then hard-linked to the final body name. On EEXIST a
// body already occupies the name (a same-origin redelivery or a recovered crash
// orphan); the existing bytes are digest-checked against the incoming body rather
// than adopted blind (C1/C3/m7):
//
//   - byte-identical (or an explicit redacted tombstone) → adopt, unchanged.
//   - divergent AND no VALID receipt yet claims the id (the canonical name is
//     free, or holds only a corrupt file the caller will quarantine before it
//     links the NEW receipt whose event_digest is over THESE bytes) → replace the
//     orphan atomically, so the receipt-to-body digest invariant holds at
//     admission instead of birthing a permanent bodyMismatch.
//   - divergent WITH a valid receipt already claiming the id → keep
//     first-writer-wins: Admit's link will EEXIST and return that receipt, so the
//     incoming digest is discarded and the stored body must stay as its owner
//     left it.
//
// The receipt existence check is done under the store mutex the caller holds. The
// bodies dir is fsynced so the new entry survives a crash.
func (s *IngressReceiptStore) writeBodyOnce(id string, body []byte) error {
	bodyPath := s.bodyPathForID(id)
	tmp, err := s.writeTempIn(s.bodiesDir(), "body-*.tmp", body)
	if err != nil {
		return err
	}
	linkErr := os.Link(tmp, bodyPath)
	if linkErr == nil {
		if serr := fsyncDir(s.bodiesDir()); serr != nil {
			_ = os.Remove(tmp)
			return fmt.Errorf("ingress receipts: fsync bodies dir after link: %w", serr)
		}
		_ = os.Remove(tmp)
		return nil
	}
	_ = os.Remove(tmp)
	if !errors.Is(linkErr, os.ErrExist) {
		return fmt.Errorf("ingress receipts: link body %q: %w", bodyPath, linkErr)
	}

	// EEXIST: a body already occupies the final name. Decide adopt vs replace.
	existing, rerr := s.readBodyFile(id)
	if rerr != nil {
		// Cannot read the existing body (transient, or a concurrent redact/remove
		// race): leave it in place, first-writer-wins as before.
		return nil
	}
	if isRedactedBody(existing) || eventDigest(existing) == eventDigest(body) {
		// A deliberate redacted tombstone, or byte-identical bytes: adopt.
		return nil
	}
	// Divergent bytes. A VALID receipt claiming the id means first-writer-wins
	// (the incoming digest never persists), so adopt the existing bytes. A missing
	// or corrupt receipt means the incoming receipt WILL persist its digest over
	// these bytes, so replace the orphan to keep event_digest == sha256(body).
	if _, recErr := s.readReceiptFile(s.pathForID(id)); recErr == nil {
		return nil
	}
	if aerr := s.writeBodyAtomic(id, body); aerr != nil {
		return aerr
	}
	return nil
}

// writeBodyAtomic rewrites a body sidecar via temp + rename with an fsync of the
// file and the bodies dir. Used by redaction, which overwrites the existing body
// with the tombstone.
func (s *IngressReceiptStore) writeBodyAtomic(id string, data []byte) error {
	bodyPath := s.bodyPathForID(id)
	tmp, err := s.writeTempIn(s.bodiesDir(), "body-*.tmp", data)
	if err != nil {
		return err
	}
	if err := os.Rename(tmp, bodyPath); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("ingress receipts: rename body %q: %w", bodyPath, err)
	}
	if err := fsyncDir(s.bodiesDir()); err != nil {
		return fmt.Errorf("ingress receipts: fsync bodies dir after body rename: %w", err)
	}
	return nil
}

// readBodyFile reads a body sidecar's raw bytes with the same O_NOFOLLOW,
// size-bounded confinement as readReceiptFile. A missing file surfaces
// os.ErrNotExist.
func (s *IngressReceiptStore) readBodyFile(id string) ([]byte, error) {
	path := s.bodyPathForID(id)
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, &os.PathError{Op: "open", Path: path, Err: err}
	}
	f := os.NewFile(uintptr(fd), path)
	defer func() { _ = f.Close() }()
	data, err := io.ReadAll(io.LimitReader(f, maxIngressReceiptBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read %q: %w", path, err)
	}
	if int64(len(data)) > maxIngressReceiptBytes {
		return nil, fmt.Errorf("body %q exceeds %d bytes", path, maxIngressReceiptBytes)
	}
	return data, nil
}

// loadBody resolves a receipt's raw inner event and classifies the resolution. A
// legacy receipt returns its embedded Event (bodyEmbedded). A body-split receipt
// reads its sidecar: bodyOK once the bytes verify against event_digest,
// bodyRedacted for the tombstone, bodyMissing when absent (or the ref is
// malformed), bodyMismatch on a digest mismatch. It never takes the store mutex,
// so it is safe to call from a scan already holding it. The bytes for any
// non-ok state are a JSON null so decoders degrade to an empty message.
func (s *IngressReceiptStore) loadBody(r *IngressReceipt) (json.RawMessage, bodyStatus) {
	if r == nil {
		return json.RawMessage("null"), bodyMissing
	}
	if r.BodyRef == "" {
		if len(r.Event) == 0 {
			return json.RawMessage("null"), bodyEmbedded
		}
		return r.Event, bodyEmbedded
	}
	if !isReceiptID(r.BodyRef) {
		return json.RawMessage("null"), bodyMissing
	}
	raw, err := s.readBodyFile(r.BodyRef)
	if err != nil {
		return json.RawMessage("null"), bodyMissing
	}
	if isRedactedBody(raw) {
		return json.RawMessage("null"), bodyRedacted
	}
	if eventDigest(raw) != r.EventDigest {
		// Read-path integrity verification (m6): the sweep no longer hashes bodies,
		// so a digest mismatch is only ever detected here. Count it monotonically so
		// the operator signal survives even when the receipt parks and ages out.
		s.bodyDigestMismatches.Add(1)
		return json.RawMessage("null"), bodyMismatch
	}
	return json.RawMessage(raw), bodyOK
}

// classifyBodyShallow classifies a receipt's body sidecar for the /healthz sweep
// gauge WITHOUT hashing it (m6). It stats for existence and reads only a bounded
// prefix to probe the redacted tombstone; a present, non-tombstone body is
// reported bodyOK (existence-verified, integrity unverified — that is the read
// path's job, loadBody). Legacy embedded receipts have no sidecar. It never takes
// the store mutex, so a scan already holding it can call it, and it never reads
// (or hashes) the up-to-4-MiB body under that mutex the HTTP admission path
// contends for.
func (s *IngressReceiptStore) classifyBodyShallow(r *IngressReceipt) bodyStatus {
	if r == nil || r.BodyRef == "" {
		return bodyEmbedded
	}
	if !isReceiptID(r.BodyRef) {
		return bodyMissing
	}
	fd, err := syscall.Open(s.bodyPathForID(r.BodyRef), syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		return bodyMissing
	}
	f := os.NewFile(uintptr(fd), s.bodyPathForID(r.BodyRef))
	defer func() { _ = f.Close() }()
	// The tombstone is a tiny fixed object; a real event's prefix truncated here
	// is unparseable JSON, so isRedactedBody rejects it and we classify bodyOK.
	const tombstoneProbeBytes = 4096
	buf, rerr := io.ReadAll(io.LimitReader(f, tombstoneProbeBytes))
	if rerr != nil {
		return bodyMissing
	}
	if isRedactedBody(buf) {
		return bodyRedacted
	}
	return bodyOK
}

// receiptBody is the single accessor every reader goes through to obtain a
// receipt's raw inner Slack event, transparently resolving the body sidecar for
// body-split receipts and returning the embedded event verbatim for legacy ones.
// A redacted, missing, or digest-mismatched body yields a JSON null so callers
// degrade uniformly (hydration → context_unavailable, reconciliation → no match)
// without needing to know which shape the receipt is.
func (s *IngressReceiptStore) receiptBody(r *IngressReceipt) json.RawMessage {
	body, _ := s.loadBody(r)
	return body
}

// isRedactedBody reports whether raw is the redacted tombstone.
func isRedactedBody(raw []byte) bool {
	var probe struct {
		Redacted bool `json:"redacted"`
	}
	if err := json.Unmarshal(raw, &probe); err != nil {
		return false
	}
	return probe.Redacted
}

// redactReceiptBody truncates a receipt's body sidecar to the fixed redacted
// tombstone ({"redacted": true, "event_digest": ...}) atomically, preserving the
// receipt's immutable digest. It is the operator-only redaction hook (exposed as
// an admin verb) and is NOT wired to any automatic trigger in this phase. A
// legacy embedded receipt has no separable body and is rejected.
func (s *IngressReceiptStore) redactReceiptBody(r *IngressReceipt) error {
	if r == nil || r.BodyRef == "" {
		return errors.New("ingress receipts: receipt has no separable body to redact")
	}
	if !isReceiptID(r.BodyRef) {
		return fmt.Errorf("ingress receipts: invalid body ref %q", r.BodyRef)
	}
	tomb, err := json.MarshalIndent(redactedBodyMarker{Redacted: true, EventDigest: r.EventDigest}, "", "  ")
	if err != nil {
		return fmt.Errorf("ingress receipts: marshal tombstone: %w", err)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	// Re-verify the receipt still exists under the store mutex (m2): the retention
	// sweep does not take the admin single-flight, so between the handler's GetByID
	// and here the receipt+body can be pair-deleted. writeBodyAtomic RENAMES the
	// tombstone into place (create-or-replace), which would resurrect a receipt-less
	// tombstone in the just-cleaned bodies dir and answer a false 200. Refuse with
	// ErrReceiptSwept (the handler maps it to 404) so the verb response stays
	// truthful and never leaves an orphan tombstone.
	if _, rerr := s.readReceiptFile(s.pathForID(r.ID)); rerr != nil {
		if errors.Is(rerr, os.ErrNotExist) {
			return ErrReceiptSwept
		}
		return fmt.Errorf("ingress receipts: redact re-check receipt %q: %w", r.ID, rerr)
	}
	// Redaction truncates an EXISTING body, never creates one: if the sidecar is
	// already gone (pair-deleted, or a mid-flight race), do not rename a tombstone
	// into an empty bodies dir.
	if _, berr := os.Lstat(s.bodyPathForID(r.BodyRef)); berr != nil {
		if errors.Is(berr, os.ErrNotExist) {
			return ErrReceiptSwept
		}
		return fmt.Errorf("ingress receipts: redact stat body %q: %w", r.BodyRef, berr)
	}
	if err := s.writeBodyAtomic(r.BodyRef, tomb); err != nil {
		s.writeFailures.Add(1)
		return err
	}
	return nil
}

// deleteBody removes a receipt's body sidecar (pair-delete at retention).
// Best-effort: a missing body is fine, any other failure is logged, never fatal.
func (s *IngressReceiptStore) deleteBody(r *IngressReceipt) {
	if r == nil || r.BodyRef == "" {
		return
	}
	path := s.bodyPathForID(r.BodyRef)
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		log.Printf("WARN: ingress receipts: pair-delete body %q: %v", path, err)
	}
}

// bodyFiles maps each body sidecar's receipt id to its path. A missing bodies
// dir is treated as empty; temp (*.tmp) files are skipped.
func (s *IngressReceiptStore) bodyFiles() (map[string]string, error) {
	entries, err := os.ReadDir(s.bodiesDir())
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, fmt.Errorf("ingress receipts: scan bodies %q: %w", s.bodiesDir(), err)
	}
	out := make(map[string]string)
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		name := e.Name()
		if !strings.HasSuffix(name, bodyFileSuffix) {
			continue
		}
		out[strings.TrimSuffix(name, bodyFileSuffix)] = filepath.Join(s.bodiesDir(), name)
	}
	return out, nil
}

// gcOrphanBodies removes body sidecars whose receipt no longer exists — a true
// crash orphan (the body was written but the receipt link never landed) or a body
// whose pair-delete missed. It is deliberately conservative: a body is removed
// ONLY when the receipt is affirmatively absent, so a receipt merely unreadable
// this pass (a transient EIO/EMFILE, or a quarantine whose rename failed) never
// loses its intact payload (C2/C8). Guards, cheapest first:
//
//   - live[id] — the receipt survived this sweep (non-terminal, within retention,
//     or a failed remove): keep its body.
//   - readErr[id] — the receipt errored on read this pass (may still be live on
//     disk, repairable against an intact body): never GC on an unread receipt.
//   - the body is younger than the grace window (m1): a cross-process in-flight
//     admission may not have linked its receipt yet — give it time.
//   - a receipt file OR a quarantine sibling still exists at the canonical name:
//     affirmative-absence, not "absent from the live map".
//
// Best-effort; the bodies dir is fsynced once if anything was removed. Called by
// the janitor under the store mutex.
func (s *IngressReceiptStore) gcOrphanBodies(live, readErr map[string]bool, now time.Time) {
	bodies, err := s.bodyFiles()
	if err != nil {
		log.Printf("WARN: ingress receipts: orphan-body scan: %v", err)
		return
	}
	removedAny := false
	for id, path := range bodies {
		if live[id] || readErr[id] {
			continue
		}
		info, statErr := os.Lstat(path)
		if statErr != nil {
			continue // vanished under us, or unreadable: never force-remove
		}
		if now.Sub(info.ModTime()) < bodyGCGraceWindow {
			continue // grace window: an in-flight admission may still link its receipt
		}
		if s.receiptOrQuarantineExists(id) {
			continue // affirmative-absence required before deleting a body
		}
		if derr := os.Remove(path); derr != nil {
			if errors.Is(derr, os.ErrNotExist) {
				continue
			}
			log.Printf("WARN: ingress receipts: gc orphan body %q: %v", path, derr)
			continue
		}
		removedAny = true
	}
	if removedAny {
		if serr := fsyncDir(s.bodiesDir()); serr != nil {
			log.Printf("WARN: ingress receipts: fsync bodies dir after orphan gc: %v", serr)
		}
	}
}

// receiptOrQuarantineExists reports whether a receipt file, or a quarantined
// sibling of one, still exists at the canonical name for id — the affirmative
// presence check that gates orphan-body GC. Cheap: one lstat plus a glob for the
// rare *.corrupt siblings.
func (s *IngressReceiptStore) receiptOrQuarantineExists(id string) bool {
	if _, err := os.Lstat(s.pathForID(id)); err == nil {
		return true
	}
	matches, err := filepath.Glob(s.pathForID(id) + "-*.corrupt")
	if err == nil && len(matches) > 0 {
		return true
	}
	return false
}

// quarantine renames a corrupt receipt file aside to a unique *.corrupt name and
// fsyncs the directory. The random token keeps repeated quarantines of the same
// origin from clobbering earlier forensic copies. It renames the RECEIPT ONLY,
// leaving the paired body untouched — Admit's corrupt-reclaim path quarantines a
// stale receipt AFTER writing the fresh admission's body, so touching the body
// here would strand the receipt being admitted. Scan callers that want forensic
// body parity use quarantineNonFatal, which pairs the body aside explicitly.
func (s *IngressReceiptStore) quarantine(path string) error {
	return s.quarantineTo(path, randomHexToken())
}

// quarantineTo renames path aside to path+"-"+token+".corrupt" and fsyncs the dir.
func (s *IngressReceiptStore) quarantineTo(path, token string) error {
	target := path + "-" + token + ".corrupt"
	if err := os.Rename(path, target); err != nil {
		return fmt.Errorf("rename %q -> %q: %w", path, target, err)
	}
	if err := fsyncDir(s.dir); err != nil {
		return fmt.Errorf("fsync dir after quarantine: %w", err)
	}
	log.Printf("WARN: ingress receipts: quarantined corrupt receipt %q -> %q", path, target)
	return nil
}

// quarantineNonFatal quarantines a corrupt scan entry, logging rather than
// propagating any failure — a single bad file must never fail a scan. It also
// renames the paired body sidecar aside under the SAME token
// (bodies/<id>.body-<token>.corrupt), preserving the raw payload the split moved
// out of the receipt so a receipt-corruption alone never destroys an intact body
// (C2/C8). This is the split-store analogue of the pre-split forensic copy, which
// carried the embedded event inside the quarantined receipt. Renaming the body
// aside also removes it from the orphan-GC's view, so it is never collected in the
// same pass that quarantined its receipt.
func (s *IngressReceiptStore) quarantineNonFatal(path string, cause error) {
	token := randomHexToken()
	if qerr := s.quarantineTo(path, token); qerr != nil {
		log.Printf("WARN: ingress receipts: quarantine %q (corrupt: %v) failed: %v", path, cause, qerr)
		return
	}
	id, ok := receiptIDFromPath(path)
	if !ok {
		return
	}
	bodyPath := s.bodyPathForID(id)
	corruptBody := bodyPath + "-" + token + ".corrupt"
	if err := os.Rename(bodyPath, corruptBody); err != nil {
		if !errors.Is(err, os.ErrNotExist) {
			log.Printf("WARN: ingress receipts: preserve body %q for quarantine: %v", bodyPath, err)
		}
		return
	}
	if serr := fsyncDir(s.bodiesDir()); serr != nil {
		log.Printf("WARN: ingress receipts: fsync bodies dir after body quarantine: %v", serr)
	}
	log.Printf("WARN: ingress receipts: preserved body %q -> %q for forensics", bodyPath, corruptBody)
}

// receiptIDFromPath extracts the receipt id from a store receipt path
// (<dir>/<id>.json), validating the id shape. A path that is not a well-formed
// receipt file reports ok=false.
func receiptIDFromPath(path string) (string, bool) {
	name := filepath.Base(path)
	if !strings.HasSuffix(name, ".json") {
		return "", false
	}
	id := strings.TrimSuffix(name, ".json")
	if !isReceiptID(id) {
		return "", false
	}
	return id, true
}

// validateOrigin rejects an origin missing any keyed component. Unkeyable
// events are dropped before Admit (Phase 1d), so this is a defensive
// guard rather than a routine path.
func validateOrigin(o ReceiptOrigin) error {
	if o.TeamID == "" || o.ChannelID == "" || o.TS == "" {
		return fmt.Errorf("ingress receipts: origin requires team/channel/ts, got %+v", o)
	}
	return nil
}

// normalizeEvent guarantees a legacy receipt's Event is valid JSON so marshaling
// a receipt with an absent inner event cannot error. A body-split receipt
// (BodyRef set) carries no embedded event and is left untouched — the guard also
// stops Update from re-embedding an "event": null on a split receipt read back
// from disk.
func normalizeEvent(r *IngressReceipt) {
	if r.BodyRef != "" {
		return
	}
	if len(r.Event) == 0 {
		r.Event = json.RawMessage("null")
	}
}

// splitReceiptBody moves a receipt's raw inner event into its bodies/ sidecar
// form: it returns the exact body bytes to persist and rewrites the receipt to
// carry only the reference — body_ref (its own id), event_digest (sha256 of the
// body bytes), schema_version — with the embedded Event cleared. Called once, at
// Admit, before the body and receipt are written.
func splitReceiptBody(r *IngressReceipt) []byte {
	body := append([]byte(nil), r.Event...)
	if len(body) == 0 {
		body = []byte("null")
	}
	r.BodyRef = r.ID
	r.EventDigest = eventDigest(body)
	r.SchemaVersion = ingressReceiptSchemaBodyRef
	r.Event = nil
	return body
}

// eventDigest is the sha256 hex over the stored body bytes — the receipt's
// immutable integrity anchor.
func eventDigest(body []byte) string {
	sum := sha256.Sum256(body)
	return hex.EncodeToString(sum[:])
}

// marshalReceipt encodes a receipt to indented JSON.
func marshalReceipt(r *IngressReceipt) ([]byte, error) {
	data, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("ingress receipts: marshal %q: %w", r.ID, err)
	}
	return data, nil
}

// isTerminalStatus reports whether a receipt status is terminal
// (delivered / no_delivery / failed). Non-terminal receipts are returned
// by Pending and never swept.
func isTerminalStatus(status string) bool {
	switch status {
	case ingressStatusDelivered, ingressStatusNoDelivery, ingressStatusFailed:
		return true
	default:
		return false
	}
}

// receiptID derives the origin-keyed receipt id. The readable prefix is
// built from safeStorageID-sanitized components (hostile/long components
// hashed); a short digest over the exact (team, channel, ts) tuple —
// separated by NUL so components can never be confused — is appended so
// two distinct origins can never collide even if their sanitized readable
// forms would.
func receiptID(o ReceiptOrigin) string {
	readable := safeStorageID(o.TeamID, "team") + "-" +
		safeStorageID(o.ChannelID, "chan") + "-" +
		safeStorageID(o.TS, "ts")
	sum := sha256.Sum256([]byte(o.TeamID + "\x00" + o.ChannelID + "\x00" + o.TS))
	return "in-" + readable + "-" + hex.EncodeToString(sum[:])[:12]
}

// isReceiptID reports whether id matches the exact shape receiptID produces:
// "in-" followed by one or more bytes from [A-Za-z0-9._-] (the pattern
// ^in-[A-Za-z0-9._-]+$). Every generated id passes — the readable prefix is
// built from safeStorageID components (that same character set) and a hex digest
// — while any id carrying a path separator, NUL, or other hostile byte is
// rejected before it can be joined into a store path.
func isReceiptID(id string) bool {
	if !strings.HasPrefix(id, "in-") || len(id) <= len("in-") {
		return false
	}
	for i := 0; i < len(id); i++ {
		ch := id[i]
		switch {
		case ch >= 'a' && ch <= 'z':
		case ch >= 'A' && ch <= 'Z':
		case ch >= '0' && ch <= '9':
		case ch == '.' || ch == '_' || ch == '-':
		default:
			return false
		}
	}
	return true
}

// safeStorageID returns value unchanged when it is a short, filename-safe
// token; otherwise it returns "<prefix>-<sha256[:24]>". Mirrors the
// intake packs' safe_storage_id sanitizer (hash long/hostile components).
func safeStorageID(value, prefix string) string {
	value = strings.TrimSpace(value)
	if value != "" && len(value) <= maxSafeComponentLen && isSafeStorageValue(value) {
		return value
	}
	sum := sha256.Sum256([]byte(value))
	return prefix + "-" + hex.EncodeToString(sum[:])[:24]
}

// isSafeStorageValue reports whether v is composed only of ASCII
// alphanumerics and the separators '-', '_', '.', with no path-traversal
// sequence or leading dot. Anything else is considered hostile and hashed.
func isSafeStorageValue(v string) bool {
	if strings.Contains(v, "..") || strings.HasPrefix(v, ".") {
		return false
	}
	for i := 0; i < len(v); i++ {
		ch := v[i]
		switch {
		case ch >= 'a' && ch <= 'z':
		case ch >= 'A' && ch <= 'Z':
		case ch >= '0' && ch <= '9':
		case ch == '-' || ch == '_' || ch == '.':
		default:
			return false
		}
	}
	return true
}

// fsyncDir fsyncs a directory so a rename/link/remove of one of its
// entries is durable across a crash.
func fsyncDir(dir string) error {
	d, err := os.Open(dir)
	if err != nil {
		return err
	}
	serr := d.Sync()
	cerr := d.Close()
	if serr != nil {
		return serr
	}
	return cerr
}

// randomHexToken returns 16 hex chars of randomness for quarantine names.
// On the (practically impossible) crypto/rand failure it falls back to a
// nanosecond timestamp; quarantine naming is best-effort forensics, not a
// correctness primitive.
func randomHexToken() string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b[:])
}

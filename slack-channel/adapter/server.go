package main

import (
	"fmt"
	"maps"
	"net/http"
	"sort"
	"sync"
	"time"
)

// inboundRef remembers the last inbound message delivered to a session so
// `reply-current` and `react` can act on "the message I just received"
// without the caller having to thread channel/ts by hand. It is in-memory
// and best-effort: an adapter restart clears it, after which reply-current
// falls back to the session's channel binding.
//
// messageTS is the specific message (what `react` reacts on); threadTS is
// the thread root to reply under (what `reply-current` threads against) —
// the parent thread when the inbound was itself a threaded reply, else the
// message's own ts.
type inboundRef struct {
	channelID string
	messageTS string
	threadTS  string
}

// server holds the adapter's configuration, the three on-disk registries
// (mirrored in memory), and the per-session last-inbound map. It is the
// single owner of registry state: verb endpoints mutate through it under a
// write lock, and the inbound path reads through it under a read lock.
//
// Two locks guard the registries: regMu protects the in-memory maps
// (readers on the inbound hot path take RLock), and writeMu serializes
// mutators. A mutator holds writeMu for the whole operation but takes regMu
// only to mutate the map and snapshot it — the disk flush happens under
// writeMu alone, so a registry write never blocks an inbound read on file
// I/O, while writeMu still guarantees on-disk order matches mutation order.
type server struct {
	cfg config

	writeMu    sync.Mutex                // serializes registry mutators (held across disk flush)
	regMu      sync.RWMutex              // protects the in-memory maps below
	channels   map[string]channelBinding // key: "<workspace>:<channel>"
	identities map[string]identity       // key: session id
	aliases    map[string]handleAlias    // key: handle

	lastMu      sync.RWMutex
	lastInbound map[string]inboundRef // key: session id

	httpClient *http.Client
	now        func() time.Time
}

func newServer(cfg config) (*server, error) {
	s := &server{
		cfg:         cfg,
		channels:    map[string]channelBinding{},
		identities:  map[string]identity{},
		aliases:     map[string]handleAlias{},
		lastInbound: map[string]inboundRef{},
		httpClient:  &http.Client{},
		now:         func() time.Time { return time.Now() },
	}
	if err := s.loadRegistries(); err != nil {
		return nil, err
	}
	return s, nil
}

func (s *server) nowStamp() string { return s.now().UTC().Format(time.RFC3339) }

// loadRegistries reads all three registry files into memory. Missing files
// are treated as empty registries (a fresh city), not an error.
func (s *server) loadRegistries() error {
	s.regMu.Lock()
	defer s.regMu.Unlock()
	if err := loadJSONMap(s.cfg.channelMappingsPath(), &s.channels); err != nil {
		return err
	}
	if err := loadJSONMap(s.cfg.identitiesPath(), &s.identities); err != nil {
		return err
	}
	if err := loadJSONMap(s.cfg.handleAliasesPath(), &s.aliases); err != nil {
		return err
	}
	return nil
}

// --- channel bindings -----------------------------------------------------

// upsertBinding validates and persists a channel→sessions binding. An
// idempotent re-bind preserves the original created_at and only advances
// updated_at.
func (s *server) upsertBinding(channelID, kind string, sessionIDs []string) (channelBinding, error) {
	cleaned, err := validateBinding(s.cfg.workspaceID, channelID, kind, sessionIDs)
	if err != nil {
		return channelBinding{}, err
	}
	s.writeMu.Lock()
	defer s.writeMu.Unlock()

	now := s.nowStamp()
	rec := channelBinding{
		WorkspaceID: s.cfg.workspaceID,
		ChannelID:   channelID,
		Kind:        kind,
		SessionIDs:  cleaned,
		CreatedAt:   now,
		UpdatedAt:   now,
	}
	s.regMu.Lock()
	key := bindingKey(s.cfg.workspaceID, channelID)
	if prev, ok := s.channels[key]; ok {
		rec.CreatedAt = prev.CreatedAt
	}
	s.channels[key] = rec
	snapshot := maps.Clone(s.channels)
	s.regMu.Unlock()

	if err := saveJSONAtomic(s.cfg.channelMappingsPath(), snapshot); err != nil {
		return channelBinding{}, err
	}
	return rec, nil
}

// bindingForChannel returns the binding for a channel in the configured
// workspace, if any.
func (s *server) bindingForChannel(channelID string) (channelBinding, bool) {
	s.regMu.RLock()
	defer s.regMu.RUnlock()
	rec, ok := s.channels[bindingKey(s.cfg.workspaceID, channelID)]
	return rec, ok
}

// channelsForSession returns the sorted channel ids the session is bound
// to within the configured workspace. Used by `publish` to resolve a
// session's single bound conversation.
func (s *server) channelsForSession(sessionID string) []string {
	s.regMu.RLock()
	defer s.regMu.RUnlock()
	var out []string
	for _, rec := range s.channels {
		for _, sid := range rec.SessionIDs {
			if sid == sessionID {
				out = append(out, rec.ChannelID)
				break
			}
		}
	}
	sort.Strings(out)
	return out
}

// --- identities -----------------------------------------------------------

func (s *server) upsertIdentity(sessionID, username, iconURL, iconEmoji string) (identity, error) {
	if err := validateIdentity(sessionID, username, iconURL, iconEmoji); err != nil {
		return identity{}, err
	}
	s.writeMu.Lock()
	defer s.writeMu.Unlock()

	now := s.nowStamp()
	rec := identity{
		SessionID: sessionID,
		Username:  username,
		IconURL:   iconURL,
		IconEmoji: iconEmoji,
		CreatedAt: now,
		UpdatedAt: now,
	}
	s.regMu.Lock()
	if prev, ok := s.identities[sessionID]; ok {
		rec.CreatedAt = prev.CreatedAt
	}
	s.identities[sessionID] = rec
	snapshot := maps.Clone(s.identities)
	s.regMu.Unlock()

	if err := saveJSONAtomic(s.cfg.identitiesPath(), snapshot); err != nil {
		return identity{}, err
	}
	return rec, nil
}

// removeIdentity deletes a session's identity override. It is idempotent:
// removing a missing entry reports removed=false without erroring.
func (s *server) removeIdentity(sessionID string) (bool, error) {
	s.writeMu.Lock()
	defer s.writeMu.Unlock()

	s.regMu.Lock()
	if _, ok := s.identities[sessionID]; !ok {
		s.regMu.Unlock()
		return false, nil
	}
	delete(s.identities, sessionID)
	snapshot := maps.Clone(s.identities)
	s.regMu.Unlock()

	if err := saveJSONAtomic(s.cfg.identitiesPath(), snapshot); err != nil {
		return false, err
	}
	return true, nil
}

func (s *server) identityFor(sessionID string) (identity, bool) {
	s.regMu.RLock()
	defer s.regMu.RUnlock()
	rec, ok := s.identities[sessionID]
	return rec, ok
}

// --- handle aliases -------------------------------------------------------

func (s *server) upsertHandleAlias(handle, sessionID string) (handleAlias, error) {
	h, err := validateHandle(handle, sessionID)
	if err != nil {
		return handleAlias{}, err
	}
	s.writeMu.Lock()
	defer s.writeMu.Unlock()

	now := s.nowStamp()
	rec := handleAlias{Handle: h, SessionID: sessionID, CreatedAt: now, UpdatedAt: now}
	s.regMu.Lock()
	if prev, ok := s.aliases[h]; ok {
		rec.CreatedAt = prev.CreatedAt
	}
	s.aliases[h] = rec
	snapshot := maps.Clone(s.aliases)
	s.regMu.Unlock()

	if err := saveJSONAtomic(s.cfg.handleAliasesPath(), snapshot); err != nil {
		return handleAlias{}, err
	}
	return rec, nil
}

func (s *server) removeHandleAlias(handle string) (bool, error) {
	h := normalizeHandle(handle)
	if h == "" {
		return false, fmt.Errorf("handle is required")
	}
	s.writeMu.Lock()
	defer s.writeMu.Unlock()

	s.regMu.Lock()
	if _, ok := s.aliases[h]; !ok {
		s.regMu.Unlock()
		return false, nil
	}
	delete(s.aliases, h)
	snapshot := maps.Clone(s.aliases)
	s.regMu.Unlock()

	if err := saveJSONAtomic(s.cfg.handleAliasesPath(), snapshot); err != nil {
		return false, err
	}
	return true, nil
}

func (s *server) aliasFor(handle string) (handleAlias, bool) {
	s.regMu.RLock()
	defer s.regMu.RUnlock()
	rec, ok := s.aliases[normalizeHandle(handle)]
	return rec, ok
}

// --- last-inbound tracking ------------------------------------------------

func (s *server) recordInbound(sessionID string, ref inboundRef) {
	s.lastMu.Lock()
	defer s.lastMu.Unlock()
	s.lastInbound[sessionID] = ref
}

func (s *server) latestInbound(sessionID string) (inboundRef, bool) {
	s.lastMu.RLock()
	defer s.lastMu.RUnlock()
	ref, ok := s.lastInbound[sessionID]
	return ref, ok
}

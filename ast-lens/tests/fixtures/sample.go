// Package store implements an in-memory session store with optional
// write-through to a backing cache. It is safe for concurrent use; all
// exported methods take the package-level mutex.
package store

import (
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/example/cache"
)

// ErrNotFound is returned when a session id is absent from the store.
var ErrNotFound = errors.New("store: session not found")

// ErrExpired is returned when a session exists but its TTL has elapsed.
var ErrExpired = errors.New("store: session expired")

// DefaultTTL is the fallback session lifetime when none is supplied.
const DefaultTTL = 30 * time.Minute

// maxSessions caps the number of live sessions before eviction kicks in.
const maxSessions = 4096

// Session is a single user session held by the store.
type Session struct {
	ID        string
	UserID    int64
	CreatedAt time.Time
	ExpiresAt time.Time
	Data      map[string]string
}

// Repository is the behaviour the store exposes to its callers.
type Repository interface {
	Get(id string) (*Session, error)
	Save(s *Session) error
	Delete(id string) error
	Len() int
}

// Store is the concrete in-memory Repository implementation.
type Store struct {
	mu       sync.RWMutex
	sessions map[string]*Session
	cache    *cache.Client
	ttl      time.Duration
	now      func() time.Time
}

// Option configures a Store at construction time.
type Option func(*Store)

// WithTTL overrides the default session TTL.
func WithTTL(d time.Duration) Option {
	return func(s *Store) {
		s.ttl = d
	}
}

// WithCache attaches a write-through cache client.
func WithCache(c *cache.Client) Option {
	return func(s *Store) {
		s.cache = c
	}
}

// New constructs a Store with the supplied options applied.
func New(opts ...Option) *Store {
	s := &Store{
		sessions: make(map[string]*Session),
		ttl:      DefaultTTL,
		now:      time.Now,
	}
	for _, opt := range opts {
		opt(s)
	}
	return s
}

// Get returns the session for id or ErrNotFound / ErrExpired.
func (s *Store) Get(id string) (*Session, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	sess, ok := s.sessions[id]
	if !ok {
		return nil, ErrNotFound
	}
	if s.isExpired(sess) {
		return nil, ErrExpired
	}
	return sess, nil
}

// Save inserts or replaces a session, evicting if at capacity.
func (s *Store) Save(sess *Session) error {
	if sess == nil || sess.ID == "" {
		return fmt.Errorf("store: invalid session")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.sessions) >= maxSessions {
		s.evictOldest()
	}
	if sess.ExpiresAt.IsZero() {
		sess.ExpiresAt = s.now().Add(s.ttl)
	}
	s.sessions[sess.ID] = sess
	if s.cache != nil {
		go s.writeThrough(sess)
	}
	return nil
}

// Delete removes a session if present; absence is not an error.
func (s *Store) Delete(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.sessions, id)
	return nil
}

// Len reports the number of sessions currently held.
func (s *Store) Len() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.sessions)
}

// Purge removes all expired sessions and returns the count removed.
func (s *Store) Purge() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	removed := 0
	for id, sess := range s.sessions {
		if s.isExpired(sess) {
			delete(s.sessions, id)
			removed++
		}
	}
	return removed
}

// isExpired reports whether sess has passed its expiry instant.
func (s *Store) isExpired(sess *Session) bool {
	return !sess.ExpiresAt.IsZero() && s.now().After(sess.ExpiresAt)
}

// evictOldest drops the session with the earliest CreatedAt.
func (s *Store) evictOldest() {
	var oldestID string
	var oldest time.Time
	for id, sess := range s.sessions {
		if oldestID == "" || sess.CreatedAt.Before(oldest) {
			oldestID = id
			oldest = sess.CreatedAt
		}
	}
	if oldestID != "" {
		delete(s.sessions, oldestID)
	}
}

// writeThrough mirrors a session into the attached cache, best-effort.
func (s *Store) writeThrough(sess *Session) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Println("store: writeThrough recovered:", r)
		}
	}()
	key := fmt.Sprintf("sess:%s", sess.ID)
	_ = s.cache.Set(key, sess.UserID, s.ttl)
}

// NewSession builds a Session with a fresh creation timestamp.
func NewSession(id string, userID int64) *Session {
	return &Session{
		ID:        id,
		UserID:    userID,
		CreatedAt: time.Now(),
		Data:      make(map[string]string),
	}
}

// MergeData copies src entries into dst, returning the mutated dst.
func MergeData(dst, src map[string]string) map[string]string {
	if dst == nil {
		dst = make(map[string]string)
	}
	for k, v := range src {
		dst[k] = v
	}
	return dst
}

// validateID enforces the internal id format (private helper).
func validateID(id string) error {
	if len(id) < 8 {
		return errors.New("store: id too short")
	}
	for _, r := range id {
		if r == ' ' {
			return errors.New("store: id contains space")
		}
	}
	return nil
}

// countActive is a private helper that tallies non-expired sessions.
func countActive(s *Store) int {
	n := 0
	for _, sess := range s.sessions {
		if !s.isExpired(sess) {
			n++
		}
	}
	return n
}

// dumpStats is a private diagnostic that prints store internals.
func dumpStats(s *Store) string {
	return fmt.Sprintf("sessions=%d ttl=%s", len(s.sessions), s.ttl)
}

// Stats reports counts of total and active sessions for callers.
func (s *Store) Stats() (total, active int) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.sessions), countActive(s)
}

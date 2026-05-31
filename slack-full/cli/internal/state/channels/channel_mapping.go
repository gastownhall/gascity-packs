// Package channels persists Slack channel → (rig | session) bindings
// written by `gc slack map-channel` and read by the slack-pack
// adapter's /slack/interactions handler.
//
// Ported from cmd/gc/slack_channel_mapping.go (gc-nqy49) as part of
// the slack-cli relocation epic gc-coe10. Behavior identical to the
// cmd/gc original — Phase 2 deletes the original after consumers cut
// over.
package channels

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"time"
)

// Record is the persisted representation of a (workspace_id,
// channel_id) → (target_kind, target_id) binding written by `gc slack
// map-channel` and read by the slack-pack adapter's
// /slack/interactions handler. The schema is the only contract between
// the CLI (writer) and the adapter (reader, at adapter/, pack-relative);
// both sides MUST match it byte-for-byte. The authoritative description
// lives at schema/channel_mappings.schema.json (pack-relative).
//
// CreatedAt is set on first Set and preserved on every idempotent
// re-Set for the same composite key. UpdatedAt advances on every Set.
type Record struct {
	WorkspaceID string    `json:"workspace_id"`
	ChannelID   string    `json:"channel_id"`
	TargetKind  string    `json:"target_kind"` // "rig" or "session"
	TargetID    string    `json:"target_id"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// TargetKindRig and TargetKindSession are the only legal target_kind
// values. Records with any other kind are rejected at Set time AND at
// load time (corrupt-file rejection).
const (
	TargetKindRig     = "rig"
	TargetKindSession = "session"
)

// Path returns the on-disk path for the channel mapping registry of
// the city rooted at cityPath. Replaces the cmd/gc helper that went
// through internal/citylayout.RuntimePath.
func Path(cityPath string) string {
	return filepath.Join(cityPath, ".gc", "slack", "channel_mappings.json")
}

// Registry mirrors apps.Registry: in-memory sync.RWMutex-protected
// map keyed by composite key, atomic temp+rename writes, 0o700/0o600
// perms, tolerant load on missing file.
type Registry struct {
	mu       sync.RWMutex
	byKey    map[string]Record
	diskPath string
}

// Key composes the registry key from (workspaceID, channelID).
func Key(workspaceID, channelID string) string {
	return workspaceID + ":" + channelID
}

// NewRegistry opens (or creates) the registry at diskPath. A missing
// file yields an empty registry (tolerant load); a file with a record
// carrying an unknown target_kind is rejected so downstream readers
// (the adapter) cannot consume corrupt state silently.
func NewRegistry(diskPath string) (*Registry, error) {
	r := &Registry{
		byKey:    make(map[string]Record),
		diskPath: diskPath,
	}
	if err := r.load(); err != nil {
		return nil, fmt.Errorf("load slack channel mapping registry from %s: %w", diskPath, err)
	}
	return r, nil
}

// Get returns the mapping record for (workspaceID, channelID), plus a
// bool indicating whether one is registered.
func (r *Registry) Get(workspaceID, channelID string) (Record, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	rec, ok := r.byKey[Key(workspaceID, channelID)]
	return rec, ok
}

// Set is idempotent: re-setting an existing (workspace_id, channel_id)
// preserves the original CreatedAt and overwrites the rest of the
// record. The registry size never grows from idempotent re-sets.
func (r *Registry) Set(rec Record) error {
	if rec.WorkspaceID == "" {
		return fmt.Errorf("slack channel mapping: workspace_id is required")
	}
	if rec.ChannelID == "" {
		return fmt.Errorf("slack channel mapping: channel_id is required")
	}
	if rec.TargetKind == "" {
		return fmt.Errorf("slack channel mapping: target_kind is required")
	}
	if rec.TargetID == "" {
		return fmt.Errorf("slack channel mapping: target_id is required")
	}
	if rec.TargetKind != TargetKindRig &&
		rec.TargetKind != TargetKindSession {
		return fmt.Errorf("slack channel mapping: target_kind %q must be %q or %q",
			rec.TargetKind, TargetKindRig, TargetKindSession)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	key := Key(rec.WorkspaceID, rec.ChannelID)
	if existing, ok := r.byKey[key]; ok {
		// Preserve CreatedAt across idempotent re-sets — only UpdatedAt
		// (and the target fields) advance.
		rec.CreatedAt = existing.CreatedAt
	}
	r.byKey[key] = rec
	return r.saveLocked()
}

// Remove deletes the mapping for (workspaceID, channelID) if present.
// Returns whether an entry existed; missing entries are not an error so
// callers can treat Remove as idempotent.
func (r *Registry) Remove(workspaceID, channelID string) (bool, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	key := Key(workspaceID, channelID)
	_, existed := r.byKey[key]
	if !existed {
		return false, nil
	}
	delete(r.byKey, key)
	if err := r.saveLocked(); err != nil {
		return existed, err
	}
	return existed, nil
}

// All returns every registered mapping, sorted by composite key
// (<workspace_id>:<channel_id>). Deterministic order keeps `gc slack
// status` and JSON dumps diff-stable.
func (r *Registry) All() []Record {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]Record, 0, len(r.byKey))
	keys := make([]string, 0, len(r.byKey))
	for k := range r.byKey {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		out = append(out, r.byKey[k])
	}
	return out
}

// MaxBytes caps the size of the JSON registry file we'll read off
// disk. The slack channel-mapping registry stores at most a few
// hundred records of a fixed shape, so 10 MiB is several orders of
// magnitude over what a healthy install ever produces; a file beyond
// that is either corrupt or hostile and must not be loaded.
const MaxBytes = 10 << 20 // 10 MiB

func (r *Registry) load() error {
	if r.diskPath == "" {
		return nil
	}
	f, err := os.Open(r.diskPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return err
	}
	defer func() { _ = f.Close() }()
	data, err := io.ReadAll(io.LimitReader(f, MaxBytes+1))
	if err != nil {
		return fmt.Errorf("read %s: %w", r.diskPath, err)
	}
	if int64(len(data)) > MaxBytes {
		return fmt.Errorf("registry file %s exceeds %d bytes", r.diskPath, MaxBytes)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var stored map[string]Record
	if err := dec.Decode(&stored); err != nil {
		return fmt.Errorf("decode slack channel mapping store: %w", err)
	}
	for key, rec := range stored {
		if rec.TargetKind != TargetKindRig &&
			rec.TargetKind != TargetKindSession {
			return fmt.Errorf("slack channel mapping store: record %q has invalid target_kind %q (must be %q or %q)",
				key, rec.TargetKind, TargetKindRig, TargetKindSession)
		}
	}
	if stored != nil {
		r.byKey = stored
	}
	return nil
}

func (r *Registry) saveLocked() error {
	if r.diskPath == "" {
		return nil
	}
	// 0o700/0o600: records carry workspace ids and gc target ids; not
	// world-readable. Chmod after MkdirAll so the contract holds even
	// when the directory pre-exists with looser permissions.
	dir := filepath.Dir(r.diskPath)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("mkdir slack channel mapping store dir %q: %w", dir, err)
	}
	if err := os.Chmod(dir, 0o700); err != nil {
		return fmt.Errorf("chmod slack channel mapping store dir %q: %w", dir, err)
	}
	data, err := json.MarshalIndent(r.byKey, "", "  ")
	if err != nil {
		return fmt.Errorf("encode slack channel mapping store: %w", err)
	}
	// os.CreateTemp picks a unique name in dir, so two concurrent CLI
	// invocations writing the same registry don't clobber each other's
	// temp file before the rename.
	f, err := os.CreateTemp(dir, "channel_mappings-*.json.tmp")
	if err != nil {
		return fmt.Errorf("create slack channel mapping store tmp: %w", err)
	}
	tmpName := f.Name()
	cleanup := func() { _ = os.Remove(tmpName) }
	if err := f.Chmod(0o600); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("chmod slack channel mapping store tmp: %w", err)
	}
	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("write slack channel mapping store tmp: %w", err)
	}
	if err := f.Close(); err != nil {
		cleanup()
		return fmt.Errorf("close slack channel mapping store tmp: %w", err)
	}
	if err := os.Rename(tmpName, r.diskPath); err != nil {
		cleanup()
		return fmt.Errorf("rename slack channel mapping store: %w", err)
	}
	return nil
}

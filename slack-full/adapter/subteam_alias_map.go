package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"sort"
	"sync"
)

// subteamAliasMap is the read-mostly adapter-side view of the
// subteam-aliases.json file written by the operator. It maps a Slack
// User Group ("subteam") ID (e.g. "S0123ABCD") to the gc handle the
// adapter should treat the mention as addressing.
//
// This is the operator-facing counterpart of handleAliasRegistry:
// where handleAliasRegistry is runtime-mutable via the in-process
// /handle-alias HTTP endpoint, subteamAliasMap is CLI/operator-edited
// off-band (file edited directly, or written by a future
// `gc slack subteam-alias` command) and reloaded on SIGHUP via the
// same Stage/Commit pattern as channelMappingRegistry,
// rigMappingRegistry, and roomLaunchMappingRegistry.
//
// The map is the ONLY gate for unlabeled subteam mentions
// (`<!subteam^Sxxx>`) — Slack does not emit a handle label in that
// shape, so the adapter must resolve `Sxxx` → handle via this map
// before it can route the inbound through the existing
// address-by-handle dispatch path. The labeled form
// `<!subteam^Sxxx|@handle>` is gated separately by aliasReg.Get on
// the `@handle` label (matching the gpk-2zi behavior). See the
// processSlackEvent wiring for the full picture.
//
// Locked-down Slack apps that lack the `usergroups:read` scope are
// fully supported: subteam-aliases.json is a static file the operator
// populates manually. No usergroups.list fetch is performed by v1.
type subteamAliasMap struct {
	mu         sync.RWMutex
	byID       map[string]string // subteam_id -> handle
	diskPath   string
}

// subteamAliasSnapshot is a parsed-but-not-yet-committed view of
// subteam-aliases.json. nil = "file absent" sentinel — same SIGHUP
// semantics as roomLaunchMappingSnapshot.
type subteamAliasSnapshot struct {
	byID map[string]string
}

// newSubteamAliasMap opens (or creates) the map at diskPath. A missing
// file yields an empty map — operators on locked-down apps without
// the file in place still get a fully-functional adapter; subteam
// mentions just fall through to channel fanout (the bead's
// "unknown-subteam-ID via unlabeled form" branch).
func newSubteamAliasMap(diskPath string) (*subteamAliasMap, error) {
	m := &subteamAliasMap{
		byID:     make(map[string]string),
		diskPath: diskPath,
	}
	if err := m.load(); err != nil {
		return nil, fmt.Errorf("load subteam alias map from %s: %w", diskPath, err)
	}
	return m, nil
}

// Get returns the handle bound to subteamID plus a bool indicating
// whether one is registered. A miss means the subteam is NOT enabled
// for address-by-handle routing — the adapter falls through to its
// existing channel-fanout behavior.
func (m *subteamAliasMap) Get(subteamID string) (string, bool) {
	if m == nil {
		return "", false
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	h, ok := m.byID[subteamID]
	return h, ok
}

// Len returns the number of bindings currently loaded. Used by the
// startup / SIGHUP log lines so operators can confirm a reload picked
// up an edit.
func (m *subteamAliasMap) Len() int {
	if m == nil {
		return 0
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.byID)
}

// All returns every loaded binding as `subteam_id=handle` strings,
// sorted by subteam_id for diff-stable test ordering. Tests only.
func (m *subteamAliasMap) All() []string {
	if m == nil {
		return nil
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	ids := make([]string, 0, len(m.byID))
	for id := range m.byID {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		out = append(out, id+"="+m.byID[id])
	}
	return out
}

// maxSubteamAliasBytes caps the JSON file size. Slack User Group IDs
// are ~11 chars, handles are short strings; even a workspace with
// thousands of User Groups is comfortably under a few hundred KiB. 10
// MiB matches roomLaunchMappingRegistry's ceiling and is several
// orders of magnitude above any healthy install.
const maxSubteamAliasBytes = 10 << 20 // 10 MiB

// parseSubteamAliasMap reads diskPath into a ready-to-commit snapshot.
// nil + nil = "file absent" sentinel for SIGHUP semantics, matching
// parseRoomLaunchMappingRegistry. Empty handles or empty subteam IDs
// are rejected at parse time so a corrupt upstream write can't quietly
// dispatch to "" handles or under "" subteam IDs.
func parseSubteamAliasMap(diskPath string) (*subteamAliasSnapshot, error) {
	if diskPath == "" {
		return nil, nil
	}
	f, err := openRegistryFile(diskPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, maxSubteamAliasBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", diskPath, err)
	}
	if int64(len(data)) > maxSubteamAliasBytes {
		return nil, fmt.Errorf("subteam alias file %s exceeds %d bytes", diskPath, maxSubteamAliasBytes)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var stored map[string]string
	if err := dec.Decode(&stored); err != nil {
		return nil, fmt.Errorf("decode subteam alias map: %w", err)
	}
	for id, handle := range stored {
		if id == "" {
			return nil, fmt.Errorf("subteam alias map: empty subteam_id key")
		}
		if handle == "" {
			return nil, fmt.Errorf("subteam alias map: empty handle for subteam_id %q", id)
		}
	}
	if stored == nil {
		stored = make(map[string]string)
	}
	return &subteamAliasSnapshot{byID: stored}, nil
}

// load is the constructor-time helper — called pre-publish, no lock needed.
func (m *subteamAliasMap) load() error {
	snap, err := parseSubteamAliasMap(m.diskPath)
	if err != nil {
		return err
	}
	if snap != nil {
		m.byID = snap.byID
	}
	return nil
}

// Stage parses the on-disk file into a snapshot ready for atomic Commit.
// nil snapshot + nil error = file absent, preserve live state.
func (m *subteamAliasMap) Stage() (*subteamAliasSnapshot, error) {
	return parseSubteamAliasMap(m.diskPath)
}

// Commit atomically swaps the in-memory snapshot under the write lock.
func (m *subteamAliasMap) Commit(snap *subteamAliasSnapshot) {
	if snap == nil {
		return
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.byID = snap.byID
}

// Reload combines Stage and Commit; per-registry test convenience.
func (m *subteamAliasMap) Reload() error {
	snap, err := m.Stage()
	if err != nil {
		return err
	}
	m.Commit(snap)
	return nil
}

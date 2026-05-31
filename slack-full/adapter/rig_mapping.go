package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

// rigMappingDiskRecord is the byte-for-byte mirror of the slack-cli's
// rigs.Record (cli/internal/state/rigs/rig_mapping.go, pack-relative).
// The schema lives at schema/rig_mappings.schema.json (pack-relative).
//
// SlingTarget and FixFormula are dispatch-routing fields (cby.18.a):
// the adapter passes SlingTarget to `gc sling --target` and uses
// FixFormula as the molecule name to spawn. Both are optional in the
// JSON Schema for legacy-record tolerance — load-time missing → empty
// string; ResolveSlingTarget surfaces a fix-it error at use time when
// SlingTarget is empty.
type rigMappingDiskRecord struct {
	WorkspaceID string   `json:"workspace_id"`
	RigName     string   `json:"rig_name"`
	ChannelIDs  []string `json:"channel_ids"`
	// ChannelPatterns are glob patterns matched against Slack channel
	// NAMES (path.Match syntax restricted to a-z, 0-9, '-', '_', * ?
	// [ ] ^ !). Persisted in lockstep with cmd/gc.slackRigMappingRecord.
	// Either ChannelIDs or ChannelPatterns must be non-empty. The
	// runtime resolver tier that consumes patterns ships with the
	// slash-command intake bead — for now this field is parsed,
	// validated, and indexed into byPattern so the adapter is
	// forward-compatible with files written by the new CLI (without
	// parsing, DisallowUnknownFields would reject them).
	ChannelPatterns []string  `json:"channel_patterns,omitempty"`
	SlingTarget     string    `json:"sling_target,omitempty"`
	FixFormula      string    `json:"fix_formula,omitempty"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// rigMappingRegistry is a read-mostly in-memory view of the
// rig_mappings.json file written by `gc slack map-rig`. Loaded once at
// adapter startup and re-read on SIGHUP via Stage/Commit (gc-cby.23).
// Same caveat as channelMappingRegistry — a watcher would race against
// in-flight Slack interactions, and Slack's 3-second slash-command
// latency budget is too tight to retry.
type rigMappingRegistry struct {
	mu        sync.RWMutex
	byKey     map[string]rigMappingDiskRecord // "<workspace_id>:<rig_name>"
	byChannel map[string]string               // "<workspace_id>:<channel_id>" -> rigName
	// byPattern groups patterns by composite (workspaceID, rigName)
	// key. Population is mechanical (one pattern → one entry under the
	// owning rig's key) so SIGHUP reload can swap it atomically. The
	// resolver that walks this index ships with cby.b — for now it is
	// parsed and exposed via PatternsForRig so the adapter is
	// forward-compatible with operator-written pattern records.
	byPattern map[string][]string // "<workspace_id>:<rig_name>" -> sorted patterns
	diskPath  string
}

// rigMappingSnapshot is a parsed-but-not-yet-committed view of
// rig_mappings.json. Carries BOTH byKey and byChannel pre-built so the
// live indexes never desync mid-commit. nil = "file absent" sentinel.
type rigMappingSnapshot struct {
	byKey     map[string]rigMappingDiskRecord
	byChannel map[string]string
	// byPattern is swapped together with byKey/byChannel under the
	// same write lock so a SIGHUP reload never exposes a state where
	// patterns reference rigs that are no longer present (or vice
	// versa).
	byPattern map[string][]string
}

func rigMappingKey(workspaceID, rigName string) string {
	return workspaceID + ":" + rigName
}

func rigChannelKey(workspaceID, channelID string) string {
	return workspaceID + ":" + channelID
}

// newRigMappingRegistry opens (or creates) the registry at diskPath.
// A missing file yields an empty registry. Unknown fields, empty
// channel_ids, and missing workspace_id/rig_name are rejected at
// load time so a corrupt upstream write can't silently be served as
// policy.
func newRigMappingRegistry(diskPath string) (*rigMappingRegistry, error) {
	r := &rigMappingRegistry{
		byKey:     make(map[string]rigMappingDiskRecord),
		byChannel: make(map[string]string),
		byPattern: make(map[string][]string),
		diskPath:  diskPath,
	}
	if err := r.load(); err != nil {
		return nil, fmt.Errorf("load rig mapping registry from %s: %w", diskPath, err)
	}
	return r, nil
}

// ResolveSlingTarget returns the dispatch-routing fields for the
// (workspaceID, rigName) record, or an actionable error. Three failure
// modes:
//
//   - record missing → "no rig mapping for workspace=... rig=..."
//   - record present but SlingTarget empty (legacy or partially
//     configured) → fix-it message instructing the operator to re-run
//     `gc slack map-rig --sling-target ...`. The message is verbatim
//     so callers can surface it to operators (Slack DM, log line) and
//     the operator knows the exact verb to run.
//
// FixFormula is returned as-is (may be empty); the dispatch handler
// (cby.18.3) decides whether to fall back to a config-driven default.
func (r *rigMappingRegistry) ResolveSlingTarget(workspaceID, rigName string) (target, fixFormula string, err error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	rec, ok := r.byKey[rigMappingKey(workspaceID, rigName)]
	if !ok {
		return "", "", fmt.Errorf("no rig mapping for workspace=%q rig=%q; run `gc slack map-rig %s --workspace-id %s --channel <c> --sling-target <rig>/<role>` to create one",
			workspaceID, rigName, rigName, workspaceID)
	}
	if rec.SlingTarget == "" {
		return "", "", fmt.Errorf("rig %q in workspace %q has no sling target; re-run `gc slack map-rig %s --workspace-id %s --sling-target <rig>/<role>` to set one",
			rigName, workspaceID, rigName, workspaceID)
	}
	return rec.SlingTarget, rec.FixFormula, nil
}

// LookupRigForChannel returns the record covering (workspaceID,
// channelID), the source discriminator "rig", and ok=true on hit.
// Per-channel `map-channel` bindings (cby.3) take precedence — call
// the channel registry first.
func (r *rigMappingRegistry) LookupRigForChannel(workspaceID, channelID string) (rigMappingDiskRecord, string, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	rigName, ok := r.byChannel[rigChannelKey(workspaceID, channelID)]
	if !ok {
		return rigMappingDiskRecord{}, "", false
	}
	rec, ok := r.byKey[rigMappingKey(workspaceID, rigName)]
	if !ok {
		return rigMappingDiskRecord{}, "", false
	}
	return rec, "rig", true
}

// LookupRigForChannelName extends LookupRigForChannel with channel-
// name-aware pattern matching (gc-px8.9, the resolver tier deferred
// from cby.22).
//
// Resolution order:
//
//  1. Literal channel-ID hit via LookupRigForChannel (existing
//     behaviour wins; source="rig"). The literal lock is released
//     before the pattern scan begins, so this method is not a
//     nested-RLock hazard.
//  2. If no literal hit AND channelName is non-empty, scan the
//     workspace's pattern index. source="rig-pattern" on hit.
//
// Conflict policy when 2+ patterns match:
//
//   - Longest pattern wins (more specific patterns beat coarser ones,
//     so an operator can carve a sub-namespace out of a coarser
//     claim).
//   - Equal-length matches break by lexical pattern order ascending
//     (stable, deterministic across map iteration order).
//   - Equal-length, equal-pattern collisions across rigs break by
//     lexical rig key — the only way to reach this branch is for two
//     rigs in the same workspace to register the exact same pattern,
//     which is itself a misconfiguration.
//   - Multi-match cases emit a WARN log line naming every match plus
//     the resolved winner so operators see the contradictory binding
//     in adapter logs.
//
// channelName="" disables the pattern path entirely. Callers that
// don't have a channel-name in hand (block_actions, view_submission)
// should use LookupRigForChannel directly.
func (r *rigMappingRegistry) LookupRigForChannelName(workspaceID, channelID, channelName string) (rigMappingDiskRecord, string, bool) {
	if rec, src, ok := r.LookupRigForChannel(workspaceID, channelID); ok {
		return rec, src, true
	}
	if channelName == "" {
		return rigMappingDiskRecord{}, "", false
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	type match struct {
		rigKey  string
		pattern string
	}
	prefix := workspaceID + ":"
	var matches []match
	for rigKey, patterns := range r.byPattern {
		if !strings.HasPrefix(rigKey, prefix) {
			continue
		}
		for _, p := range patterns {
			ok, err := path.Match(p, channelName)
			if err != nil {
				// Patterns are validated at write/load — reaching this
				// branch means the registry was corrupted out-of-band.
				// Skip the pattern rather than fail the lookup.
				continue
			}
			if ok {
				matches = append(matches, match{rigKey: rigKey, pattern: p})
			}
		}
	}
	if len(matches) == 0 {
		return rigMappingDiskRecord{}, "", false
	}
	sort.Slice(matches, func(i, j int) bool {
		if len(matches[i].pattern) != len(matches[j].pattern) {
			return len(matches[i].pattern) > len(matches[j].pattern)
		}
		if matches[i].pattern != matches[j].pattern {
			return matches[i].pattern < matches[j].pattern
		}
		return matches[i].rigKey < matches[j].rigKey
	})
	if len(matches) > 1 {
		summary := make([]string, 0, len(matches))
		for _, m := range matches {
			summary = append(summary, fmt.Sprintf("%s=>%s", m.pattern, m.rigKey))
		}
		log.Printf("WARN: %d channel_patterns match channel %q in workspace %q: %s; resolved to pattern=%q rig=%q (longest-match wins, lexical tiebreak)",
			len(matches), channelName, workspaceID, strings.Join(summary, ", "),
			matches[0].pattern, matches[0].rigKey)
	}
	rec, ok := r.byKey[matches[0].rigKey]
	if !ok {
		return rigMappingDiskRecord{}, "", false
	}
	return rec, "rig-pattern", true
}

// Len returns the number of records currently loaded. Read-locked so
// callers (e.g. startup logs) don't race with concurrent Set in tests.
func (r *rigMappingRegistry) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.byKey)
}

// All returns every loaded rig mapping, sorted by composite key for
// diff-stable ordering.
func (r *rigMappingRegistry) All() []rigMappingDiskRecord {
	r.mu.RLock()
	defer r.mu.RUnlock()
	keys := make([]string, 0, len(r.byKey))
	for k := range r.byKey {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out := make([]rigMappingDiskRecord, 0, len(keys))
	for _, k := range keys {
		out = append(out, r.byKey[k])
	}
	return out
}

// Set is provided for tests only. Production reads only — operator
// writes go through `gc slack map-rig`.
func (r *rigMappingRegistry) Set(rec rigMappingDiskRecord) error {
	if rec.WorkspaceID == "" || rec.RigName == "" {
		return fmt.Errorf("rig mapping: workspace_id and rig_name required")
	}
	if len(rec.ChannelIDs) == 0 && len(rec.ChannelPatterns) == 0 {
		return fmt.Errorf("rig mapping: at least one channel_id or channel_pattern required")
	}
	// Normalise patterns once so byKey[k].ChannelPatterns and byPattern[k]
	// stay in lockstep — callers reading the record via LookupRigForChannel
	// must see the same ordering PatternsForRig returns.
	patterns := dedupSortedAdapterPatterns(rec.ChannelPatterns)
	for _, p := range patterns {
		if err := validateAdapterChannelPattern(p); err != nil {
			return fmt.Errorf("rig mapping: %w", err)
		}
	}
	rec.ChannelPatterns = patterns
	r.mu.Lock()
	defer r.mu.Unlock()
	key := rigMappingKey(rec.WorkspaceID, rec.RigName)
	if existing, ok := r.byKey[key]; ok {
		for _, ch := range existing.ChannelIDs {
			delete(r.byChannel, rigChannelKey(rec.WorkspaceID, ch))
		}
		delete(r.byPattern, key)
	}
	r.byKey[key] = rec
	for _, ch := range rec.ChannelIDs {
		r.byChannel[rigChannelKey(rec.WorkspaceID, ch)] = rec.RigName
	}
	if len(patterns) > 0 {
		stored := make([]string, len(patterns))
		copy(stored, patterns)
		r.byPattern[key] = stored
	}
	return r.saveLocked()
}

// PatternsForRig returns the sorted glob patterns associated with
// (workspaceID, rigName), or nil if the rig has none. Read-locked so
// the caller never observes a snapshot mid-swap.
func (r *rigMappingRegistry) PatternsForRig(workspaceID, rigName string) []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	got := r.byPattern[rigMappingKey(workspaceID, rigName)]
	if len(got) == 0 {
		return nil
	}
	out := make([]string, len(got))
	copy(out, got)
	return out
}

// dedupSortedAdapterPatterns drops empties, dedupes, and sorts the
// input. Mirrors cmd/gc.dedupSortedValidPatterns minus the validation
// step (callers run validateAdapterChannelPattern after).
func dedupSortedAdapterPatterns(in []string) []string {
	if len(in) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(in))
	out := make([]string, 0, len(in))
	for _, s := range in {
		if s == "" {
			continue
		}
		if _, dup := seen[s]; dup {
			continue
		}
		seen[s] = struct{}{}
		out = append(out, s)
	}
	if len(out) == 0 {
		return nil
	}
	sort.Strings(out)
	return out
}

// validateAdapterChannelPattern mirrors cmd/gc.validateChannelPattern.
// Charset (lowercase a-z, 0-9, '-', '_', glob metas * ? [ ] ^ !) plus
// a path.Match probe to flush ErrBadPattern early. Duplicated here
// rather than imported because the adapter is a separate Go module.
// maxAdapterChannelPatternLen mirrors cmd/gc.maxChannelPatternLen.
// Duplicated here because the adapter is a separate Go module.
const maxAdapterChannelPatternLen = 128

func validateAdapterChannelPattern(pattern string) error {
	if pattern == "" {
		return fmt.Errorf("channel_pattern is required")
	}
	if len(pattern) > maxAdapterChannelPatternLen {
		return fmt.Errorf("channel_pattern exceeds maximum length %d (got %d)", maxAdapterChannelPatternLen, len(pattern))
	}
	for _, r := range pattern {
		switch {
		case r >= 'a' && r <= 'z':
		case r >= '0' && r <= '9':
		case r == '-' || r == '_':
		case r == '*' || r == '?' || r == '[' || r == ']' || r == '^':
		default:
			return fmt.Errorf("channel_pattern %q contains illegal character %q (allowed: a-z, 0-9, -, _, glob metas * ? [ ] ^)", pattern, r)
		}
	}
	if _, err := path.Match(pattern, "x"); err != nil {
		return fmt.Errorf("channel_pattern %q is malformed: %w", pattern, err)
	}
	return nil
}

// maxRigRegistryBytes caps the size of the JSON rig-mapping file
// we'll read off disk. Rig mappings are a few hundred records of a
// fixed shape; 10 MiB is several orders of magnitude over a healthy
// install. A file beyond that is either corrupt or hostile and must
// not be loaded. A separate constant from maxRegistryBytes in
// interactions.go keeps each file's size policy explicit.
const maxRigRegistryBytes = 10 << 20 // 10 MiB

// parseRigMappingRegistry reads diskPath into a ready-to-commit snapshot
// with byKey and byChannel both pre-built. nil + nil = "file absent"
// sentinel. Validation errors return (nil, err); on overlap (only
// possible via a hand-edited file) the first-by-sorted-key rig wins and
// a WARN is logged. Logging on each parse means a SIGHUP reload of a
// chronically-overlapping file re-emits the WARN — operators see drift
// they introduced; deduping is tracked separately.
func parseRigMappingRegistry(diskPath string) (*rigMappingSnapshot, error) {
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
	data, err := io.ReadAll(io.LimitReader(f, maxRigRegistryBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", diskPath, err)
	}
	if int64(len(data)) > maxRigRegistryBytes {
		return nil, fmt.Errorf("registry file %s exceeds %d bytes", diskPath, maxRigRegistryBytes)
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	var stored map[string]rigMappingDiskRecord
	if err := dec.Decode(&stored); err != nil {
		return nil, fmt.Errorf("decode rig mapping store: %w", err)
	}
	for key, rec := range stored {
		if rec.WorkspaceID == "" || rec.RigName == "" {
			return nil, fmt.Errorf("rig mapping store: record %q missing workspace_id or rig_name", key)
		}
		if len(rec.ChannelIDs) == 0 && len(rec.ChannelPatterns) == 0 {
			return nil, fmt.Errorf("rig mapping store: record %q has neither channel_ids nor channel_patterns", key)
		}
		for _, p := range rec.ChannelPatterns {
			if err := validateAdapterChannelPattern(p); err != nil {
				return nil, fmt.Errorf("rig mapping store: record %q: %w", key, err)
			}
		}
	}
	if stored == nil {
		stored = make(map[string]rigMappingDiskRecord)
	}

	byChannel := make(map[string]string)
	byPattern := make(map[string][]string)
	keys := make([]string, 0, len(stored))
	for k := range stored {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		rec := stored[k]
		for _, ch := range rec.ChannelIDs {
			ck := rigChannelKey(rec.WorkspaceID, ch)
			if existing, ok := byChannel[ck]; ok && existing != rec.RigName {
				log.Printf("WARN: rig mapping store: channel %q in workspace %q claimed by rig %q and rig %q (hand-edited?); rig %q wins for resolver",
					ch, rec.WorkspaceID, existing, rec.RigName, existing)
				continue
			}
			byChannel[ck] = rec.RigName
		}
		if len(rec.ChannelPatterns) > 0 {
			patterns := append([]string(nil), rec.ChannelPatterns...)
			sort.Strings(patterns)
			byPattern[k] = patterns
		}
	}

	return &rigMappingSnapshot{byKey: stored, byChannel: byChannel, byPattern: byPattern}, nil
}

// load is the constructor-time helper — called pre-publish, no lock needed.
func (r *rigMappingRegistry) load() error {
	snap, err := parseRigMappingRegistry(r.diskPath)
	if err != nil {
		return err
	}
	if snap != nil {
		r.byKey = snap.byKey
		r.byChannel = snap.byChannel
		r.byPattern = snap.byPattern
	}
	return nil
}

// Stage parses the on-disk file into a snapshot ready for atomic Commit.
// nil snapshot + nil error = file absent, preserve live state.
func (r *rigMappingRegistry) Stage() (*rigMappingSnapshot, error) {
	return parseRigMappingRegistry(r.diskPath)
}

// Commit atomically swaps byKey, byChannel, AND byPattern under the
// write lock so resolver readers never observe a desync between the
// three indexes — for example, a state where new patterns are live
// but the inverted byChannel index is still stale (or vice versa).
func (r *rigMappingRegistry) Commit(snap *rigMappingSnapshot) {
	if snap == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.byKey = snap.byKey
	r.byChannel = snap.byChannel
	r.byPattern = snap.byPattern
}

// Reload combines Stage and Commit; per-registry test convenience.
func (r *rigMappingRegistry) Reload() error {
	snap, err := r.Stage()
	if err != nil {
		return err
	}
	r.Commit(snap)
	return nil
}

func (r *rigMappingRegistry) saveLocked() error {
	if r.diskPath == "" {
		return nil
	}
	dir := filepath.Dir(r.diskPath)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("mkdir rig mapping store dir %q: %w", dir, err)
	}
	data, err := json.MarshalIndent(r.byKey, "", "  ")
	if err != nil {
		return fmt.Errorf("encode rig mapping store: %w", err)
	}
	return writeFile0600(r.diskPath, data)
}

// resolveChannelTarget returns the binding that should handle the
// slash command, along with a source discriminator. Per-channel
// map-channel bindings are overrides on top of the rig→channel-set
// default; channel mapping wins. The returned source is "channel"
// when cby.3 hits, "rig" when cby.4 hits, "" when neither.
//
// The returned record carries either a real channelMappingDiskRecord
// from cby.3 OR a synthetic channelMappingDiskRecord built from the
// rig record (TargetKind="rig", TargetID=<rigName>) so callers can
// route through a single switch statement. The synthetic record's
// CreatedAt/UpdatedAt mirror the rig record's so observability
// downstream stays accurate.
func resolveChannelTarget(chanReg *channelMappingRegistry, rigReg *rigMappingRegistry, workspaceID, channelID string) (channelMappingDiskRecord, string, bool) {
	return resolveChannelTargetWithName(chanReg, rigReg, workspaceID, channelID, "")
}

// resolveChannelTargetWithName is the channel-name-aware resolver
// (gc-px8.9). The signature mirrors resolveChannelTarget plus a
// channelName argument; channelName="" reduces the function to the
// legacy literal-only behaviour.
//
// Tier order:
//
//  1. channel-mapping registry exact (cby.3). This includes both
//     session and rig targets, so an operator's `gc slack map-channel`
//     override always beats whatever the rig store would have chosen.
//  2. rig-mapping registry exact channel-ID (cby.4).
//  3. rig-mapping registry channel-name pattern (cby.22 storage,
//     gc-px8.9 resolver). Conflict policy lives in
//     LookupRigForChannelName.
//  4. Unbound — the caller writes the help message.
//
// Source discriminators returned: "channel", "rig", "rig-pattern", or
// "" on miss.
func resolveChannelTargetWithName(chanReg *channelMappingRegistry, rigReg *rigMappingRegistry, workspaceID, channelID, channelName string) (channelMappingDiskRecord, string, bool) {
	if chanReg != nil {
		if rec, ok := chanReg.Get(workspaceID, channelID); ok {
			return rec, "channel", true
		}
	}
	if rigReg != nil {
		if rec, src, ok := rigReg.LookupRigForChannelName(workspaceID, channelID, channelName); ok {
			return channelMappingDiskRecord{
				WorkspaceID: rec.WorkspaceID,
				ChannelID:   channelID,
				TargetKind:  channelMappingTargetKindRig,
				TargetID:    rec.RigName,
				CreatedAt:   rec.CreatedAt,
				UpdatedAt:   rec.UpdatedAt,
			}, src, true
		}
	}
	return channelMappingDiskRecord{}, "", false
}

// logCrossStoreOverlapWarnings inspects both registries and emits a
// WARN line for every (workspace, channel) where the cby.3 channel
// store binds the channel to a `rig` target AND the cby.4 rig store
// claims the same channel for a DIFFERENT rig. Channel mapping wins
// at resolution time; the WARN is purely observability so operators
// see the contradictory binding in adapter logs at startup.
//
// Lock order: chanReg then rigReg. Must be consistent across all
// callers that hold both locks.
func logCrossStoreOverlapWarnings(chanReg *channelMappingRegistry, rigReg *rigMappingRegistry) {
	if chanReg == nil || rigReg == nil {
		return
	}
	chanReg.mu.RLock()
	defer chanReg.mu.RUnlock()
	rigReg.mu.RLock()
	defer rigReg.mu.RUnlock()
	for _, m := range chanReg.byKey {
		if m.TargetKind != channelMappingTargetKindRig {
			continue
		}
		ck := rigChannelKey(m.WorkspaceID, m.ChannelID)
		if rigName, ok := rigReg.byChannel[ck]; ok && rigName != m.TargetID {
			log.Printf("WARN: channel %q in workspace %q is bound by both map-channel (rig=%q) and map-rig (rig=%q); map-channel wins",
				m.ChannelID, m.WorkspaceID, m.TargetID, rigName)
		}
	}
}

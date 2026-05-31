// Package apps persists per-workspace Slack app records (manifest +
// signing secret + post-OAuth fields) to <city>/.gc/slack/apps.json.
// The same on-disk schema is read by the slack-pack adapter at
// startup and on SIGHUP.
//
// Ported from cmd/gc/slack_app_registry.go (gc-nqy49) as part of the
// slack-cli relocation epic gc-coe10. Behavior identical to the
// cmd/gc original — Phase 2 deletes the original after consumers cut
// over.
package apps

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

// MaxBytes caps the size of the JSON registry file the loader will
// read off disk. Matches channels.MaxBytes / rooms.MaxBytes — bumped
// here as part of gc-cby.32 to bring this loader in line with the
// LimitReader + size-cap pattern used by the other registry loaders
// (was os.ReadFile with no cap).
const MaxBytes = 10 << 20 // 10 MiB

// Record is the persisted representation of a Slack app imported
// into a gc city. The schema is the only contract between the CLI
// (writer) and the adapter (reader, at adapter/, pack-relative);
// both sides MUST match it byte-for-byte. The authoritative
// description lives at schema/apps.schema.json (pack-relative).
//
// BotUserID and SigningSecret are populated post-OAuth (gc-cby.9), not
// at import time; both are optional. ManifestRaw preserves the raw
// manifest bytes verbatim so future readers can re-parse fields the
// current struct ignores (forward-compat).
//
// Log/CLI policy (gc-cby.13): SigningSecret, ManifestRaw, ManifestPath,
// and BotUserID MUST NOT be passed through fmt.Fprintf, log.*, or any
// human-facing output sink. DisplayName is operator-supplied via the
// uploaded manifest and MUST be passed through SanitizeForLog before
// printing. Use SafeLogFields() to obtain a struct that exposes only
// the allowlisted fields with DisplayName already sanitized.
type Record struct {
	WorkspaceID   string          `json:"workspace_id"`
	AppID         string          `json:"app_id"`
	BotUserID     string          `json:"bot_user_id,omitempty"`
	DisplayName   string          `json:"display_name,omitempty"`
	Scopes        []string        `json:"scopes,omitempty"`
	SlashCommands []string        `json:"slash_commands,omitempty"`
	SigningSecret string          `json:"signing_secret,omitempty"`
	ManifestPath  string          `json:"manifest_path,omitempty"`
	ManifestRaw   json.RawMessage `json:"manifest_raw,omitempty"`
	ImportedAt    time.Time       `json:"imported_at"`
}

// LogView is the safe-for-print projection of Record.
// It intentionally omits SigningSecret, ManifestRaw, ManifestPath, and
// BotUserID (gc-cby.13 deny-list); DisplayName is pre-sanitized.
// Adding a new sensitive field to Record must NOT add a field
// here without explicit policy review.
type LogView struct {
	WorkspaceID       string
	AppID             string
	DisplayName       string
	ScopeCount        int
	SlashCommandCount int
	ImportedAt        time.Time
}

// SafeLogFields returns the allowlisted, sanitized projection of r for
// human-facing output. See Record's "Log/CLI policy" comment
// for the deny-list rationale.
func (r Record) SafeLogFields() LogView {
	return LogView{
		WorkspaceID:       r.WorkspaceID,
		AppID:             r.AppID,
		DisplayName:       SanitizeForLog(r.DisplayName),
		ScopeCount:        len(r.Scopes),
		SlashCommandCount: len(r.SlashCommands),
		ImportedAt:        r.ImportedAt,
	}
}

// JSONView is the safe-for-emission projection of Record
// used by `gc slack status --json` (gc-cby.13). It excludes
// SigningSecret (HMAC verification credential, populated post-OAuth in
// gc-cby.9), ManifestRaw (large, redundant with the on-disk file), and
// ManifestPath/BotUserID (operator-internal). The on-disk apps.json
// continues to serialize the full Record through json.Marshal
// — that path is the persistence contract and intentionally retains
// every field. This view is for the operator-facing `--json` CLI
// projection only.
type JSONView struct {
	WorkspaceID   string    `json:"workspace_id"`
	AppID         string    `json:"app_id"`
	DisplayName   string    `json:"display_name,omitempty"`
	Scopes        []string  `json:"scopes,omitempty"`
	SlashCommands []string  `json:"slash_commands,omitempty"`
	ImportedAt    time.Time `json:"imported_at"`
}

// SafeJSONFields returns the allowlisted projection of r for the
// `--json` CLI emission. DisplayName is NOT sanitized here — JSON
// encoding escapes control bytes (, \n, etc.) so the wire form
// is safe regardless of payload, and downstream consumers may want
// the original Unicode for non-CLI rendering.
func (r Record) SafeJSONFields() JSONView {
	return JSONView{
		WorkspaceID:   r.WorkspaceID,
		AppID:         r.AppID,
		DisplayName:   r.DisplayName,
		Scopes:        r.Scopes,
		SlashCommands: r.SlashCommands,
		ImportedAt:    r.ImportedAt,
	}
}

// ansiCSIPattern matches complete ANSI CSI sequences per ECMA-48:
// ESC [ , optional parameter bytes 0x30-0x3f, optional intermediate
// bytes 0x20-0x2f, terminator byte 0x40-0x7e. CSI is the dominant
// terminal-corrupting escape family.
//
// Non-CSI escape forms (OSC `\x1b]...\x07`, DCS `\x1bP...\x1b\`,
// SS2/SS3, single-char escapes) are NOT matched by this regex —
// the bare ESC at the head of those sequences is instead stripped
// by the control-byte loop in SanitizeForLog. That defangs the
// terminal-control effect (no ESC means the kernel of the sequence
// never executes) but leaves the inert payload bytes (e.g. the
// "0;title" of an OSC) as plain text in the output. Acceptable for
// the gc-cby.13 threat model (terminal corruption + log-aggregator
// tripping); a tighter "strip every escape family entirely" pass
// would need additional patterns and is not required for any known
// attack class against display_name.
var ansiCSIPattern = regexp.MustCompile(`\x1b\[[0-?]*[ -/]*[\x40-\x7e]`)

// SanitizeForLog returns s with bytes that corrupt terminals or log
// aggregators removed: ANSI CSI sequences, control bytes below 0x20
// (except horizontal tab), DEL (0x7f), and any invalid UTF-8 byte.
// Newline (0x0a) and carriage return (0x0d) are STRIPPED — log
// aggregators and `%s`-format printers split on those bytes, so
// preserving them in operator-supplied strings would let an attacker
// forge log lines or overwrite the line in a TTY.
//
// Legitimate Unicode (CJK, emoji, accented Latin) passes through
// unchanged. Used at every CLI/log boundary that prints
// operator-supplied strings such as Record.DisplayName
// (gc-cby.13).
func SanitizeForLog(s string) string {
	if s == "" {
		return s
	}
	withoutCSI := ansiCSIPattern.ReplaceAllString(s, "")
	// Builder size: upper bound — the loop only removes bytes.
	var b strings.Builder
	b.Grow(len(withoutCSI))
	for i := 0; i < len(withoutCSI); {
		r, size := utf8.DecodeRuneInString(withoutCSI[i:])
		if r == utf8.RuneError && size == 1 {
			i++
			continue
		}
		i += size
		if r < 0x20 && r != '\t' {
			continue
		}
		if r == 0x7f {
			continue
		}
		b.WriteRune(r)
	}
	return b.String()
}

// Path returns the on-disk path of the apps registry under
// <cityPath>/.gc/slack/apps.json. Replaces the cmd/gc helper that
// went through internal/citylayout.RuntimePath.
func Path(cityPath string) string {
	return filepath.Join(cityPath, ".gc", "slack", "apps.json")
}

// Registry mirrors the adapter's identityRegistry in
// adapter/main.go (pack-relative; sync.RWMutex + atomic temp+rename
// writes, 0o700/0o600 perms, tolerant load on missing file). The
// duplication is intentional: the writer side and the reader side
// cannot share a package without coupling the two binaries' Go
// modules.
type Registry struct {
	mu       sync.RWMutex
	byKey    map[string]Record
	diskPath string
}

// Key composes the registry key used to look up a Record. Workspaces
// may host multiple gc-imported apps, each keyed by (workspace_id,
// app_id) so the lookup is unambiguous.
func Key(workspaceID, appID string) string {
	return workspaceID + ":" + appID
}

// NewRegistry opens the registry at diskPath. A missing file yields
// an empty registry (tolerant load).
func NewRegistry(diskPath string) (*Registry, error) {
	r := &Registry{
		byKey:    make(map[string]Record),
		diskPath: diskPath,
	}
	if err := r.load(); err != nil {
		return nil, fmt.Errorf("load slack app registry from %s: %w", diskPath, err)
	}
	return r, nil
}

// Get returns the Record for (workspaceID, appID) and a boolean
// indicating whether one is registered.
func (r *Registry) Get(workspaceID, appID string) (Record, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	rec, ok := r.byKey[Key(workspaceID, appID)]
	return rec, ok
}

// Set is idempotent: re-setting an existing (workspace_id, app_id)
// overwrites the record in place; the registry size does not grow.
func (r *Registry) Set(rec Record) error {
	if rec.WorkspaceID == "" || rec.AppID == "" {
		return fmt.Errorf("slack app registry: workspace_id and app_id are both required (got workspace_id=%q app_id=%q)", rec.WorkspaceID, rec.AppID)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.byKey[Key(rec.WorkspaceID, rec.AppID)] = rec
	return r.saveLocked()
}

// All returns every Record currently held by the registry. The slice
// is freshly allocated; callers may mutate or reorder it freely.
func (r *Registry) All() []Record {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]Record, 0, len(r.byKey))
	for _, rec := range r.byKey {
		out = append(out, rec)
	}
	return out
}

func (r *Registry) load() error {
	if r.diskPath == "" {
		return nil
	}
	f, err := os.Open(r.diskPath)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("open slack app store %s: %w", r.diskPath, err)
	}
	defer func() { _ = f.Close() }()
	// LimitReader caps the read at MaxBytes+1 so a hostile or corrupt
	// file can't force a multi-gigabyte allocation before the size
	// check fires. The +1 lets us detect overflow precisely:
	// reading exactly MaxBytes+1 means the underlying file is at
	// least MaxBytes+1 bytes (gc-cby.32).
	data, err := io.ReadAll(io.LimitReader(f, MaxBytes+1))
	if err != nil {
		return fmt.Errorf("read slack app store %s: %w", r.diskPath, err)
	}
	if int64(len(data)) > MaxBytes {
		return fmt.Errorf("slack app store %s exceeds %d bytes", r.diskPath, MaxBytes)
	}
	var stored map[string]Record
	if err := json.Unmarshal(data, &stored); err != nil {
		return fmt.Errorf("decode slack app store: %w", err)
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
	// 0o700/0o600: records carry workspace ids and (post-OAuth)
	// signing secrets — not world-readable. Chmod after MkdirAll so
	// the contract holds even when the directory already exists with
	// looser permissions (MkdirAll is a no-op on existing dirs).
	dir := filepath.Dir(r.diskPath)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("mkdir slack app store dir: %w", err)
	}
	if err := os.Chmod(dir, 0o700); err != nil {
		return fmt.Errorf("chmod slack app store dir: %w", err)
	}
	data, err := json.MarshalIndent(r.byKey, "", "  ")
	if err != nil {
		return fmt.Errorf("encode slack app store: %w", err)
	}
	// os.CreateTemp picks a unique name in dir, so two concurrent CLI
	// invocations writing the same registry don't clobber each other's
	// temp file before the rename.
	f, err := os.CreateTemp(dir, "apps-*.json.tmp")
	if err != nil {
		return fmt.Errorf("create slack app store tmp: %w", err)
	}
	tmpName := f.Name()
	cleanup := func() { _ = os.Remove(tmpName) }
	if err := f.Chmod(0o600); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("chmod slack app store tmp: %w", err)
	}
	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("write slack app store tmp: %w", err)
	}
	if err := f.Close(); err != nil {
		cleanup()
		return fmt.Errorf("close slack app store tmp: %w", err)
	}
	if err := os.Rename(tmpName, r.diskPath); err != nil {
		cleanup()
		return fmt.Errorf("rename slack app store: %w", err)
	}
	return nil
}

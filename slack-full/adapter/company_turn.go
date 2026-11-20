package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// company_turn.go — the per-session current-turn pointer the Go delivery
// worker writes before every company wake (Phase 2c). It is the deterministic
// context source the Python verbs read (no receipt scanning). Field order
// matches company-current-turn/<session>.json in the golden fixtures.

const companyCurrentTurnSchemaV = 1

// companyCurrentTurn mirrors company-current-turn/<session>.json.
type companyCurrentTurn struct {
	SchemaVersion int `json:"schema_version"`
	// TurnRef selects the immutable per-delivery record under by-ref/. It is
	// omitted only for pre-rollout fixtures and compatibility pointers.
	TurnRef       string `json:"turn_ref,omitempty"`
	Session       string `json:"session"`
	ReceiptID     string `json:"receipt_id"`
	TeamID        string `json:"team_id"`
	ChannelID     string `json:"channel_id"`
	TS            string `json:"ts"`
	Room          string `json:"room"`
	Kind          string `json:"kind"`
	ThreadRootTS  string `json:"thread_root_ts"`
	Agent         string `json:"agent"`
	DelegationKey string `json:"delegation_key,omitempty"`
	// OwnerAppID is the DM owner app's api_app_id, carried on kind "dm"
	// pointers so the Python reply-current verb can validate the reply's
	// session against the owner agent's dm binding. Empty (omitted) on room
	// pointers, keeping their bytes unchanged.
	OwnerAppID string `json:"owner_app_id,omitempty"`
	// City is the target session's gc city when a city-qualified binding
	// delivered this turn cross-city; empty = the adapter's own city.
	City string `json:"city,omitempty"`
	// RosterDriftOverlay marks a targeted turn delivered to the agent's
	// dm_bindings session because the live-membership overlay admitted it
	// without a room binding. reply-current accepts that session for this turn
	// only; omitted on every other pointer, keeping their bytes unchanged.
	RosterDriftOverlay bool   `json:"roster_drift_overlay,omitempty"`
	DeliveredAt        string `json:"delivered_at"`
}

// companyTurnReference derives one stable opaque reference for a frozen
// receipt target. Redrives of the same target reuse it; different agents,
// sessions, cities, or wake kinds under one receipt cannot collide.
func companyTurnReference(receiptID string, td TargetDelivery) string {
	sum := sha256.Sum256([]byte(strings.Join([]string{
		receiptID, td.City, td.Session, td.Agent, td.Kind,
	}, "\x00")))
	return fmt.Sprintf("gct-%x", sum[:10])
}

func validCompanyTurnReference(ref string) bool {
	if len(ref) != len("gct-")+20 || !strings.HasPrefix(ref, "gct-") {
		return false
	}
	for _, ch := range ref[len("gct-"):] {
		if (ch < '0' || ch > '9') && (ch < 'a' || ch > 'f') {
			return false
		}
	}
	return true
}

// persistCurrentTurn creates the immutable by-ref record first, then advances
// the legacy per-session pointer to the exact bytes that won the create-once
// claim. The returned value is that durable record and must be used to render
// the wake, so a retry after a partial write cannot advertise divergent
// routing metadata.
func persistCurrentTurn(turnsDir string, p companyCurrentTurn) (companyCurrentTurn, error) {
	if strings.TrimSpace(turnsDir) == "" {
		return companyCurrentTurn{}, errors.New("company: current-turn dir unset")
	}
	if !validCompanyTurnReference(p.TurnRef) {
		return companyCurrentTurn{}, fmt.Errorf(
			"company: invalid immutable turn_ref %q", p.TurnRef)
	}
	persisted, err := writeCurrentTurnRecordOnce(turnsDir, p)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	if err := writeCurrentTurnPointer(turnsDir, persisted); err != nil {
		return companyCurrentTurn{}, err
	}
	return persisted, nil
}

// writeCurrentTurnRecordOnce installs by-ref/<turn_ref>.json without ever
// replacing an existing path. A redrive adopts an existing record only when
// every immutable identity/routing field matches; delivered_at remains the
// timestamp of the first successful record creation.
func writeCurrentTurnRecordOnce(turnsDir string, p companyCurrentTurn) (companyCurrentTurn, error) {
	data, err := marshalCurrentTurn(p)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	dir := filepath.Join(turnsDir, "by-ref")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return companyCurrentTurn{}, err
	}
	path := filepath.Join(dir, p.TurnRef+".json")
	created, err := companyCreateFileOnce(path, data)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	if created {
		return p, nil
	}
	info, err := os.Lstat(path)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	if !info.Mode().IsRegular() {
		return companyCurrentTurn{}, fmt.Errorf(
			"company: immutable turn record %q is not a regular file", path)
	}
	existingData, err := os.ReadFile(path)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	var existing companyCurrentTurn
	if err := json.Unmarshal(existingData, &existing); err != nil {
		return companyCurrentTurn{}, fmt.Errorf(
			"company: decode immutable turn record %q: %w", path, err)
	}
	candidate := p
	candidate.DeliveredAt = existing.DeliveredAt
	candidateData, err := marshalCurrentTurn(candidate)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	existingCanonical, err := marshalCurrentTurn(existing)
	if err != nil {
		return companyCurrentTurn{}, err
	}
	if !bytes.Equal(candidateData, existingCanonical) {
		return companyCurrentTurn{}, fmt.Errorf(
			"company: immutable turn_ref collision for %q", p.TurnRef)
	}
	return existing, nil
}

// companyCreateFileOnce writes a fully-fsynced temp file and claims the final
// path with a hard link. The final name therefore exposes either no file or
// complete bytes, and EEXIST never overwrites the first writer.
func companyCreateFileOnce(path string, data []byte) (bool, error) {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return false, err
	}
	f, err := os.CreateTemp(dir, ".turn-*.tmp")
	if err != nil {
		return false, err
	}
	tmp := f.Name()
	cleanup := func() { _ = os.Remove(tmp) }
	if err := f.Chmod(0o600); err != nil {
		_ = f.Close()
		cleanup()
		return false, err
	}
	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		cleanup()
		return false, err
	}
	if err := f.Sync(); err != nil {
		_ = f.Close()
		cleanup()
		return false, err
	}
	if err := f.Close(); err != nil {
		cleanup()
		return false, err
	}
	if err := os.Link(tmp, path); err != nil {
		cleanup()
		if errors.Is(err, os.ErrExist) {
			return false, nil
		}
		return false, err
	}
	if err := fsyncDir(dir); err != nil {
		cleanup()
		return false, err
	}
	cleanup()
	return true, nil
}

// sweepCurrentTurnRecords removes immutable records (and abandoned writer
// temps) older than cutoff. The by-ref directory is dedicated to these files;
// symlinks and unexpected names/types are never followed or removed.
func sweepCurrentTurnRecords(turnsDir string, cutoff time.Time) (int, error) {
	dir := filepath.Join(turnsDir, "by-ref")
	entries, err := os.ReadDir(dir)
	if errors.Is(err, os.ErrNotExist) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	removed := 0
	var errs []error
	for _, entry := range entries {
		name := entry.Name()
		isRecord := strings.HasSuffix(name, ".json") &&
			validCompanyTurnReference(strings.TrimSuffix(name, ".json"))
		isTemp := strings.HasPrefix(name, ".turn-") && strings.HasSuffix(name, ".tmp")
		if (!isRecord && !isTemp) || entry.Type()&os.ModeSymlink != 0 {
			continue
		}
		info, ierr := entry.Info()
		if ierr != nil {
			errs = append(errs, ierr)
			continue
		}
		if !info.Mode().IsRegular() || !info.ModTime().Before(cutoff) {
			continue
		}
		if rerr := os.Remove(filepath.Join(dir, name)); rerr != nil {
			if !errors.Is(rerr, os.ErrNotExist) {
				errs = append(errs, rerr)
			}
			continue
		}
		removed++
	}
	if removed > 0 {
		if serr := fsyncDir(dir); serr != nil {
			errs = append(errs, serr)
		}
	}
	return removed, errors.Join(errs...)
}

// writeCurrentTurnPointer atomically writes the pointer for one wake into
// turnsDir/<session>.json. Called before the gc session POST so the pointer
// is durable before the turn can act on it. An unset turnsDir is a
// misconfiguration (never true in production, where main resolves a default):
// it is rejected rather than silently writing to the process CWD.
//
// The session name is passed through the shared filename-component sanitizer
// before it becomes a filename: an operator-supplied name containing '/', a
// leading '.', ".." or any byte outside [A-Za-z0-9._-] is hashed to a safe
// component so a hostile bind can never escape turnsDir. A well-formed session
// name is filename-safe and passes through unchanged (byte-parity with the
// Python reader for the common case). The pointer's `session` JSON field keeps
// the raw name.
//
// A DM turn is written to a dedicated subdirectory `turnsDir/dm/<session>.json`
// and an mpim turn to `turnsDir/mpim/<session>.json` (each created 0700 on
// demand) rather than `turnsDir/<session>.dm.json`: the shared sanitizer passes
// interior dots through, so a room turn of a session literally named "<x>.dm"
// and the DM turn of session "<x>" would otherwise resolve to the SAME file and
// clobber each other, misdirecting a private reply into a room (review C6 / m2 /
// m13). Giving each dm-family kind its own subdirectory keeps the room, dm, and
// mpim namespaces disjoint regardless of session name — an mpim wake can never
// clobber an unanswered 1:1 DM turn (spec §Pointer).
func writeCurrentTurnPointer(turnsDir string, p companyCurrentTurn) error {
	if strings.TrimSpace(turnsDir) == "" {
		return errors.New("company: current-turn dir unset")
	}
	data, err := marshalCurrentTurn(p)
	if err != nil {
		return err
	}
	dir := turnsDir
	switch p.Kind {
	case receiptKindDM:
		dir = filepath.Join(turnsDir, "dm")
	case receiptKindMpim:
		dir = filepath.Join(turnsDir, "mpim")
	}
	if dir != turnsDir {
		if err := os.MkdirAll(dir, 0o700); err != nil {
			return err
		}
	}
	filename := companySanitizeComponent(p.Session) + ".json"
	return companyWriteFileAtomic(filepath.Join(dir, filename), data)
}

// marshalCurrentTurn encodes the pointer with the byte-for-byte fixture shape
// (2-space indent, fixture field order).
func marshalCurrentTurn(p companyCurrentTurn) ([]byte, error) {
	return json.MarshalIndent(p, "", "  ")
}

// companyPointerFromTarget builds a current-turn pointer from a receipt and one
// frozen target.
func companyPointerFromTarget(r *IngressReceipt, room *CompanyRoom, td TargetDelivery, threadRootTS string, now time.Time) companyCurrentTurn {
	roomName := ""
	if room != nil {
		roomName = room.Name
	}
	return companyCurrentTurn{
		SchemaVersion:      companyCurrentTurnSchemaV,
		TurnRef:            companyTurnReference(r.ID, td),
		Session:            td.Session,
		City:               td.City,
		ReceiptID:          r.ID,
		TeamID:             r.Origin.TeamID,
		ChannelID:          r.Origin.ChannelID,
		TS:                 r.Origin.TS,
		Room:               roomName,
		Kind:               td.Kind,
		ThreadRootTS:       threadRootTS,
		Agent:              td.Agent,
		DelegationKey:      td.DelegationKey,
		OwnerAppID:         r.OwnerAppID,
		RosterDriftOverlay: td.RosterDriftOverlay,
		DeliveredAt:        now.UTC().Format(time.RFC3339),
	}
}

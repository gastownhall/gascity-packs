package main

import (
	"errors"
	"fmt"
	"log"
	"os"
	"strings"
)

// appsRegistryStageLabel is the name passed to stage() for the apps
// registry. stage() wraps each registry's error as "<label>: <inner>",
// so the resulting message starts with appsRegistryErrorPrefix —
// scrubAppsRegistryError matches on the prefix to find the apps
// component. Keep label and prefix in sync via the constant binding.
const appsRegistryStageLabel = "apps registry"
const appsRegistryErrorPrefix = appsRegistryStageLabel + ":"

// appsRegistryScrubSentinel replaces the apps-registry component of a
// reload error chain before it is logged. apps_registry.go parse errors
// today carry only structural detail (file path, byte offset, JSON
// decode position), but the encoding/json contract does not document
// that payload values are absent from type-mismatch messages — a future
// stdlib version or a json-decoder swap could change that. Defensive
// scrub keeps signing-secret material out of journald regardless.
const appsRegistryScrubSentinel = "apps registry: reload failed (see structured debug log)"

// scrubAppsRegistryError formats err for operator-facing logging while
// replacing any apps-registry-prefixed component with a fixed sentinel.
//
// errors.Join (the only producer of multi-error chains in
// reloadAllRegistries) returns a value that implements
// `Unwrap() []error`. We use that structural API to identify each
// component error individually rather than splitting err.Error() on
// newlines — splitting is brittle if a future apps-registry error
// contains an embedded newline (the second line wouldn't carry the
// "apps registry:" prefix and would slip through unscrubbed).
//
// Errors not produced by errors.Join (e.g. a single-source failure) are
// inspected by their Error() string prefix as a fallback.
//
// Returns empty string for nil so call sites can use it unconditionally.
func scrubAppsRegistryError(err error) string {
	if err == nil {
		return ""
	}
	type multi interface{ Unwrap() []error }
	if m, ok := err.(multi); ok {
		parts := m.Unwrap()
		scrubbed := make([]string, len(parts))
		for i, p := range parts {
			scrubbed[i] = scrubAppsRegistryError(p)
		}
		return strings.Join(scrubbed, "\n")
	}
	msg := err.Error()
	if strings.HasPrefix(msg, appsRegistryErrorPrefix) {
		return appsRegistryScrubSentinel
	}
	return msg
}

// reloadAllRegistries re-reads the four CLI-written registry files and
// atomically swaps the in-memory snapshots — SIGHUP entry point for
// gc-cby.23.
//
// All-or-nothing: every registry is Stage'd first; only if every Stage
// succeeds are the snapshots Commit'd. A single parse failure aborts
// the entire reload with the live state untouched. Without this the
// adapter would briefly serve mixed-policy requests (e.g. new app
// secrets routed through stale channel mappings).
//
// nil snapshot from Stage means the file is absent — operators clear a
// registry by writing `{}`, NOT by `rm` (a stray `rm` would otherwise
// wipe live state on the next SIGHUP).
//
// NOT reloaded here (intentional gc-cby.23 boundary): identityRegistry
// and handleAliasRegistry (written in-process via HTTP endpoints) and
// threadSessionRegistry (written in-process by launcher / teardown).
// If a future CLI command writes to any of those, extend this
// orchestrator.
//
// gc-cby.9 follow-up: an in-process Set on appsRegistry (planned for the
// OAuth callback path) racing a SIGHUP-driven Stage→Commit can briefly
// roll the in-memory snapshot back to the pre-Set version (Set holds the
// write lock, then Commit installs a snapshot taken before Set ran).
// Stage's snapshot is whole-file, so the next reload converges. Document
// the constraint where Set callers live, or sequence Set→file-write→
// Set-mutex-hold-through-Commit if that's not acceptable.
func reloadAllRegistries(
	apps *appsRegistry,
	chans *channelMappingRegistry,
	rigs *rigMappingRegistry,
	rooms *roomLaunchMappingRegistry,
	subteams *subteamAliasMap,
) error {
	var (
		commits []func()
		errs    []error
	)
	stage := func(name string, err error, commit func()) {
		if err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", name, err))
			return
		}
		commits = append(commits, commit)
	}

	if apps != nil {
		snap, err := apps.Stage()
		stage(appsRegistryStageLabel, err, func() { apps.Commit(snap) })
	}
	if chans != nil {
		snap, err := chans.Stage()
		stage("channel mapping", err, func() { chans.Commit(snap) })
	}
	if rigs != nil {
		snap, err := rigs.Stage()
		stage("rig mapping", err, func() { rigs.Commit(snap) })
	}
	if rooms != nil {
		snap, err := rooms.Stage()
		stage("room launch mapping", err, func() { rooms.Commit(snap) })
	}
	if subteams != nil {
		snap, err := subteams.Stage()
		stage("subteam alias", err, func() { subteams.Commit(snap) })
	}

	if len(errs) > 0 {
		return errors.Join(errs...)
	}
	for _, c := range commits {
		c()
	}
	return nil
}

// runReloadLoop drains sigCh and invokes reload for each signal until
// stop is closed. Buffer-size-1 on sigCh at the call site means
// repeated SIGHUPs during a slow reload coalesce — that's correct.
// stop is `<-chan struct{}` so any cancellation source (test fixture,
// janitor context) can drive shutdown without importing context here.
func runReloadLoop(stop <-chan struct{}, sigCh <-chan os.Signal, reload func()) {
	for {
		select {
		case <-stop:
			return
		case _, ok := <-sigCh:
			if !ok {
				return
			}
			reload()
		}
	}
}

// logReloadOutcome wraps reloadAllRegistries with a one-line log entry
// per SIGHUP cycle so operators can correlate slack-CLI writes with
// adapter reloads in journalctl. A failed reload preserves live state
// and is logged at WARN — corrupt input must not crash the binary.
func logReloadOutcome(
	apps *appsRegistry,
	chans *channelMappingRegistry,
	rigs *rigMappingRegistry,
	rooms *roomLaunchMappingRegistry,
	subteams *subteamAliasMap,
) {
	log.Printf("SIGHUP received: reloading slack-pack registries")
	if err := reloadAllRegistries(apps, chans, rigs, rooms, subteams); err != nil {
		log.Printf("WARN: registry reload failed (live state preserved): %s", scrubAppsRegistryError(err))
		return
	}
	log.Printf("registry reload OK: apps=%d channels=%d rigs=%d rooms=%d subteams=%d",
		apps.Len(), chans.Len(), rigs.Len(), rooms.Len(), subteams.Len())
}

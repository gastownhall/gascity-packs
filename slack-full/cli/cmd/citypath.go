// Package cmd holds the gc-slack-cli verb implementations registered on
// the cobra root in main.go. Each verb is a thin port of the
// corresponding cmd/gc/cmd_slack_<verb>.go original — same flags, same
// outputs, same error paths — re-pointed at the slack-cli module's
// internal/state/* helpers.
package cmd

import (
	"fmt"
	"os"
	"path/filepath"
)

// cityPathEnv lets operators override the city resolution by setting
// the absolute path explicitly. Useful when the cwd-walk would resolve
// to the wrong city (e.g. when the gc-slack-cli is invoked from a
// rig directory whose enclosing city differs from the one the
// operator wants to write to).
const cityPathEnv = "GC_CITY_PATH"

// ResolveCityPath finds the city root by, in order:
//
//  1. Honoring the GC_CITY_PATH env var when it points at a city
//     directory (validated via cityHasMarker).
//  2. Walking up from the current working directory looking for the
//     first ancestor that contains either city.toml (declared city)
//     or .gc/ (runtime-only city).
//
// Returns an error mentioning the cwd when neither path resolves —
// the cmd/gc original surfaces a similar message via citylayout, so
// operator muscle memory carries over.
//
// This helper is the slack-cli analog of the cmd/gc resolveCity()
// function, with the gc-internal city registry walks stripped.
// Phase 1 leaves call this once per invocation at the top of their
// runX function, before any registry IO.
func ResolveCityPath() (string, error) {
	if v := os.Getenv(cityPathEnv); v != "" {
		abs, err := filepath.Abs(v)
		if err != nil {
			return "", fmt.Errorf("resolve %s=%q: %w", cityPathEnv, v, err)
		}
		if !cityHasMarker(abs) {
			return "", fmt.Errorf("%s=%q does not point at a city directory (no city.toml or .gc/)", cityPathEnv, v)
		}
		return abs, nil
	}
	cwd, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("resolve cwd: %w", err)
	}
	return findCityFromDir(cwd)
}

// findCityFromDir walks up from dir looking for the nearest ancestor
// containing a city marker. Returns an error when no marker is found
// up to the filesystem root.
func findCityFromDir(dir string) (string, error) {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return "", fmt.Errorf("resolve %q: %w", dir, err)
	}
	cur := abs
	for {
		if cityHasMarker(cur) {
			return cur, nil
		}
		parent := filepath.Dir(cur)
		if parent == cur {
			return "", fmt.Errorf("no city directory found at or above %q (looked for city.toml or .gc/)", abs)
		}
		cur = parent
	}
}

// cityHasMarker reports whether dir contains either a city.toml file
// (declared city) or a .gc/ directory (runtime root). Mirrors the
// cmd/gc citylayout.HasCityConfig || HasRuntimeRoot check.
func cityHasMarker(dir string) bool {
	if fi, err := os.Stat(filepath.Join(dir, "city.toml")); err == nil && !fi.IsDir() {
		return true
	}
	if fi, err := os.Stat(filepath.Join(dir, ".gc")); err == nil && fi.IsDir() {
		return true
	}
	return false
}

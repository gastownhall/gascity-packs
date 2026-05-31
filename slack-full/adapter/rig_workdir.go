package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// rigWorkdir resolves a rig name (the bead-prefix used in routes.jsonl)
// to an absolute filesystem path. It mirrors the reader in
// internal/api/handler_beads.go:resolveRoutePrefix and the writer in
// cmd/gc/rig_beads.go:writeRoutesFile so the slack-pack adapter — which
// lives in a separate Go module and cannot import internal/config —
// can map an inbound dispatch's rig to the workdir its bd commands
// should run in (gc-cby.18.2).
//
// The schema is one JSON object per line: {"prefix":"<rig>","path":"<rel-or-abs>"}
// with paths interpreted relative to cityPath when not already absolute.
// Malformed and blank lines are skipped; a missing routes file or an
// unknown rig returns an error with cityPath/rigName context.
func rigWorkdir(cityPath, rigName string) (string, error) {
	if strings.TrimSpace(cityPath) == "" {
		return "", fmt.Errorf("rigWorkdir: cityPath must not be empty")
	}
	if strings.TrimSpace(rigName) == "" {
		return "", fmt.Errorf("rigWorkdir: rigName must not be empty")
	}

	routesPath := filepath.Join(cityPath, ".beads", "routes.jsonl")
	data, err := os.ReadFile(routesPath)
	if err != nil {
		return "", fmt.Errorf("reading routes.jsonl at %q: %w", routesPath, err)
	}

	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var entry struct {
			Prefix string `json:"prefix"`
			Path   string `json:"path"`
		}
		if err := json.Unmarshal([]byte(line), &entry); err != nil {
			// Skip malformed lines — matches the tolerance in
			// resolveRoutePrefix so a single bad line in routes.jsonl
			// can't take the whole adapter down.
			continue
		}
		if entry.Prefix != rigName {
			continue
		}
		resolved := entry.Path
		if !filepath.IsAbs(resolved) {
			resolved = filepath.Join(cityPath, resolved)
		}
		abs, err := filepath.Abs(resolved)
		if err != nil {
			return "", fmt.Errorf("resolving absolute path for rig %q: %w", rigName, err)
		}
		return abs, nil
	}
	return "", fmt.Errorf("rig %q not found in %s", rigName, routesPath)
}

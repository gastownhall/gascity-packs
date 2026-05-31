package main

import "path/filepath"

// RuntimePath joins parts under the city's slack-pack runtime root
// (<cityPath>/.gc/slack/...). Mirrors the gc-internal helper at
// internal/citylayout.RuntimePath but bakes in the "slack" subdir so
// this module can stay free of internal-package imports — the
// slack-pack ships as an independent example and must not couple to
// gc internals.
func RuntimePath(cityPath string, parts ...string) string {
	return filepath.Join(append([]string{cityPath, ".gc", "slack"}, parts...)...)
}

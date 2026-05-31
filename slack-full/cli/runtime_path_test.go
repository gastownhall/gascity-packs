package main

import (
	"path/filepath"
	"testing"
)

// TestRuntimePath pins the slack-pack-CLI helper that replaces
// internal/citylayout.RuntimePath. The CLI module deliberately does
// NOT import the gc internal package — the helper is short enough
// (one filepath.Join) that duplicating it costs less than coupling
// the slack-pack to gc internals (gc-coe10 / gc-wj70y).
//
// Contract: parts are joined under "<cityPath>/.gc/slack". With no
// parts the result is the slack runtime root itself.
func TestRuntimePath(t *testing.T) {
	cases := []struct {
		name     string
		cityPath string
		parts    []string
		want     string
	}{
		{
			name:     "no parts returns slack runtime root",
			cityPath: "/cities/alpha",
			parts:    nil,
			want:     filepath.Join("/cities/alpha", ".gc", "slack"),
		},
		{
			name:     "single part appended",
			cityPath: "/cities/alpha",
			parts:    []string{"apps.json"},
			want:     filepath.Join("/cities/alpha", ".gc", "slack", "apps.json"),
		},
		{
			name:     "multiple parts joined in order",
			cityPath: "/cities/alpha",
			parts:    []string{"channel-mappings", "T123.json"},
			want:     filepath.Join("/cities/alpha", ".gc", "slack", "channel-mappings", "T123.json"),
		},
		{
			name:     "relative city path preserved",
			cityPath: "alpha",
			parts:    []string{"apps.json"},
			want:     filepath.Join("alpha", ".gc", "slack", "apps.json"),
		},
		{
			name:     "empty city path still produces slack-rooted layout",
			cityPath: "",
			parts:    []string{"apps.json"},
			want:     filepath.Join(".gc", "slack", "apps.json"),
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := RuntimePath(tc.cityPath, tc.parts...)
			if got != tc.want {
				t.Errorf("RuntimePath(%q, %v) = %q, want %q", tc.cityPath, tc.parts, got, tc.want)
			}
		})
	}
}

// TestRuntimePathDoesNotMutateCallerSlice guards against the variadic
// slice append corrupting a caller-owned slice. Append on a slice with
// spare capacity will write through the caller's backing array and
// surface as a confusing distant-action bug. The defensive prefix
// allocation in RuntimePath prevents that.
func TestRuntimePathDoesNotMutateCallerSlice(t *testing.T) {
	parts := make([]string, 1, 8) // capacity > length: append would reuse backing array
	parts[0] = "apps.json"
	_ = RuntimePath("/cities/alpha", parts...)
	if parts[0] != "apps.json" {
		t.Errorf("caller slice mutated: parts[0] = %q, want %q", parts[0], "apps.json")
	}
}

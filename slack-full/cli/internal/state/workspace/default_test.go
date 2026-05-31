package workspace

import "testing"

// TestIDDefaultFromEnv covers the env-var read for the shared
// SLACK_WORKSPACE_ID default applied to every `gc slack` verb's
// --workspace-id flag (gc-cby.24).
func TestIDDefaultFromEnv(t *testing.T) {
	cases := []struct {
		name string
		env  string
		want string
	}{
		{"unset", "", ""},
		{"plain", "T0123456", "T0123456"},
		{"trim_leading_trailing", "  T0123456  ", "T0123456"},
		{"whitespace_only_treated_as_empty", "   ", ""},
		{"tab_and_newline_only", "\t\n", ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Setenv(IDEnv, tc.env)
			got := IDDefault()
			if got != tc.want {
				t.Errorf("IDDefault() = %q, want %q", got, tc.want)
			}
		})
	}
}

package main

import (
	"bytes"
	"strings"
	"testing"
)

// TestRootHelpOnNoArgs pins the gc-slack-cli convention that bare
// invocation prints usage rather than running silently. Cobra
// auto-promotes help when no Run is defined on the root, but a
// future contributor adding a default Run could regress it; this
// test guards the contract from gc-wj70y.
func TestRootHelpOnNoArgs(t *testing.T) {
	cmd := newRootCmd()
	var out bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetErr(&out)
	cmd.SetArgs(nil)
	if err := cmd.Execute(); err != nil {
		t.Fatalf("Execute() with no args: unexpected error: %v", err)
	}
	got := out.String()
	if !strings.Contains(got, "gc-slack-cli") {
		t.Errorf("usage output missing binary name: %q", got)
	}
	if !strings.Contains(got, "Usage:") {
		t.Errorf("usage output missing 'Usage:' header: %q", got)
	}
}

// TestRootRejectsUnknownSubcommand pins the contract that an unknown
// subcommand exits non-zero. Cobra's default behavior surfaces this
// as a non-nil Execute error; main() translates that into os.Exit(1).
func TestRootRejectsUnknownSubcommand(t *testing.T) {
	cmd := newRootCmd()
	var out bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetErr(&out)
	cmd.SetArgs([]string{"definitely-not-a-real-subcommand"})
	err := cmd.Execute()
	if err == nil {
		t.Fatal("Execute() with unknown subcommand: want error, got nil")
	}
	if !strings.Contains(err.Error(), "definitely-not-a-real-subcommand") {
		t.Errorf("error %q does not mention the unknown subcommand", err)
	}
}

// TestRunSuccessExitCode covers the run() wrapper's success path —
// no-args invocation prints help and returns 0.
func TestRunSuccessExitCode(t *testing.T) {
	var stderr bytes.Buffer
	got := run(nil, &stderr)
	if got != 0 {
		t.Errorf("run(nil) = %d, want 0", got)
	}
	if stderr.Len() != 0 {
		t.Errorf("run(nil) stderr = %q, want empty", stderr.String())
	}
}

// TestRunErrorExitCode covers the run() wrapper's failure path:
// non-zero exit code and a "gc-slack-cli:"-prefixed stderr line so
// downstream operator tooling can grep on it consistently.
func TestRunErrorExitCode(t *testing.T) {
	var stderr bytes.Buffer
	got := run([]string{"definitely-not-a-real-subcommand"}, &stderr)
	if got != 1 {
		t.Errorf("run(unknown) = %d, want 1", got)
	}
	if !strings.HasPrefix(stderr.String(), "gc-slack-cli:") {
		t.Errorf("stderr %q missing 'gc-slack-cli:' prefix", stderr.String())
	}
	if !strings.Contains(stderr.String(), "definitely-not-a-real-subcommand") {
		t.Errorf("stderr %q does not mention the unknown subcommand", stderr.String())
	}
}
